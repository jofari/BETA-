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
| `python beta.py candidates` | l'inventaire du registre de candidates |
| `python beta.py cribler` | passe des candidates à la batterie S1-S9 |
| `python beta.py comparer` | compare les stratégies déjà mesurées entre elles |
| `python beta.py idee note "..."` | note une idée — **gratuit**, le compteur ne bouge pas |
| `python beta.py idee liste` | les idées notées, promues, écartées |
| `python beta.py idee promouvoir I1 --experience R7 ...` | l'idée devient une expérience préenregistrée — **le compteur avance** |
| `python beta.py atelier nouveau <module> --hypothese R7` | un squelette prêt à remplir |
| `python beta.py atelier valider <module>` | sas statique + épreuve de causalité |
| `python beta.py atelier local "<règle>" --module r7_x --hypothese R7` | la fait écrire par un modèle local |
| `python beta.py atelier modeles` | quels serveurs locaux répondent |
| `python beta.py auto proposer --sujet "..."` | le modèle local note des hypothèses — **gratuit**, rien n'est mesuré |
| `python beta.py auto cribler --experience R7 --intentions f.txt` | écrit un lot de candidates et le crible — **un cran de compteur chacune** |
| `python scripts/preenregistrer.py` | préenregistre R1-R6 (idempotent) |
| `python scripts/mesurer.py` | mesure R1 et R6, applique Benjamini-Hochberg, clôt au registre |
| `python scripts/epreuve_mcp.py` | **éprouve le pont MCP pour de vrai** (sous-processus, JSON-RPC) |
| `python beta.py mcp` | le serveur MCP stdio (7 outils) — normalement lancé par le client |

## Le dashboard

Six onglets, port **7474** (ALPHA occupe 7373) :

- **Stratégie** — le R moyen affiché **à côté de son MDE**, avec un bandeau qui dit en clair
  quand l'écart est sous le seuil de détection. Courbe d'équity en R cumulés, distribution
  des R, ventilation par sens / paire / stratégie, raisons de **sortie** et raisons de
  **rejet**. Le hold-out est exclu par défaut ; l'inclure affiche un avertissement permanent.
- **Comparaison** — le classement, les courbes superposées (AritV1 en pointillé), la matrice
  de corrélation et la p-value du *meilleur* du lot. C'est le seul onglet qui répond à
  « celle-ci apporte-t-elle quelque chose que je n'ai pas déjà ? ».
- **Atelier** — écrire une candidate, à la main ou avec un modèle local. Éditeur, bouton
  « demander au modèle local », sas, dépôt. Rien n'entre dans `beta/candidates/` sans avoir
  passé le contrôle statique **et** l'épreuve de causalité.
- **Données** — les séries du lake, leur couverture réelle, et la **borne commune** : un run
  multi-paires ne peut pas aller plus loin que la série qui s'arrête le plus tôt.
- **Protocole** — le compteur d'essais cumulés, le registre d'expériences, et la **boîte à
  idées** : noter est gratuit, seule la promotion avance le compteur.

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

```
python beta.py cribler --candidates r2_mean_reversion --paires BTC,ETH --timeframe 4h
```

Sans `--candidates`, tout le registre passe **ensemble** — c'est nécessaire, pas cosmétique :
S7 (reality check du maximum) et S9 (corrélation des équity) comparent les candidates entre
elles et n'ont aucun sens une par une. Les cribler en solo donnerait des résultats faux dans
le sens flatteur, chacune se croyant seule au monde.

En Python, pour piloter finement :

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

## Suggérer une idée

```
python beta.py idee note "Le funding extrême précède un retournement de la tendance courte."
python beta.py idee liste
python beta.py idee promouvoir I1 --experience R7 --hypothese "..." --metrique "..."        --confirmee "..." --infirmee "..."
```

Deux étages, un seul point de bascule :

```
IDEES.jsonl          gratuit, aucune forme imposée — le compteur d'essais NE BOUGE PAS
    |
    | promouvoir()   <- LE moment où ça coûte : le compteur avance d'un cran
    v
EXPERIMENTS.jsonl    hypothèse falsifiable, métrique primaire, règle de décision
```

