# CLAUDE.md — BETA, doctrine du projet

**Banc d'essai d'edges.** Ouvert le 2026-08-18 (décision F1 d'ARIT ; les arbitrages vivent depuis le 19/08 dans `DECISIONS.md` de ce dépôt).
Objectif : tester **plusieurs** hypothèses d'edge sur les mêmes données, avec une batterie
statistique qui les tue quand elles ne valent rien — et le dire.

**Les consignes sont rangées en trois familles** (15/11/2026) :
1. **Obligatoire à toute session** — ce fichier, puis `DECISIONS.md` en entier (décisions
   ouvertes, ~160 lignes). Les règles communes à tous les projets de Jonas sont dans le
   `CLAUDE.md` global de la machine (`C:\Users\jofar\.claude\CLAUDE.md` sur le PC,
   `/root/.claude/CLAUDE.md` sur le VPS).
2. **Utile dans tel dossier** — un `CLAUDE.md` par dossier, chargé seulement quand on y travaille :
   `beta/stats/` (portes et outils), `beta/lake/` (univers), `beta/marches/` (vrais marchés),
   `deploy/` (VPS, timers).
3. **À ouvrir seulement si besoin** — tableau en bas de ce fichier.

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
   **Deux compteurs d'essais cumulatifs** depuis le 23/10 (Jonas), un par famille déclarée
   au préenregistrement (`famille_compteur`) : le **trading actif**, initialisé à 30 (la
   dette déjà consommée sur les mêmes 8,5 ans ; 93 au 23/10 : R1-R12, VC2-VC5), et
   l'**invest**, parti de 0 (38 au 23/10 : TI1, T1A). Chaque candidate est jugée au N de SA
   famille (`experiences.n_essais_pour`). Par défaut un essai compte en trading actif : un
   test invest le déclare (`famille_compteur="invest"`). Jamais remis à zéro. Les ~7 150
   configurations essayées HORS protocole par les voies A, B et C (sept.-oct.) ne sont
   comptées dans aucun des deux : **A3 tranchée par Jonas le 23/10** (archives des décisions).
   Un **diagnostic** (`diagnostic=True`, Jonas 24/10, T1F) est journalisé au registre sans
   avancer le compteur : il re-mesure contre un modèle nul des signaux déjà comptés.
5. **Hold-out scellé.** Aucune donnée postérieure à la date de scellement ne sert à choisir
   quoi que ce soit. Le regarder, c'est le brûler. ⚠️ Depuis le 13/10 : **consommé** pour
   l'allocation quotidienne (voies A/B/C, VC2-VC5 l'ont regardé hors moteur), qui ne se juge
   plus qu'en forward ; **scellé** pour tout le reste, et toute lecture de train passe par
   `holdout.borner_train()` (une borne inclusive y lisait la bougie du 01/01/2025).
6. **Buy-and-hold est la référence imposée** de toute candidate, sur la même période. Ce qui
   ne bat pas le hold mesure le marché, pas un edge.
7. **Une candidate écrite vite est une source d'HYPOTHÈSES, jamais d'edge** — qu'elle
   vienne d'un modèle local, d'une vidéo ou d'une intuition de fin de soirée. L'atelier
   abaisse le coût d'**écrire** une candidate ; il ne touche à rien de ce qui permet d'en
   **confirmer** une. Préenregistrement, compteur d'essais, batterie S1-S10 : inchangés,
   devant elle, dans cet ordre.
   ⚠️ **Le sas de l'atelier n'est pas un bac à sable.** Qui peut écrire dans
   `beta/candidates/` peut déjà exécuter du code ici. Il attrape des **erreurs** — look-ahead,
   état caché, chargement de données — pas un adversaire. On relit le code déposé.
   La garde qui compte n'est pas la liste de motifs interdits, c'est l'épreuve de
   **causalité** : `signaux(df[:t])` doit rendre exactement `signaux(df)[:t]`. Une liste
   attrape ce qu'elle connaît ; celle-ci attrape ce qu'on n'avait pas prévu.
   **Depuis le 04/11/2026, le moteur la refait sur les séries mêmes du run, avant tout
   calcul** (`pipeline.eprouver_le_run`, rapport dans `data/runs/<run>/epreuve.json`) ; dans
   l'atelier, `atelier valider <module> --actif <série> --timeframe <tf> [--debut ...]`
   l'éprouve sur la série qu'elle tradera et donne le nombre de signaux d'avant le
   préenregistrement (sans `--actif` : une série témoin, BTC 4 h, et le rapport le dit).
