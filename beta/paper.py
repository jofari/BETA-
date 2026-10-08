"""Paper trading — execution SIMULEE des consignes des suivis, contre le vrai carnet Binance.

Demande de Jonas (2026-10-08) : « deployer les 3 voies C en paper pour voir les resultats sur
du long terme » — la voie C figee du 03/10, VC2 (infirmee, suivie pour information) et VC3
(en dry-run). Il a choisi l'execution simulee plutot que le testnet ou le seul suivi au cours
de cloture.

Ce que le paper ajoute aux suivis (SUIVI_*.jsonl) : l'EXECUTION. Les suivis traitent au cours
de cloture de 00:00 UTC et modelisent le slippage (0 pour la voie C, 5/10 pb par cote pour
VC2 et VC3). Ici, chaque consigne est executee au marche quand le timer passe (~01:00 UTC),
en parcourant le vrai carnet Binance de ce moment-la — perpetuels USDT-M pour C et VC2, spot
pour VC3 —, avec un capital fictif, les pas de lot et minimums de l'exchange, les frais du
bareme et le funding reellement regle. Deux ecarts sont journalises par ordre :
    cout_carnet_pb       prix moyen obtenu contre le milieu du carnet : le prix de la liquidite
    ecart_ouverture_pb   prix moyen obtenu contre l'ouverture de 00:00 UTC, le prix que suppose
                         le modele : liquidite + delai d'execution
C'est de quoi juger le critere « slippage reel <= 2x le modele » du dry-run (registre).

Rien ne sort : aucune cle, aucun ordre ; seules les routes PUBLIQUES de Binance sont lues.

Comptabilite, la meme pour le spot et les perpetuels lineaires USDT-M : un compte = du cash
en USDT et une quantite par paire. Acheter q au prix f : cash -= q*f + frais ; vendre :
cash += q*f - frais ; equite = cash + somme(q * milieu). En perpetuels, q < 0 est un short, et
chaque echeance de funding retire q * prix de marque * taux du cash (le long paie quand le
taux est positif). Le spot interdit q < 0 et le cash negatif. Marge et liquidation ne sont
pas simulees : le brut reste <= 2 (voie C, VC2) et <= 1 (VC3), loin de toute liquidation.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from beta import config
from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c_voltarget as vc

log = logging.getLogger("beta.paper")

SPOT, PERPETUEL = "spot", "perpetuel"
PAIRES = vc.PAIRES

# La taille du canari d'ARIT (etapes de validation : dry-run 6 mois, canari 10 k, paliers x2).
# Le paper doit buter sur les memes pas de lot et minimums que le canari : a 10 k, un pas de
# 0,001 BTC en perpetuels pese deja ~0,8 % de l'equite.
CAPITAL_USDT = 10_000.0

PROFONDEUR = 100                    # niveaux lus par cote : ~100x la taille d'un ordre a 10 k
TIMEOUT_HTTP_S = 10.0
ESSAIS_HTTP = 3


class PaperError(RuntimeError):
    """Marche illisible, ou consigne inexploitable : la voie ne s'execute pas ce jour-la."""


# =========================================================================================
# Les voies : ou lire la consigne, sur quel instrument, a quels frais
# =========================================================================================

@dataclass(frozen=True)
class Voie:
    nom: str
    suivi: str                          # journal de consignes, a la racine du depot
    instrument: str
    taker_pb: float                     # frais par cote, ceux du modele
    slippage_modele_pb: dict            # ce que le modele suppose, par paire (comparaison)


def voies() -> dict[str, Voie]:
    """Les trois voies. Frais et slippage RELUS dans leurs configs : rien n'est recopie ici."""
    vc2, vc3 = c2.config("VC2"), c2.config("VC3")
    return {
        # Voie C figee : perpetuels, taker 5 pb, aucun slippage dans son journal.
        "VOIE_C": Voie("VOIE_C", "SUIVI_VOIE_C.jsonl", PERPETUEL, vc.BPS_TAKER,
                       {p: 0.0 for p in PAIRES}),
        "VC2": Voie("VC2", "SUIVI_VC2.jsonl", vc2.get("instrument", PERPETUEL),
                    vc2["frais"]["taker_pb"], dict(vc2["frais"]["slippage_pb"])),
        "VC3": Voie("VC3", "SUIVI_VC3.jsonl", vc3.get("instrument", PERPETUEL),
                    vc3["frais"]["taker_pb"], dict(vc3["frais"]["slippage_pb"])),
    }


