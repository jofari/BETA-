"""Mise a jour quotidienne du lake : BETA tient ses donnees a jour LUI-MEME.

Jusqu'au 03/10, le lake importait les 4 paires historiques, le funding des 6 et toute la
macro depuis les fichiers d'ARIT — qui ne bougent que quand ARIT les retelecharge. Constat
du 03/10 : tout etait fige au 05-09/09, soit un mois de marche absent de toute mesure.

BETA ne peut pas rafraichir ARIT (invariant n° 1). Il garde donc SA copie, dans `data/` :

1. `amorcer` : un feather absent de `data/raw/` est COPIE depuis ARIT (lecture seule). C'est
   gratuit et evite ~27 min de telechargement ; une fois la copie faite, ARIT ne sert plus.
2. freqtrade complete chaque feather a partir de sa derniere bougie (bougies 5m/1h/4h/1d,
   funding 8h, mark), en secondes. Il exclut lui-meme la bougie encore ouverte.
3. les 6 paires passent au lake par la meme porte qu'avant (`integrer_telechargement`).
4. le F&G et les series FRED sont retelecharges en entier dans `data/macro/` (quelques
   centaines de Ko) — ecriture atomique : un telechargement rate laisse l'ancien fichier.

`data/` reste jetable (invariant n° 8) : le supprimer, puis relancer, rejoue 1 a 4.
"""

from __future__ import annotations

import io
import json
import logging
import pathlib
import shutil
import urllib.request

import pandas as pd

from beta import config
from beta.lake import construction, telechargement, univers

log = logging.getLogger("beta.lake.maj")

# Les suffixes freqtrade d'une paire futures, hors bougies : funding 8h et prix mark.
SUFFIXES_ANNEXES = (config.FUNDING_SUFFIXE, "1h-mark")

# Series FRED lues par `lecture.macro_globales` : nom de fichier -> identifiant FRED.
# Memes fichiers, meme format (observation_date,<ID>) que ceux d'ARIT : la lecture ne change pas.
SERIES_FRED = {
    "vix.csv": "VIXCLS", "tips10y.csv": "DFII10", "breakeven10y.csv": "T10YIE",
    "hy_oas.csv": "BAMLH0A0HYM2", "ig_oas.csv": "BAMLC0A0CM", "dxy.csv": "DTWEXBGS",
    "spread_2s10s.csv": "T10Y2Y", "fedfunds.csv": "DFF", "BAA10Y.csv": "BAA10Y",
    "AAA10Y.csv": "AAA10Y",
}
URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
URL_FNG = "https://api.alternative.me/fng/?limit=0&format=json"
TIMEOUT_HTTP_S = 60

# Au-dela, une serie est EN RETARD et la mise a jour sort en erreur (le timer systemd passe
# en echec, ce qui se voit). Les bougies : la veille doit etre la. Le funding : 3 reglements
# par jour. FRED : publication J+1 ouvre, week-ends et feries -> 7 jours de marge.
RETARD_MAX = {"bougies_1d": pd.Timedelta(days=2), "funding": pd.Timedelta(hours=24),
              "fred": pd.Timedelta(days=7), "fred_hebdo": pd.Timedelta(days=16),
              "fng": pd.Timedelta(days=3)}
# DTWEXBGS (dollar large) est publie par la Fed une fois par SEMAINE (H.10, le lundi, pour la
# semaine d'avant) : 8-13 jours de retard sont normaux. Constate le 03/10 (derniere : 25/09).
FRED_HEBDO = {"dxy.csv"}


class MajError(RuntimeError):
    """Mise a jour impossible ou incomplete."""


# --- 1. amorcage depuis ARIT ---------------------------------------------------------------

def _feathers_arit(paire: univers.Paire) -> list[tuple[pathlib.Path, pathlib.Path]]:
    """(source ARIT, cible BETA) pour chaque feather de la paire."""
    couples = [(config.chemin_feather_arit(paire.slug, tf),
                config.chemin_feather_brut(paire.slug, tf)) for tf in univers.TIMEFRAMES]
    for suffixe in SUFFIXES_ANNEXES:
        nom = f"{paire.slug}-{suffixe}.feather"
        couples.append((config.ARIT_DATA / nom, config.BRUT / config.TRADING_MODE / nom))
    return couples


def amorcer(paires: tuple[univers.Paire, ...] = univers.PAIRES) -> list[str]:
    """Copie depuis ARIT chaque feather ABSENT de `data/raw/`. Ne remplace jamais une copie.

    Remplacer serait reculer : la copie de BETA est, par construction, au moins aussi
    recente que celle d'ARIT des qu'elle a ete completee une fois. Renvoie les noms copies.
    """
    config.preparer_dossiers()
    copies = []
    for paire in paires:
        for source, cible in _feathers_arit(paire):
            if cible.exists() or not source.exists():
                continue
            cible.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, cible)            # lecture seule cote ARIT
            copies.append(cible.name)
    if copies:
        log.info("amorcage depuis ARIT : %d feather(s) copie(s)", len(copies))
    return copies


# --- 4. macro --------------------------------------------------------------------------------

def _telecharger_texte(url: str) -> str:
    """L'appel reseau, isole : c'est lui que les tests remplacent.

    En-tetes par defaut : fredgraph.csv met certains User-Agent personnalises au trou noir
    (constate cote ARIT le 07/08, ReadTimeout reproductible).
    """
    with urllib.request.urlopen(url, timeout=TIMEOUT_HTTP_S) as reponse:
        return reponse.read().decode("utf-8")