8. **`data/` est jetable, jamais versionné.** Supprimer `data/` doit laisser BETA repartir
   proprement via `scripts/build_lake.py`.
9. **Tout en UTC**, sans exception. Les timestamps du lake sont tz-aware.
10. **Ce qui compte les essais vit à la RACINE**, jamais dans `data/` : `EXPERIMENTS.jsonl`,
    `RUNS.jsonl` et `IDEES.jsonl`. Un compteur qu'un nettoyage remet à zéro est un compteur
    qui ment, et une idée perdue par un nettoyage est une idée qu'on n'aura pas deux fois.
    ⚠️ Les deux premiers ne mesurent pas la même chose — hypothèses d'un côté, mesures de
    l'autre. **Tranché par Jonas le 20/08 (A1, option b) : N porte les mesures** —
    `N = base + mesures distinctes (RUNS.jsonl) + hypothèses préenregistrées sans mesure`,
    appliqué dans `experiences.compteur()`.
11. **Noter une idée est GRATUIT ; la promouvoir COÛTE.** `IDEES.jsonl` n'a aucune forme
    imposée et n'avance pas le compteur ; `promouvoir()` écrit le préenregistrement et
    avance le compteur d'un cran, donc durcit le seuil de toutes les autres hypothèses.
    Cette asymétrie est la fonctionnalité : sans étage gratuit devant, préenregistrer chaque
    idée de passage coûterait trop cher, donc on n'en noterait aucune, donc on les perdrait
    toutes. Elle vaut aussi côté MCP — `beta_suggest_idea` contre `beta_register_edge`.
12. **Comparer plusieurs stratégies fait partie du banc, ce n'est pas un extra.** S7 (reality
    check du maximum) et S9 (corrélation des équity) n'ont aucun sens candidate par
    candidate : cribler dix candidates dix fois en solo donnerait dix résultats flatteurs et
    faux. La comparaison relit `data/runs/` et ne dépend d'aucun criblage — deux stratégies
    mesurées à trois semaines d'écart doivent se comparer sans être remesurées — et ne garde
    **qu'un run par candidate**, sinon l'univers de S7 se remplit de copies d'elle-même.
    ⚠️ **AritV1 est la seconde référence imposée, à côté du buy-and-hold** — mais par sa
    COURBE seulement, jamais par son R par trade : ses sorties sont les siennes, celles des
    candidates viennent de la triple barrière du moteur.
13. **Choisir parmi plusieurs se paie d'une PBO** (S10, Jonas 26/10/2026). Dans un lot de
    `cribler()`, la PBO par CSCV du choix (`beta/stats/pbo.py` : somme des R clôturés chaque
    jour, du premier au dernier jour de clôture du lot, 16 blocs, Sharpe) est la **dixième
    porte**, franchie si PBO < 20 % (`batterie.SEUIL_PBO`). Incalculable (historique trop
    court, candidate sans trade sur une moitié) = non exécutée = INDÉCIDABLE au mieux. Côté
    invest, un préenregistrement qui choisira un réglage parmi plusieurs déclare
    `n_configurations` et met la PBO dans sa règle de décision, sinon `preenregistrer()`
    refuse.

## Ce qui distingue BETA d'un backtester de plus

