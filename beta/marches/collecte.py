"""Collecte des vrais marches : telecharger, valider, comparer a la copie, ecrire, decrire.

Une serie = `data/marches/<NOM>-1d.parquet` (colonne `date` = minuit UTC de la date de seance,
puis les colonnes de la source) + son entree dans `data/marches/etat.json` (couverture, trous,
empreinte, provenance). Trois regles :

1. une source en echec ne touche pas la copie : on garde l'ancienne et on le dit (sortie 1) ;
2. une REVISION du passe (valeur deja stockee qui change a la source) est comptee et
   journalisee dans `revisions.jsonl` : une mesure figee doit pouvoir dire sur quoi elle a
   tourne, et son empreinte de donnees change si la source reecrit l'histoire ;
3. la bougie d'une seance pas encore close n'est jamais ecrite (Yahoo sert un « close » qui bouge
   pendant la seance).

`data/` est jetable : `scripts/marches.py --construire` refait tout depuis les sources.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import time
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from beta import config
from beta.marches import sources
from beta.marches.series import SERIES, Serie, par_nom

log = logging.getLogger("beta.marches.collecte")

DOSSIER = config.DATA / "marches"
ETAT = DOSSIER / "etat.json"
REVISIONS = DOSSIER / "revisions.jsonl"

HEURE_CLOTURE_LOCALE = 17          # la bougie du jour D est close a D 17:00, heure de la bourse
SEUIL_TROU_SEANCES = 5             # « trou » rapporte : plus de 5 jours ouvres absents d'affilee
ANNEE_WGC_DEBUT = 1970
PAUSE_WGC_S = 1.0
# Au-dela, la serie est EN RETARD et la collecte sort en 1 (alerte Discord par le timer).
# Yahoo : 4 jours de fermeture au plus (Paques) ; WGC : Paques a Londres ; H.10 : hebdomadaire.
RETARD_MAX_J = {"yahoo": 5, "wgc": 6, "fred": 12, "ds1": 3}   # ds1 : lot DS1 de 00:15 UTC


def chemin(nom: str, tf: str = "1d") -> pathlib.Path:
    return DOSSIER / f"{nom}-{tf}.parquet"


def lire(nom: str, tf: str = "1d") -> pd.DataFrame:
    """La serie stockee, indexee par `date` (UTC, minuit de la date de seance)."""
    p = chemin(par_nom(nom).nom, tf)
    if not p.exists():
        raise FileNotFoundError(f"{nom} : pas encore collectee (python scripts/marches.py)")
    return pd.read_parquet(p).set_index("date").sort_index()


def etat() -> dict:
    return json.loads(ETAT.read_text(encoding="utf-8")) if ETAT.exists() else {}


# =========================================================================================
# Validation et description
# =========================================================================================

def seances_closes(df: pd.DataFrame, fuseau: str, maintenant: pd.Timestamp | None = None
                   ) -> pd.DataFrame:
    """Retire les bougies dont la seance n'est pas finie (date + 17:00 locale > maintenant)."""
    maintenant = (maintenant or pd.Timestamp.now(tz="UTC")).tz_convert(fuseau).tz_localize(None)
    cloture = df.index + pd.Timedelta(hours=HEURE_CLOTURE_LOCALE)
    return df[cloture <= maintenant]


def trous(dates: pd.DatetimeIndex, seuil: int = SEUIL_TROU_SEANCES) -> list[dict]:
    """Les intervalles entre deux observations ou manquent plus de `seuil` jours ouvres.

    Jours ouvres = lundi-vendredi, sans calendrier de feries : aucune fermeture reguliere de
    bourse n'en enleve plus de 4 d'affilee, donc au-dela de 5 c'est un trou de la serie.
    """
    jours = np.unique(pd.DatetimeIndex(dates).normalize().to_numpy(dtype="datetime64[D]"))
    if len(jours) < 2:
        return []
    manquants = np.busday_count(jours[:-1], jours[1:]) - 1
    return [{"apres": str(jours[i]), "avant": str(jours[i + 1]), "jours_ouvres": int(manquants[i])}
            for i in np.flatnonzero(manquants > seuil)]


