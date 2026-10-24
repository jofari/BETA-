"""Les appels reseau des vrais marches, isoles : ce sont eux que les tests remplacent.

Chaque fonction rend la serie BRUTE de sa source, triee, sans doublon : en quotidien, indexee par
la date de l'observation (date locale de la seance, naive) ; en intraday, par l'heure UTC
d'OUVERTURE de la bougie (tz-aware). Elle ne decide rien : la collecte valide, compare a ce qui
est stocke et ecrit. Une reponse inattendue leve `SourceError` : on garde alors l'ancienne copie
plutot que d'ecrire un faux.
"""

from __future__ import annotations

import io
import logging
import subprocess
import lzma
import re
import struct
import urllib.request
import zipfile

import pandas as pd
import requests

log = logging.getLogger("beta.marches.sources")

TIMEOUT_S = 60
# fsapi.gold.org refuse le User-Agent de urllib (403) ; un navigateur passe.
UA_NAVIGATEUR = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                 "Chrome/130 Safari/537.36")
# Une PLAGE D'UN AN rend le fixing LBMA PM, jours ouvres seulement ; une plage de quelques
# jours rend un autre prix (spot, 7 jours sur 7). D'ou une requete par annee civile.
URL_WGC = "https://fsapi.gold.org/api/goldprice/v13/chart/price/usd/oz/{debut},{fin}"
# fredgraph.csv : en-tetes par defaut de urllib, comme `lake.maj` (certains User-Agent
# personnalises partent au trou noir, constate cote ARIT le 07/08).
URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
# Dukascopy : bougies BID a la minute d'une journee UTC, et ticks d'une heure. ⚠️ Le mois des
# URL commence a 00 (janvier). Bride si l'on enchaine : une requete a la fois, espacees, et un
# 503 se retente plus tard (constate le 20/10). Prix entiers : diviser par l'echelle.
URL_DUKASCOPY_JOUR = ("https://datafeed.dukascopy.com/datafeed/{instrument}/{a:04d}/{m:02d}/"
                      "{j:02d}/BID_candles_min_1.bi5")
# Bougies BID a l'HEURE d'un mois entier (secondes depuis le debut du mois) : 1 requete par mois
# au lieu d'une par jour. Sert au rattrapage du 1h/1d quand la bride rend le jour par jour
# interminable (21/10 : 429 sur notre IP, 0 jour lu en 2 h).
URL_DUKASCOPY_MOIS = ("https://datafeed.dukascopy.com/datafeed/{instrument}/{a:04d}/{m:02d}/"
                      "BID_candles_hour_1.bi5")
URL_DUKASCOPY_HEURE = ("https://datafeed.dukascopy.com/datafeed/{instrument}/{a:04d}/{m:02d}/"
                       "{j:02d}/{h:02d}h_ticks.bi5")
ECHELLE_DUKASCOPY = {"XAUUSD": 1000.0}
# Le paquet complet du H.10 publie par la Fed Board (SDMX, ~2 Mo zippe) : la SOURCE de DEXJPUS.
# Secours quand FRED est indisponible (maintenance du 21/10), et controle croise sinon.
URL_FRB_H10 = "https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&filetype=zip"
SERIES_FRB = {"DEXJPUS": "RXI_N.B.JA"}
COLONNES = ["open", "high", "low", "close", "volume"]
# DS1 (base souveraine, conteneur Timescale sur la meme machine) : lue par `docker exec psql`,
# en lecture seule, sans mot de passe dans BETA et sans pilote PostgreSQL dans son venv.
DS1_CONTENEUR = "ds1-db"
DS1_SQL = ("COPY (SELECT jour, ouverture, haut, bas, cloture, volume FROM bougies_1d "
           "WHERE source = '{source}' AND symbole = 'BTCUSD' ORDER BY jour) TO STDOUT WITH CSV HEADER")


class SourceError(RuntimeError):
    """Source injoignable, en maintenance, ou reponse qui n'est pas la serie demandee."""


