"""Historique public de Binance (data.binance.vision) : ce que l'API REST ne garde pas.

Ajoute le 10/10 (feu vert de Jonas, propose le 08/10) pour preparer la strategie de
microstructure : une idee qui tient sur ces series se backteste DES MAINTENANT, sans
attendre que DS1 ait accumule des mois de carnet.

Trois jeux, perpetuels USDT-M, les 6 paires de `univers.PAIRES`, publies jour par jour (J-1) :

- `metrics`   (5 min, BTC depuis 09/2020, les autres depuis 12/2021) : open interest
  (`sum_open_interest` en pieces, `sum_open_interest_value` en USDT), ratios long/short
  des top traders par comptes (`count_toptrader_long_short_ratio`) et par positions
  (`sum_toptrader_long_short_ratio`), ratio global par comptes (`count_long_short_ratio`),
  ratio volume taker acheteur/vendeur (`sum_taker_long_short_vol_ratio`). Noms d'origine
  gardes tels quels : les traduire serait inventer une semantique que Binance ne documente pas.
- `bookDepth` (30 s, depuis 01/2023) : profondeur CUMULEE a +-0,2/1/2/3/4/5 % du milieu,
  une ligne par instantane : `qte_bid_100` = pieces cote acheteur jusqu'a -1 %,
  `usd_ask_020` = USDT cote vendeur jusqu'a +0,2 % (code = pourcentage x 100).
- `aggTrades` (a la ms, depuis 12/2019) : AGREGE A LA MINUTE au telechargement, sinon des
  dizaines de Go. Par minute : ouverture/haut/bas/cloture, quantites et USDT achetes
  (taker acheteur) et vendus (taker vendeur), nombre d'aggTrades et de transactions,
  plus gros aggTrade en USDT. Le detail a la ms est PERDU ; le refaire = retelecharger.

Ce qui n'existe qu'a DS1 (carnet L20 a 500 ms, liquidations) n'est pas ici.

Trous (invariant n° 3) : Binance saute des jours (08/10/2026 absent pour bookDepth) et en
publie de partiels (07/10/2026 : 3 h sur 24). La liste des fichiers publies (S3) fait foi :
un jour non publie entre le premier et le dernier est un TROU (couverture 0), un jour publie
est mesure :
- metrics, bookDepth : part des creneaux de `pas_audit_s` ou il y a au moins une ligne ;
- aggTrades : continuite de `agg_trade_id`, consecutif sur TOUT l'historique. Le temps ne
  marche pas ici : XRP en 01/2020 a 18 % de tranches de 10 min sans aucune transaction
  (marche mince, pas donnee perdue). Couverture de la serie = transactions presentes /
  (dernier id - premier id + 1) : un jour absent ou un fichier tronque s'y voit au trade pres.
Le resume par serie va dans `data/vision/etat.duckdb`, table `series`, colonne `suspect`.

Un jour publie apres coup est rattrape au passage suivant : la liste est relue a chaque fois.
`data/` reste jetable (invariant n° 8) : le supprimer puis relancer refait tout (~2 h).
"""

from __future__ import annotations

import collections
import concurrent.futures
import datetime as dt
import hashlib
import io
import logging
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import NamedTuple

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv

from beta import config
from beta.lake import univers

log = logging.getLogger("beta.lake.vision")

URL_LISTE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix={prefixe}&marker={marqueur}"
URL_FICHIER = "https://data.binance.vision/{cle}"
PREFIXE = "data/futures/um/daily/{jeu}/{symbole}/"
TIMEOUT_HTTP_S = 120
ESSAIS_HTTP = 3
TELECHARGEMENTS_SIMULTANES = 4      # ~11 Mo/s mesures le 10/10 depuis le VPS, par flux
# Binance publie J-1 dans la journee, mais saute parfois quelques jours avant de rattraper.
RETARD_MAX_J = 4


class VisionError(RuntimeError):
    """Fichier corrompu, illisible ou liste impossible a lire."""


class Jeu(NamedTuple):
    nom: str
    pas_audit_s: int        # creneau de la mesure de couverture
    colonnes: tuple[str, ...] | None   # noms a imposer quand le CSV n'a pas d'en-tete


