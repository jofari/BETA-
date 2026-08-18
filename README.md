# BETA — banc d'essai d'edges

Un endroit où l'on teste **plusieurs** hypothèses de trading sur les mêmes données, avec
l'outillage statistique qui les tue quand elles ne valent rien.

**État au 2026-08-18 : le lake de données seulement.** Le reste (moteur de backtest,
batterie statistique, dashboard, MCP) est conçu mais non codé — périmètre volontairement
réduit, décidé par Jonas.

---

## Démarrage

**Double-cliquer `BETA.cmd`.** Le navigateur s'ouvre sur `http://127.0.0.1:7474`.

En ligne de commande :

| Commande | Effet |
|---|---|
| `python beta.py serve` | le dashboard |
| `python beta.py lake` | construit ou actualise le lake OHLCV |
| `python beta.py strategie` | importe les données de stratégie depuis ARIT |
| `python beta.py etat` | le catalogue, dans le terminal |
| `python beta.py doctor` | ce qui est en place et ce qui manque |

## Le dashboard

Trois onglets, port **7474** (ALPHA occupe 7373) :

- **Stratégie** — le R moyen affiché **à côté de son MDE**, avec un bandeau qui dit en clair
  quand l'écart est sous le seuil de détection. Courbe d'équity en R cumulés, distribution
  des R, ventilation par sens / paire / stratégie, raisons de **sortie** et raisons de
  **rejet**. Le hold-out est exclu par défaut ; l'inclure affiche un avertissement permanent.
- **Données** — les séries du lake, leur couverture réelle, et la **borne commune** : un run
  multi-paires ne peut pas aller plus loin que la série qui s'arrête le plus tôt.
- **Protocole** — le compteur d'essais cumulés et le registre d'expériences.

Zéro dépendance front, zéro CDN : les graphiques sont dessinés au canvas. Même palette
qu'ALPHA, accent vert au lieu de bleu pour distinguer les deux onglets d'un coup d'œil.

## Reconstruire les données

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
beta/config.py    le SEUL endroit où un chemin de données est écrit
beta/lake/        univers · telechargement · construction · catalogue · lecture · strategie
beta/protocole/   experiences (le verrou) · holdout        <- dont tout dépend
beta/stats/       descriptif — ne voit que des séries de R, jamais une stratégie
beta/moteur/      (vide — attend un feu vert)
beta/rapport/     serveur + web/ (le dashboard)
scripts/build_lake.py        construit le lake OHLCV
scripts/import_strategie.py  importe les données de stratégie
beta.py · BETA.cmd           les points d'entrée
```

`protocole/` est **sous** le moteur, pas à côté : un run sans préenregistrement ne pourra
pas exister, et ça se verra dans les imports.

Flux : `ARIT (lecture seule) ─┐`
       `freqtrade download ───┴→ feather → lake.convertir → parquet + catalogue → data.load`

## Tests

```powershell
& C:\Users\jofar\venvs\arit\Scripts\python.exe -m pytest -q
```

68 tests. Ils protègent en priorité la **détection des trous** et la convention
d'horodatage du resampling (une bougie porte l'heure de son **ouverture** — s'y tromper
décale la série et fabrique du look-ahead en silence).

## Ce que BETA ne fait pas

- **Il ne modifie jamais ARIT2.0.** Il le lit. Les deux projets ont des cycles séparés.
- Il ne garde rien de jetable sous git : `data/` est ignoré et reconstructible.
- Il ne mesure rien pour l'instant. Quand il le fera, ce sera avec préenregistrement
  obligatoire et hold-out scellé — voir `CLAUDE.md`.