def _ms(ts: pd.Timestamp) -> int:
    return int(ts.value // 1_000_000)


def _propre(s: pd.Series | pd.DataFrame, nom: str):
    if s.index.has_duplicates:
        raise SourceError(f"{nom} : dates en double")
    return s.sort_index()


# =========================================================================================
# Yahoo
# =========================================================================================

def yahoo_1d(ticker: str) -> pd.DataFrame:
    """Toute l'histoire quotidienne Yahoo : open, high, low, close, volume ; index = date de
    seance LOCALE (Yahoo horodate la bougie a minuit, heure de la bourse)."""
    import yfinance as yf  # import tardif : seule cette fonction en depend

    try:
        brut = yf.Ticker(ticker).history(period="max", interval="1d", auto_adjust=False,
                                         actions=False, timeout=TIMEOUT_S, raise_errors=True)
    except Exception as exc:  # yfinance leve des types varies selon la panne
        raise SourceError(f"Yahoo {ticker} : {type(exc).__name__}: {exc}") from exc
    if brut is None or brut.empty:
        raise SourceError(f"Yahoo {ticker} : reponse vide")
    df = brut.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].copy()
    df.index = brut.index.tz_localize(None).normalize()
    df.index.name = "date"
    return _propre(df.astype(float), f"Yahoo {ticker}")


def yahoo_intraday(ticker: str, intervalle: str, periode: str) -> pd.DataFrame:
    """Les bougies intraday Yahoo (5m : 60 jours au plus ; 1h : 730 jours), index = ouverture
    UTC. La derniere bougie peut etre EN COURS : la collecte la retire."""
    import yfinance as yf

    try:
        brut = yf.Ticker(ticker).history(period=periode, interval=intervalle, auto_adjust=False,
                                         actions=False, timeout=TIMEOUT_S, raise_errors=True)
    except Exception as exc:
        raise SourceError(f"Yahoo {ticker} {intervalle} : {type(exc).__name__}: {exc}") from exc
    if brut is None or brut.empty:
        raise SourceError(f"Yahoo {ticker} {intervalle} : reponse vide")
    df = brut.rename(columns=str.lower)[COLONNES].astype(float)
    df.index = brut.index.tz_convert("UTC")
    df.index.name = "date"
    return _propre(df.dropna(subset=["close"]), f"Yahoo {ticker} {intervalle}")


# =========================================================================================
# Dukascopy : or comptant intraday (BID)
# =========================================================================================

def _dukascopy(url: str) -> bytes | None:
    """Le contenu decompresse ; None si la source n'a rien (404, ou fichier vide)."""
    try:
        r = requests.get(url, timeout=TIMEOUT_S, headers={"User-Agent": UA_NAVIGATEUR})
    except requests.RequestException as exc:
        raise SourceError(f"{url} : {type(exc).__name__}: {exc}") from exc
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise SourceError(f"{url} : HTTP {r.status_code} (bride ? reessayer plus tard)")
    if not r.content:
        return None
    try:
        return lzma.decompress(r.content)
    except lzma.LZMAError as exc:
        raise SourceError(f"{url} : contenu illisible ({exc})") from exc


def _url_jour(gabarit: str, instrument: str, jour: pd.Timestamp, **k) -> str:
    return gabarit.format(instrument=instrument, a=jour.year, m=jour.month - 1, j=jour.day, **k)


def dukascopy_minutes(instrument: str, jour: pd.Timestamp) -> pd.DataFrame:
    """Les bougies BID a la minute du jour UTC `jour` ; les minutes sans echange (volume nul,
    remplies par Dukascopy : pause de 21:00 UTC, week-end) sont retirees."""
    brut = _dukascopy(_url_jour(URL_DUKASCOPY_JOUR, instrument, jour))
    if not brut:
        return pd.DataFrame(columns=COLONNES, index=pd.DatetimeIndex([], tz="UTC", name="date"))
    echelle = ECHELLE_DUKASCOPY[instrument]
    rec = list(struct.iter_unpack(">5if", brut))           # s, open, close, low, high, volume
    df = pd.DataFrame(rec, columns=["s", "open", "close", "low", "high", "volume"])
    df.index = pd.DatetimeIndex(pd.Timestamp(jour.date(), tz="UTC")
                                + pd.to_timedelta(df["s"], unit="s"), name="date")
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]] / echelle
    return _propre(df.loc[df["volume"] > 0, COLONNES].astype(float), f"Dukascopy {jour:%F}")


