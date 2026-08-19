# BETA — banc d'essai d'edges

Un endroit où l'on teste **plusieurs** hypothèses de trading sur les mêmes données, avec
l'outillage statistique qui les tue quand elles ne valent rien.

**État au 2026-08-19** : complet et en service. Données, protocole, dashboard, **moteur de
criblage**, **batterie statistique S1-S9**, **pont freqtrade** et **serveur MCP**.
Trois hypothèses sont passées à la batterie ; **aucune n'a survécu** — une infirmée, deux
indécidables. Ce qui manque maintenant, ce sont des **données** : funding, macro et spot
(chantiers D5-D7), sans lesquelles trois hypothèses préenregistrées restent à l'arrêt.

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
| `python scripts/preenregistrer.py` | préenregistre R1-R6 (idempotent) |
| `python scripts/mesurer.py` | mesure R1 et R6, applique Benjamini-Hochberg, clôt au registre |
| `python -m beta.mcp.serveur` | le serveur MCP stdio (7 outils) |

## Le dashboard

Quatre onglets, port **7474** (ALPHA occupe 7373) :

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
from beta.lake import lecture, strategie

df = lecture.load("BTC", "4h")                                # tout l'historique
df = lecture.load("ETH", "1h", debut="2023-01-01", fin="2024-01-01")
df = lecture.load("SOL", "15m")                               # dérivé du 5m, exact
lecture.catalogue()                                           # ce que contient le lake

trades = strategie.lire("trades", train_seulement=True)       # hold-out exclu
```

## Cribler une candidate

```python
from beta.moteur import pipeline, registre
from beta.moteur.contrats import Run

candidate = registre.charger("r2_mean_reversion")
run = Run(candidate=candidate, paires=("BTC", "ETH"), timeframe="4h")   # refuse sans
verdict, artefacts = pipeline.executer(run)                            # préenregistrement
print(verdict.texte())
```

`Run(...)` appelle `protocole.exiger()` dans son constructeur : **il n'existe aucun chemin**
par lequel un chiffre sort du moteur sans que l'hypothèse ait été écrite avant. Et un
`Verdict` ne peut être `CONFIRMEE` ni avec une porte échouée, ni avec une porte **non
exécutée** — une porte qu'on n'a pas passée ne se présume pas franchie.

Sortie de R2, la première candidate du banc :

```
mean_reversion_z (R2) : INFIRMEE
  n = 790 · r_moyen = -0.2326 · mde_r = 0.1450 · win_rate = 0.27
  [ECHEC] S2_sharpe_degonfle    Sharpe -0,179 contre 0,076 attendu du max de 36 essais
  [ECHEC] S8_buy_and_hold       écart de rendement -1633 pts contre le hold
  ...
  reserve : 3180 signaux mesurés, 790 retenus après élimination des chevauchements
```

## La batterie

Neuf portes, dans `beta/stats/`. **Aucune ne peut améliorer un résultat** — elles ne savent
que le dégrader. Une candidate qui les franchit toutes n'est pas prouvée : elle est
seulement *pas encore tuée*.

| | Porte | Ce qu'elle tue |
|---|---|---|
| S1 | Benjamini-Hochberg | ce qui ne survit pas à la famille de tests déclarée |
| S2 | Sharpe dégonflé (DSR) | ce qui ne dépasse pas le Sharpe attendu de N essais sur du bruit |
| S3 | Bootstrap par blocs stationnaire | ce qui ne survit pas à la dépendance temporelle |
| S4 | Monte-Carlo | ce qui doit son drawdown à la chance de la chronologie |
| S5 | Chemins synthétiques | ce qui gagne autant sur un marché sans structure |
| S6 | Walk-forward purgé + CPCV | ce qui ne tient pas hors échantillon |
| S7 | Reality check de White / SPA | le meilleur d'un lot, quand le lot est du bruit |
| S8 | Buy-and-hold | ce qui mesure le marché plutôt qu'un edge |
| S9 | Corrélation des équity | ce qui répète une candidate déjà retenue |

## Le serveur MCP

`python -m beta.mcp.serveur` — JSON-RPC stdio, aucune dépendance. Sept outils :
`beta_data_catalog`, `beta_load_ohlcv`, `beta_results`, `beta_register_edge`,
`beta_submit_strategy`, `beta_run_backtest`, `beta_publish`.

**`beta_run_backtest` refuse un run sans préenregistrement**, et aucun paramètre ne le
contourne. Un agent capable de lancer mille backtests sans préenregistrer produirait mille
faux gagnants en une nuit, et le compteur d'essais — donc toute la batterie — ne vaudrait
plus rien.

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
beta/stats/       descriptif · bootstrap · multitest · montecarlo · synthetique
                  walkforward · reference · diversification · batterie   (S1-S9)
beta/moteur/      contrats (les 3 contrats gelés) · espace_r · registre · pipeline
                  pont_freqtrade (le seul verdict portefeuille)
beta/candidates/  une hypothèse par fichier, isolée, jetable
beta/recherche/   les mesures R1-R6, chacune sur son préenregistrement
beta/mcp/         serveur MCP stdio (7 outils, zéro dépendance)
beta/rapport/     serveur + runs + actions + web/ (le dashboard)
scripts/build_lake.py        construit le lake OHLCV
scripts/import_strategie.py  importe les données de stratégie
scripts/preenregistrer.py    écrit R1-R6 au registre, avant toute mesure
scripts/mesurer.py           mesure, corrige par BH, clôt au registre
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

142 tests. Ils protègent en priorité la **détection des trous** et la convention
d'horodatage du resampling (une bougie porte l'heure de son **ouverture** — s'y tromper
décale la série et fabrique du look-ahead en silence).

## Ce que BETA ne fait pas

- **Il ne modifie jamais ARIT2.0.** Il le lit. Les deux projets ont des cycles séparés.
- Il ne garde rien de jetable sous git : `data/` est ignoré et reconstructible.
- **Il ne rend pas de verdict portefeuille depuis le criblage.** Un chiffre issu de
  `espace_r` se lit en R par trade : ni frais de financement, ni slots concurrents, ni
  compounding. L'autre verdict vient du pont freqtrade, et de lui seul.
- Il ne mesure rien sans préenregistrement, et le compteur d'essais (**36**, parti de 30)
  n'est jamais remis à zéro — voir `CLAUDE.md`.