def _ecrire_atomique(cible: pathlib.Path, contenu: str) -> None:
    cible.parent.mkdir(parents=True, exist_ok=True)
    tmp = cible.with_suffix(cible.suffix + ".partiel")
    tmp.write_text(contenu, encoding="utf-8")
    tmp.replace(cible)


def valider_fred(texte: str, sid: str) -> pd.DataFrame:
    """Le CSV doit etre celui de la serie demandee et non vide — sinon on garde l'ancien."""
    lignes = texte.strip().splitlines()
    if len(lignes) < 2 or lignes[0].split(",")[:2] != ["observation_date", sid]:
        raise MajError(f"FRED {sid} : reponse inattendue ({lignes[0][:80] if lignes else 'vide'})")
    df = pd.read_csv(io.StringIO(texte), parse_dates=["observation_date"])
    return df


def valider_fng(texte: str) -> list:
    donnees = json.loads(texte).get("data") or []
    if not donnees or "timestamp" not in donnees[0]:
        raise MajError("F&G : reponse sans donnees")
    return donnees


def maj_macro() -> dict[str, str]:
    """Retelecharge le F&G et les series FRED dans `data/macro/`. Retourne {nom: etat}.

    Une serie en echec n'annule pas les autres et laisse son ancien fichier en place.
    """
    etats: dict[str, str] = {}
    for fichier, sid in SERIES_FRED.items():
        try:
            texte = _telecharger_texte(URL_FRED.format(sid=sid))
            df = valider_fred(texte, sid)
            _ecrire_atomique(config.MACRO_GLOBAL / fichier, texte)
            etats[fichier] = "ok"
            log.info("FRED %-13s %5d lignes, derniere %s", sid, len(df),
                     df["observation_date"].max().date())
        except Exception as exc:                     # noqa: BLE001 - reseau : tout peut lever
            etats[fichier] = f"echec : {exc}"
            log.error("FRED %s : %s", sid, exc)
    try:
        texte = _telecharger_texte(URL_FNG)
        donnees = valider_fng(texte)
        _ecrire_atomique(config.MACRO / "fear_greed.json", texte)
        etats["fear_greed.json"] = "ok"
        log.info("F&G %d points", len(donnees))
    except Exception as exc:                         # noqa: BLE001
        etats["fear_greed.json"] = f"echec : {exc}"
        log.error("F&G : %s", exc)
    return etats


# --- fraicheur -------------------------------------------------------------------------------

def fraicheur(maintenant: pd.Timestamp | None = None) -> list[dict]:
    """Derniere date de chaque serie et retard. Une ligne par serie, `en_retard` en clair."""
    from beta.lake import lecture
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    lignes = []

    def noter(serie: str, genre: str, derniere) -> None:
        derniere = pd.Timestamp(derniere) if derniere is not None else None
        if derniere is not None and derniere.tz is None:
            derniere = derniere.tz_localize("UTC")
        retard = (maintenant - derniere) if derniere is not None else None
        # Une bougie 1d porte l'heure de son OUVERTURE : celle d'hier est la plus recente close.
        lignes.append({"serie": serie, "derniere": derniere, "retard": retard,
                       "en_retard": retard is None or retard > RETARD_MAX[genre]})

    for paire in univers.PAIRES:
        try:
            noter(f"{paire.base} 1d", "bougies_1d", lecture.load(paire.base, "1d")["date"].max())
        except Exception:                            # noqa: BLE001 - absente = en retard
            noter(f"{paire.base} 1d", "bougies_1d", None)
        try:
            noter(f"{paire.base} funding", "funding", lecture.funding(paire.base)["date"].max())
        except Exception:                            # noqa: BLE001
            noter(f"{paire.base} funding", "funding", None)
    for fichier in SERIES_FRED:
        chemin = config.chemin_macro(fichier, globale=True)
        derniere = None
        if chemin.exists():
            derniere = pd.read_csv(chemin, parse_dates=["observation_date"])[
                "observation_date"].max()
        noter(f"FRED {fichier[:-4]}", "fred_hebdo" if fichier in FRED_HEBDO else "fred",
              derniere)
    try:
        noter("F&G", "fng", lecture.fear_greed()["date"].max())
    except Exception:                                # noqa: BLE001
        noter("F&G", "fng", None)
    return lignes


# --- orchestration ---------------------------------------------------------------------------

def mettre_a_jour(reseau: bool = True) -> list[str]:
    """Amorce, complete, integre au lake, rafraichit la macro. Retourne la liste des problemes.

    `reseau=False` : amorcage + integration seulement (aucun appel exterieur).
    """
    problemes: list[str] = []
    amorcer()
    if reseau:
        # Une paire a la fois : en mode « completer », l'attente reseau est de quelques
        # secondes, mais chaque freqtrade charge tout l'historique 5m de sa paire. Six en
        # parallele = ~3,3 Go (mesure du 03/10, dont 1,9 Go de swap) sur un VPS partage.
        for paire in univers.PAIRES:
            for base, etat in telechargement.telecharger((paire,)).items():
                if etat != "ok":
                    problemes.append(f"{base} (telechargement) : {etat}")
    for paire in univers.PAIRES:
        for timeframe in univers.TIMEFRAMES:
            if not config.chemin_feather_brut(paire.slug, timeframe).exists():
                problemes.append(f"{paire.base} {timeframe} : feather absent de data/raw")
                continue
            try:
                construction.integrer_telechargement(paire, timeframe)
            except construction.LakeError as exc:
                problemes.append(f"{paire.base} {timeframe} (conversion) : {exc}")
    if reseau:
        for nom, etat in maj_macro().items():
            if etat != "ok":
                problemes.append(f"macro {nom} : {etat}")
    return problemes
