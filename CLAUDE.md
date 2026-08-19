# CLAUDE.md — BETA, doctrine du projet

**Banc d'essai d'edges.** Ouvert le 2026-08-18 (décision F1 d'ARIT ; les arbitrages vivent depuis le 19/08 dans `DECISIONS.md` de ce dépôt).
Objectif : tester **plusieurs** hypothèses d'edge sur les mêmes données, avec une batterie
statistique qui les tue quand elles ne valent rien — et le dire.

Lire ce fichier + `README.md` en début de session.

---

## Pourquoi BETA existe

L'entrée d'ARIT n'a aucun edge directionnel mesurable : **78 signaux en 5 ans**,
p = 0,38 / 0,30 contre le modèle nul, E[R] du sélecteur long **pire que le hasard**
(−0,0736 contre −0,0123). Continuer à réparer une seule mécanique dont le substrat est à
espérance nulle est un pari sur une seule carte.

BETA élargit l'univers plutôt que d'affiner le signal. Le calcul qui justifie tout le
projet : passer de 4 à 20 paires multiplie n par 5 et **divise le MDE par 2,2** — aucun
raffinement de feature ne produit un gain comparable.

## État actuel — périmètre volontairement réduit

Jonas, 18/08 : **« je veux juste des data pour le moment »**. Sont donc **hors périmètre**
tant qu'il ne les rouvre pas : la génération automatique de stratégies, le scraping YouTube,
le dashboard, le serveur MCP. Ils sont conçus (plan de session du 18/08) mais **non codés**.

Ce qui est en périmètre : **le lake de données**, et rien d'autre.

---

## Invariants — ne pas casser

1. **BETA ne modifie JAMAIS `ARIT2.0`.** Il le lit — les feathers déjà téléchargés, et rien
   de plus. Aucune écriture, aucun import de code de production ARIT. Les deux projets ont
   des cycles de vie séparés ; un couplage ici casserait l'interdit n° 5 d'ARIT (ne jamais
   hyperopter G1-G7 et les poids) par la bande.
2. **Le lake est la seule source de données.** Aucun chemin de fichier OHLCV écrit à la main
   ailleurs que dans `beta/config.py`. Le but du projet est qu'on ne cherche plus jamais où
   sont les données : on appelle `beta.data.load(pair, tf)`.
3. **Un lake sans trous déclarés est un lake qui ment.** Toute conversion enregistre au
   catalogue le nombre de bougies manquantes et la couverture réelle. Un backtest sur une
   série trouée produit des résultats faux **en silence** — c'est la panne la plus coûteuse
   possible ici.
4. **Rien ne se mesure sans préenregistrement.** Dès qu'une mesure existera dans BETA, elle
   passera par un registre `EXPERIMENTS.jsonl` sur le modèle de celui d'ARIT
   (`ARIT2.0/research/EXPERIMENTS.md`), avec le **compteur d'essais cumulatif initialisé à
   30** — la dette déjà consommée sur les mêmes 8,5 ans. Jamais remis à zéro.
5. **Hold-out scellé.** Aucune donnée postérieure à la date de scellement ne sert à choisir
   quoi que ce soit. Le regarder, c'est le brûler.
6. **Buy-and-hold est la référence imposée** de toute candidate, sur la même période. Ce qui
   ne bat pas le hold mesure le marché, pas un edge.
7. **`data/` est jetable, jamais versionné.** Supprimer `data/` doit laisser BETA repartir
   proprement via `scripts/build_lake.py`.
8. **Tout en UTC**, sans exception. Les timestamps du lake sont tz-aware.

## Ce qui distingue BETA d'un backtester de plus

Un banc d'essai est une **machine à multiplier les tests** : il produira d'autant plus de
faux gagnants qu'il est efficace. Les garde-fous ne sont donc pas des compléments, ce sont
les fonctionnalités principales — MDE affiché avant toute p-value, Benjamini-Hochberg sur la
famille déclarée, Sharpe dégonflé, bootstrap par blocs stationnaire, walk-forward avec purge
et embargo, corrélation des courbes d'équity entre candidates.

> Ces outils ne peuvent que rendre un résultat **pire**, jamais meilleur. Leur seul usage
> honnête est de **tuer** un candidat, pas de le sacrer.

## Contexte machine

- Windows 11, 16 Go de RAM, RTX 5060. **Jamais de `read_parquet` global en pandas** : le
  lake se requête en SQL via DuckDB, qui lit le parquet sans tout charger.
- venv partagé avec ARIT pour l'instant : `C:\Users\jofar\venvs\arit` (freqtrade y est déjà,
  et `download-data` en dépend). **Dette assumée** — un venv propre à BETA se justifiera le
  jour où les dépendances divergeront.
- Dépendances pip autorisées (décision du 18/08), mais chacune doit se justifier.
  Aujourd'hui : pandas, pyarrow, duckdb, numpy, scipy, freqtrade.
- BETA vit **hors OneDrive** (`C:\Users\jofar\BETA`), comme ALPHA — OneDrive a déjà vidé des
  fichiers sur ce poste.

## Univers

**6 paires**, perpétuels Binance : `BTC` `ETH` `SOL` `BNB` (déjà téléchargées par ARIT,
**importées, jamais re-téléchargées**) + `LINK` `XRP` (ajoutées le 18/08, les deux
perpétuels les plus anciens après les majors — c'est l'historique qui commande, puisque le
N est le goulot). Source unique : `beta/univers.py`.

Timeframes stockés : `5m` `1h` `4h` `1d`. Tout autre timeframe multiple de 5 min est
**dérivé à la volée** par resampling — on ne télécharge pas ce qu'on peut calculer.

## Conventions

- Réponses à Jonas **en français**. Code et docstrings **sans accents** (console Windows en
  cp1252), fichiers `.md` accentués normalement.
- Paths en `pathlib`, jamais de séparateur codé en dur.
- `logging`, jamais `print`, hors sortie de rapport destinée à être lue.
- Tests : `& C:\Users\jofar\venvs\arit\Scripts\python.exe -m pytest -q`
- Git : branche `main`, **push après chaque commit**. Repo **privé**.