@dataclass(frozen=True)
class Consigne:
    jour: dt.date                       # le jour ou elle s'execute
    poids: dict[str, float]             # position voulue, en fraction de l'equite
    a_traiter: frozenset[str]           # paires dont le modele change la position ce jour-la
    source: str


def lire_journal(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def lire_consigne(chemin: Path) -> Consigne | None:
    """La consigne portee par la derniere ligne d'un suivi, pour le lendemain de cette ligne.

    Deux formats : les suivis de la voie C2 donnent la `position` tenue demain (egale a la
    derive quand rien ne bouge) ; celui de la voie C donne la `cible` du moteur, que le modele
    n'atteint que s'il franchit la bande. Dans les deux, `ordres` liste ce qui change, et il
    est vide quand le modele ne traite pas.
    """
    lignes = lire_journal(chemin)
    if not lignes or "consigne_lendemain" not in lignes[-1]:
        return None
    derniere = lignes[-1]
    c = derniere["consigne_lendemain"]
    jour = dt.date.fromisoformat(derniere["date"]) + dt.timedelta(days=1)
    poids = c["position"] if "position" in c else c["cible"]
    a_traiter = frozenset(p for p, o in c.get("ordres", {}).items() if o != 0.0)
    return Consigne(jour, {p: float(poids[p]) for p in PAIRES}, a_traiter,
                    f"{chemin.name}, ligne du {derniere['date']}")


# =========================================================================================
# Le marche : carnet, regles de l'exchange, ouverture du jour, funding
# =========================================================================================

@dataclass(frozen=True)
class Carnet:
    bids: list[tuple[float, float]]     # (prix, quantite), du meilleur au pire
    asks: list[tuple[float, float]]
    horodatage: str

    @property
    def milieu(self) -> float:
        return (self.bids[0][0] + self.asks[0][0]) / 2.0


@dataclass(frozen=True)
class Regles:
    pas: str                            # pas de quantite d'un ordre au marche, en texte exact
    qte_min: float
    notional_min: float

    @property
    def decimales(self) -> int:
        return max(0, -Decimal(self.pas).normalize().as_tuple().exponent)


def au_pas(qte: float, regles: Regles, vers_zero: bool = False) -> float:
    """La quantite ramenee a un multiple du pas : au plus proche, ou vers zero."""
    pas = float(regles.pas)
    n = qte / pas
    n = math.floor(abs(n) + 1e-9) * (1 if n >= 0 else -1) if vers_zero else round(n)
    return round(n * pas, regles.decimales)


class MarcheBinance:
    """Les routes PUBLIQUES de Binance. Aucune cle, aucun ordre."""

    BASES = {SPOT: "https://api.binance.com/api/v3", PERPETUEL: "https://fapi.binance.com/fapi/v1"}

    def __init__(self) -> None:
        self._regles: dict[str, dict[str, Regles]] = {}

    def _get(self, instrument: str, route: str, **params) -> object:
        url = f"{self.BASES[instrument]}/{route}?{urllib.parse.urlencode(params)}"
        for essai in range(1, ESSAIS_HTTP + 1):
            try:
                with urllib.request.urlopen(url, timeout=TIMEOUT_HTTP_S) as reponse:  # noqa: S310
                    return json.loads(reponse.read())
            except (OSError, ValueError) as exc:
                if essai == ESSAIS_HTTP:
                    raise PaperError(f"{url} : {exc}") from exc
                time.sleep(2 ** essai)
        raise AssertionError("inatteignable")

    def carnet(self, instrument: str, symbole: str) -> Carnet:
        brut = self._get(instrument, "depth", symbol=symbole, limit=PROFONDEUR)
        # Le spot ne date pas son carnet : l'heure de reception en tient lieu.
        horo = (dt.datetime.fromtimestamp(brut["T"] / 1000, dt.UTC) if "T" in brut
                else dt.datetime.now(dt.UTC))
        carnet = Carnet(_niveaux(brut["bids"]), _niveaux(brut["asks"]),
                        horo.isoformat(timespec="milliseconds"))
        if not carnet.bids or not carnet.asks or carnet.bids[0][0] >= carnet.asks[0][0]:
            raise PaperError(f"{instrument} {symbole} : carnet vide ou croise")
        return carnet

    def regles(self, instrument: str, symbole: str) -> Regles:
        if instrument not in self._regles:
            if instrument == SPOT:
                symboles = json.dumps([f"{p}USDT" for p in PAIRES], separators=(",", ":"))
                info = self._get(SPOT, "exchangeInfo", symbols=symboles)
            else:
                info = self._get(PERPETUEL, "exchangeInfo")
            self._regles[instrument] = {s["symbol"]: _regles(instrument, s)
                                        for s in info["symbols"]
                                        if s["symbol"] in {f"{p}USDT" for p in PAIRES}
                                        and s.get("contractType", "PERPETUAL") == "PERPETUAL"}
        return self._regles[instrument][symbole]

    def ouverture(self, instrument: str, symbole: str, jour: dt.date) -> float:
        """Le prix d'ouverture de la bougie 1d du jour : celui ou le modele traite."""
        bougie = self._get(instrument, "klines", symbol=symbole, interval="1d", limit=1)[0]
        debut = dt.datetime.fromtimestamp(bougie[0] / 1000, dt.UTC).date()
        if debut != jour:
            raise PaperError(f"{symbole} : bougie 1d du {debut}, attendue {jour}")
        return float(bougie[1])

    def funding(self, symbole: str, depuis: dt.datetime, jusqu_a: dt.datetime) -> list[dict]:
        """Les echeances reglees dans ]depuis, jusqu_a] : instant, taux, prix de marque."""
        brut = self._get(PERPETUEL, "fundingRate", symbol=symbole, limit=1000,
                         startTime=int(depuis.timestamp() * 1000) + 1,
                         endTime=int(jusqu_a.timestamp() * 1000))
        return [{"instant": int(e["fundingTime"]), "taux": float(e["fundingRate"]),
                 "marque": float(e["markPrice"]) if e.get("markPrice") else None} for e in brut]


def _niveaux(brut: list) -> list[tuple[float, float]]:
    return [(float(prix), float(qte)) for prix, qte in brut]


def _pas(texte: str) -> str:
    """« 0.00100000 » -> « 0.001 », « 10.00000000 » -> « 10 » : le pas exact, en texte."""
    return format(Decimal(texte).normalize(), "f")


def _regles(instrument: str, symbole: dict) -> Regles:
    f = {x["filterType"]: x for x in symbole["filters"]}
    if instrument == SPOT:
        # Le MARKET_LOT_SIZE du spot vaut 0 : c'est le LOT_SIZE qui s'applique.
        notional = f.get("NOTIONAL", {}).get("minNotional") or f["MIN_NOTIONAL"]["minNotional"]
        return Regles(_pas(f["LOT_SIZE"]["stepSize"]), float(f["LOT_SIZE"]["minQty"]),
                      float(notional))
    return Regles(_pas(f["MARKET_LOT_SIZE"]["stepSize"]), float(f["MARKET_LOT_SIZE"]["minQty"]),
                  float(f["MIN_NOTIONAL"]["notional"]))


# =========================================================================================
# L'execution d'une journee (pure : le marche est passe en argument)
# =========================================================================================

def executer(qte: float, carnet: Carnet) -> tuple[float, int, bool]:
    """Prix moyen d'un ordre au marche de `qte` (> 0 achat, < 0 vente), qui mange le carnet.

    Au-dela des niveaux lus, le reste est compte au pire prix vu — optimiste, donc signale
    (`complet` faux) ; a 10 k, cela n'arrive pas.
    """
    niveaux = carnet.asks if qte > 0 else carnet.bids
    reste, cout, n = abs(qte), 0.0, 0
    for prix, dispo in niveaux:
        pris = min(reste, dispo)
        cout += pris * prix
        reste -= pris
        n += 1
        if reste <= 1e-12:
            break
    complet = reste <= 1e-12
    if not complet:
        cout += reste * niveaux[-1][0]
    return cout / abs(qte), n, complet


def compte_initial() -> dict:
    return {"cash": CAPITAL_USDT, "quantites": {p: 0.0 for p in PAIRES}}


def journee(voie: Voie, consigne: Consigne | None, compte: dict, depuis: dt.datetime | None,
            marche, maintenant: dt.datetime) -> dict:
    """Une journee de paper : funding regle depuis la derniere execution, puis les ordres.

    `compte` (cash, quantites) est l'etat apres la derniere execution, faite a `depuis` (None
    le premier jour). La premiere journee construit toute la position de la consigne ; les
    suivantes ne touchent que les paires que le modele change (`a_traiter`).
    """
    jour = maintenant.date()
    symboles = {p: f"{p}USDT" for p in PAIRES}
    cash = float(compte["cash"])
    q = {p: float(compte["quantites"].get(p, 0.0)) for p in PAIRES}
    premiere = depuis is None

    carnets = {p: marche.carnet(voie.instrument, symboles[p]) for p in PAIRES}
    regles = {p: marche.regles(voie.instrument, symboles[p]) for p in PAIRES}
    milieu = {p: carnets[p].milieu for p in PAIRES}

    # 1. Le funding regle pendant la detention : la position n'a pas bouge depuis `depuis`.
    funding = {}
    if voie.instrument == PERPETUEL and not premiere:
        for p in PAIRES:
            if q[p] == 0.0:
                continue
            montant = sum(q[p] * (e["marque"] or milieu[p]) * e["taux"]
                          for e in marche.funding(symboles[p], depuis, maintenant))
            funding[p] = round(montant, 8)
            cash -= montant
    equite_avant = cash + sum(q[p] * milieu[p] for p in PAIRES)

    # 2. Les quantites visees, au pas de l'exchange, et ce qui ne passe pas les minimums.
    if consigne is None:
        a_traiter: set[str] = set()
    elif premiere:
        a_traiter = {p for p in PAIRES if consigne.poids[p] != 0.0}
    else:
        a_traiter = set(consigne.a_traiter)
    voulus, ignores = {}, []
    for p in sorted(a_traiter):
        cible = au_pas(consigne.poids[p] * equite_avant / milieu[p], regles[p])
        if voie.instrument == SPOT:
            cible = max(cible, 0.0)
        ordre = round(cible - q[p], regles[p].decimales)
        if ordre == 0.0:
            continue
        reduit = q[p] != 0.0 and cible * q[p] >= 0.0 and abs(cible) < abs(q[p])
        notional = abs(ordre) * milieu[p]
        # Binance exempte du minimum un ordre qui ne fait que reduire une position en
        # perpetuels (reduceOnly) ; en spot, un reliquat sous le minimum ne se vend pas.
        exempte = voie.instrument == PERPETUEL and reduit
        if (notional < regles[p].notional_min and not exempte) or abs(ordre) < regles[p].qte_min:
            ignores.append({"paire": p, "qte": ordre, "notional": round(notional, 2),
                            "raison": f"sous le minimum ({regles[p].notional_min:g} USDT, "
                                      f"{regles[p].qte_min:g})"})
            continue
        voulus[p] = ordre

    # 3. Spot : pas d'emprunt. Les ventes passent d'abord ; si les achats coutent plus que le
    #    cash disponible, ils sont reduits ensemble, au prorata, vers le pas inferieur.
    if voie.instrument == SPOT:
        achats = {p: o for p, o in voulus.items() if o > 0}
        dispo = cash + sum(-o * executer(o, carnets[p])[0] * (1 - voie.taker_pb / 1e4)
                           for p, o in voulus.items() if o < 0)
        cout = sum(o * executer(o, carnets[p])[0] * (1 + voie.taker_pb / 1e4)
                   for p, o in achats.items())
        if cout > dispo:
            echelle = max(dispo, 0.0) / cout
            for p, o in achats.items():
                voulus[p] = au_pas(o * echelle, regles[p], vers_zero=True)
                if voulus[p] * milieu[p] < regles[p].notional_min:
                    ignores.append({"paire": p, "qte": o, "raison": "cash insuffisant"})
                    del voulus[p]

    # 4. Les ordres, ventes d'abord.
    ordres, frais = [], 0.0
    ouvertures = {p: marche.ouverture(voie.instrument, symboles[p], jour) for p in voulus}
    for p, ordre in sorted(voulus.items(), key=lambda po: po[1]):
        prix, niveaux, complet = executer(ordre, carnets[p])
        f = abs(ordre) * prix * voie.taker_pb / 1e4
        cash -= ordre * prix + f
        q[p] = round(q[p] + ordre, regles[p].decimales)
        frais += f
        sens = 1.0 if ordre > 0 else -1.0
        ordres.append({
            "paire": p, "sens": "achat" if ordre > 0 else "vente", "qte": ordre,
            "notional": round(abs(ordre) * prix, 4), "prix": prix, "milieu": milieu[p],
            "bid": carnets[p].bids[0][0], "ask": carnets[p].asks[0][0],
            "ouverture": ouvertures[p], "frais": round(f, 6),
            "cout_carnet_pb": round(sens * (prix / milieu[p] - 1.0) * 1e4, 3),
            "ecart_ouverture_pb": round(sens * (prix / ouvertures[p] - 1.0) * 1e4, 3),
            "slippage_modele_pb": float(voie.slippage_modele_pb[p]),
            "niveaux": niveaux, "complet": complet, "carnet_lu_a": carnets[p].horodatage,
        })
    if voie.instrument == SPOT and (cash < -1e-6 or any(v < 0 for v in q.values())):
        raise PaperError(f"{voie.nom} : spot a decouvert apres execution ({cash:.2f} USDT)")

    equite_apres = cash + sum(q[p] * milieu[p] for p in PAIRES)
    return {
        "date": jour.isoformat(), "voie": voie.nom, "instrument": voie.instrument,
        "execute_le": maintenant.isoformat(timespec="seconds"),
        "capital_initial": CAPITAL_USDT, "premiere": premiere,
        "consigne": None if consigne is None else {
            "source": consigne.source, "a_traiter": sorted(a_traiter),
            "poids": {p: consigne.poids[p] for p in PAIRES}},
        "milieux": milieu, "funding": funding, "equite_avant": equite_avant,
        "ordres": ordres, "ignores": ignores, "frais": round(frais, 6),
        "cash": cash, "quantites": q, "equite": equite_apres,
        "poids": {p: q[p] * milieu[p] / equite_apres for p in PAIRES},
    }


# =========================================================================================
# Une voie, un jour : le journal PAPER_<voie>.jsonl, en ajout seul
# =========================================================================================

def journal_paper(voie: Voie, repertoire: Path | None = None) -> Path:
    return (repertoire or config.RACINE) / f"PAPER_{voie.nom}.jsonl"


def executer_voie(voie: Voie, marche, maintenant: dt.datetime, repertoire: Path | None = None,
                  suivis: Path | None = None) -> dict | None:
    """Execute la consigne du jour d'une voie, une seule fois par jour UTC.

    `repertoire` : ou vit le journal paper ; `suivis` : ou lire les journaux de consignes.
    Les deux valent la racine du depot par defaut.

    Retourne la ligne ecrite, ou None si la voie a deja ete executee aujourd'hui. Une consigne
    absente ou d'un autre jour (suivi en panne) leve PaperError : rien n'est ecrit, et le
    lendemain reprend avec le funding des deux jours.
    """
    chemin = journal_paper(voie, repertoire)
    lignes = lire_journal(chemin)
    if lignes and lignes[-1]["date"] == maintenant.date().isoformat():
        return None
    consigne = lire_consigne((suivis or config.RACINE) / voie.suivi)
    if consigne is None or consigne.jour != maintenant.date():
        recue = "aucune" if consigne is None else f"celle du {consigne.jour}"
        raise PaperError(f"{voie.nom} : pas de consigne pour le {maintenant.date()} dans "
                         f"{voie.suivi} ({recue}). Voir le timer du suivi.")
    if lignes:
        compte = {"cash": lignes[-1]["cash"], "quantites": lignes[-1]["quantites"]}
        depuis = dt.datetime.fromisoformat(lignes[-1]["execute_le"])
    else:
        compte, depuis = compte_initial(), None
    ligne = journee(voie, consigne, compte, depuis, marche, maintenant)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=True) + "\n")
    return ligne
