# BETA — banc d'essai d'edges

Un endroit où l'on teste **plusieurs** hypothèses de trading sur les mêmes données, avec
l'outillage statistique qui les tue quand elles ne valent rien.

**État au 2026-08-18 : le lake de données seulement.** Le reste (moteur de backtest,
batterie statistique, dashboard, MCP) est conçu mais non codé — périmètre volontairement
réduit, décidé par Jonas.

---

## Démarrage

```powershell
cd C:\Users\jofar\BETA
& C:\Users\jofar\venvs\arit\Scripts\python.exe scripts\build_lake.py
```

Le script est **idempotent** : le relancer ne re-télécharge rien d'inutile et reconstruit un
lake identique.

| Option | Effet |
|---|---|
| `--sans-telechargement` | aucun appel réseau : importe ARIT et convertit seulement |
| `--etat` | affiche le catalogue et sort |
| `--purge` | repart d'un lake vide (`data/` est jetable) |

## Lire des données

```python
from beta import data

df = data.load("BTC", "4h")                                   # tout l'historique
df = data.load("ETH", "1h", debut="2023-01-01", fin="2024-01-01")
df = data.load("SOL", "15m")                                  # dérivé du 5m, exact
data.catalogue()                                              # ce que contient le lake
```

C'est le **seul** point d'entrée. Plus aucun chemin de fichier OHLCV n'est écrit à la main
ailleurs que dans `beta/config.py` — c'était la raison d'être du projet.

## L'univers

6 perpétuels Binance, `beta/univers.py` comme source unique :

| Paire | Origine | Historique |
|---|---|---|
| BTC · ETH · SOL · BNB | **importées d'ARIT**, jamais re-téléchargées | 2019-09 → 2020-09 selon la paire |
| LINK · XRP | ajoutées le 18/08 | ~2020-01 |

Le critère d'ajout n'est pas la popularité mais **l'ancienneté du contrat perpétuel** : le
goulot du projet est le nombre de signaux, donc c'est l'historique qui compte.

Timeframes stockés : `5m` `1h` `4h` `1d`. Tout autre multiple de 5 min est **dérivé du 5m
par resampling** — exact, pas approché. On ne télécharge pas ce qu'on peut calculer.

## Le catalogue, et pourquoi il compte plus que les données

Chaque série convertie inscrit au catalogue DuckDB (`data/lake/catalogue.duckdb`) sa
couverture **réelle** : nombre de bougies, bornes, bougies **manquantes**, plus grand trou,
doublons retirés, provenance.

> Une série trouée ne lève aucune exception. Elle produit un backtest faux, en silence, et
> personne ne s'en aperçoit avant d'avoir bâti dessus.

Une série dont la couverture tombe sous 99 % est marquée `suspect` et la lecture émet un
avertissement. C'est l'invariant n° 3 du projet.

```powershell
& C:\Users\jofar\venvs\arit\Scripts\python.exe scripts\build_lake.py --etat
```

## Architecture

```
beta/univers.py   les 6 paires et les timeframes — source de vérité unique
beta/config.py    le SEUL endroit où un chemin de données est écrit
beta/download.py  freqtrade download-data, un processus par paire, en parallèle
beta/lake.py      feather → parquet + audit des trous + catalogue
beta/data.py      l'API de lecture (filtrage poussé dans DuckDB, resampling à la volée)
scripts/build_lake.py   le point d'entrée unique
```

Flux : `ARIT (lecture seule) ─┐`
       `freqtrade download ───┴→ feather → lake.convertir → parquet + catalogue → data.load`

## Tests

```powershell
& C:\Users\jofar\venvs\arit\Scripts\python.exe -m pytest -q
```

24 tests. Ils protègent en priorité la **détection des trous** et la convention
d'horodatage du resampling (une bougie porte l'heure de son **ouverture** — s'y tromper
décale la série et fabrique du look-ahead en silence).

## Ce que BETA ne fait pas

- **Il ne modifie jamais ARIT2.0.** Il le lit. Les deux projets ont des cycles séparés.
- Il ne garde rien de jetable sous git : `data/` est ignoré et reconstructible.
- Il ne mesure rien pour l'instant. Quand il le fera, ce sera avec préenregistrement
  obligatoire et hold-out scellé — voir `CLAUDE.md`.
