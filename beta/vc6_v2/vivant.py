"""VC6 V2, paper de plomberie : la decision du jour, avec le code du backtest, sur le lake VIVANT.

Le backtest lit les copies figees au 31/10/2026 (`beta.vc6_v2.donnees`). Le paper lit le lake
(invariant 2 : le lake est la seule source), avec les memes fonctions de calcul : cloture de la
barre 5 min de 23:55 (`beta.vc6.donnees.clotures_perp`), RV, HAR et replis, ecart-type 30 jours
(`beta.controle_har.campagne.previsions`), funding du jour ]D 00:00 ; D+1 00:00] (application 5),
puis les entrees et le moteur de la V2 (`beta.vc6_v2.donnees.entrees_principal`,
`beta.vc6_v2.moteur.simuler`) depuis la premiere decision de la periode principale (31/05/2021).
L'etat de la rampe et de la bande est donc celui du backtest.

La decision prise a la cloture du jour D (pour D+1) est la derniere ligne de la meme chaine,
prolongee d'une journee fictive (rendement et funding nuls) : `simuler` decide avec la ligne
D_{j-1} et ne lit jamais la journee fictive pour decider. Une epreuve verifie que la prolongation
ne change aucune journee deja jouee.

Signal fantome (Jonas, 02/11/2026), SANS effet sur les ordres : sigma HAR nourri par l'estimateur
de Garman-Klass sur les bougies 1 j du lake, a la place de la RV 5 min (memes MCO, memes replis).
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.controle_har import campagne as har_campagne
from beta.controle_har import har as hr
from beta.lake import lecture
from beta.vc6 import campagne as c1
from beta.vc6 import donnees as dn1
from beta.vc6_v2 import donnees as dn
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import regles as R

UN = pd.Timedelta(days=1)
GK_K = 2.0 * math.log(2.0) - 1.0
ESSAI = "poche_baissiere_har"


class DonneeManquante(RuntimeError):
    """Une donnee de la decision manque a la cloture : aucun nouvel ordre, et une alerte."""


class CausaliteError(RuntimeError):
    """La journee fictive a change une journee deja jouee."""


def _jour(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return (t.tz_convert(None) if t.tzinfo else t).normalize()


def barres_5m(actif: str, jour) -> pd.DataFrame:
    """Barres 5 min du perpetuel ouvertes avant la fin du jour, au format des copies figees."""
    df = lecture.load(actif, "5m", colonnes=("close", "volume"))
    df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date"), utc=True))
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df = df[df.index < _jour(jour).tz_localize("UTC") + UN]
    if df.empty or not (df["close"] > 0).all():
        raise DonneeManquante(f"{actif} : bougies 5 min absentes ou cloture non positive")
    if ((df.index - df.index.floor("5min")) != pd.Timedelta(0)).any():
        raise DonneeManquante(f"{actif} : barres 5 min hors de la grille de 5 min")
    return df


def reglements(actif: str, jour) -> pd.Series:
    """Les reglements de funding du perpetuel jusqu'a la fin du jour (D+1 00:00 inclus). Le jour
    doit etre complet : un reglement a D+1 00:00 ou apres doit exister dans le lake."""
    f = lecture.funding(actif)
    s = pd.Series(f["funding_rate"].to_numpy(dtype=float),
                  index=pd.DatetimeIndex(pd.to_datetime(f["date"], utc=True)))
    s = s[~s.index.duplicated(keep="last")].sort_index()
    fin = _jour(jour).tz_localize("UTC") + UN
    if s.empty or s.index.max() < fin:
        dernier = "aucun" if s.empty else f"{s.index.max():%Y-%m-%d %H:%M}"
        raise DonneeManquante(f"{actif} : funding du {_jour(jour):%Y-%m-%d} incomplet (dernier "
                              f"reglement {dernier})")
    return s[s.index <= fin]


def funding_jour(s: pd.Series) -> pd.DataFrame:
    """Somme et nombre des reglements de ]D 00:00 ; D+1 00:00] (meme calcul que
    `beta.vc6.donnees.funding_jour`)."""
    jour = (s.index - pd.Timedelta(microseconds=1)).tz_convert(None).normalize()
    g = s.groupby(jour)
    out = pd.DataFrame({"somme": g.sum(), "nombre": g.size()})
    complet = pd.date_range(out.index.min(), out.index.max(), freq="D")
    if len(complet.difference(out.index)):
        raise DonneeManquante("jour sans reglement de funding")
    return out


def charger(jour) -> dict:
    """Tout ce que lit la decision de la cloture de `jour`. DonneeManquante si une piece manque."""
    jour = _jour(jour)
    manquants, barres, regl = [], {}, {}
    for a in R.POCHES:
        try:
            barres[a] = barres_5m(a, jour)
            derniere = (jour + pd.Timedelta(hours=23, minutes=55)).tz_localize("UTC")
            if derniere not in barres[a].index:
                manquants.append(f"{a} : barre 5 min de 23:55 du {jour:%Y-%m-%d} absente")
        except DonneeManquante as exc:
            manquants.append(str(exc))
        try:
            regl[a] = reglements(a, jour)
        except DonneeManquante as exc:
            manquants.append(str(exc))
    if manquants:
        raise DonneeManquante(" ; ".join(manquants))
    try:
        closes = dn1.clotures_perp(barres)
        funding = {a: funding_jour(regl[a]) for a in R.POCHES}
    except (dn1.DonneesError, DonneeManquante) as exc:
        raise DonneeManquante(str(exc)) from exc
    prev = {a: har_campagne.previsions(b) for a, b in barres.items()}
    return {"jour": jour, "closes": closes, "prev": prev, "reglements": regl, "funding": funding,
            "sigma": pd.DataFrame({a: np.sqrt(R.JOURS_AN * prev[a]["har"]) for a in R.POCHES}),
            "ecart_type": pd.DataFrame({a: np.sqrt(R.JOURS_AN * prev[a]["ecart_type"])
                                        for a in R.POCHES})}


def entrees(d: dict) -> mt.Entrees:
    """Les entrees du backtest, de la premiere decision (31/05/2021) a la cloture de `jour`."""
    try:
        return dn.entrees_principal(d, R.DEBUT_PRINCIPAL, f"{d['jour']:%Y-%m-%d}")
    except c1.CampagneError as exc:
        raise DonneeManquante(str(exc)) from exc


def prolonger(ent: mt.Entrees) -> mt.Entrees:
    """Une journee fictive apres la derniere cloture. Rendement et funding nuls ce jour-la ; mode,
    sigma et funding annualise recopies (le moteur ne les lit jamais pour cette journee)."""
    return mt.Entrees(
        jours=ent.jours.append(pd.DatetimeIndex([ent.jours[-1] + UN])),
        baissier=np.append(ent.baissier, ent.baissier[-1]),
        sigma={a: np.append(s, s[-1]) for a, s in ent.sigma.items()},
        funding_annuel={a: np.append(s, s[-1]) for a, s in ent.funding_annuel.items()},
        funding_jour={a: np.append(s, 0.0) for a, s in ent.funding_jour.items()},
        rendements={a: np.append(s, 0.0) for a, s in ent.rendements.items()})


def nets(y: np.ndarray, lignes: list[tuple[str, str]]) -> dict[str, float]:
    """Position nette par actif (poche BTC + poche baissiere BTC), en fraction du capital."""
    out = dict.fromkeys(R.POCHES, 0.0)
    for q, (_, a) in enumerate(lignes):
        out[a] += float(y[q])
    return out


def decider(d: dict) -> dict:
    """La decision de la cloture de `d['jour']` pour le lendemain, et ce que le journal retient."""
    ent = entrees(d)
    p = mt.parametres_essai(ESSAI)
    sim = mt.simuler(ent, p)
    ext = mt.simuler(prolonger(ent), p)
    n = ent.n
    if not (np.array_equal(ext["y"][:n], sim["y"]) and np.array_equal(ext["r"][:n], sim["r"])):
        raise CausaliteError("la journee fictive change des journees deja jouees")
    lignes = ext["lignes"]
    y, y_avant, cible = ext["y"][n], ext["y"][n - 1], ext["cible"][n]
    poids, avant = nets(y, lignes), nets(y_avant, lignes)
    k_b = lignes.index(("baissiere", "BTC"))
    sig_btc = float(ent.sigma["BTC"][n])
    poches = {}
    for i, a in enumerate(R.POCHES):
        w = R.POIDS[a]
        poches[a] = {"sigma_har": float(ent.sigma[a][n]),
                     "ecart_type_30j": float(d["ecart_type"][a].loc[d["jour"]]),
                     "funding_annualise": float(ent.funding_annuel[a][n]),
                     "e_cible": float(cible[i] / w), "e_modele": float(y[i] / w),
                     "contraint": bool(ext["contraint"][n, i])}
    return {
        "jour_decision": f"{d['jour']:%Y-%m-%d}",
        "mode_btc": "baissier" if bool(ext["baissier"][n]) else "haussier",
        "en_rampe": bool(ext["en_rampe"][n]),
        "poches": poches,
        "poche_baissiere": {"e_btc_formule": float(min(max(R.CIBLE / sig_btc, R.CLIP_BAISSIERE[0]),
                                                           R.CLIP_BAISSIERE[1])),
                            "cible": float(cible[k_b]), "modele": float(y[k_b])},
        "poids_modele": poids, "poids_modele_veille": avant,
        "a_traiter": sorted(a for a in R.POCHES if poids[a] != avant[a]),
        "levier_modele": bool(any(poches[a]["e_modele"] > 1.0 + 1e-12 for a in R.POCHES)),
        "_ext": ext, "_ent": ent,
    }


def garman_klass(ohlc: pd.DataFrame) -> pd.Series:
    """Variance journaliere de Garman-Klass : 0,5 ln(H/L)^2 - (2 ln 2 - 1) ln(C/O)^2 (>= 0)."""
    o, h, lo, c = (ohlc[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
    return pd.Series(0.5 * np.log(h / lo) ** 2 - GK_K * np.log(c / o) ** 2, index=ohlc.index)


def fantome(d: dict) -> dict:
    """Signal fantome : sigma HAR nourri par Garman-Klass sur les bougies 1 j du lake, a la
    cloture de `jour`, a cote du sigma HAR 5 min. Memes MCO et memes replis (ecart-type 30 jours
    des clotures de 23:55) que le HAR du backtest. Ne decide rien."""
    jour = d["jour"]
    sortie = {}
    for a in R.POCHES:
        df = lecture.load(a, "1d", colonnes=("open", "high", "low", "close"))
        df.index = pd.DatetimeIndex(pd.to_datetime(df.pop("date"), utc=True)).tz_convert(
            None).normalize()
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df[(df.index <= jour) & (df[["open", "high", "low", "close"]] > 0).all(axis=1)]
        gk = garman_klass(df)
        gk = gk.reindex(pd.date_range(gk.index.min(), jour, freq="D"))
        h = hr.har(gk)
        ecart = d["prev"][a]["ecart_type"].reindex(gk.index)
        retenue, avant, negative = hr.replis(h["prevision"], h["jours_rv"], ecart)
        v = retenue.get(jour)
        sortie[a] = {"sigma_har_gk": (float(math.sqrt(R.JOURS_AN * v))
                                      if v is not None and np.isfinite(v) and v > 0 else None),
                     "gk_du_jour": (None if pd.isna(gk.get(jour)) else float(gk.loc[jour])),
                     "repli": bool(avant.get(jour, False) or negative.get(jour, False))}
    return sortie