Un banc d'essai est une **machine à multiplier les tests** : il produira d'autant plus de
faux gagnants qu'il est efficace. Les garde-fous ne sont donc pas des compléments, ce sont
les fonctionnalités principales — MDE affiché avant toute p-value, Benjamini-Hochberg sur la
famille déclarée, Sharpe dégonflé, bootstrap par blocs stationnaire, walk-forward avec purge
et embargo, corrélation des courbes d'équity entre candidates, PBO du choix dans un lot.

> Ces outils ne peuvent que rendre un résultat **pire**, jamais meilleur. Leur seul usage
> honnête est de **tuer** un candidat, pas de le sacrer.

**Portes et outils ne sont pas la même chose** (15/11/2026). Les dix portes S1-S10
(`beta/stats/batterie.py`) rendent l'issue ; leurs seuils ne changent que par décision de Jonas.
Les outils informatifs (`sharpe`, `risque`, `robustesse`, `selection`, `fiche`) donnent des
chiffres à lire à côté, sans seuil et sans verdict. Détail : `beta/stats/CLAUDE.md`.

## Contexte machine — le PC

- Windows 11, 16 Go de RAM, RTX 5060. **Jamais de `read_parquet` global en pandas** : le
  lake se requête en SQL via DuckDB, qui lit le parquet sans tout charger.
- venv partagé avec ARIT pour l'instant : `C:\Users\jofar\venvs\arit` (freqtrade y est déjà,
  et `download-data` en dépend). **Dette assumée** — un venv propre à BETA se justifiera le
  jour où les dépendances divergeront.
- Dépendances pip autorisées (décision du 18/08), mais chacune doit se justifier.
  Aujourd'hui : pandas, pyarrow, duckdb, numpy, scipy, freqtrade, **yfinance** (14/09 : seule
  source libre fiable pour indices/ETF en quotidien ; stooq bloque les robots).
- BETA vit **hors OneDrive** (`C:\Users\jofar\BETA-` ; `C:\Users\jofar\BETA` est un ancien
  clone du même dépôt, supprimé le 15/11/2026), comme ALPHA — OneDrive a déjà vidé des
  fichiers sur ce poste.

## Le VPS

Le même dépôt vit sur un VPS Linux (`/root/BETA-`, venv `/root/venvs/beta`). Le PC et le VPS
poussent sur le même `main` : **`git pull --ff-only` avant de coder**. Une quinzaine de timers
`beta-*` y tournent sans personne (lake, suivi et paper des voies C, journaux poussés chaque nuit,
vrais marchés) et alertent le salon Discord BETA en cas d'échec ; le dashboard `beta-web` est en
lecture seule sur `127.0.0.1:7474`. Horaires, journaux et règles d'exploitation :
`deploy/CLAUDE.md`. ⚠️ Sur le VPS, ne jamais changer de branche dans `/root/BETA-` (les timers
exécutent ce dossier) : travailler dans un worktree.

## Univers

Source unique : `beta/lake/univers.py`. `data.load(nom, timeframe)` lit tout.
- **6 paires** (perpétuels Binance) : `BTC` `ETH` `SOL` `BNB` `LINK` `XRP`, en `5m` `1h` `4h` `1d`
  (les autres multiples de 5 min sont dérivés à la volée).
- **3 perpétuels TradFi** (`univers.TRADFI`, hors de `PAIRES`) : `XAU` `QQQ` `SPY`.
- **5 indices quotidiens** (`univers.INDICES`, `1d` seulement) : `SP500` `NASDAQ` `CAC40`
  `MSCIWORLD` `XAUUSD`.
- **Historique public Binance** (`lecture.vision`) : `metrics`, `bookDepth`, `aggTrades`.
- **Vrais marchés** (`beta/marches`, structure parallèle) : `SPX` `NDX` `VIX` `XAU_LBMA`
  `DEXJPUS` `VIXCLS` `BTC_DS1` en quotidien, `SPX` `NDX` `XAU_SPOT` en intraday.

