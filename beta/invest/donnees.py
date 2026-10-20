"""Test invest — les donnees : prix du panier, votes du socle point-in-time, controles C5.

Les votes sont ceux du socle VC (`voie_c2.votes`, config relue dans le registre), a une
difference pres, decidee par Jonas le 20/10 (D1) : DFII10 et NASDAQ100 n'entrent qu'a leur date
de PUBLICATION par FRED, et non avec un decalage fixe de 2 jours calendaires. Le decalage fixe
fait lire la valeur du vendredi des le dimanche, alors que FRED ne la publie que le jour ouvre
suivant (constate en live : vote DFII10 du 13/10 = 0 dans le journal, -1 au recalcul).

Regle : une observation datee D est utilisable a la decision t (00:00 UTC) si
t >= jour ouvre US suivant D + 1 jour (H.15 vers 20:15 UTC ; NASDAQ100 le matin suivant). La
peremption du socle est conservee, mesuree a la decision : 4 j (DFII10), 7 j (NASDAQ).
`vote_publie` est le calcul du socle rejoue sur les seules donnees publiees, en une passe
(le test d'equivalence le verifie contre `voie_c2`). T10YIE (publie le jour meme), momentum et
F&G sont deja point-in-time : ils restent ceux de `voie_c2.votes`.

Les votes ne dependent que de BTC et des series macro : ils se calculent sur TOUT l'historique de
BTC (depuis 2019-09), pas sur le calendrier commun des 6 paires (qui ne commence qu'avec SOL, le
2020-09-14) — sinon le momentum vaudrait 0 en rodage pendant les 4 premiers mois du stress test.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from beta import config
from beta.lake import lecture
from beta.strategies import voie_c2 as c2

log = logging.getLogger("beta.invest.donnees")

VOTES = ("momentum_btc", "taux_reel_10a", "inflation_anticipee_10a", "nasdaq", "fear_greed")
VOTES_PUBLICATION = ("taux_reel_10a", "nasdaq")            # D1 : calendrier de publication
SOCLE = "VC3"                                              # blocs des votes = VC2, VC4, VC5
SERIES_FRED = ("DFII10", "T10YIE", "NASDAQ100")
ECART_FRED_MAX_J = 4               # vendredi -> mardi apres un lundi ferie
RETARD_FRED_MAX_J = 7              # comme `lake.maj` : au-dela, la serie est en retard
TROUS_FNG_ACCEPTES = {"2024-10-26": "D6, Jonas 20/10 : regle de peremption du socle "
                                    "(valeur du 25/10, <= 48 h)"}
JOURS = ("lun", "mar", "mer", "jeu", "ven", "sam", "dim")
UN_JOUR = pd.Timedelta(days=1)


class DonneesError(RuntimeError):
    """Serie manquante, trouee ou en retard : on s'arrete et on le dit (C5)."""


# =========================================================================================
# Calendrier de publication
# =========================================================================================

def ns(index: pd.DatetimeIndex) -> np.ndarray:
    """Nanosecondes UTC. pandas 3 infere des index en `us` : sans unite commune, deux `asi8`
    ne se comparent pas (et `to_numpy()` d'un index avec fuseau rend des objets)."""
    return index.as_unit("ns").asi8


def feries_us(debut, fin) -> np.ndarray:
    """Feries federaux US (dates naives, jours) : FRED et le H.15 ne publient pas ces jours-la."""
    debut = pd.Timestamp(debut).tz_localize(None) - pd.Timedelta(days=10)
    fin = pd.Timestamp(fin).tz_localize(None) + pd.Timedelta(days=10)
    return USFederalHolidayCalendar().holidays(debut, fin).to_numpy(dtype="datetime64[D]")