COLONNES_AGGTRADES = ("agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id",
                      "transact_time", "is_buyer_maker")

# aggTrades : creneau de 10 min. Une minute sans transaction existe sur une alt en 2020 ;
# dix minutes sans rien sur un perpetuel, c'est un fichier tronque.
JEUX = {
    "metrics": Jeu("metrics", 300, None),
    "bookDepth": Jeu("bookDepth", 60, None),
    "aggTrades": Jeu("aggTrades", 600, COLONNES_AGGTRADES),
}

SCHEMA_ETAT = """
CREATE TABLE IF NOT EXISTS jours (
    jeu VARCHAR NOT NULL, base VARCHAR NOT NULL, jour DATE NOT NULL,
    lignes BIGINT, couverture_pct DOUBLE, sha256 VARCHAR,
    id_min BIGINT, id_max BIGINT, n_brut BIGINT,      -- aggTrades seulement
    maj TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (jeu, base, jour));
CREATE TABLE IF NOT EXISTS series (
    jeu VARCHAR NOT NULL, base VARCHAR NOT NULL, debut DATE, fin DATE,
    jours_attendus BIGINT, jours_absents BIGINT, plus_grand_trou_j BIGINT,
    lignes BIGINT, couverture_pct DOUBLE, suspect BOOLEAN, maj TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (jeu, base));
"""


def symbole(base: str) -> str:
    return f"{base}{univers.QUOTE}"


# --- reseau ----------------------------------------------------------------------------------

def _http(url: str) -> bytes:
    """L'appel reseau, isole : c'est lui que les tests remplacent. 404 = pas de nouvel essai."""
    for essai in range(1, ESSAIS_HTTP + 1):
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT_HTTP_S) as reponse:
                return reponse.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404 or essai == ESSAIS_HTTP:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if essai == ESSAIS_HTTP:
                raise
        time.sleep(5 * essai)
    raise AssertionError("inatteignable")


def lister(jeu: str, base: str) -> dict[dt.date, str]:
    """Les jours PUBLIES d'un jeu pour une paire : {jour: cle du .zip}. Pagine par 1000."""
    prefixe = PREFIXE.format(jeu=jeu, symbole=symbole(base))
    motif = re.compile(r"-(\d{4}-\d{2}-\d{2})\.zip$")
    jours: dict[dt.date, str] = {}
    marqueur = ""
    while True:
        xml = _http(URL_LISTE.format(prefixe=urllib.parse.quote(prefixe),
                                     marqueur=urllib.parse.quote(marqueur)))
        try:
            racine = ET.fromstring(xml)
        except ET.ParseError as exc:
            raise VisionError(f"liste {prefixe} illisible : {exc}") from exc
        ns = racine.tag[:racine.tag.index("}") + 1] if racine.tag.startswith("{") else ""
        cles = [c.text or "" for c in racine.iter(f"{ns}Key")]
        for cle in cles:
            m = motif.search(cle)
            if m:
                jours[dt.date.fromisoformat(m.group(1))] = cle
        tronquee = (racine.findtext(f"{ns}IsTruncated") or "").lower() == "true"
        if not tronquee or not cles:
            return jours
        marqueur = cles[-1]


def telecharger(cle: str) -> tuple[bytes, str]:
    """Le .zip et son empreinte, VERIFIEE contre le .CHECKSUM publie a cote."""
    contenu = _http(URL_FICHIER.format(cle=cle))
    attendu = _http(URL_FICHIER.format(cle=cle + ".CHECKSUM")).decode().split()[0].lower()
    reel = hashlib.sha256(contenu).hexdigest()
    if reel != attendu:
        raise VisionError(f"{cle} : sha256 {reel[:12]} != publie {attendu[:12]}")
    return contenu, reel


# --- lecture et transformation d'un jour ----------------------------------------------------

