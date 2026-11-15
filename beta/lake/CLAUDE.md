# CLAUDE.md — `beta/lake/` : le lake et son univers

> Famille 2 (utile dans ce dossier) : se charge quand on travaille ici. Les invariants du lake
> (n° 2, 3, 8, 9) sont dans le `CLAUDE.md` de la racine. Texte déplacé de la racine le 15/11/2026.


**6 paires**, perpétuels Binance : `BTC` `ETH` `SOL` `BNB` (déjà téléchargées par ARIT :
leurs feathers **amorcent** la copie de BETA, qui est ensuite **complétée** chaque jour —
jamais re-téléchargée en entier, cf. `beta/lake/maj.py`) + `LINK` `XRP` (ajoutées le 18/08, les deux
perpétuels les plus anciens après les majors — c'est l'historique qui commande, puisque le
N est le goulot). Source unique : `beta/lake/univers.py`.

**3 perpétuels TradFi** (Jonas, 20/10) : `XAU` (or, XAUUSDT, coté depuis le 11/12/2025),
`QQQ` (NASDAQ-100 par son ETF) et `SPY` (S&P 500 par son ETF), cotés depuis le 06/04/2026,
24/24 7/7 sur Binance USDⓈ-M. Mêmes timeframes et même porte que les 6 paires (freqtrade →
parquet → catalogue, funding compris), historique complet depuis la cotation, complétés chaque
nuit APRÈS le reste (`maj.mettre_a_jour_tradfi`). Ils sont dans `univers.TRADFI`, **hors** de
`univers.PAIRES` : rien de ce qui parcourt l'univers crypto ne les ramasse sans le dire.
`data.load("XAU", "1h")`. ⚠️ `SPXUSDT` chez Binance est le jeton mème SPX6900, pas le S&P 500.
DS1 collecte aussi leur carnet et leur bookTicker en live (services `ds1-*-tradfi`).

**Historique public Binance** (10/10, `beta/lake/vision.py`) : `metrics` (OI, ratios
long/short, 5 min), `bookDepth` (profondeur cumulée ±0,2-5 %, 30 s, depuis 2023) et
`aggTrades` agrégés à la minute (flux acheteur/vendeur taker), mêmes 6 paires, hors du
catalogue OHLCV : `lecture.vision("bookDepth", "BTC")`, couverture par `scripts/vision.py --etat`.

Timeframes stockés : `5m` `1h` `4h` `1d`. Tout autre timeframe multiple de 5 min est
**dérivé à la volée** par resampling — on ne télécharge pas ce qu'on peut calculer.

**5 indices quotidiens** (spike du 14/09, structure parallèle `univers.INDICES`) : `SP500`
`NASDAQ` `CAC40` `MSCIWORLD` `XAUUSD` — yfinance, **`1d` seulement**, depuis 2010, même
schéma parquet et même catalogue que les paires (audit en jours **ouvrés**, jours fériés
tolérés, trou > 7 jours = suspect). Sans funding ni Fear & Greed (crypto-only) ; les séries
macro globales FRED se joignent normalement. `data.load("SP500", "1d")`, et rien d'autre :
demander un `4h` sur un indice est une `DataError`, pas un resampling.