Sans l'étage gratuit, préenregistrer chaque idée de passage coûterait un cran de compteur —
donc durcirait le seuil de toutes les autres — donc on n'en noterait aucune, donc on les
perdrait. Ce que la **promotion** force à écrire est exactement ce qui manque à une idée pour
devenir mesurable ; une idée qu'on n'arrive pas à promouvoir est une idée qu'on n'a pas
encore su rendre falsifiable, et le dire est déjà un résultat.

Une idée **écartée** ne disparaît jamais, et son motif est obligatoire : savoir ce qu'on a
décidé de *ne pas* tester vaut autant que savoir ce qu'on a testé.

## Comparer plusieurs stratégies

```
python beta.py comparer
```

Il relit `data/runs/`, il ne relance rien : deux stratégies mesurées à trois semaines d'écart
se comparent sans être remesurées ensemble. Ce que la comparaison montre et qu'aucune fiche
individuelle ne peut montrer :

| | Ce que ça répond |
|---|---|
| **classement** | qui est devant — trié sur le R moyen, jamais sur l'issue, sinon les candidates qui ont eu la chance qu'une porte ne tourne pas passeraient en tête |
| **S7 reality check** | *et si le meilleur du lot était bon par accident ?* Vingt candidates de bruit pur produisent toujours une « meilleure » flatteuse |
| **S9 matrice de corrélation** | deux stratégies rentables corrélées à 0,9 n'en font pas deux : elles en font une, testée deux fois |
| **vs AritV1** | *est-ce mieux que ce qui tourne déjà ?* — la question que le buy-and-hold ne pose pas |

⚠️ **Un seul run par candidate**, le plus récent : deux runs de la même stratégie ne sont pas
deux stratégies, et les compter double gonflerait l'univers de S7 avec une copie de lui-même.

⚠️ **AritV1 se compare par sa COURBE, jamais par son R par trade.** Sa courbe est reconstruite
avec le même sizing que les candidates (risque fixe de 1 %, sans composition) — sinon l'écart
mesurerait la convention de sizing avant de mesurer la stratégie.

Premier résultat comparatif : R2 est **décorrélée d'AritV1 (0,008)** sur 1 419 jours communs,
et lui perd **296 points de rendement**. Décorrélée et perdante n'est pas une candidate.

## L'atelier — écrire d'autres candidates

Deux voies, un seul chemin de dépôt.

```
python beta.py atelier nouveau r7_breakout --hypothese R7      # à la main
python beta.py atelier local "cassure du plus haut des 20 dernières bougies"        --module r7_breakout --hypothese R7                      # modèle local
python beta.py atelier valider r7_breakout
```

Le modèle tourne **sur cette machine** — Ollama (11434) ou LM Studio (1234), détecté
automatiquement, `urllib` seul, aucune dépendance ajoutée. Une hypothèse de trading n'a pas
à passer par un tiers pour devenir dix lignes de pandas.

**Deux étages, et le second est celui qui compte.**

| Étage | Ce qu'il voit | Ce qu'il ne voit pas |
|---|---|---|
| **sas** (`ast`, sans importer) | imports hors liste blanche, `open`/`exec`, `shift(-n)`, `center=True`, `bfill`, effets de bord à l'import, `creer()` manquant | tout look-ahead qui ne ressemble à aucun motif connu |
| **épreuve** (sous-processus, chronomètre) | **causalité**, déterminisme, contrat, non-dégénérescence | rien de ce qui précède ne lui échappe |

L'épreuve de causalité tient en une phrase : **`signaux(df[:t])` doit rendre exactement
`signaux(df)[:t]`.** Une fonction causale ne peut pas produire autre chose sur un préfixe,
puisque chaque ligne ne dépend que de son passé. Une normalisation par `close.mean()` passe
le sas sans encombre — aucun motif interdit — et se fait tuer par l'épreuve, qui voit 110
signaux du passé changer quand on tronque la série.

