"""Intraday des vrais marches (Jonas, 20/10 : « le vrai SPX, le vrai Nasdaq, le vrai XAUUSD en 5m,
1H, 4H, 1D », en direct et en historique, ni Binance ni freqtrade).

- SPX, NDX : Yahoo, 5m (la source ne garde que 60 jours : l'historique s'allonge a chaque
  passage) et 1h (730 jours). Direct : un passage toutes les 5 min (`beta-marches-direct`).
- XAU_SPOT : or comptant XAU/USD, bougies BID Dukascopy a la minute, agregees en 5m, 1h et 1d
  (jour UTC). Historique depuis 2003 rattrape LENTEMENT (la source bride : une requete a la fois,
  espacees) par `beta-marches-histo` ; journee en cours par les ticks horaires (retard <= ~1 h),
  remplaces par les bougies officielles une fois la journee publiee.
- 4h : jamais stocke, derive du 1h a la lecture sur la grille UTC 00/04/08/12/16/20 (convention
  du lake). Pour un indice, la seance 13:30-20:00 UTC tombe donc dans deux bougies 4h.

Fichiers : `data/marches/<NOM>-<tf>.parquet`, colonne `date` = OUVERTURE de la bougie, en UTC.
Les ecritures passent par un verrou de fichier : le direct et le rattrapage tournent ensemble.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import logging
import time
from datetime import UTC, datetime

import pandas as pd

from beta.marches import collecte, sources

log = logging.getLogger("beta.marches.intraday")

INTRADAY = {
    "SPX": {"source": "yahoo", "identifiant": "^GSPC", "periodes": {"5m": "60d", "1h": "730d"}},
    "NDX": {"source": "yahoo", "identifiant": "^NDX", "periodes": {"5m": "60d", "1h": "730d"}},
    "XAU_SPOT": {"source": "dukascopy", "identifiant": "XAUUSD", "depuis": "2003-05-05",
                 "tfs": ("5m", "1h", "1d")},
}
PAS = {"5m": pd.Timedelta(minutes=5), "1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4),
       "1d": pd.Timedelta(days=1)}
REGLE = {"5m": "5min", "1h": "1h", "4h": "4h", "1d": "1D"}
PERIODE_DIRECT = "5d"                 # un passage courant ne relit que les 5 derniers jours
PAUSE_DUKASCOPY_S = 4.0              # entre deux heures de ticks (direct)
PAUSE_RATTRAPAGE_S = 10.0            # entre deux jours (rattrapage) : ~1 jour pour tout 2003+
ATTENTE_BRIDE_S = 300.0
ECHECS_MAX = 3                        # 503 d'affilee : on s'arrete, la progression est gardee
ECRIRE_TOUS_LES_N_JOURS = 30
# Un fichier de jour VIDE n'est definitif qu'apres ce delai (publication tardive de la veille) :
# avant, le jour n'est pas marque lu et sera redemande.
DELAI_JOUR_VIDE_J = 3


def _etat_chemin():
    return collecte.DOSSIER / "etat_intraday.json"


def _jours_chemin(nom: str):
    return collecte.DOSSIER / f"{nom}-jours.json"


@contextlib.contextmanager
def verrou(nom: str):
    collecte.DOSSIER.mkdir(parents=True, exist_ok=True)
    with (collecte.DOSSIER / f".verrou_{nom}").open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _lire_brut(nom: str, tf: str) -> pd.DataFrame | None:
    p = collecte.chemin(nom, tf)
    if not p.exists():
        return None
    return pd.read_parquet(p).set_index("date").sort_index()


def lire(nom: str, tf: str, maintenant: pd.Timestamp | None = None) -> pd.DataFrame:
    """Les bougies stockees ; « 4h » est derive du 1h (grille UTC), sans la bougie 4h en cours."""
    if tf == "4h":
        maintenant = maintenant or pd.Timestamp.now(tz="UTC")
        return closes_seulement(agreger(lire(nom, "1h"), "4h"), "4h", maintenant)
    df = _lire_brut(nom, tf)
    if df is None:
        raise FileNotFoundError(f"{nom} {tf} : pas encore collecte (python scripts/marches.py "
                                "--direct)")
    return df


def agreger(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """OHLCV sur la grille UTC de `tf` (bougie etiquetee par son ouverture)."""
    if df.empty:
        return df.copy()
    g = df.resample(REGLE[tf], label="left", closed="left")
    out = pd.DataFrame({"open": g["open"].first(), "high": g["high"].max(),
                        "low": g["low"].min(), "close": g["close"].last(),
                        "volume": g["volume"].sum()})
    return out.dropna(subset=["close"])


def closes_seulement(df: pd.DataFrame, tf: str, maintenant: pd.Timestamp) -> pd.DataFrame:
    """Retire la bougie en cours (son ouverture + son pas depasse maintenant)."""
    return df[df.index + PAS[tf] <= maintenant]


def fusionner(ancien: pd.DataFrame | None, neuf: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Le neuf remplace l'ancien sur leur recouvrement ; rend aussi le nombre de clotures
    changees (une source qui reecrit le passe se voit)."""
    if ancien is None or ancien.empty:
        return neuf.sort_index(), 0
    communes = ancien.index.intersection(neuf.index)
    changees = int((ancien.loc[communes, "close"] - neuf.loc[communes, "close"]).abs()
                   .gt(1e-9 * neuf.loc[communes, "close"].abs()).sum())
    garde = ancien.loc[ancien.index.difference(neuf.index)]
    return pd.concat([garde, neuf]).sort_index(), changees


