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
   **Deux compteurs d'essais cumulatifs** depuis le 23/10 (Jonas), un par famille déclarée
   au préenregistrement (`famille_compteur`) : le **trading actif**, initialisé à 30 (la
   dette déjà consommée sur les mêmes 8,5 ans ; 93 au 23/10 : R1-R12, VC2-VC5), et
   l'**invest**, parti de 0 (38 au 23/10 : TI1, T1A). Chaque candidate est jugée au N de SA
   famille (`experiences.n_essais_pour`). Par défaut un essai compte en trading actif : un
   test invest le déclare (`famille_compteur="invest"`). Jamais remis à zéro. Les ~7 150
   configurations essayées HORS protocole par les voies A, B et C (sept.-oct.) ne sont
   comptées dans aucun des deux : **A3 tranchée par Jonas le 23/10** (`DECISIONS.md`).
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
10. **Ce qui compte les essais vit à la RACINE**, jamais dans `data/` : `EXPERIMENTS.jsonl`,
    `RUNS.jsonl` et `IDEES.jsonl`. Un compteur qu'un nettoyage remet à zéro est un compteur
    qui ment, et une idée perdue par un nettoyage est une idée qu'on n'aura pas deux fois.
    ⚠️ Les deux premiers ne mesurent pas la même chose — hypothèses d'un côté, mesures de
    l'autre — et l'écart est un arbitrage ouvert (`DECISIONS.md` § A1).
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

## Ce qui distingue BETA d'un backtester de plus

Un banc d'essai est une **machine à multiplier les tests** : il produira d'autant plus de
faux gagnants qu'il est efficace. Les garde-fous ne sont donc pas des compléments, ce sont
les fonctionnalités principales — MDE affiché avant toute p-value, Benjamini-Hochberg sur la
famille déclarée, Sharpe dégonflé, bootstrap par blocs stationnaire, walk-forward avec purge
et embargo, corrélation des courbes d'équity entre candidates.

> Ces outils ne peuvent que rendre un résultat **pire**, jamais meilleur. Leur seul usage
> honnête est de **tuer** un candidat, pas de le sacrer.

## Contexte machine — le PC

- Windows 11, 16 Go de RAM, RTX 5060. **Jamais de `read_parquet` global en pandas** : le
  lake se requête en SQL via DuckDB, qui lit le parquet sans tout charger.
- venv partagé avec ARIT pour l'instant : `C:\Users\jofar\venvs\arit` (freqtrade y est déjà,
  et `download-data` en dépend). **Dette assumée** — un venv propre à BETA se justifiera le
  jour où les dépendances divergeront.
- Dépendances pip autorisées (décision du 18/08), mais chacune doit se justifier.
  Aujourd'hui : pandas, pyarrow, duckdb, numpy, scipy, freqtrade, **yfinance** (14/09 : seule
  source libre fiable pour indices/ETF en quotidien ; stooq bloque les robots).
- BETA vit **hors OneDrive** (`C:\Users\jofar\BETA`), comme ALPHA — OneDrive a déjà vidé des
  fichiers sur ce poste.

## Le VPS — ce qui tourne sans personne (depuis début octobre)

Le même dépôt vit aussi sur un VPS Linux (`/root/BETA-`, venv `/root/venvs/arit`, unités
systemd dans `deploy/`). Le PC et le VPS poussent sur le même `main` : **`git pull --ff-only`
avant de coder**.

- **Timers (UTC)** : `beta-maj` 00:20 (lake) · `beta-suivi` 00:45 (voie C) ·
  `beta-suivi-vc2`…`vc5` 00:50 · `beta-paper` 01:00 (cinq voies) · `beta-journaux` 01:15
  (commit + push des journaux) · `beta-vision` 03:30 (historique public Binance) ·
  `beta-vc4-sessions` (08:02 Londres, 09:32 New York, en semaine) · `beta-paper-direct`
  (chaque minute) · `beta-marches` 23:10 (vrais marchés, quotidien) · `beta-marches-direct`
  (toutes les 5 min, intraday) · `beta-marches-histo` (toutes les heures, rattrapage de l'or
  intraday depuis 2003).
- **Journaux forward**, à la racine, en ajout seul : `SUIVI_*.jsonl`, `CONSIGNES_VC4.jsonl`,
  `PAPER_*.jsonl` (poussés chaque nuit) ; `DIRECT_PAPER.jsonl` (relevé minute, hors git).
- **Dashboard** `beta-web` en lecture seule sur `127.0.0.1:7474`, ouvert depuis le PC par
  le tunnel `VPS.cmd`. Après un changement de son code : `systemctl restart beta-web`.