def dukascopy_heures_mois(instrument: str, mois: pd.Timestamp) -> pd.DataFrame:
    """Les bougies BID a l'heure du mois UTC de `mois` ; heures sans echange retirees."""
    debut = pd.Timestamp(year=mois.year, month=mois.month, day=1, tz="UTC")
    brut = _dukascopy(URL_DUKASCOPY_MOIS.format(instrument=instrument, a=debut.year,
                                                m=debut.month - 1))
    if not brut:
        return pd.DataFrame(columns=COLONNES, index=pd.DatetimeIndex([], tz="UTC", name="date"))
    echelle = ECHELLE_DUKASCOPY[instrument]
    rec = list(struct.iter_unpack(">5if", brut))           # s, open, close, low, high, volume
    df = pd.DataFrame(rec, columns=["s", "open", "close", "low", "high", "volume"])
    df.index = pd.DatetimeIndex(debut + pd.to_timedelta(df["s"], unit="s"), name="date")
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]] / echelle
    return _propre(df.loc[df["volume"] > 0, COLONNES].astype(float), f"Dukascopy {debut:%Y-%m}")


def dukascopy_ticks(instrument: str, heure: pd.Timestamp) -> pd.DataFrame:
    """Les ticks (bid, ask) de l'heure UTC `heure`, index = horodatage UTC du tick."""
    brut = _dukascopy(_url_jour(URL_DUKASCOPY_HEURE, instrument, heure, h=heure.hour))
    if not brut:
        return pd.DataFrame(columns=["bid", "ask", "volume"],
                            index=pd.DatetimeIndex([], tz="UTC", name="date"))
    echelle = ECHELLE_DUKASCOPY[instrument]
    rec = list(struct.iter_unpack(">3i2f", brut))          # ms, ask, bid, vol ask, vol bid
    df = pd.DataFrame(rec, columns=["ms", "ask", "bid", "v_ask", "v_bid"])
    df.index = pd.DatetimeIndex(heure.floor("h") + pd.to_timedelta(df["ms"], unit="ms"),
                                name="date")
    return pd.DataFrame({"bid": df["bid"] / echelle, "ask": df["ask"] / echelle,
                         "volume": df["v_bid"]}, index=df.index).sort_index()


# =========================================================================================
# World Gold Council : fixing LBMA PM
# =========================================================================================

def _json(url: str) -> dict:
    try:
        r = requests.get(url, timeout=TIMEOUT_S, headers={"User-Agent": UA_NAVIGATEUR})
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as exc:
        raise SourceError(f"{url} : {type(exc).__name__}: {exc}") from exc


def wgc_annee(annee: int) -> pd.Series:
    """Le fixing LBMA PM (USD/oz) de chaque jour ouvre de l'annee civile `annee`."""
    debut = pd.Timestamp(f"{annee}-01-01", tz="UTC")
    fin = pd.Timestamp(f"{annee}-12-31 23:59:59", tz="UTC")
    j = _json(URL_WGC.format(debut=_ms(debut), fin=_ms(fin)))
    points = (j.get("chartData") or {}).get("USD")
    if points is None:
        raise SourceError(f"WGC {annee} : pas de serie USD dans la reponse")
    s = pd.Series({pd.Timestamp(int(t), unit="ms").normalize(): float(v) for t, v in points},
                  dtype=float, name="close")
    s.index.name = "date"
    if len(s) and (s.index.dayofweek >= 5).any():
        raise SourceError(f"WGC {annee} : valeurs le week-end — ce n'est pas le fixing PM")
    if len(s) and ((s.index.year != annee).any() or (s <= 0).any()):
        raise SourceError(f"WGC {annee} : dates hors de l'annee ou prix <= 0")
    return _propre(s, f"WGC {annee}")


# =========================================================================================
# FRED
# =========================================================================================