> Une liste de motifs interdits attrape ce qu'elle connaît ; la causalité attrape ce qu'on
> n'avait pas prévu.

⚠️ **Le sas n'est pas un bac à sable.** Qui peut écrire dans `beta/candidates/` peut déjà
exécuter du code ici. Il attrape des **erreurs**, pas un adversaire — on relit le code
déposé, surtout celui qu'un modèle vient d'écrire. Et une candidate écrite par une machine
est une source d'**hypothèses**, jamais d'edge : elle entre au banc par la même porte que les
autres, préenregistrement compris.

## L'auto-recherche — la boucle, et ce qu'elle refuse

C'est la pièce la plus dangereuse du dépôt. Un banc d'essai branché sur un générateur de
code est une machine à produire des faux gagnants : le modèle écrit vingt candidates, on
garde la meilleure, et le chiffre publié est le maximum d'une distribution nulle. Ça
ressemble à une découverte.

**Deux étages, et ils ne se mélangent jamais.**

```
python beta.py auto proposer --sujet "régimes de volatilité" --combien 5   # GRATUIT
python beta.py auto cribler --experience R7 --intentions intentions.txt    # COÛTEUX
```

`proposer` n'écrit que dans `IDEES.jsonl` : le compteur d'essais ne bouge pas, rien n'est
mesuré, et il faut un geste humain (`idee promouvoir`) pour qu'une idée devienne une
expérience. C'est la seule façon honnête de laisser une machine élargir l'univers
d'hypothèses. `cribler` mesure, donc paie.

**Trois verrous, dans le code plutôt que dans la doctrine.**

| Verrou | Ce qu'il empêche |
|---|---|
| la boucle ne **préenregistre jamais** | qu'une machine décide qu'une idée vaut un cran de compteur. Elle exige une hypothèse déjà écrite, et refuse de démarrer sinon |
| le **budget est borné par `famille_taille`**, déclarée avant | qu'on écrive dix candidates puis qu'on déclare une famille de dix. Le *m* de Benjamini-Hochberg doit être fixe avant de voir les p-values, sinon il s'ajuste à ce qui arrange. Le lot criblé est exactement le lot **écrit** — pas toutes les candidates rattachées à l'hypothèse — sinon le budget vérifié et le lot mesuré divergent dès le deuxième lot |
| le modèle **n'invente pas les hypothèses** | qu'une intention naisse et se teste dans le même mouvement. L'intention vient de Jonas ou d'une idée promue ; la boucle automatise le passage de l'intention au code |

Elle refuse aussi le hold-out, et tout lot au-delà de `BUDGET_MAX = 20` — au-delà, personne
ne relit ce que le modèle a écrit. Chaque refus nomme sa raison de protocole et rend 1.

**Le criblage se fait sur le lot entier, jamais candidate par candidate.** C'est ce qui
permet à S1 (Benjamini-Hochberg), S7 (reality check) et S9 (corrélation) d'exister : les
trois portes comparent les candidates entre elles, et les lancer une par une donnerait à
chacune l'illusion d'être seule au monde — dans le sens flatteur. **N est figé avant le
premier passage** (`compteur() + taille du lot`) : le lot est payé d'avance, et ses
candidates sont jugées au même seuil.

⚠️ Ce que le modèle a écrit et que la boucle a déposé est **à relire**. Le sas attrape des
erreurs, pas un adversaire.

## Le serveur MCP

`python beta.py mcp` — JSON-RPC stdio, aucune dépendance. Déclaré dans `.mcp.json` (Claude
Code) et `~/.lmstudio/mcp.json` (le modèle local reçoit les mêmes outils). Sept outils :
`beta_data_catalog`, `beta_load_ohlcv`, `beta_results`, `beta_register_edge`,
`beta_submit_strategy`, `beta_run_backtest`, `beta_publish`.