Dates de cotation, sources, pièges et qualité : `beta/lake/CLAUDE.md` et
`beta/marches/CLAUDE.md` (chargés quand on travaille dans ces dossiers).

## Conventions

- Réponses à Jonas **en français**. Code et docstrings **sans accents** (console Windows en
  cp1252), fichiers `.md` accentués normalement.
- Paths en `pathlib`, jamais de séparateur codé en dur.
- `logging`, jamais `print`, hors sortie de rapport destinée à être lue.
- Tests : `& C:\Users\jofar\venvs\arit\Scripts\python.exe -m pytest -q` (PC) ;
  `/root/venvs/beta/bin/python -m pytest -q` (VPS).
- **Chaque test lit une copie figée de ses données, jamais la source vivante** (Jonas,
  25/10/2026). Une source peut réécrire le passé : Yahoo a révisé la clôture NDX du 23/10 le
  24/10 à 23:11 UTC, et un test de T1F a échoué sans qu'aucun code ait changé. Les copies figées
  vivent dans `tests/donnees/`, nommées par leur empreinte, avec un `.json` qui dit d'où elles
  viennent. Le script qui les produit est dans `scripts/` (`figer_donnees_t1j.py`).
- **Les chiffres et le verdict d'une mesure sortent du programme, pas de Claude** (Jonas,
  24/10 et 04/11/2026). Après une mesure du moteur :
  `python scripts/rapport_experience.py <ids> [--eprouver]` écrit
  `rapports/<ids>/RAPPORT.md` et `RESUME_DISCORD.md` ; c'est ce résumé, **tel quel**, qui part
  sur le salon Discord BETA, avec le rapport en pièce jointe. Aucun chiffre recalculé ou
  arrondi à la main, aucun verdict reformulé ; un avis de Claude va dans un fichier à part
  (`--avis`), recopié dans une section marquée « ce n'est PAS le programme ».
- Pont MCP : déclaré dans `.mcp.json` (Claude Code voit les 7 outils en ouvrant le dossier)
  et dans `~/.lmstudio/mcp.json`. L'éprouver **pour de vrai** :
  `python scripts/epreuve_mcp.py` — un vrai sous-processus, un vrai JSON-RPC. Les tests en
  processus ne prouvent rien du transport ; c'est là qu'un pont casse.
- Modèles locaux : Ollama sur 11434, LM Studio sur 1234. `python beta.py atelier modeles`
  dit lequel répond. **Rien ne sort de la machine.**
- Git : branche `main`, **push après chaque commit**. Repo **privé**.

## À ouvrir seulement si besoin (famille 3)

| Besoin | Fichier |
|---|---|
| Ce que BETA ne sait pas encore faire, état d'avancement (fait foi) | `CHANTIERS.md` (append-only, barré en place) |
| Mode d'emploi, commandes, architecture | `README.md` |
| Une décision déjà tranchée et son motif (voies C, compteurs, hold-out, coûts, S6, S8, S10, TI1, Temps 1, R13 et R14) | `archives/DECISIONS_closes_2026-11-15.md` |
| Rapport d'une mesure | `rapports/<ids>/RAPPORT.md` (écrit par le programme) |
| Fiche de robustesse d'un run (informative) | `python scripts/fiche_robustesse.py <run_id>` → `data/runs/<run_id>/robustesse.md` |
| Dossiers d'une voie ou d'un labo | `VC6_V1/`, `VC6_V2/`, `temps1*/`, `pbo_*/`, `MOMENTUM30_BTC/` — **textes figés** (préenregistrements, spécifications) : ne jamais les réécrire ni les déplacer |
| Ce qui est clos | `archives/` (son `README.md`) |
| Décisions qui portent sur AritV1 en production | `DECISIONS.md` du dépôt `ARIT2.0` |