def _texte(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_S) as reponse:
            return reponse.read().decode("utf-8")
    except OSError as exc:
        raise SourceError(f"{url} : {type(exc).__name__}: {exc}") from exc


def fred_csv(sid: str) -> pd.Series:
    """La serie FRED telle que publiee aujourd'hui ; les jours sans valeur (« . ») sont retires."""
    texte = _texte(URL_FRED.format(sid=sid))
    lignes = texte.strip().splitlines()
    if len(lignes) < 2 or lignes[0].split(",")[:2] != ["observation_date", sid]:
        entete = lignes[0][:80] if lignes else "vide"
        raise SourceError(f"FRED {sid} : reponse inattendue ({entete}) — maintenance ?")
    df = pd.read_csv(io.StringIO(texte), parse_dates=["observation_date"])
    s = pd.to_numeric(df[sid], errors="coerce")
    s.index = pd.DatetimeIndex(df["observation_date"]).normalize()
    s.index.name = "date"
    return _propre(s.dropna().rename("close").astype(float), f"FRED {sid}")


def frb_h10(sid: str) -> pd.Series:
    """La serie H.10 de la Fed Board qui correspond a `sid` (FRED) ; « ND » (ferie) retire."""
    try:
        r = requests.get(URL_FRB_H10, timeout=TIMEOUT_S, headers={"User-Agent": UA_NAVIGATEUR})
        r.raise_for_status()
        xml = zipfile.ZipFile(io.BytesIO(r.content)).read("H10_data.xml").decode("utf-8")
    except (requests.RequestException, zipfile.BadZipFile, KeyError) as exc:
        raise SourceError(f"FRB H.10 : {type(exc).__name__}: {exc}") from exc
    nom = SERIES_FRB[sid]
    m = re.search(rf'<kf:Series[^>]*SERIES_NAME="{re.escape(nom)}"[^>]*>(.*?)</kf:Series>',
                  xml, re.S)
    if m is None:
        raise SourceError(f"FRB H.10 : serie {nom} absente du paquet")
    obs = re.findall(r'OBS_STATUS="(\w+)" OBS_VALUE="([^"]*)" TIME_PERIOD="([\d-]+)"',
                     m.group(1))
    s = pd.Series({pd.Timestamp(d): float(v) for statut, v, d in obs if statut == "A"},
                  dtype=float, name="close")
    s.index.name = "date"
    if s.empty:
        raise SourceError(f"FRB H.10 : serie {nom} vide")
    return _propre(s, f"FRB H.10 {nom}")


def ds1_bougies_1d(source: str) -> pd.DataFrame:
    """Les bougies 1d BTC/USD d'une source de DS1 (jours UTC clos), colonnes OHLCV."""
    if source not in ("bitstamp", "coinbase"):
        raise SourceError(f"DS1 : source inconnue {source!r}")
    commande = ["docker", "exec", DS1_CONTENEUR, "sh", "-c",
                'psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-ds1}" -X -q -c "'
                + DS1_SQL.format(source=source) + '"']
    try:
        texte = subprocess.run(commande, capture_output=True, text=True, timeout=TIMEOUT_S,
                               check=True).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceError(f"DS1 bougies_1d {source} : {type(exc).__name__}: {exc}") from exc
    df = pd.read_csv(io.StringIO(texte), parse_dates=["jour"])
    if df.empty:
        raise SourceError(f"DS1 bougies_1d {source} : aucune bougie")
    df = df.rename(columns={"jour": "date", "ouverture": "open", "haut": "high", "bas": "low",
                            "cloture": "close"}).set_index("date")
    df.index = pd.DatetimeIndex(df.index).normalize()
    return _propre(df[COLONNES].astype(float), f"DS1 {source}")


def premieres_publications(sid: str) -> pd.Series:
    """Date de PREMIERE publication de chaque observation (ALFRED). Branche plus bas, une fois
    l'acces sans cle verifie (FRED/ALFRED en maintenance le 21/10 a 17:20 UTC)."""
    raise SourceError(f"ALFRED {sid} : acces non encore etabli")
