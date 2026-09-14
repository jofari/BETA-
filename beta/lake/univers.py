"""L'univers de BETA : les paires, les indices, les timeframes, et rien d'autre.

Source de verite UNIQUE. Toute liste de paires ecrite ailleurs dans le projet est un bug :
c'est exactement le genre de duplication qui fait tourner un backtest sur 4 paires en
croyant en couvrir 6.

Pourquoi ces 6 paires (decision de Jonas, 2026-08-18) :
- BTC / ETH / SOL / BNB sont les 4 paires historiques d'ARIT. Elles sont DEJA telechargees
  dans `ARIT2.0/user_data/data/binance/futures/` : on les IMPORTE, on ne les retelecharge
  jamais (27 min pour 4 paires, pour un resultat identique au bit pres).
- LINK et XRP sont ajoutees pour elargir l'univers. Le critere n'est pas la popularite mais
  l'ANCIENNETE du contrat perpetuel : ce sont les deux plus anciens apres les majors
  (~janvier 2020). Le goulot du projet est le nombre de signaux, donc c'est l'historique qui
  commande — passer de 4 a 6 paires ne vaut que si les 2 nouvelles apportent des annees, pas
  seulement des lignes.

Les 5 INDICES (spike du 2026-09-14) sont une structure PARALLELE, pas une extension de
`Paire` : source differente (yfinance, pas Binance), un seul timeframe (1d), pas de
funding ni de Fear & Greed. Ils elargissent l'univers en classes d'actifs la ou les paires
l'elargissent en nombre ; le calcul qui justifie BETA (n x 5 => MDE / 2,2) est le meme.
"""

from __future__ import annotations

from typing import NamedTuple

MARCHE = "futures"          # perpetuels Binance — le short l'impose (A2 cote ARIT)
QUOTE = "USDT"
MARCHE_INDICES = "indice"   # ce qu'inscrit le catalogue dans `marche` pour une serie yfinance


class Paire(NamedTuple):
    """Une paire de l'univers.

    `importable` dit si ARIT l'a deja sur disque : c'est ce qui evite de retelecharger.
    `depuis` est la date de debut demandee au telechargement, pas la couverture reelle —
    celle-la est mesuree apres coup et vit dans le catalogue du lake.
    """

    base: str
    depuis: str          # AAAAMMJJ, borne basse demandee a l'exchange
    importable: bool     # deja telechargee par ARIT2.0
    note: str

    @property
    def symbole(self) -> str:
        """Notation ccxt/freqtrade des perpetuels : BTC/USDT:USDT."""
        return f"{self.base}/{QUOTE}:{QUOTE}"

    @property
    def slug(self) -> str:
        """Notation des noms de fichiers freqtrade : BTC_USDT_USDT."""
        return f"{self.base}_{QUOTE}_{QUOTE}"


PAIRES: tuple[Paire, ...] = (
    Paire("BTC", "20190901", True, "socle historique d'ARIT"),
    Paire("ETH", "20190901", True, "socle historique d'ARIT"),
    Paire("SOL", "20200901", True, "socle historique d'ARIT — listee plus tard"),
    Paire("BNB", "20200201", True, "socle historique d'ARIT"),
    Paire("LINK", "20200101", False, "ajout 18/08 — perp parmi les plus anciens (oracle)"),
    Paire("XRP", "20200101", False, "ajout 18/08 — perp parmi les plus anciens (paiements)"),
)

class Indice(NamedTuple):
    """Une serie quotidienne hors crypto : indice boursier, ETF, ou future sur l'or.

    `ticker` est la notation yfinance (`^GSPC`, `GC=F`) ; `base` est le nom court qui
    circule dans BETA et sert aussi de nom de fichier. `depuis` est la borne demandee a la
    source, pas la couverture reelle — celle-la vit dans le catalogue, comme pour une paire
    (URTH n'existe que depuis 2012 : yfinance rend ce qu'il a).
    """

    ticker: str          # notation yfinance
    base: str            # nom court, aussi slug de fichier : SP500-1d.parquet
    depuis: str          # AAAAMMJJ, borne basse demandee a la source (meme forme que Paire)
    note: str

    @property
    def symbole(self) -> str:
        """Ce que la source appelle la serie. Cle du catalogue, comme `Paire.symbole`."""
        return self.ticker

    @property
    def slug(self) -> str:
        return self.base