def _ecrire(df: pd.DataFrame, nom: str, tf: str) -> None:
    cible = collecte.chemin(nom, tf)
    tmp = cible.with_suffix(".partiel")
    sortie = df.copy()
    sortie.index = pd.DatetimeIndex(sortie.index).tz_convert("UTC").as_unit("ms")
    sortie.index.name = "date"
    sortie.reset_index().to_parquet(tmp, index=False)
    tmp.replace(cible)


def integrer(nom: str, tf: str, neuf: pd.DataFrame) -> dict:
    """Fusion + ecriture d'un timeframe, sous verrou ; rend son resume."""
    with verrou(nom):
        fusion, changees = fusionner(_lire_brut(nom, tf), neuf)
        if not fusion.empty:
            _ecrire(fusion, nom, tf)
    return {"debut": None if fusion.empty else fusion.index.min().isoformat(),
            "fin": None if fusion.empty else fusion.index.max().isoformat(),
            "n": int(len(fusion)), "revisions": changees}


def _noter(nom: str, resume: dict) -> None:
    with verrou("etat_intraday"):
        p = _etat_chemin()
        etat = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        etat[nom] = {**etat.get(nom, {}), **resume,
                     "maj_le": datetime.now(UTC).isoformat(timespec="seconds")}
        p.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")


def etat() -> dict:
    p = _etat_chemin()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# =========================================================================================
# Yahoo : SPX, NDX
# =========================================================================================

def maj_yahoo(nom: str, maintenant: pd.Timestamp | None = None) -> dict:
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    s = INTRADAY[nom]
    resume = {"source": "yahoo", "identifiant": s["identifiant"]}
    for tf, profondeur in s["periodes"].items():
        periode = profondeur if _lire_brut(nom, tf) is None else PERIODE_DIRECT
        try:
            neuf = closes_seulement(sources.yahoo_intraday(s["identifiant"], tf, periode), tf,
                                    maintenant)
            resume[tf] = {**integrer(nom, tf, neuf), "statut": "ok"}
        except sources.SourceError as exc:
            log.error("%s %s : %s", nom, tf, exc)
            resume[tf] = {"statut": "echec", "erreur": str(exc)}
    _noter(nom, resume)
    return resume


# =========================================================================================
# Dukascopy : XAU_SPOT
# =========================================================================================

