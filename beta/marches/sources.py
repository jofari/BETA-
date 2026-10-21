"""Les appels reseau des vrais marches, isoles : ce sont eux que les tests remplacent.

Chaque fonction rend la serie BRUTE de sa source, indexee par la date de l'observation (date
locale de la seance, naive), triee, sans doublon. Elle ne decide rien : la collecte valide,
compare a ce qui est stocke et ecrit. Une reponse inattendue leve `SourceError` : on garde
alors l'ancienne copie plutot que d'ecrire un faux.
"""

from __future__ import annotations

import io
import logging
import urllib.request

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


def premieres_publications(sid: str) -> pd.Series:
    """Date de PREMIERE publication de chaque observation (ALFRED). Branche plus bas, une fois
    l'acces sans cle verifie (FRED/ALFRED en maintenance le 21/10 a 17:20 UTC)."""
    raise SourceError(f"ALFRED {sid} : acces non encore etabli")