- **Alertes** : toute unité `beta-*` en échec — alarme du dry-run comprise (sorties 4 et 5) —
  part sur le salon Discord BETA (drop-in `deploy/notif.conf`).
- Tests sur le VPS : `cd /root/BETA- && /root/venvs/arit/bin/python -m pytest -q`.

## Univers

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

**Les vrais marchés** (Jonas, 20-21/10 : « pas la version de Binance », « sortir de freqtrade »).
Le paquet `beta/marches` est une structure **parallèle** au lake, comme `vision`. Fichiers dans
`data/marches/` : `<NOM>-<tf>.parquet`, plus `etat.json` et `etat_intraday.json`. Rien de ce
qui tourne ne la lit ; seuls les labos `beta/temps1` (T1A) et `beta/temps1_justesse` (T1J,
test de justesse du 24/10) l'utilisent. Noms **neufs**, sans collision
avec le lake (test) : `SP500`, `NASDAQ` et `XAUUSD` gardent leur sens ci-dessus.
- Quotidien (`collecte.lire("SPX")`, timer `beta-marches`, 23:10 UTC) :
  - `SPX` : S&P 500 `^GSPC`, Yahoo, depuis 1927 ;
  - `NDX` : Nasdaq-100 `^NDX`, Yahoo, depuis 1985 ;
  - `VIX` : `^VIX`, Yahoo, depuis 1990 ;
  - `XAU_LBMA` : or comptant au fixing LBMA PM, via l'API du World Gold Council, à requêter
    **par année** (une plage courte rend un autre prix, 7 jours sur 7), depuis 1970 ;
  - `DEXJPUS` : USD/JPY H.10, FRED, hebdomadaire ; colonne `publie_le` = première publication
    ALFRED.
  - `VIXCLS` : le VIX tel que publié par FRED (T1J, 24/10), à côté de `^VIX` ;
  - `BTC_DS1` : clôture journalière BTC/USD Bitstamp, lue dans la base souveraine DS1 (table
    `bougies_1d`, lot DS1 de 00:15 UTC) par `docker exec psql`, en lecture seule, depuis 2011.
  - Règles : la séance du jour n'est jamais écrite avant sa clôture, et une réécriture du passé
    par la source part dans `revisions.jsonl`.
- Intraday (`intraday.lire("SPX", "5m")`, avec un 4h dérivé du 1h sur la grille UTC) :
  - `SPX`, `NDX` : Yahoo 5m (60 jours à la source, s'allonge à chaque passage) et 1h (730 jours),
    timer `beta-marches-direct` toutes les 5 min ;
  - `XAU_SPOT` : or comptant XAU/USD, bougies BID Dukascopy à la minute agrégées en 5m/1h/1d. La
    journée en cours vient des ticks horaires (retard ≤ ~1 h) ; l'historique depuis 2003 est
    rattrapé par `beta-marches-histo`. ⚠️ Dukascopy bride : une requête à la fois, 4 s entre deux,
    arrêt propre après trois 503 et reprise à l'heure suivante.
- Qualité, vérifiée le 21/10 :
  - `SP500` du lake = `SPX`, à l'identique ;
  - **FRED `NASDAQ100` (vote du socle) est faux sur 407 séances de 2003-2005** (31/12/2003 : 1 459,06
    contre 1 467,92 officiel) : Yahoo `^NDX` est juste. Le socle ne lit que 2019+ ;
  - FRED `VIXCLS` et `^VIX` diffèrent sur 11 séances, mais jamais de part et d'autre de 25.

## Conventions

- Réponses à Jonas **en français**. Code et docstrings **sans accents** (console Windows en
  cp1252), fichiers `.md` accentués normalement.
- Paths en `pathlib`, jamais de séparateur codé en dur.
- `logging`, jamais `print`, hors sortie de rapport destinée à être lue.
- Tests : `& C:\Users\jofar\venvs\arit\Scripts\python.exe -m pytest -q` (PC) ;
  `/root/venvs/arit/bin/python -m pytest -q` (VPS).
- Pont MCP : déclaré dans `.mcp.json` (Claude Code voit les 7 outils en ouvrant le dossier)
  et dans `~/.lmstudio/mcp.json`. L'éprouver **pour de vrai** :
  `python scripts/epreuve_mcp.py` — un vrai sous-processus, un vrai JSON-RPC. Les tests en
  processus ne prouvent rien du transport ; c'est là qu'un pont casse.
- Modèles locaux : Ollama sur 11434, LM Studio sur 1234. `python beta.py atelier modeles`
  dit lequel répond. **Rien ne sort de la machine.**
- Git : branche `main`, **push après chaque commit**. Repo **privé**.
