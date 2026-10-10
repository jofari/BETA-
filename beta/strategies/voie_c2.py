"""Voie C2 — long uniquement, regime BTC a votes. Regles fixees par Jonas le 2026-10-07.

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python beta/strategies/voie_c2.py

Preenregistrement : `scripts/preenregistrer_vc2.py`, ids VC2 (5 votes) et VC2T (temoin sans
macro) ; `scripts/preenregistrer_vc3.py`, id VC3 (poche BTC « maximum », en spot). La config
n'est PAS recopiee ici : elle est relue dans le registre par `config()`, qui refuse de
tourner si l'experience n'est pas preenregistree ou si l'empreinte differe. Le registre est
donc la seule source, et le verrou de BETA s'applique a la voie C2.

Trois etats, chaque jour, selon la somme des votes :
    haussier  >= seuil haut : moteur vol-cible de la config figee du 03/10, sans short ni carry
    baissier  <= seuil bas  : EPISODE jusqu'au prochain haussier — au signal, poche BTC a 25 %
                              du plus haut de l'equite (plafond 100 % du capital du jour), alts
                              -50 % ; ensuite la poche flotte et chaque alt sort en entier
                              quand son propre rendement 126 j est negatif ; aucun rachat
    veille    entre les deux : aucun ajout ; l'exposition ne peut que baisser, au prorata,
                              quand le brut voulu par le moteur haussier passe sous le brut
                              tenu de plus que la bande

Trois cles absentes de VC2/VC2T, ajoutees pour VC3 (absentes = comportement de VC2) :
    baissier.poche  "maximum" : au signal, BTC = min(tenu, 25 % du plus haut) — la regle ne
                    fait que vendre. Defaut "cible" : BTC ramene a 25 % du plus haut, achat
                    compris (c'etait un achat dans 9 episodes sur 9 de VC2).
    instrument      "spot" : aucun funding. Defaut "perpetuel" : le long paie le funding.
    plafond_brut    exposition brute maximale ; le voulu du moteur haussier est ramene au
                    plafond, au prorata (spot : 1, pas d'emprunt). Defaut : aucun.

Causalite : la ligne t est la position tenue PENDANT le jour t, decidee a t 00:00 UTC sur les
clotures <= t-1, le F&G date <= t-1 et les series FRED datees <= t-2 (une serie H.15 datee J
est publiee vers J+1 20:15 UTC, apres le passage du timer de 00:45). Deux epreuves le
verifient (`epreuve_causalite`) : troncature (calculer(d[:t]) == calculer(d)[:t]) et
perturbation (fausser tout ce qui n'est pas encore public a t ne change pas la ligne t).
"""

from __future__ import annotations

import hashlib
import json
import logging

import numpy as np
import pandas as pd

from beta.lake import lecture
from beta.protocole import experiences
from beta.strategies import voie_c_optim as vo
from beta.strategies import voie_c_verif as vv
from beta.strategies import voie_c_voltarget as vc

log = logging.getLogger("beta.strategies.voie_c2")

HAUSSIER, BAISSIER, VEILLE = "haussier", "baissier", "veille"

# Meme point de depart que toutes les mesures de la voie C : rodages (180 j de vol, 126 j de
# momentum, 30 j de sigma) termines.
DEPART_SIMULATION = pd.Timestamp("2021-06-12", tz="UTC")
FIN_BACKTEST = pd.Timestamp("2026-09-05", tz="UTC")
FIN_TRAIN = pd.Timestamp(vc.FIN_TRAIN, tz="UTC")


class ConfigError(RuntimeError):
    """Config absente du registre, ou differente de ce qui a ete preenregistre."""