**`beta_run_backtest` refuse un run sans préenregistrement**, et aucun paramètre ne le
contourne. Un agent capable de lancer mille backtests sans préenregistrer produirait mille
faux gagnants en une nuit, et le compteur d'essais — donc toute la batterie — ne vaudrait
plus rien.

`scripts/epreuve_mcp.py` le traverse **pour de vrai** : sous-processus, JSON-RPC ligne à
ligne, sept épreuves. Il existe parce que les tests en processus appellent `traiter()`
directement, qui rend des objets Python — ils ne prouvent rien du transport. Il a trouvé du
premier coup que le serveur écrivait en **cp1252** sous Windows : le premier tiret cadratin
d'une description d'outil sortait en `0x97`, et le client n'obtenait jamais la liste des
outils. Un pont ne casse pas dans sa logique, il casse dans son branchement.

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
beta/protocole/   experiences (le verrou) · idees (l'étage gratuit) · holdout  <- dont tout dépend
beta/stats/       descriptif · bootstrap · multitest · montecarlo · synthetique
                  walkforward · reference · diversification · batterie   (S1-S9)
                  comparaison (le banc COMPARATIF : classement, S7, matrice, vs AritV1)
beta/moteur/      contrats (les 3 contrats gelés) · espace_r · registre · pipeline
                  pont_freqtrade (le seul verdict portefeuille)
beta/candidates/  une hypothèse par fichier, isolée, jetable
beta/atelier/     sas (statique) · epreuve (sous-processus) · depot · local · gabarit · cli
beta/recherche/   les mesures R1-R6, chacune sur son préenregistrement
beta/mcp/         serveur MCP stdio (7 outils, zéro dépendance)
beta/rapport/     serveur + runs + actions + atelier + comparaison + web/ (le dashboard)
scripts/build_lake.py        construit le lake OHLCV
scripts/import_strategie.py  importe les données de stratégie
scripts/preenregistrer.py    écrit R1-R6 au registre, avant toute mesure
scripts/mesurer.py           mesure, corrige par BH, clôt au registre
scripts/epreuve_mcp.py       traverse le pont MCP pour de vrai
EXPERIMENTS.jsonl            les hypothèses, append-only          <- hors de data/, exprès
RUNS.jsonl                   les mesures effectuées, append-only  <- hors de data/, exprès
IDEES.jsonl                  les idées, gratuites, append-only    <- hors de data/, exprès
.mcp.json                    le pont, déclaré au client
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
- **L'atelier n'est pas un bac à sable, et il ne raccourcit rien.** Il abaisse le coût
  d'écrire une candidate ; préenregistrement, compteur et batterie restent devant elle.
- ⚠️ **Le compteur compte les hypothèses, pas les mesures.** Tant qu'il y a une candidate
  par hypothèse c'est la même chose ; l'atelier peut casser l'égalité. `RUNS.jsonl` mesure
  l'écart et `beta.py doctor` l'affiche, mais **aucun seuil n'a bougé** : c'est un arbitrage
  ouvert (`DECISIONS.md` § A1), pas un correctif à glisser dans un commit.
- Il ne génère pas de stratégie depuis une vidéo (P4, reporté) : une vidéo est une source
  d'hypothèses, jamais d'edge — exactement comme un modèle local.
- ⚠️ **Il ne peut aujourd'hui CONFIRMER aucune candidate.** S1 n'est jamais exécutée par le
  pipeline (`famille=` n'est pas passé à la batterie), or une issue CONFIRMEE exige les neuf
  portes exécutées. Le plafond réel est INDECIDABLE — sûr par défaut, mais le chemin de la
  confirmation est inatteignable. Dette **T9**, `CHANTIERS.md`.
- ⚠️ **Le criblage ne clôt pas l'expérience au registre** : le verdict va dans `data/runs/` et
  `RUNS.jsonl`, jamais dans `EXPERIMENTS.jsonl`. Dette **T10**.
- **Il n'a encore jamais comparé deux stratégies** : une seule candidate existe. La moitié
  comparative du banc (S7, S9) tourne à vide tant que c'est le cas.