def _lire_csv(contenu: bytes, jeu: Jeu) -> pa.Table:
    """Le CSV du .zip. Les vieux aggTrades (avant 2022) n'ont PAS d'en-tete : on le detecte."""
    with zipfile.ZipFile(io.BytesIO(contenu)) as z:
        noms = [n for n in z.namelist() if n.endswith(".csv")]
        if len(noms) != 1:
            raise VisionError(f"zip inattendu : {z.namelist()}")
        with z.open(noms[0]) as f:
            premiere = f.readline().decode("utf-8", "replace")
        sans_entete = premiere[:1].isdigit()
        if sans_entete and jeu.colonnes is None:
            raise VisionError(f"{jeu.nom} : CSV sans en-tete ({premiere[:60]!r})")
        options = pacsv.ReadOptions(column_names=list(jeu.colonnes) if sans_entete else None)
        with z.open(noms[0]) as f:
            return pacsv.read_csv(f, read_options=options)


def _agreger_aggtrades(table: pa.Table) -> pd.DataFrame:
    """aggTrades -> une ligne par minute. Ordre intra-minute = agg_trade_id (monotone)."""
    if table.num_rows == 0:
        return pd.DataFrame()
    t_max = pc.max(table["transact_time"]).as_py()
    par_seconde = 1_000_000 if t_max > 10**14 else 1_000      # ms, ou us (spot depuis 2025)
    with duckdb.connect() as conn:
        conn.register("t", table)
        df = conn.execute(f"""
            SELECT (transact_time // {par_seconde * 60}) * 60 AS s,
                   arg_min(price, agg_trade_id) AS ouverture, max(price) AS haut,
                   min(price) AS bas, arg_max(price, agg_trade_id) AS cloture,
                   coalesce(sum(quantity) FILTER (WHERE NOT is_buyer_maker), 0) AS qte_achat,
                   coalesce(sum(quantity) FILTER (WHERE is_buyer_maker), 0) AS qte_vente,
                   coalesce(sum(price * quantity) FILTER (WHERE NOT is_buyer_maker), 0)
                       AS usd_achat,
                   coalesce(sum(price * quantity) FILTER (WHERE is_buyer_maker), 0)
                       AS usd_vente,
                   count(*) AS n_agg,
                   sum(last_trade_id - first_trade_id + 1)::BIGINT AS n_trades,
                   max(price * quantity) AS usd_max_agg
            FROM t GROUP BY s ORDER BY s""").df()
    df.insert(0, "date", pd.to_datetime(df.pop("s"), unit="s", utc=True))
    return df


def _code_niveau(pct: float) -> str:
    return f"{'bid' if pct < 0 else 'ask'}_{round(abs(pct) * 100):03d}"


def _pivoter_bookdepth(table: pa.Table) -> pd.DataFrame:
    """Une ligne par instantane, deux colonnes (pieces, USDT) par niveau."""
    df = table.to_pandas()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["timestamp"], utc=True)
    large = df.pivot_table(index="date", columns="percentage", values=["depth", "notional"],
                           aggfunc="last")
    large.columns = [f"{'qte' if v == 'depth' else 'usd'}_{_code_niveau(p)}"
                     for v, p in large.columns]
    return large.sort_index(axis=1).reset_index()


def _nettoyer_metrics(table: pa.Table) -> pd.DataFrame:
    df = table.to_pandas()
    if df.empty:
        return df
    df.insert(0, "date", pd.to_datetime(df.pop("create_time"), utc=True))
    return (df.drop(columns=["symbol"], errors="ignore")
              .sort_values("date").drop_duplicates("date", keep="last"))


TRANSFORMATIONS = {"aggTrades": _agreger_aggtrades, "bookDepth": _pivoter_bookdepth,
                   "metrics": _nettoyer_metrics}


class Jour(NamedTuple):
    df: pd.DataFrame
    couverture_pct: float
    id_min: int | None = None        # aggTrades : bornes et nombre d'aggTrades du fichier
    id_max: int | None = None
    n_brut: int | None = None