def disponibilite(dates: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """A(D) : le jour (00:00 UTC) a partir duquel l'observation datee D est utilisable.

    Jour ouvre US suivant D (publication), plus un jour (on decide a 00:00 UTC). Un D lui-meme
    ferie (seance NASDAQ d'un Columbus Day) se rattache au jour ouvre qui le suit.
    """
    if len(dates) == 0:
        return pd.DatetimeIndex([], tz="UTC")
    jours = dates.tz_convert("UTC").tz_localize(None).to_numpy(dtype="datetime64[D]")
    publication = np.busday_offset(jours, 1, roll="backward",
                                   holidays=feries_us(dates.min(), dates.max()))
    return pd.DatetimeIndex(publication.astype("datetime64[ns]") + np.timedelta64(1, "D"),
                            tz="UTC")


def age_max_j(p: dict, decalage_j: int) -> int:
    """La peremption du socle, mesuree a la decision : `perime_h` au jour t - decalage."""
    return int(decalage_j + p["perime_h"] / 24)


def vote_publie(score_obs: pd.Series, calendrier: pd.DatetimeIndex, age_max_j: int) -> pd.Series:
    """Le score de la derniere observation PUBLIEE a chaque decision t ; 0 si aucune n'est
    publiee, si son score est NaN (rodage) ou si elle a plus de `age_max_j` jours."""
    s = score_obs.sort_index()
    if s.empty:
        return pd.Series(0.0, index=calendrier)
    rang = np.searchsorted(ns(disponibilite(s.index)), ns(calendrier), side="right") - 1
    valeur = np.where(rang >= 0, s.to_numpy(dtype=float)[np.maximum(rang, 0)], np.nan)
    age_j = (ns(calendrier) - ns(s.index)[np.maximum(rang, 0)]) / 86_400e9
    frais = (rang >= 0) & (age_j <= age_max_j)
    return pd.Series(np.where(frais, np.nan_to_num(valeur, nan=0.0), 0.0), index=calendrier)


def vote_nasdaq_seances(nas: pd.Series, btc: pd.Series, p: dict) -> pd.Series:
    """Le vote NASDAQ du socle a chaque SEANCE (couplage + cassure), sans peremption."""
    nas = nas.dropna()
    return c2._vote_nasdaq(nas, btc, {**p, "perime_h": float("inf")}, nas.index)


def votes_pit(d: dict, cfg: dict) -> pd.DataFrame:
    """`voie_c2.votes`, avec DFII10 et NASDAQ remplaces par leur version publiee (D1)."""
    v = c2.votes(d, cfg).copy()
    cal, dec = v.index, cfg["decalages"]["fred_j"]
    for nom in VOTES_PUBLICATION:
        p = cfg["votes_macro"][nom]
        if nom == "nasdaq":
            score = vote_nasdaq_seances(d[p["fred"]], d["closes"]["BTC"], p)
        else:
            score = c2._score_variation(d[p["fred"]].dropna(), p["fenetre_obs"], p["seuil_pt"],
                                        p["signe_hausse"])
        v[nom] = vote_publie(score, cal, age_max_j(p, dec))
    return v[list(VOTES)]


def diagnostic_pit(socle: pd.DataFrame, pit: pd.DataFrame, cfg: dict,
                   periodes: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> dict:
    """Jours ou le vote (et l'etat du regime) differe entre decalage fixe et publication.

    Aucun P&L, aucun compteur : une comparaison de signaux, rendue avec le rapport.
    """
    etat_socle, etat_pit = c2.etats(socle, cfg), c2.etats(pit, cfg)
    sortie = {}
    for nom, (debut, fin) in periodes.items():
        m = (socle.index >= debut) & (socle.index <= fin)
        votes = {}
        for v in VOTES:
            diff = socle.index[m][(socle[v][m] != pit[v][m]).to_numpy()]
            jours = pd.Series([JOURS[x] for x in diff.dayofweek]).value_counts()
            votes[v] = {"jours": int(len(diff)),
                        "par_jour": {j: int(jours[j]) for j in JOURS if j in jours}}
        diff_etat = socle.index[m][(etat_socle[m] != etat_pit[m]).to_numpy()]
        sortie[nom] = {"jours": int(m.sum()), "votes": votes,
                       "etat": {"jours": int(len(diff_etat)),
                                "dates": [f"{x:%Y-%m-%d}" for x in diff_etat]}}
    return sortie


# =========================================================================================
# Controles (C5) : on s'arrete plutot que d'inventer
# =========================================================================================

def controler_prix(closes: pd.DataFrame, debut: pd.Timestamp, fin: pd.Timestamp) -> None:
    if closes.empty or closes.index.max() < fin:
        derniere = "aucune" if closes.empty else f"{closes.index.max():%Y-%m-%d}"
        raise DonneesError(f"prix : derniere cloture commune {derniere}, il faut le "
                           f"{fin:%Y-%m-%d} (lake a jour ? journalctl -u beta-maj)")
    fenetre = closes[(closes.index >= debut) & (closes.index <= fin)]
    manquants = pd.date_range(debut, fin, freq="D").difference(fenetre.index)
    if len(manquants):
        raise DonneesError(f"prix : {len(manquants)} jour(s) absent(s) du calendrier commun : "
                           + ", ".join(f"{x:%Y-%m-%d}" for x in manquants[:10]))
    trous = fenetre.isna()
    if trous.any().any():
        raise DonneesError("prix : cloture(s) absente(s) : " + ", ".join(
            f"{p} {fenetre.index[trous[p]][0]:%Y-%m-%d}" for p in fenetre.columns
            if trous[p].any()))


def controler_fred(serie: pd.Series, nom: str, debut: pd.Timestamp, fin: pd.Timestamp) -> None:
    obs = serie.dropna()
    if obs.empty or (fin - obs.index.max()).days > RETARD_FRED_MAX_J:
        derniere = "aucune" if obs.empty else f"{obs.index.max():%Y-%m-%d}"
        raise DonneesError(f"{nom} : derniere observation {derniere}, en retard de plus de "
                           f"{RETARD_FRED_MAX_J} j au {fin:%Y-%m-%d}")
    fenetre = obs.index[(obs.index >= debut) & (obs.index <= fin)]
    ecarts = pd.Series(fenetre[1:] - fenetre[:-1], index=fenetre[1:]).dt.days
    gros = ecarts[ecarts > ECART_FRED_MAX_J]
    if len(gros):
        raise DonneesError(f"{nom} : trou de {int(gros.iloc[0])} j avant le "
                           f"{gros.index[0]:%Y-%m-%d} (au plus {ECART_FRED_MAX_J} j attendus)")


def controler_fng(fng: pd.Series, debut: pd.Timestamp, fin: pd.Timestamp) -> list[str]:
    """Le F&G du jour t-1 sert a la decision t : tous les jours de [debut - 1, fin - 1]."""
    obs = fng.dropna().index
    if len(obs) == 0 or obs.max() < fin - UN_JOUR:
        raise DonneesError(f"fear_greed : derniere valeur "
                           f"{'aucune' if len(obs) == 0 else f'{obs.max():%Y-%m-%d}'}, il faut "
                           f"le {fin - UN_JOUR:%Y-%m-%d}")
    manquants = pd.date_range(debut - UN_JOUR, fin - UN_JOUR, freq="D").difference(obs)
    acceptes = [f"fear_greed {x:%Y-%m-%d}" for x in manquants
                if f"{x:%Y-%m-%d}" in TROUS_FNG_ACCEPTES]
    autres = [f"{x:%Y-%m-%d}" for x in manquants if f"{x:%Y-%m-%d}" not in TROUS_FNG_ACCEPTES]
    if autres:
        raise DonneesError("fear_greed : jour(s) absent(s) : " + ", ".join(autres[:10]))
    return acceptes


def controler(d: dict, debut: pd.Timestamp, fin: pd.Timestamp) -> list[str]:
    """Prix, FRED et F&G complets sur [debut, fin] ; rend les trous ACCEPTES (D6)."""
    controler_prix(d["closes"], debut, fin)
    for nom in SERIES_FRED:
        controler_fred(d[nom], nom, debut, fin)
    return controler_fng(d["fng"], debut, fin)


def controler_rodage(d: dict, cfg: dict, debut: pd.Timestamp) -> None:
    """Chaque vote doit avoir fini son rodage avant `debut` : un 0 de rodage n'est pas un vote."""
    btc = d["closes"]["BTC"].dropna()
    fen = cfg["vote_momentum"]["fenetre"]
    if btc.empty or btc.index.min() > debut - pd.Timedelta(days=fen + 1):
        raise DonneesError(f"momentum_btc : il faut {fen + 1} j de BTC avant le "
                           f"{debut:%Y-%m-%d} (debut {btc.index.min():%Y-%m-%d})")
    dec = cfg["decalages"]["fred_j"]
    for nom, p in cfg["votes_macro"].items():
        if nom == "fear_greed":
            continue
        avant = d[p["fred"]].dropna()
        avant = avant[avant.index <= debut - pd.Timedelta(days=dec)]
        if nom == "nasdaq":
            avant, besoin = avant[avant.index >= btc.index.min()], p["rho_long"] + 1
        else:
            besoin = p["fenetre_obs"] + 1
        if len(avant) < besoin:
            raise DonneesError(f"{nom} : {len(avant)} observations avant le {debut:%Y-%m-%d}, "
                               f"il en faut {besoin} (rodage)")


# =========================================================================================
# Chargement
# =========================================================================================

def empreinte(closes: pd.DataFrame, votes: pd.DataFrame) -> str:
    """Les donnees qui entrent dans un run : memes octets = meme empreinte (C1)."""
    h = hashlib.sha256()
    for df in (closes, votes):
        h.update(",".join(map(str, df.columns)).encode())
        h.update(ns(df.index).tobytes())
        h.update(np.ascontiguousarray(df.to_numpy(dtype=float)).tobytes())
    return h.hexdigest()[:16]


def lake_disponible() -> bool:
    return (config.chemin_parquet("BTC_USDT_USDT", "1d").exists()
            and config.chemin_macro("nasdaq100.csv", globale=True).exists())


@dataclass
class Donnees:
    closes: pd.DataFrame          # 6 paires, calendrier commun, <= fin
    votes: pd.DataFrame           # votes en vigueur chaque jour (mode `pit`)
    votes_socle: pd.DataFrame     # `voie_c2.votes` tel quel, pour le diagnostic PIT
    funding: pd.DataFrame
    dff: pd.Series                # taux sans risque FRED DFF (%, option rf)
    cfg_socle: dict
    fin: pd.Timestamp
    pit: str
    trous_acceptes: list[str]
    empreinte: str


def charger(fin: pd.Timestamp, debut_controle: pd.Timestamp,
            pit: str = "publication") -> Donnees:
    """Tout ce qu'un run lit, controle (C5) depuis `debut_controle` (le P0 le plus ancien)."""
    if pit not in ("publication", "socle"):
        raise ValueError(f"pit inconnu : {pit}")
    cfg = c2.config(SOCLE)
    d = c2.donnees(fin)
    btc = lecture.load("BTC", "1d", fin=f"{fin:%Y-%m-%d}", colonnes=("close",))
    d_votes = {**d, "closes": pd.DataFrame(
        {"BTC": btc.set_index("date")["close"].astype(float)})}
    acceptes = controler(d, debut_controle, fin)
    # Les votes lisent avant P0 : 126 j de BTC, 60 observations FRED, 90 seances NASDAQ.
    controler_prix(d_votes["closes"], debut_controle - pd.Timedelta(days=130), fin)
    for nom in SERIES_FRED:
        controler_fred(d[nom], nom, debut_controle - pd.Timedelta(days=200), fin)
    controler_rodage(d_votes, cfg, debut_controle)
    socle = c2.votes(d_votes, cfg)[list(VOTES)]
    votes = votes_pit(d_votes, cfg) if pit == "publication" else socle
    votes = votes.reindex(d["closes"].index)
    globales = lecture.macro_globales()
    dff = globales["fedfunds"].dropna() if "fedfunds" in globales else pd.Series(dtype=float)
    return Donnees(closes=d["closes"], votes=votes, votes_socle=socle.reindex(d["closes"].index),
                   funding=d["funding"], dff=dff, cfg_socle=cfg, fin=fin, pit=pit,
                   trous_acceptes=acceptes, empreinte=empreinte(d["closes"], votes))
