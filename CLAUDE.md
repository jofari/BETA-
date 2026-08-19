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

## État actuel — périmètre

Le périmètre du 18/08 (« je veux juste des data pour le moment ») a été **rouvert par Jonas
le 19/08** : feu vert sur le moteur (M1-M4), sur le pont MCP (P1-P3, P5), et ouverture de
**l'atelier de candidates** (§ A des chantiers) — écrire une stratégie à la main ou avec un
modèle local (Ollama, LM Studio).

Reste **hors périmètre** tant qu'il ne le rouvre pas : le pipeline **YouTube → stratégie
générée** (P4). Le motif n'a pas changé : une vidéo est une source d'**hypothèses**, jamais
d'edge.

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
4. **Rien ne se mesure sans préenregistrement.** Verrou matériel depuis le 18/08 :
   `contrats.Run` appelle `protocole.exiger()` dans son constructeur, donc aucun chiffre ne
   sort du moteur sans que l'hypothèse ait été écrite avant, dans `EXPERIMENTS.jsonl`.
   Compteur d'essais cumulatif **initialisé à 30** — la dette déjà consommée sur les mêmes
   8,5 ans. Jamais remis à zéro.
5. **Hold-out scellé.** Aucune donnée postérieure à la date de scellement ne sert à choisir
   quoi que ce soit. Le regarder, c'est le brûler.
6. **Buy-and-hold est la référence imposée** de toute candidate, sur la même période. Ce qui
   ne bat pas le hold mesure le marché, pas un edge.
7. **Une candidate écrite vite est une source d'HYPOTHÈSES, jamais d'edge** — qu'elle
   vienne d'un modèle local, d'une vidéo ou d'une intuition de fin de soirée. L'atelier
   abaisse le coût d'**écrire** une candidate ; il ne touche à rien de ce qui permet d'en
   **confirmer** une. Préenregistrement, compteur d'essais, batterie S1-S9 : inchangés,
   devant elle, dans cet ordre.
   ⚠️ **Le sas de l'atelier n'est pas un bac à sable.** Qui peut écrire dans
   `beta/candidates/` peut déjà exécuter du code ici. Il attrape des **erreurs** — look-ahead,
   état caché, chargement de données — pas un adversaire. On relit le code déposé.
   La garde qui compte n'est pas la liste de motifs interdits, c'est l'épreuve de
   **causalité** : `signaux(df[:t])` doit rendre exactement `signaux(df)[:t]`. Une liste
   attrape ce qu'elle connaît ; celle-ci attrape ce qu'on n'avait pas prévu.
8. **`data/` est jetable, jamais versionné.** Supprimer `data/` doit laisser BETA repartir
   proprement via `scripts/build_lake.py`.
9. **Tout en UTC**, sans exception. Les timestamps du lake sont tz-aware.
10. **Ce qui compte les essais vit à la RACINE**, jamais dans `data/` : `EXPERIMENTS.jsonl`
    et `RUNS.jsonl`. Un compteur qu'un nettoyage remet à zéro est un compteur qui ment.
    ⚠️ Les deux ne mesurent pas la même chose — hypothèses d'un côté, mesures de l'autre —
    et l'écart est un arbitrage ouvert (`DECISIONS.md` § A1).

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
- Pont MCP : déclaré dans `.mcp.json` (Claude Code voit les 7 outils en ouvrant le dossier)
  et dans `~/.lmstudio/mcp.json`. L'éprouver **pour de vrai** :
  `python scripts/epreuve_mcp.py` — un vrai sous-processus, un vrai JSON-RPC. Les tests en
  processus ne prouvent rien du transport ; c'est là qu'un pont casse.
- Modèles locaux : Ollama sur 11434, LM Studio sur 1234. `python beta.py atelier modeles`
  dit lequel répond. **Rien ne sort de la machine.**
- Git : branche `main`, **push après chaque commit**. Repo **privé**.