def empreinte(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def config(id_exp: str) -> dict:
    """La config PREENREGISTREE de VC2, VC2T ou VC3, verifiee par son empreinte."""
    entree = experiences.exiger(id_exp)
    cfg = entree.get("config")
    if not cfg:
        raise ConfigError(f"{id_exp} : pas de config dans le registre")
    if empreinte(cfg) != entree.get("empreinte"):
        raise ConfigError(f"{id_exp} : empreinte {empreinte(cfg)} != registre "
                          f"{entree.get('empreinte')}")
    if tuple(cfg["paires"]) != vc.PAIRES or cfg["paires"][0] != "BTC":
        raise ConfigError(f"{id_exp} : paires {cfg['paires']} != {vc.PAIRES} (BTC en tete)")
    return cfg


# =========================================================================================
# Donnees (seule partie qui lit le lake)
# =========================================================================================

def donnees(fin: pd.Timestamp | None = None) -> dict:
    """Tout ce dont `calculer` a besoin, tronque a `fin` (date incluse) si demande."""
    index = vc.calendrier_commun(vc.PAIRES)
    if fin is not None:
        index = index[index <= fin]
    closes = vc.clotures(vc.PAIRES, index)
    funding_j = vc.funding_quotidien(vc.PAIRES, index)
    globales = lecture.macro_globales()
    fng = lecture.fear_greed().set_index("date")["fng"]
    fng.index = fng.index.normalize()
    fng = fng[~fng.index.duplicated(keep="last")]
    d = {"closes": closes, "funding": funding_j,
         "DFII10": globales["tips10y"].dropna(), "T10YIE": globales["breakeven10y"].dropna(),
         "NASDAQ100": lecture.nasdaq100(), "fng": fng}
    return tronquer(d, fin) if fin is not None else d


def tronquer(d: dict, fin: pd.Timestamp) -> dict:
    """Coupe chaque serie a `fin` incluse : ce qu'on aurait eu en relancant a cette date-la."""
    return {k: v[v.index <= fin] for k, v in d.items()}


# =========================================================================================
# Les votes : chaque serie est d'abord notee « same-day » (donnees datees <= D), puis decalee
# =========================================================================================

def _score_variation(obs: pd.Series, fenetre_obs: int, seuil: float, signe_hausse: int):
    """Composant « taux » d'ARIT, generalise : variation ABSOLUE sur `fenetre_obs` OBSERVATIONS.

    Arrondi a 1e-6 avant comparaison : une variation de 0,10 pt exactement doit compter, ce
    que le flottant brut ne garantit pas (1,85 - 1,75 = 0,0999999...).
    """
    diff = (obs - obs.shift(fenetre_obs)).round(6)
    out = pd.Series(0.0, index=obs.index)
    out[diff >= seuil] = float(signe_hausse)
    out[diff <= -seuil] = float(-signe_hausse)
    out[diff.isna()] = np.nan
    return out


def _score_fng(obs: pd.Series, bas: float, haut: float) -> pd.Series:
    out = pd.Series(0.0, index=obs.index)
    out[obs < bas] = -1.0
    out[obs >= haut] = 1.0
    return out


def _aligner(score_obs: pd.Series, calendrier: pd.DatetimeIndex, perime_h: float):
    """`_component_frame` d'ARIT : score porte sur le calendrier 7/7, 0 si perime ou absent."""
    cal = calendrier.union(score_obs.index)
    jours = pd.Series(cal, index=cal)
    score_ff = score_obs.reindex(cal).ffill(limit=int(perime_h / 24))
    # Fraicheur lue sur les DATES d'observation (score NaN en rodage compris), comme ARIT.
    derniere_obs = jours.where(jours.isin(score_obs.index)).ffill()
    age_h = (jours - derniere_obs) / pd.Timedelta(hours=1)
    frais = derniere_obs.notna() & (age_h <= perime_h)
    return score_ff.where(frais, 0.0).fillna(0.0).reindex(calendrier)


def _vote_nasdaq(nas: pd.Series, btc: pd.Series, p: dict, calendrier: pd.DatetimeIndex):
    """Bloc c6/c7 d'ARIT en vote : -1 si BTC est COUPLE et l'indice casse, 0 sinon — jamais +1.

    Calcule sur les SESSIONS US (rho calendaire 7/7 sous-estime le couplage d'un tiers, piege
    documente cote ARIT). Serie perimee (> perime_h) ou non demarree : 0. ARIT bloque les deux
    sens sur donnee perimee (A4) ; dans un vote, l'equivalent de « ne rien faire » est 0 — une
    donnee absente ne donne jamais de direction.
    """
    nas = nas.dropna()
    if nas.empty:
        return pd.Series(0.0, index=calendrier)
    cassure = (nas < nas.shift(1).rolling(p["cassure_obs"]).min()).fillna(False)
    btc_s = btc.reindex(nas.index.union(btc.index)).ffill().reindex(nas.index)
    r_btc, r_nas = np.log(btc_s).diff(), np.log(nas).diff()
    rho_c = r_btc.rolling(p["rho_court"]).corr(r_nas)
    rho_l = r_btc.rolling(p["rho_long"]).corr(r_nas)
    etat = pd.Series(np.nan, index=nas.index, dtype="object")
    etat[(rho_c >= p["arme_si"]) & (rho_l >= p["confirme_long_si"])] = "COUPLE"
    etat[rho_c < p["desarme_sous"]] = "DECOUPLE"
    etat = etat.ffill().fillna("TRANSITION")
    vote_sessions = pd.Series(np.where((etat == "COUPLE") & cassure, -1.0, 0.0), index=nas.index)
    cal = calendrier.union(nas.index)
    valeur = vote_sessions.reindex(cal).ffill()
    derniere = pd.Series(nas.index, index=nas.index).reindex(cal).ffill()
    age_h = (pd.Series(cal, index=cal) - derniere) / pd.Timedelta(hours=1)
    frais = derniere.notna() & (age_h <= p["perime_h"])
    return valeur.where(frais, 0.0).fillna(0.0).reindex(calendrier)


def votes(d: dict, cfg: dict) -> pd.DataFrame:
    """Les votes EN VIGUEUR chaque jour t (deja decales : utilisables a t 00:00 UTC)."""
    closes = d["closes"]
    cal = closes.index
    dec = cfg["decalages"]
    btc = closes["BTC"]
    mom = np.sign(btc / btc.shift(cfg["vote_momentum"]["fenetre"]) - 1.0)
    sortie = {"momentum_btc": mom.shift(dec["prix_j"]).fillna(0.0)}
    for nom, p in cfg["votes_macro"].items():
        if nom == "fear_greed":
            same_day = _aligner(_score_fng(d["fng"].dropna(), p["bas"], p["haut"]), cal,
                                p["perime_h"])
            sortie[nom] = same_day.shift(dec["fng_j"]).fillna(0.0)
        elif nom == "nasdaq":
            same_day = _vote_nasdaq(d[p["fred"]], btc, p, cal)
            sortie[nom] = same_day.shift(dec["fred_j"]).fillna(0.0)
        else:
            obs = d[p["fred"]].dropna()
            same_day = _aligner(_score_variation(obs, p["fenetre_obs"], p["seuil_pt"],
                                                 p["signe_hausse"]), cal, p["perime_h"])
            sortie[nom] = same_day.shift(dec["fred_j"]).fillna(0.0)
    return pd.DataFrame(sortie, index=cal)


def etats(v: pd.DataFrame, cfg: dict) -> pd.Series:
    somme = v.sum(axis=1)
    s = cfg["seuils_etat"]
    return pd.Series(np.where(somme >= s["haussier"], HAUSSIER,
                              np.where(somme <= s["baissier"], BAISSIER, VEILLE)),
                     index=v.index)


# =========================================================================================
# Le moteur haussier : la config figee du 03/10, sans short ni carry
# =========================================================================================

def moteur_haussier(closes: pd.DataFrame, h: dict) -> dict:
    rend = closes.pct_change()
    inverse = vc.inverse_vol(rend, h["fenetre_vol_jambes"])
    somme_inv = inverse.sum(axis=1)
    base = inverse.div(somme_inv, axis=0)
    momentum = np.sign(closes / closes.shift(h["fenetre_mom"]) - 1.0)
    tendance = (inverse * momentum.clip(lower=0.0)).div(somme_inv, axis=0)
    comp = h["poids_jambes"] * (base + tendance)
    r_comp = (comp.shift(1) * rend).sum(axis=1, skipna=False)
    sigma = vo.sigma_composite(r_comp, "glissant", h["fenetre"])
    levier_calcule = (h["cible"] / sigma.replace(0.0, np.nan)).clip(h["lmin"], h["lmax"])
    levier = vv.hysteresis(levier_calcule, h["seuil_levier"])
    cible = comp.shift(1).mul(levier.shift(1), axis=0)
    # Les briques intermediaires ne servent qu'a l'affichage (`indicateurs`).
    return {"composite": comp, "sigma": sigma, "levier": levier, "cible": cible,
            "levier_calcule": levier_calcule, "inverse": inverse, "base": base,
            "tendance": tendance, "momentum": momentum}


# =========================================================================================
# Le deroulement : etats -> positions tenues, avec derive, frais par paire et funding
# =========================================================================================

def couts_par_cote(cfg: dict) -> np.ndarray:
    f = cfg["frais"]
    return np.array([(f["taker_pb"] + f["slippage_pb"][p]) / 1e4 for p in cfg["paires"]])


def derouler(etat: np.ndarray, cible: np.ndarray, rend: np.ndarray, fund: np.ndarray,
             alt_en_baisse: np.ndarray, cfg: dict) -> dict:
    """Jour par jour, comme `voie_c_optim.derouler_bande`, plus les regles d'etat.

    `alt_en_baisse[i]` (bool, une colonne par alt) : rendement 126 j de l'alt < 0, connu a i.
    La position BTC est la colonne 0.
    """
    n, k = cible.shape
    b, bande = cfg["baissier"], cfg["haussier"]["bande"]
    couts = couts_par_cote(cfg)
    poche_maximum = b.get("poche", "cible") == "maximum"
    paie_funding = cfg.get("instrument", "perpetuel") == "perpetuel"
    plafond_brut = cfg.get("plafond_brut")
    tenu = np.zeros(k)
    r_brut, r_net = np.zeros(n), np.zeros(n)
    frais, funding, turnover, equite = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    positions = np.zeros((n, k))
    episodes = 0
    e_courante, plus_haut, episode = 1.0, 1.0, False
    for i in range(n):
        if i > 0:
            derive = np.nan_to_num(tenu * (1.0 + rend[i - 1]) / (1.0 + r_brut[i - 1]))
            e_courante *= 1.0 + r_net[i - 1]
            plus_haut = max(plus_haut, e_courante)
        else:
            derive = np.zeros(k)
        voulu = np.nan_to_num(cible[i])
        if plafond_brut is not None and np.abs(voulu).sum() > plafond_brut:
            voulu = voulu * (plafond_brut / float(np.abs(voulu).sum()))
        if etat[i] == HAUSSIER:
            episode = False
            ecart = float(np.abs(voulu - derive).sum())
            tenu = voulu if (ecart > bande or not derive.any()) else derive
        elif etat[i] == BAISSIER:
            tenu = derive.copy()
            if not episode:
                episode, episodes = True, episodes + 1
                poche = min(b["poche_btc_du_plus_haut"] * plus_haut / e_courante,
                            b["plafond_poche"])
                tenu[0] = min(derive[0], poche) if poche_maximum else poche
                tenu[1:] = derive[1:] * (1.0 - b["coupe_alts"])
            tenu[1:][alt_en_baisse[i]] = 0.0
        else:
            tenu = derive.copy()
            brut_tenu, brut_voulu = float(np.abs(derive).sum()), float(np.abs(voulu).sum())
            if brut_tenu - brut_voulu > bande:
                tenu = derive * (brut_voulu / brut_tenu)
        echange = np.abs(tenu - derive)
        turnover[i] = float(echange.sum())
        frais[i] = float((echange * couts).sum())
        r_brut[i] = float(np.nansum(tenu * rend[i]))
        funding[i] = float(np.nansum(tenu * fund[i])) if paie_funding else 0.0
        r_net[i] = r_brut[i] - frais[i] - funding[i]
        if 1.0 + r_net[i] <= 0.0:
            # Equite <= 0 : le compte est liquide. On s'arrete fort plutot que de continuer
            # avec des positions de signe absurde.
            raise RuntimeError(f"ruine au jour {i} : rendement net {r_net[i]:.2%}")
        positions[i] = tenu
        equite[i] = e_courante
    return {"r_brut": r_brut, "r_net": r_net, "frais": frais, "funding": funding,
            "turnover": turnover, "positions": positions, "equite_debut": equite,
            "episodes": episodes}


def calculer(d: dict, cfg: dict, depart: pd.Timestamp = DEPART_SIMULATION) -> dict:
    """Toute la chaine, PURE : donnees -> votes, etats, cibles, positions, rendements."""
    closes = d["closes"]
    rend = closes.pct_change()
    v = votes(d, cfg)
    et = etats(v, cfg)
    mh = moteur_haussier(closes, cfg["haussier"])
    fen = cfg["baissier"]["fenetre_mom_alts"]
    alts = list(vc.PAIRES[1:])
    en_baisse = ((closes[alts] / closes[alts].shift(fen) - 1.0) < 0.0).shift(1)
    en_baisse = en_baisse.fillna(False).astype(bool)

    jours = closes.index[closes.index >= depart]
    sortie = derouler(et.reindex(jours).to_numpy(), mh["cible"].reindex(jours).to_numpy(float),
                      rend.reindex(jours).to_numpy(float),
                      d["funding"].reindex(jours).to_numpy(float),
                      en_baisse.reindex(jours).to_numpy(bool), cfg)
    return {"jours": jours, "votes": v.reindex(jours), "etat": et.reindex(jours),
            "levier": mh["levier"].shift(1).reindex(jours),
            "sigma": mh["sigma"].shift(1).reindex(jours), "cible": mh["cible"].reindex(jours),
            "moteur": mh, **sortie}


# =========================================================================================
# Indicateurs : les valeurs BRUTES derriere chaque vote et derriere le moteur (affichage)
# =========================================================================================
#
# Rien ici ne decide. Chaque vote est RE-DERIVE de ses valeurs brutes par un autre chemin que
# `votes` (report de la derniere observation sur le calendrier, puis decalage) ; les tests
# verifient sur tout l'historique que les deux chemins donnent le meme vote. En production, un
# ecart n'est pas avale : `coherent` passe a faux et le dashboard le montre.

COUPLAGE = {1.0: "COUPLE", -1.0: "DECOUPLE", 0.0: "TRANSITION"}


def _report(obs: pd.DataFrame, cal: pd.DatetimeIndex) -> pd.DataFrame:
    """Chaque jour du calendrier recoit la derniere ligne datee <= ce jour, et sa date."""
    obs = obs.assign(date_obs=obs.index)
    return obs.reindex(cal.union(obs.index)).ffill().reindex(cal)


def _fraicheur(out: pd.DataFrame, cal: pd.DatetimeIndex, perime_h: float) -> pd.DataFrame:
    """Age de l'observation reportee ; un score perime ou absent vote 0, comme `_aligner`."""
    out["age_h"] = (pd.Series(cal, index=cal) - out["date_obs"]) / pd.Timedelta(hours=1)
    frais = out["date_obs"].notna() & (out["age_h"] <= perime_h)
    out["perimee"] = ~frais
    out["vote"] = out["score"].where(frais, 0.0).fillna(0.0)
    return out


def _detail_momentum(closes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    btc, fen = closes["BTC"], cfg["vote_momentum"]["fenetre"]
    out = pd.DataFrame({"valeur": btc, "reference": btc.shift(fen),
                        "date_reference": pd.Series(closes.index, index=closes.index).shift(fen),
                        "date_obs": closes.index}, index=closes.index)
    out["variation"] = out["valeur"] / out["reference"] - 1.0
    out["vote"] = np.sign(out["variation"])
    return out


def _detail_variation(obs: pd.Series, p: dict, cal: pd.DatetimeIndex) -> pd.DataFrame:
    obs = obs.dropna()
    n = p["fenetre_obs"]
    df = pd.DataFrame({"valeur": obs, "reference": obs.shift(n),
                       "date_reference": pd.Series(obs.index, index=obs.index).shift(n)})
    df["variation"] = (df["valeur"] - df["reference"]).round(6)
    signe = float(p["signe_hausse"])
    df["score"] = np.where(df["variation"] >= p["seuil_pt"], signe,
                           np.where(df["variation"] <= -p["seuil_pt"], -signe, 0.0))
    df.loc[df["variation"].isna(), "score"] = np.nan
    return _fraicheur(_report(df, cal), cal, p["perime_h"])


def _detail_fng(fng: pd.Series, p: dict, cal: pd.DatetimeIndex) -> pd.DataFrame:
    obs = fng.dropna()
    df = pd.DataFrame({"valeur": obs})
    df["score"] = np.where(obs < p["bas"], -1.0, np.where(obs >= p["haut"], 1.0, 0.0))
    return _fraicheur(_report(df, cal), cal, p["perime_h"])


def _detail_nasdaq(nas: pd.Series, btc: pd.Series, p: dict,
                   cal: pd.DatetimeIndex) -> pd.DataFrame:
    nas = nas.dropna()
    if nas.empty:
        return pd.DataFrame({"vote": 0.0, "date_obs": pd.NaT}, index=cal)
    plus_bas = nas.shift(1).rolling(p["cassure_obs"]).min()
    btc_s = btc.reindex(nas.index.union(btc.index)).ffill().reindex(nas.index)
    r_btc, r_nas = np.log(btc_s).diff(), np.log(nas).diff()
    rho_c = r_btc.rolling(p["rho_court"]).corr(r_nas)
    rho_l = r_btc.rolling(p["rho_long"]).corr(r_nas)
    couplage = pd.Series(np.nan, index=nas.index)
    couplage[(rho_c >= p["arme_si"]) & (rho_l >= p["confirme_long_si"])] = 1.0
    couplage[rho_c < p["desarme_sous"]] = -1.0
    couplage = couplage.ffill().fillna(0.0)
    cassure = (nas < plus_bas).astype(float)
    df = pd.DataFrame({"valeur": nas, "plus_bas": plus_bas, "cassure": cassure,
                       "rho_court": rho_c, "rho_long": rho_l, "couplage": couplage})
    df["score"] = np.where((couplage == 1.0) & (cassure == 1.0), -1.0, 0.0)
    return _fraicheur(_report(df, cal), cal, p["perime_h"])


def details_votes(d: dict, cfg: dict) -> dict[str, pd.DataFrame]:
    """Pour chaque vote, une table indexee par jour de DECISION t : les valeurs lues (deja
    decalees, donc datees <= t-1 ou <= t-2) et le vote qui en sort, colonne `vote`."""
    closes = d["closes"]
    cal, dec = closes.index, cfg["decalages"]
    sortie = {"momentum_btc": _detail_momentum(closes, cfg).shift(dec["prix_j"])}
    for nom, p in cfg["votes_macro"].items():
        if nom == "fear_greed":
            det, decalage = _detail_fng(d["fng"], p, cal), dec["fng_j"]
        elif nom == "nasdaq":
            det, decalage = _detail_nasdaq(d[p["fred"]], closes["BTC"], p, cal), dec["fred_j"]
        else:
            det, decalage = _detail_variation(d[p["fred"]], p, cal), dec["fred_j"]
        sortie[nom] = det.shift(decalage)
    for det in sortie.values():
        det["vote"] = det["vote"].fillna(0.0)
    return sortie


def _nombre(x, chiffres: int = 6):
    """Valeur JSON : None pour une valeur absente, flottant arrondi sinon."""
    if x is None or pd.isna(x):
        return None
    return round(float(x), chiffres)


def _date(x) -> str | None:
    return None if x is None or pd.isna(x) else f"{pd.Timestamp(x):%Y-%m-%d}"


def _vote_lisible(nom: str, r: pd.Series, cfg: dict) -> dict:
    sortie = {"lu": _date(r.get("date_obs")), "valeur": _nombre(r.get("valeur")),
              "vote_recalcule": int(r["vote"])}
    if nom == "momentum_btc":
        sortie.update(reference=_nombre(r["reference"]),
                      date_reference=_date(r["date_reference"]),
                      variation=_nombre(r["variation"]),
                      params={"fenetre_j": cfg["vote_momentum"]["fenetre"]})
        return sortie
    p = cfg["votes_macro"][nom]
    sortie.update(age_h=_nombre(r.get("age_h"), 1), perimee=bool(r.get("perimee", True)),
                  params={k: v for k, v in p.items() if k != "fred"})
    if nom == "nasdaq":
        sortie.update(plus_bas=_nombre(r.get("plus_bas")),
                      cassure=bool(r.get("cassure") == 1.0),
                      rho_court=_nombre(r.get("rho_court"), 3),
                      rho_long=_nombre(r.get("rho_long"), 3),
                      couplage=COUPLAGE.get(r.get("couplage")) if pd.notna(r.get("couplage"))
                      else None)
    elif nom != "fear_greed":
        sortie.update(reference=_nombre(r.get("reference")),
                      date_reference=_date(r.get("date_reference")),
                      variation=_nombre(r.get("variation")))
    return sortie


def _moteur_lisible(mh: dict, closes: pd.DataFrame, cfg: dict, t: pd.Timestamp) -> dict | None:
    """Le moteur haussier tel qu'il sert la journee t : briques lues a t-1, comme `cible`."""
    i = closes.index.get_loc(t)
    if i == 0:
        return None
    h, j = cfg["haussier"], closes.index[i - 1]
    fen = h["fenetre_mom"]
    voulu = np.nan_to_num(mh["cible"].loc[t].to_numpy(dtype=float))
    brut_moteur = float(np.abs(voulu).sum())
    plafond = cfg.get("plafond_brut")
    echelle = plafond / brut_moteur if plafond is not None and brut_moteur > plafond else 1.0
    paires = {}
    for k, p in enumerate(closes.columns):
        inverse = mh["inverse"].at[j, p]
        reference = closes[p].iloc[i - 1 - fen] if i - 1 - fen >= 0 else np.nan
        paires[p] = {
            "vol_180j": _nombre(np.sqrt(vc.PPA) / inverse if pd.notna(inverse) else None),
            "momentum": _nombre(closes.at[j, p] / reference - 1.0),
            "tendance_active": bool(mh["momentum"].at[j, p] > 0),
            "poids_base": _nombre(mh["base"].at[j, p]),
            "poids_tendance": _nombre(mh["tendance"].at[j, p]),
            "composite": _nombre(mh["composite"].at[j, p]),
            "voulu": _nombre(voulu[k] * echelle),
        }
    return {
        "lu": f"{j:%Y-%m-%d}", "cible_vol": h["cible"], "sigma": _nombre(mh["sigma"].at[j]),
        "levier_calcule": _nombre(mh["levier_calcule"].at[j]),
        "levier": _nombre(mh["levier"].at[j]),
        "params": {k: h[k] for k in ("fenetre_vol_jambes", "fenetre_mom", "poids_jambes",
                                     "fenetre", "lmin", "lmax", "seuil_levier", "bande")},
        "somme_composite": _nombre(mh["composite"].loc[j].sum()),
        "brut_moteur": _nombre(brut_moteur), "plafond_brut": plafond,
        "brut_voulu": _nombre(brut_moteur * echelle), "paires": paires,
    }


def indicateurs(d: dict, cfg: dict, t: pd.Timestamp) -> dict:
    """Tout ce qui fait la ligne t, en valeurs brutes et lisibles (JSON) : chaque vote avec ce
    qu'il a lu, l'etat, et le moteur haussier. Pour verifier l'analyse a l'oeil."""
    det = details_votes(d, cfg)
    officiels = votes(d, cfg).loc[t]
    lus = {}
    for nom, table in det.items():
        lus[nom] = _vote_lisible(nom, table.loc[t], cfg)
        lus[nom]["vote"] = int(officiels[nom])
    somme = sum(v["vote"] for v in lus.values())
    s = cfg["seuils_etat"]
    etat = HAUSSIER if somme >= s["haussier"] else BAISSIER if somme <= s["baissier"] else VEILLE
    return {
        "date": f"{t:%Y-%m-%d}", "votes": lus, "somme": somme, "seuils": dict(s), "etat": etat,
        "coherent": all(v["vote"] == v["vote_recalcule"] for v in lus.values()),
        "moteur": _moteur_lisible(moteur_haussier(d["closes"], cfg["haussier"]),
                                  d["closes"], cfg, t),
    }


# =========================================================================================
# Epreuves de causalite
# =========================================================================================

def epreuve_causalite(d: dict, cfg: dict, t: pd.Timestamp) -> dict[str, float]:
    """Ecarts max (0 attendu) entre la chaine complete et deux chaines « a la date t ».

    1. troncature : toutes les donnees coupees a t. Les lignes <= t doivent etre identiques.
    2. perturbation : tout ce qui n'est PAS encore public a t 00:00 UTC est fausse — cloture
       du jour t (x 1,5), F&G date t, series FRED datees t-1 et t, NASDAQ des sessions t-1
       et t. La ligne t (votes, etat, position) ne doit pas bouger.
    """
    complet = calculer(d, cfg)
    ecarts: dict[str, float] = {}

    court = calculer(tronquer(d, t), cfg)
    n = len(court["jours"])
    ecarts["troncature votes"] = float(np.abs(court["votes"].to_numpy()
                                              - complet["votes"].to_numpy()[:n]).max())
    ecarts["troncature etats"] = float((court["etat"].to_numpy()
                                        != complet["etat"].to_numpy()[:n]).sum())
    ecarts["troncature positions"] = float(np.abs(court["positions"]
                                                  - complet["positions"][:n]).max())

    fausse = {k: v.copy() for k, v in tronquer(d, t).items()}
    fausse["closes"].loc[t] = fausse["closes"].loc[t] * 1.5
    fausse["fng"].loc[t] = 1.0
    for cle in ("DFII10", "T10YIE", "NASDAQ100"):
        serie = fausse[cle]
        for jour in (t - pd.Timedelta(days=1), t):
            serie.loc[jour] = serie.iloc[-1] * (0.5 if cle == "NASDAQ100" else 1.0) + 5.0
        fausse[cle] = serie.sort_index()
    pert = calculer(fausse, cfg)
    i_t = n - 1
    ecarts["perturbation votes t"] = float(np.abs(pert["votes"].to_numpy()[i_t]
                                                  - complet["votes"].to_numpy()[i_t]).max())
    ecarts["perturbation etat t"] = float(pert["etat"].iat[i_t] != complet["etat"].iat[i_t])
    ecarts["perturbation position t"] = float(np.abs(pert["positions"][i_t]
                                                     - complet["positions"][i_t]).max())
    return ecarts