def _jours_vus(nom: str) -> set[str]:
    p = _jours_chemin(nom)
    return set(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else set()


def _noter_jours(nom: str, jours: set[str]) -> None:
    with verrou(f"jours_{nom}"):
        p = _jours_chemin(nom)
        tous = _jours_vus(nom) | jours
        tmp = p.with_suffix(".partiel")
        tmp.write_text(json.dumps(sorted(tous)), encoding="utf-8")
        tmp.replace(p)


def _integrer_minutes(nom: str, minutes: list[pd.DataFrame],
                      tfs: tuple[str, ...] | None = None) -> dict:
    pleins = [m for m in minutes if not m.empty]
    if not pleins:
        return {}
    lot = pd.concat(pleins)
    lot = lot[~lot.index.duplicated(keep="last")].sort_index()
    return {tf: integrer(nom, tf, agreger(lot, tf)) for tf in (tfs or INTRADAY[nom]["tfs"])}


def jours_manquants(nom: str, maintenant: pd.Timestamp,
                    depuis_j: int | None = None) -> list[pd.Timestamp]:
    """Les jours UTC publies (jusqu'a la veille) jamais lus, du plus recent au plus ancien ;
    `depuis_j` : seulement les `depuis_j` derniers jours (le direct ne rattrape pas l'histoire)."""
    s = INTRADAY[nom]
    hier = maintenant.tz_convert("UTC").normalize() - pd.Timedelta(days=1)
    vus = _jours_vus(nom)
    debut = s["depuis"] if depuis_j is None else max(
        pd.Timestamp(s["depuis"]), hier.tz_localize(None) - pd.Timedelta(days=depuis_j - 1))
    tous = pd.date_range(debut, hier.tz_localize(None), freq="D")
    return [j for j in reversed(tous) if f"{j:%Y-%m-%d}" not in vus]


def rattraper_dukascopy(nom: str = "XAU_SPOT", limite: int | None = None,
                        maintenant: pd.Timestamp | None = None,
                        pause_s: float | None = None, depuis_j: int | None = None) -> dict:
    """Les jours manquants, du plus recent au plus ancien, une requete a la fois. Trois refus
    d'affilee (503) : arret propre, progression gardee, le timer reprendra plus tard."""
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    pause_s = PAUSE_RATTRAPAGE_S if pause_s is None else pause_s
    a_lire = jours_manquants(nom, maintenant, depuis_j)[:limite]
    minutes, lus, echecs, statut = [], set(), 0, "ok"
    for i, jour in enumerate(a_lire):
        if i:
            time.sleep(pause_s)
        try:
            m = sources.dukascopy_minutes(INTRADAY[nom]["identifiant"], jour)
            echecs = 0
            recent = jour >= maintenant.tz_convert(None).normalize() - pd.Timedelta(
                days=DELAI_JOUR_VIDE_J)
            if m.empty and recent:
                continue                     # peut-etre pas encore publie : redemande plus tard
            minutes.append(m)
            lus.add(f"{jour:%Y-%m-%d}")
        except sources.SourceError as exc:
            echecs += 1
            log.warning("%s %s : %s (%d/%d)", nom, f"{jour:%F}", exc, echecs, ECHECS_MAX)
            if echecs >= ECHECS_MAX:
                statut = "bride"
                break
            time.sleep(ATTENTE_BRIDE_S * echecs if pause_s else 0)
        if len(lus) and len(lus) % ECRIRE_TOUS_LES_N_JOURS == 0 and minutes:
            _integrer_minutes(nom, minutes)
            _noter_jours(nom, lus)
            minutes = []
    resume = _integrer_minutes(nom, minutes)
    _noter_jours(nom, lus)
    restants = len(jours_manquants(nom, maintenant))
    log.info("%s : %d jour(s) lu(s), %d restant(s), statut %s", nom, len(lus), restants, statut)
    _noter(nom, {"source": "dukascopy", "identifiant": INTRADAY[nom]["identifiant"],
                 "rattrapage": {"statut": statut, "jours_lus": len(lus),
                                "jours_restants": restants}, **resume})
    return {"statut": statut, "jours_lus": len(lus), "jours_restants": restants}


def _mois_chemin(nom: str):
    return collecte.DOSSIER / f"{nom}-mois.json"


def mois_manquants(nom: str, maintenant: pd.Timestamp) -> list[pd.Timestamp]:
    """Les mois UTC TERMINES jamais lus en bougies horaires, du plus recent au plus ancien."""
    p = _mois_chemin(nom)
    vus = set(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else set()
    fin = maintenant.tz_convert(None).normalize().replace(day=1) - pd.Timedelta(days=1)
    tous = pd.date_range(pd.Timestamp(INTRADAY[nom]["depuis"]).replace(day=1), fin, freq="MS")
    return [m for m in reversed(tous) if f"{m:%Y-%m}" not in vus]


def rattraper_mois(nom: str = "XAU_SPOT", limite: int | None = None,
                   maintenant: pd.Timestamp | None = None, pause_s: float | None = None) -> dict:
    """Le 1h et le 1d de l'histoire par les bougies horaires d'un mois entier (1 requete par
    mois). Le 5m reste au rattrapage jour par jour ; un jour deja lu a la minute garde ses
    bougies (elles priment), les heures d'un mois ne remplissent que les jours encore absents."""
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    pause_s = PAUSE_RATTRAPAGE_S if pause_s is None else pause_s
    a_lire = mois_manquants(nom, maintenant)[:limite]
    heures, lus, echecs, statut = [], [], 0, "ok"
    for i, mois in enumerate(a_lire):
        if i:
            time.sleep(pause_s)
        try:
            h = sources.dukascopy_heures_mois(INTRADAY[nom]["identifiant"], mois)
            echecs = 0
        except sources.SourceError as exc:
            echecs += 1
            log.warning("%s %s : %s (%d/%d)", nom, f"{mois:%Y-%m}", exc, echecs, ECHECS_MAX)
            if echecs >= ECHECS_MAX:
                statut = "bride"
                break
            time.sleep(ATTENTE_BRIDE_S * echecs if pause_s else 0)
            continue
        heures.append(h)
        lus.append(f"{mois:%Y-%m}")
    resume = {}
    pleins = [h for h in heures if not h.empty]
    if pleins:
        lot = pd.concat(pleins).sort_index()
        deja = _jours_vus(nom)
        lot = lot[~lot.index.strftime("%Y-%m-%d").isin(deja)]
        if not lot.empty:
            resume = {tf: integrer(nom, tf, agreger(lot, tf)) for tf in ("1h", "1d")}
    if lus:
        with verrou(f"mois_{nom}"):
            p = _mois_chemin(nom)
            tous = (set(json.loads(p.read_text(encoding="utf-8"))) if p.exists() else set())
            p.write_text(json.dumps(sorted(tous | set(lus))), encoding="utf-8")
    restants = len(mois_manquants(nom, maintenant))
    log.info("%s : %d mois lu(s), %d restant(s), statut %s", nom, len(lus), restants, statut)
    _noter(nom, {"rattrapage_mois": {"statut": statut, "mois_lus": len(lus),
                                     "mois_restants": restants}, **resume})
    return {"statut": statut, "mois_lus": len(lus), "mois_restants": restants}


def _heures_chemin(nom: str):
    return collecte.DOSSIER / f"{nom}-heures.json"


def direct_dukascopy(nom: str = "XAU_SPOT", maintenant: pd.Timestamp | None = None) -> dict:
    """Journee en cours : chaque heure UTC terminee, une fois, par ses ticks (bid) agreges a la
    minute -> 5m et 1h seulement (le 1d d'une journee en cours serait incomplet) ; plus un jour
    manquant par passage (la veille d'abord). Les bougies officielles du jour, une fois publiees,
    remplacent ces bougies tirees des ticks."""
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    resume = {"veille": rattraper_dukascopy(nom, limite=1, maintenant=maintenant, pause_s=0,
                                            depuis_j=7)}
    jour = maintenant.normalize()
    p = _heures_chemin(nom)
    vues = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    faites = set(vues.get("heures", [])) if vues.get("jour") == f"{jour:%Y-%m-%d}" else set()
    heures = [h for h in pd.date_range(jour, maintenant.floor("h") - pd.Timedelta(hours=1),
                                       freq="h") if f"{h:%H}" not in faites]
    minutes = []
    for i, h in enumerate(heures):
        if i:
            time.sleep(PAUSE_DUKASCOPY_S)    # un premier passage peut avoir 23 heures a lire
        try:
            t = sources.dukascopy_ticks(INTRADAY[nom]["identifiant"], h)
        except sources.SourceError as exc:
            log.warning("%s ticks %s : %s", nom, f"{h:%F %H}h", exc)
            break
        if t.empty:
            continue                          # pas encore publiee, ou heure sans echange
        g = t["bid"].resample("1min")
        minutes.append(pd.DataFrame({"open": g.first(), "high": g.max(), "low": g.min(),
                                     "close": g.last(),
                                     "volume": t["volume"].resample("1min").sum()})
                       .dropna(subset=["close"]))
        faites.add(f"{h:%H}")
    p.write_text(json.dumps({"jour": f"{jour:%Y-%m-%d}", "heures": sorted(faites)}),
                 encoding="utf-8")
    resume["jour"] = _integrer_minutes(nom, minutes, tfs=("5m", "1h"))
    _noter(nom, {"direct": resume})
    return resume


# Au-dela, le direct est EN RETARD (verifie par le passage quotidien, qui alerte une fois par
# jour au lieu d'un passage sur deux toutes les 5 min). Indices : week-end + ferie ; or : ferme
# du vendredi 21:00 au dimanche 22:00 UTC.
RETARD_MAX_H = {("SPX", "5m"): 96, ("NDX", "5m"): 96, ("XAU_SPOT", "1h"): 72}


def fraicheur(maintenant: pd.Timestamp | None = None) -> dict:
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    sortie = {}
    for (nom, tf), seuil in RETARD_MAX_H.items():
        df = _lire_brut(nom, tf)
        if df is None or df.empty:
            sortie[f"{nom}-{tf}"] = {"statut": "absent"}
            continue
        retard = (maintenant - (df.index.max() + PAS[tf])) / pd.Timedelta(hours=1)
        sortie[f"{nom}-{tf}"] = {"fin": df.index.max().isoformat(), "retard_h": round(retard, 1),
                                 "statut": "ok" if retard <= seuil else "en retard"}
    return sortie


def passage_direct(maintenant: pd.Timestamp | None = None) -> dict:
    """Un passage du direct : SPX et NDX (Yahoo), XAU_SPOT (Dukascopy, ticks du jour)."""
    sortie = {n: maj_yahoo(n, maintenant) for n, s in INTRADAY.items() if s["source"] == "yahoo"}
    try:
        sortie["XAU_SPOT"] = direct_dukascopy("XAU_SPOT", maintenant)
    except sources.SourceError as exc:
        log.error("XAU_SPOT direct : %s", exc)
        sortie["XAU_SPOT"] = {"statut": "echec", "erreur": str(exc)}
    return sortie