def empreinte(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(df.index.as_unit("ns").asi8.tobytes())
    h.update(np.ascontiguousarray(df["close"].to_numpy(dtype=float)).tobytes())
    return h.hexdigest()[:16]


def couverture(df: pd.DataFrame) -> dict:
    t = trous(df.index)
    return {"debut": f"{df.index.min():%Y-%m-%d}", "fin": f"{df.index.max():%Y-%m-%d}",
            "n": int(len(df)), "trous_plus_de_5_seances": len(t), "trous_exemples": t[:5],
            "valeurs_non_positives": int((df["close"] <= 0).sum()),
            "empreinte": empreinte(df)}


def revisions(ancien: pd.Series, neuf: pd.Series, rel: float = 1e-9) -> dict:
    """Ce que la source a REECRIT : valeurs changees et dates disparues, sur le passe commun."""
    communes = ancien.index.intersection(neuf.index)
    a, n = ancien.reindex(communes), neuf.reindex(communes)
    changees = communes[(np.abs(n.to_numpy() / a.to_numpy() - 1.0) > rel)]
    disparues = ancien.index[(ancien.index <= neuf.index.max())].difference(neuf.index)
    return {"valeurs_changees": int(len(changees)), "dates_disparues": int(len(disparues)),
            "exemples": [{"date": f"{d:%Y-%m-%d}", "avant": float(a[d]), "apres": float(n[d])}
                         for d in changees[:10]]}


# =========================================================================================
# Telechargement par source
# =========================================================================================

def _annees_wgc(construire: bool, aujourdhui: pd.Timestamp) -> list[int]:
    if construire:
        return list(range(ANNEE_WGC_DEBUT, aujourdhui.year + 1))
    # L'annee en cours, et la precedente pendant les premieres semaines (fin d'annee tardive).
    return [aujourdhui.year - 1, aujourdhui.year] if aujourdhui.month == 1 else [aujourdhui.year]


def telecharger(serie: Serie, construire: bool = False,
                maintenant: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict]:
    """La serie fraiche a la source (index = date naive de seance) et des notes de collecte."""
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    notes: dict = {}
    if serie.source == "yahoo":
        df = sources.yahoo_1d(serie.identifiant)
        brut = len(df)
        df = seances_closes(df.dropna(subset=["close"]), serie.fuseau, maintenant)
        notes["bougies_retirees"] = int(brut - len(df))
    elif serie.source == "wgc":
        morceaux = []
        for i, annee in enumerate(_annees_wgc(construire, maintenant)):
            if i:
                time.sleep(PAUSE_WGC_S)
            morceaux.append(sources.wgc_annee(annee))
        df = pd.concat(morceaux).to_frame("close")
        notes["annees"] = [int(x) for x in sorted(set(df.index.year))]
    elif serie.source == "fred":
        try:
            df = sources.fred_csv(serie.identifiant).to_frame("close")
            notes["source_effective"] = "fred"
        except sources.SourceError as exc:
            if serie.identifiant not in sources.SERIES_FRB:
                raise
            # La meme serie chez son editeur (Fed Board, H.10) : FRED en maintenance le 21/10.
            log.warning("%s : %s — valeurs prises au paquet H.10 de la Fed Board", serie.nom, exc)
            df = sources.frb_h10(serie.identifiant).to_frame("close")
            notes["source_effective"] = f"frb_h10 (FRED indisponible : {exc})"
        if serie.publication == "alfred":
            try:
                pub = sources.premieres_publications(serie.identifiant)
                df["publie_le"] = pub.reindex(df.index)
                notes["alfred"] = {"observations_datees": int(df["publie_le"].notna().sum())}
            except sources.SourceError as exc:
                df["publie_le"] = pd.NaT
                notes["alfred"] = {"indisponible": str(exc)}
                log.warning("%s : %s", serie.nom, exc)
    elif serie.source == "ds1":
        df = sources.ds1_bougies_1d(serie.identifiant)
    else:
        raise ValueError(f"source inconnue : {serie.source}")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise sources.SourceError(f"{serie.nom} : dates en double ou non triees")
    if df.empty:
        raise sources.SourceError(f"{serie.nom} : aucune observation")
    return df, notes


# =========================================================================================
# Mise a jour
# =========================================================================================

def _ecrire(df: pd.DataFrame, cible: pathlib.Path) -> None:
    cible.parent.mkdir(parents=True, exist_ok=True)
    sortie = df.copy()
    sortie.index = pd.DatetimeIndex(sortie.index).tz_localize("UTC").as_unit("ms")
    sortie.index.name = "date"
    tmp = cible.with_suffix(".partiel")
    sortie.reset_index().to_parquet(tmp, index=False)
    tmp.replace(cible)


def _stocke(serie: Serie) -> pd.DataFrame | None:
    p = chemin(serie.nom)
    if not p.exists():
        return None
    df = pd.read_parquet(p).set_index("date").sort_index()
    df.index = df.index.tz_convert(None)
    return df


def mettre_a_jour(serie: Serie, construire: bool = False,
                  maintenant: pd.Timestamp | None = None) -> dict:
    """Une serie : source -> validation -> fusion -> revisions -> ecriture. Rend son etat."""
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    ancien = _stocke(serie)
    construire = construire or ancien is None          # rien en stock : tout l'historique
    base = {"source": serie.source, "identifiant": serie.identifiant,
            "description": serie.description, "tente_le": maintenant.isoformat(timespec="seconds")}
    try:
        neuf, notes = telecharger(serie, construire, maintenant)
    except sources.SourceError as exc:
        log.error("%s : %s — copie existante gardee", serie.nom, exc)
        ancien_etat = etat().get(serie.nom, {})
        return {**ancien_etat, **base, "statut": "echec", "erreur": str(exc)}
    if ancien is not None and serie.source == "wgc" and not construire:
        garde = ancien[~ancien.index.year.isin(notes["annees"])]
        neuf = pd.concat([garde, neuf]).sort_index()
    rev = (revisions(ancien["close"], neuf["close"]) if ancien is not None
           else {"valeurs_changees": 0, "dates_disparues": 0, "exemples": []})
    _ecrire(neuf, chemin(serie.nom))
    if rev["valeurs_changees"] or rev["dates_disparues"]:
        log.warning("%s : la source a reecrit le passe (%d valeur(s), %d date(s) disparue(s))",
                    serie.nom, rev["valeurs_changees"], rev["dates_disparues"])
        REVISIONS.parent.mkdir(parents=True, exist_ok=True)
        with REVISIONS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"serie": serie.nom, "le": base["tente_le"], **rev},
                               ensure_ascii=False) + "\n")
    retard = (maintenant.tz_convert(None).normalize() - neuf.index.max()).days
    statut = "en retard" if retard > RETARD_MAX_J[serie.source] else "ok"
    return {**base, **couverture(neuf), **notes, "statut": statut, "retard_j": int(retard),
            "revisions": rev, "maj_le": datetime.now(UTC).isoformat(timespec="seconds")}


def tout_mettre_a_jour(noms: list[str] | None = None, construire: bool = False) -> dict:
    """Les series demandees (toutes par defaut) ; une panne n'arrete pas les autres."""
    courant = etat()
    for serie in (SERIES if not noms else [par_nom(n) for n in noms]):
        courant[serie.nom] = mettre_a_jour(serie, construire)
        log.info("%-9s %-9s %s -> %s  n=%s  trous>5=%s", serie.nom, courant[serie.nom]["statut"],
                 courant[serie.nom].get("debut"), courant[serie.nom].get("fin"),
                 courant[serie.nom].get("n"), courant[serie.nom].get("trous_plus_de_5_seances"))
    ETAT.parent.mkdir(parents=True, exist_ok=True)
    tmp = ETAT.with_suffix(".partiel")
    tmp.write_text(json.dumps(courant, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ETAT)
    return courant
