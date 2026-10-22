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
   FRED rate est retente (30 s, 120 s, 300 s) ; un echec persistant n'est qu'un avertissement
   tant que la serie a au plus 5 jours ouvres de retard (incident du 22/10).

`data/` reste jetable (invariant n° 8) : le supprimer, puis relancer, rejoue 1 a 4.
"""

from __future__ import annotations

import io
import json
import logging
import pathlib
import shutil
import time
import urllib.request

import numpy as np

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
    # Lu par `lecture.nasdaq100` seulement (vote c6/c7 de la voie C2), jamais par
    # `macro_globales` : sinon il entrerait dans la jointure macro de TOUTES les candidates.
    "nasdaq100.csv": "NASDAQ100",
}
URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
URL_FNG = "https://api.alternative.me/fng/?limit=0&format=json"
TIMEOUT_HTTP_S = 60
# Nuit du 22/10 (00:23 UTC) : les 11 series ont recu une page HTML au lieu du CSV, incident
# FRED passager (la relance de 08:00 est passee). Les series ratees sont retentees ensemble,
# par tours, apres ces attentes : 7,5 min au pire, quel que soit le nombre de series en echec
# (beta-suivi demarre a 00:45 et attend la fin de beta-maj).
ATTENTES_FRED_S = (30, 120, 300)

# Au-dela, une serie est EN RETARD et la mise a jour sort en erreur (le timer systemd passe
# en echec, ce qui se voit). Les bougies : la veille doit etre la. Le funding : 3 reglements
# par jour. FRED quotidien : en JOURS OUVRES (lun-ven), voir `RETARD_MAX_FRED_JOURS_OUVRES`.
RETARD_MAX = {"bougies_1d": pd.Timedelta(days=2), "funding": pd.Timedelta(hours=24),
              "fred_hebdo": pd.Timedelta(days=16), "fng": pd.Timedelta(days=3)}
# Publication J+1 ouvre (VIXCLS : J+2) : au-dela de 5 jours ouvres sans nouvelle observation,
# la serie est en retard et la mise a jour sort en erreur. En dessous, un FRED rate n'est
# qu'un avertissement (22/10) : l'ancien fichier reste en place et suffit.
RETARD_MAX_FRED_JOURS_OUVRES = 5
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


def _attendre(secondes: float) -> None:
    """L'attente entre deux tours FRED, isolee : les tests la remplacent."""
    time.sleep(secondes)


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

    Une serie en echec n'annule pas les autres et laisse son ancien fichier en place : rien
    n'est ecrit tant que `valider_fred` n'a pas reconnu le CSV de la serie (jamais de HTML ni
    de fichier vide). Les series FRED ratees sont retentees apres chaque `ATTENTES_FRED_S`.
    """
    etats: dict[str, str] = {}
    a_faire = dict(SERIES_FRED)
    for tour, attente in enumerate((0, *ATTENTES_FRED_S)):
        if not a_faire:
            break
        if attente:
            log.warning("FRED : %d serie(s) en echec, nouvel essai dans %d s (essai %d/%d)",
                        len(a_faire), attente, tour + 1, len(ATTENTES_FRED_S) + 1)
            _attendre(attente)
        for fichier, sid in list(a_faire.items()):
            try:
                texte = _telecharger_texte(URL_FRED.format(sid=sid))
                df = valider_fred(texte, sid)
                _ecrire_atomique(config.MACRO_GLOBAL / fichier, texte)
                etats[fichier] = "ok"
                del a_faire[fichier]
                log.info("FRED %-13s %5d lignes, derniere %s", sid, len(df),
                         df["observation_date"].max().date())
            except Exception as exc:                 # noqa: BLE001 - reseau : tout peut lever
                etats[fichier] = f"echec : {exc}"
                log.warning("FRED %s : %s", sid, exc)
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
        if retard is None:
            en_retard = True
        elif genre == "fred":
            # Jours ouvres ecoules dans ]derniere, aujourd'hui] : vendredi -> lundi = 1.
            un_jour = np.timedelta64(1, "D")
            ouvres = np.busday_count(np.datetime64(derniere.date()) + un_jour,
                                     np.datetime64(maintenant.date()) + un_jour)
            en_retard = int(ouvres) > RETARD_MAX_FRED_JOURS_OUVRES
        else:
            en_retard = retard > RETARD_MAX[genre]
        lignes.append({"serie": serie, "derniere": derniere, "retard": retard,
                       "en_retard": en_retard})

    for paire in univers.PAIRES + univers.TRADFI:
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

def rafraichir_5m(paires: tuple[univers.Paire, ...] = univers.PAIRES) -> list[str]:
    """Les bougies 5 min seulement, completees puis integrees au lake. Retourne les problemes.

    Pour VC4 (10/10), qui decide aux ouvertures de Londres et de New York : la mise a jour
    quotidienne (00:21 UTC) ne suffit pas. Meme porte que `mettre_a_jour` (freqtrade complete
    a partir de la derniere bougie et exclut celle encore ouverte ; une paire a la fois pour la
    memoire), limitee au 5 min : ~1 min pour les 6 paires.
    """
    problemes: list[str] = []
    for paire in paires:
        for base, etat in telechargement.telecharger((paire,), timeframes=("5m",)).items():
            if etat != "ok":
                problemes.append(f"{base} 5m (telechargement) : {etat}")
        try:
            construction.integrer_telechargement(paire, "5m")
        except construction.LakeError as exc:
            problemes.append(f"{paire.base} 5m (conversion) : {exc}")
    return problemes


def mettre_a_jour_tradfi(reseau: bool = True) -> list[str]:
    """Les perpetuels TradFi (or, QQQ, SPY ; Jonas 20/10) : meme porte que les 6 paires.

    Appele APRES elles par `scripts/build_lake.py` : une panne ici ne retarde jamais les
    donnees des cryptos. Une paire a la fois, comme `mettre_a_jour` ; un echec n'arrete pas
    les autres. La boucle des 6 paires n'est pas touchee : elle tourne chaque nuit.
    """
    problemes: list[str] = []
    for paire in univers.TRADFI:
        if reseau:
            for base, etat in telechargement.telecharger((paire,)).items():
                if etat != "ok":
                    problemes.append(f"{base} (telechargement) : {etat}")
        for timeframe in univers.TIMEFRAMES:
            if not config.chemin_feather_brut(paire.slug, timeframe).exists():
                problemes.append(f"{paire.base} {timeframe} : feather absent de data/raw")
                continue
            try:
                construction.integrer_telechargement(paire, timeframe)
            except construction.LakeError as exc:
                problemes.append(f"{paire.base} {timeframe} (conversion) : {exc}")
    return problemes


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
            if etat == "ok":
                continue
            if nom in SERIES_FRED:
                # Pas un probleme a lui seul : l'ancien fichier reste. La sortie en erreur ne
                # vient que de `fraicheur` (plus de 5 jours ouvres de retard).
                log.warning("macro %s : %s — ancien fichier conserve", nom, etat)
            else:
                problemes.append(f"macro {nom} : {etat}")
    return problemes