# Quotidien depuis 2010 : borne raisonnable, les series FRED utiles sont 2019+ de toute
# facon. Or = future COMEX continu (GC=F), pas le spot : c'est ce que yfinance sert.
INDICES: tuple[Indice, ...] = (
    Indice("^GSPC", "SP500", "20100101", "S&P 500"),
    Indice("^IXIC", "NASDAQ", "20100101", "Nasdaq Composite"),
    Indice("^FCHI", "CAC40", "20100101", "CAC 40"),
    Indice("URTH", "MSCIWORLD", "20100101", "iShares MSCI World ETF — cote depuis 2012-01"),
    Indice("GC=F", "XAUUSD", "20100101", "or, future COMEX continu"),
)

# Timeframes STOCKES. Tout le reste se derive par resampling (cf. beta.data.load) : on ne
# telecharge pas ce qu'on peut calculer, et un 15m derive du 5m est exact, pas approche.
TIMEFRAMES: tuple[str, ...] = ("5m", "1h", "4h", "1d")

# Les indices n'ont QUE le 1d : pas de 5m a la source, donc rien a deriver. Demander un 4h
# sur SP500 est une erreur de lecture (DataError), pas un resampling a inventer.
TIMEFRAMES_INDICES: tuple[str, ...] = ("1d",)

# Pas de chaque timeframe, en minutes. Sert a detecter les trous et a valider un resampling.
PAS_MINUTES: dict[str, int] = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120,
                               "4h": 240, "6h": 360, "12h": 720, "1d": 1440}


def symboles() -> tuple[str, ...]:
    return tuple(p.symbole for p in PAIRES)


def a_telecharger() -> tuple[Paire, ...]:
    """Les paires qu'ARIT n'a pas : les seules qui justifient un appel reseau."""
    return tuple(p for p in PAIRES if not p.importable)


def a_importer() -> tuple[Paire, ...]:
    return tuple(p for p in PAIRES if p.importable)


def par_base(base: str) -> Paire:
    for paire in PAIRES:
        if paire.base == base.upper():
            return paire
    raise KeyError(f"paire hors univers : {base} (univers : "
                   f"{', '.join(p.base for p in PAIRES)})")


def resoudre(nom: str) -> Paire | Indice:
    """Accepte 'BTC', 'BTC/USDT:USDT' ou 'BTC_USDT_USDT' — les trois notations qui circulent.

    Resout aussi les indices, par base/slug ('SP500', 'sp500') ou par ticker ('^GSPC').
    Ce qui revient est une `Paire` ou un `Indice` : `est_indice()` dit lequel, et les deux
    portent `base`, `slug` et `symbole` — c'est tout ce que le lake leur demande.
    """
    nom = nom.strip()
    for paire in PAIRES:
        if nom.upper() in (paire.base, paire.symbole.upper(), paire.slug.upper()):
            return paire
    for indice in INDICES:
        if nom.upper() in (indice.base, indice.ticker.upper(), indice.slug.upper()):
            return indice
    raise KeyError(f"actif hors univers : {nom} (paires : "
                   f"{', '.join(p.base for p in PAIRES)} ; indices : "
                   f"{', '.join(i.base for i in INDICES)})")


def est_indice(actif: Paire | Indice) -> bool:
    return isinstance(actif, Indice)


def timeframes_de(actif: Paire | Indice) -> tuple[str, ...]:
    """Les timeframes STOCKES pour cet actif : 4 pour une paire, le seul 1d pour un indice."""
    return TIMEFRAMES_INDICES if est_indice(actif) else TIMEFRAMES


def pas_minutes(timeframe: str) -> int:
    if timeframe not in PAS_MINUTES:
        raise KeyError(f"timeframe inconnu : {timeframe} "
                       f"(connus : {', '.join(PAS_MINUTES)})")
    return PAS_MINUTES[timeframe]