def transformer(jeu: str, contenu: bytes, jour: dt.date) -> Jour:
    """Le .zip d'un jour -> lignes du jour et couverture en %. Hors du jour = retire."""
    table = _lire_csv(contenu, JEUX[jeu])
    df = TRANSFORMATIONS[jeu](table)
    if df.empty:
        return Jour(df, 0.0)
    debut = pd.Timestamp(jour, tz="UTC")
    df = df[(df["date"] >= debut) & (df["date"] < debut + pd.Timedelta(days=1))]
    df = df.reset_index(drop=True)
    if jeu == "aggTrades":
        ids = pc.min_max(table["agg_trade_id"]).as_py()
        n = table.num_rows
        return Jour(df, round(100.0 * n / (ids["max"] - ids["min"] + 1), 3),
                    ids["min"], ids["max"], n)
    pas = JEUX[jeu].pas_audit_s
    creneaux = df["date"].dt.floor(f"{pas}s").nunique()
    return Jour(df, round(100.0 * creneaux / (86_400 // pas), 3))


# --- stockage --------------------------------------------------------------------------------

def _etat():
    config.VISION.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(config.VISION_ETAT))
    conn.execute("SET TimeZone='UTC'")
    conn.execute(SCHEMA_ETAT)
    return conn


def _ecrire_mois(jeu: str, base: str, mois: str, morceaux: list[pd.DataFrame]) -> None:
    """Fusionne des jours dans le parquet du mois (petit : on peut le relire en entier)."""
    cible = config.chemin_vision(jeu, base, mois)
    cible.parent.mkdir(parents=True, exist_ok=True)
    if cible.exists():
        morceaux = [pd.read_parquet(cible), *morceaux]
    df = (pd.concat([m for m in morceaux if not m.empty], ignore_index=True)
            .drop_duplicates("date", keep="last").sort_values("date"))
    tmp = cible.with_suffix(".partiel")
    df.to_parquet(tmp, index=False)
    tmp.replace(cible)


def _plus_long_trou(jours_ok: list[dt.date]) -> int:
    return max([0, *(((b - a).days - 1) for a, b in zip(jours_ok, jours_ok[1:]))])


def resumer(jeu: str, base: str, publies: dict[dt.date, str]) -> dict:
    """Couverture de la serie : un jour non publie entre le premier et le dernier = trou."""
    with _etat() as conn:
        lignes = conn.execute("SELECT jour, lignes, couverture_pct, id_min, id_max, n_brut"
                              " FROM jours"
                              " WHERE jeu = ? AND base = ? ORDER BY jour",
                              [jeu, base]).fetchall()
        if not lignes:
            return {}
        jours_ok = [ligne[0] for ligne in lignes]
        debut = min(min(publies, default=jours_ok[0]), jours_ok[0])
        fin = jours_ok[-1]
        attendus = (fin - debut).days + 1
        if jeu == "aggTrades":
            # au trade pres : un jour absent ou tronque laisse des ids sans transaction
            couverture = round(100.0 * sum(ligne[5] for ligne in lignes)
                               / (lignes[-1][4] - lignes[0][3] + 1), 3)
        else:
            couverture = round(sum(ligne[2] for ligne in lignes) / attendus, 3)
        resume = {"jeu": jeu, "base": base, "debut": debut, "fin": fin,
                  "jours_attendus": attendus, "jours_absents": attendus - len(jours_ok),
                  "plus_grand_trou_j": _plus_long_trou([debut, *jours_ok]),
                  "lignes": sum(ligne[1] for ligne in lignes), "couverture_pct": couverture,
                  "suspect": bool(couverture < 100.0 - config.TROUS_PCT_ALERTE)}
        conn.execute("DELETE FROM series WHERE jeu = ? AND base = ?", [jeu, base])
        conn.execute("INSERT INTO series VALUES (?,?,?,?,?,?,?,?,?,?, now())",
                     list(resume.values()))
    return resume


# --- orchestration ---------------------------------------------------------------------------

def mettre_a_jour_serie(jeu: str, base: str, limite_jours: int | None = None) -> list[str]:
    """Telecharge les jours publies absents de l'etat. Retourne les problemes rencontres."""
    publies = lister(jeu, base)
    with _etat() as conn:
        deja = {r[0] for r in conn.execute("SELECT jour FROM jours WHERE jeu = ? AND base = ?",
                                           [jeu, base]).fetchall()}
    a_faire = sorted(j for j in publies if j not in deja)[:limite_jours]
    problemes: list[str] = []
    if a_faire:
        log.info("%s %s : %d jour(s) a telecharger (%s -> %s)", jeu, base, len(a_faire),
                 a_faire[0], a_faire[-1])

    en_attente: dict[str, list[tuple[dt.date, Jour, str]]] = {}

    def vider(mois: str) -> None:
        jours = en_attente.pop(mois)
        _ecrire_mois(jeu, base, mois, [j.df for _, j, _ in jours])
        with _etat() as conn:              # l'etat APRES le parquet : un arret au milieu
            for jour, j, sha in jours:     # fait retelecharger, jamais l'inverse
                conn.execute("INSERT OR REPLACE INTO jours VALUES (?,?,?,?,?,?,?,?,?, now())",
                             [jeu, base, jour, len(j.df), j.couverture_pct, sha,
                              j.id_min, j.id_max, j.n_brut])

    # Fenetre bornee : jamais plus de N .zip en memoire (un jour BTC agite = ~70 Mo).
    with concurrent.futures.ThreadPoolExecutor(TELECHARGEMENTS_SIMULTANES) as pool:
        file: collections.deque = collections.deque()
        restants = iter(a_faire)
        for jour in restants:
            file.append((jour, pool.submit(telecharger, publies[jour])))
            if len(file) >= TELECHARGEMENTS_SIMULTANES:
                break
        while file:
            jour, futur = file.popleft()
            prochain = next(restants, None)
            if prochain is not None:
                file.append((prochain, pool.submit(telecharger, publies[prochain])))
            mois = jour.strftime("%Y-%m")
            for autre in [m for m in en_attente if m != mois]:
                vider(autre)
            try:
                contenu, sha = futur.result()
                resultat = transformer(jeu, contenu, jour)
            except Exception as exc:               # noqa: BLE001 - un jour rate n'arrete pas
                problemes.append(f"{jeu} {base} {jour} : {exc}")   # les autres ; il sera
                log.error("%s %s %s : %s", jeu, base, jour, exc)   # retente au passage suivant
                continue
            en_attente.setdefault(mois, []).append((jour, resultat, sha))
        for mois in list(en_attente):
            vider(mois)

    resume = resumer(jeu, base, publies)
    if not resume:
        problemes.append(f"{jeu} {base} : aucun jour en stock")
        return problemes
    retard = (dt.datetime.now(dt.timezone.utc).date() - resume["fin"]).days
    if retard > RETARD_MAX_J and limite_jours is None:
        problemes.append(f"{jeu} {base} en retard : dernier jour {resume['fin']} ({retard} j)")
    if resume["suspect"]:
        log.warning("%s %s : couverture %.2f %% (%d jours absents, plus long trou %d j)"
                    " - SUSPECT", jeu, base, resume["couverture_pct"],
                    resume["jours_absents"], resume["plus_grand_trou_j"])
    return problemes


def mettre_a_jour(jeux: tuple[str, ...] = tuple(JEUX),
                  paires: tuple[univers.Paire, ...] = univers.PAIRES,
                  limite_jours: int | None = None) -> list[str]:
    """Tous les jeux, toutes les paires. Une serie en panne n'arrete pas les autres."""
    problemes: list[str] = []
    for jeu in jeux:
        for paire in paires:
            try:
                problemes += mettre_a_jour_serie(jeu, paire.base, limite_jours)
            except Exception as exc:               # noqa: BLE001 - reseau : tout peut lever
                problemes.append(f"{jeu} {paire.base} : {exc}")
                log.error("%s %s : %s", jeu, paire.base, exc)
    return problemes


def etat() -> pd.DataFrame:
    """Une ligne par (jeu, paire). La colonne `suspect` est celle a regarder en premier."""
    if not config.VISION_ETAT.exists():
        return pd.DataFrame()
    with _etat() as conn:
        return conn.execute("SELECT * EXCLUDE (maj) FROM series ORDER BY jeu, base").df()
