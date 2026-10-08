# BETA — chantiers

> Ce que BETA ne sait pas encore faire, dans l'ordre où ça doit se faire.
> Ouvert le 2026-08-18. Append-only, comme `ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` :
> une ligne fermée est **barrée en place**, avec sa date. Si elle n'est pas barrée, elle est
> ouverte.
>
> Arbitrages de Jonas : `DECISIONS.md` (ce dépôt, depuis le 19/08 ; avant, `ARIT2.0/DECISIONS.md` § F1). Doctrine : `CLAUDE.md`.
>
> **Frontière ARIT / BETA** (posée le 19/08, symétrique de
> `ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` § MISE À JOUR DU 2026-08-19) :
> **ARIT2.0 = la stratégie qui tourne** (AritV1 : ses portes, ses scores, sa gestion, son
> dry-run, son observabilité). **BETA = la recherche d'autres stratégies** (moteur de
> criblage, batterie multi-test, hypothèses d'edge). **Aucun statut ne vit aux deux
> endroits** : le dépôt propriétaire fait foi, l'autre ne porte qu'un pointeur.
> Ce qui a migré ici le 18/08 et n'est plus suivi chez ARIT : **F1 / H7** (le banc) et
> **Q9** (Deflated Sharpe + buy-and-hold → S2 et S8). Ce qui **reste chez ARIT** malgré
> l'apparence : **Q7** (walk-forward pour AritV1 ; S6 est le même outil appliqué aux
> candidates — deux travaux, deux dépôts), **C1-bis** (paramètre d'AritV1, que **R6** se
> contente de mesurer) et **F2 / G2 / G8** (le dry-run, qui ne tourne que chez ARIT).

**État en une phrase au 19/08 (soir)** : BETA sait chercher un edge, le tuer, **en écrire
d'autres**, et depuis ce soir **les comparer entre elles** — classement, matrice de
corrélation, reality check du maximum, et AritV1 en référence à côté du buy-and-hold. Une
boîte à idées gratuite est apparue devant le préenregistrement, parce que noter une idée ne
doit pas coûter un cran de compteur. Le moteur et la batterie S1-S9 sont en place, le pont MCP est
**branché et éprouvé** (Claude Code + LM Studio), et l'**atelier** permet d'écrire une
candidate à la main ou avec un modèle local — derrière un sas statique et une épreuve de
causalité en sous-processus. Trois hypothèses sont passées à la batterie et **aucune n'a
survécu**. Ce qui manque n'est toujours pas de l'outillage mais **des données** : funding,
macro et spot, sans lesquelles R3, R4 et R5 ne sont pas mesurables — et désormais **un
arbitrage** : le compteur d'essais compte les hypothèses, pas les mesures (§ A, dette T8).

---

## Fait au 2026-08-18

| # | Chantier | État |
|---|---|---|
| ~~D1~~ | ~~Lake OHLCV : 6 paires, 4 timeframes, catalogue des trous~~ | ✅ **FERMÉ 18/08** — 24 séries, 100 % de couverture, 4,56 M bougies |
| ~~D2~~ | ~~Données de stratégie : trades, évaluations, gestion~~ | ✅ **FERMÉ 18/08** — 79 trades, 3 151 évaluations, 4 084 événements |
| ~~D3~~ | ~~Protocole : préenregistrement + hold-out scellé + compteur~~ | ✅ **FERMÉ 18/08** — verrou matériel, compteur parti de 30 |
| ~~D4~~ | ~~Dashboard + lanceur~~ | ✅ **FERMÉ 18/08** — `BETA.cmd`, port 7474 |

## Fait au 2026-08-19

| # | Chantier | État |
|---|---|---|
| ~~M1~~ | ~~`moteur/contrats.py` — Candidate / Run / Verdict~~ | ✅ **FERMÉ 19/08** — un Run appelle `protocole.exiger()` dans son constructeur |
| ~~M2~~ | ~~`moteur/espace_r.py` — triple barrière vectorisée~~ | ✅ **FERMÉ 19/08** — par blocs, coûts soustraits en R |
| ~~M3~~ | ~~Pont freqtrade~~ | ✅ **FERMÉ 19/08** — export + `--enable-protections --timeframe-detail 5m` imposés |
| ~~M4~~ | ~~Registre de candidates~~ | ✅ **FERMÉ 19/08** — découverte par import, une par fichier |
| ~~S1~~ à ~~S9~~ | ~~La batterie complète~~ | ✅ **FERMÉES 19/08** — voir la section S |
| ~~P1~~ | ~~Bouton Claude Code depuis le dashboard~~ | ✅ **FERMÉ 19/08** — liste blanche, prompt reconstruit côté serveur |
| ~~P2~~ | ~~Serveur MCP stdio~~ | ✅ **FERMÉ 19/08** — 7 outils, JSON-RPC en stdlib, zéro dépendance |
| ~~P3~~ | ~~Garde-fou du backtest MCP~~ | ✅ **FERMÉ 19/08** — refus vérifié par test |
| ~~T1~~ | ~~Repo distant privé~~ | ✅ **FERMÉE 19/08** — `github.com/jofari/BETA-`, `main` poussée |
| ~~F1~~ | ~~Fiche stratégie au dashboard~~ | ✅ **FERMÉ 19/08** — onglet Candidates, verdict avant courbe |

---

## M — le moteur (feu vert de Jonas le 19/08 — sur du code déjà écrit)

Arbitrage du 18/08 : **hybride** — moteur maison en espace-R pour cribler, freqtrade pour
confirmer les survivantes. Aucun des deux seul ne suffit : le maison ne simule ni frais, ni
slots, ni compounding ; freqtrade ne permet pas 1 000 runs Monte-Carlo.

| # | Chantier | Statut | Effort | Ce que ça débloque |
|---|---|---|---|---|
| ~~M1~~ | ~~`moteur/contrats.py` — les trois contrats gelés~~ | ✅ fermé 19/08 | S | fait : un `Verdict` ne peut être CONFIRMEE ni avec une porte échouée, ni avec une porte **non exécutée** |
| ~~M2~~ | ~~`moteur/espace_r.py` — triple barrière vectorisée~~ | ✅ fermé 19/08 | M | fait : bougie ambiguë ⇒ SL comme chez ARIT ; le coût en R croît quand le stop se resserre |
| ~~M3~~ | ~~Pont freqtrade~~ | ✅ fermé 19/08 | M | fait : refuse une candidate non survivante, sauf `forcer=True` explicite |
| ~~M4~~ | ~~Registre de candidates~~ | ✅ fermé 19/08 | S | fait : une candidate cassée est journalisée en ERROR, elle n'annule pas les autres |
| ~~M5~~ | ~~`beta.py cribler` et `beta.py candidates` — lancer le moteur depuis le terminal~~ | ✅ fermé 19/08 | S | fait : le lot passe ensemble, donc S7 et S9 ont un sens |

⚠️ **Le feu vert du 19/08 est arrivé sur du code déjà écrit** (commits `94eff2d`, `6ad1a2f`).
Ce qui manquait vraiment n'était pas le moteur mais son **lanceur** : jusqu'à M5, aucune
commande ne permettait de cribler une candidate. Un moteur sans porte d'entrée est un moteur
qu'on croit avoir.

⚠️ **M2 ne produit jamais un verdict portefeuille.** Un chiffre issu du criblage se lit en
R par trade, jamais en rendement de portefeuille. La confusion des deux est l'erreur qui
rend un banc d'essai dangereux.

---

## S — la batterie multi-test (ce qui distingue BETA d'un backtester de plus)

> **Un banc d'essai est une machine à multiplier les tests. Il produira d'autant plus de
> faux gagnants qu'il est efficace.** Ces outils ne sont donc pas des compléments — ce sont
> les fonctionnalités principales. Ils ne peuvent que rendre un résultat **pire**, jamais
> meilleur : leur seul usage honnête est de **tuer** un candidat, pas de le sacrer.

Spécification déjà écrite, dans le second cerveau de Jonas — ces chantiers l'implémentent,
ils ne la redécouvrent pas.

| # | Chantier | Statut | Effort | Source de la spec |
|---|---|---|---|---|
| ~~S0~~ | ~~MDE affiché à côté de chaque métrique~~ | ✅ fermé 18/08 | S | `stats/descriptif.py` — déjà appliqué |
| ~~S1~~ | ~~**Benjamini-Hochberg** sur la famille de tests déclarée (FDR 0,10)~~ | ✅ fermé 19/08 | S | `budget de tests et sharpe degonfle.md` · portage de `ARIT2.0/analysis/mesures.py:106` |
| ~~S2~~ | ~~**Sharpe dégonflé (DSR)** — dégonfle le Sharpe par le maximum attendu de N essais, N venant du compteur cumulatif~~ | ✅ fermé 19/08 | S | Bailey & López de Prado (2014) · même note |
| ~~S3~~ | ~~**Bootstrap par blocs stationnaire** (Politis-Romano), ℓ fixé avant, sensibilité publiée sur 3 longueurs~~ | ✅ fermé 19/08 | M | `bootstrap par blocs stationnaire.md` |
| ~~S4~~ | ~~**Monte-Carlo** — permutation de l'ordre des trades + rééchantillonnage, cône d'équity~~ | ✅ fermé 19/08 | M | `monte-carlo (validation).md` |
| ~~S5~~ | ~~**Chemins synthétiques** — GBM et phase randomization, la stratégie rejouée sur ~200 séries~~ | ✅ fermé 19/08 | L | `chemins synthetiques - GBM et phase randomization.md` |
| ~~S6~~ | ~~**Walk-forward avec purge et embargo (CPCV)**~~ | ✅ fermé 19/08 | L | `walk-forward purge et embargo (CPCV).md` |
| ~~S7~~ | ~~**Reality Check de White / SPA de Hansen** — bootstrap sur la statistique du **maximum** d'un univers de N candidates~~ | ✅ fermé 19/08 | L | `budget de tests et sharpe degonfle.md` |
| ~~S8~~ | ~~**Buy-and-hold** comme référence imposée de toute candidate, même période~~ | ✅ fermé 19/08 | S | ex-Q9 d'ARIT · `DECISIONS.md` |
| ~~S9~~ | ~~**Corrélation des courbes d'équity** entre candidates — deux stratégies rentables corrélées à 0,9 n'apportent rien~~ | ✅ fermé 19/08 | M | `DECISIONS.md`, critère de diversification |

**Ordre imposé** : S1, S2 et S8 **avant** la première comparaison de candidates. Sans elles,
le premier gagnant du banc sera un artefact, et on l'aura cru. — *Respecté : les neuf portes
existaient avant la première candidate.*

Vérifié par test plutôt que par relecture : la batterie **ne sacre pas** le meilleur d'un lot
de vingt séries de bruit pur (S7, p > 0,05), et **voit** une vraie gagnante glissée dedans.
C'est le seul contrôle qui dise quelque chose sur une batterie de garde-fous.

---

## R — la recherche d'edge (l'objet même du projet)

Objectif de F1, mot pour mot : « tester **d'autres stratégies** que AritV1, pour trouver
celle qui a le meilleur rendement **et diversifier les formes d'investissement** ».

### R0 — le protocole de recherche, avant les candidates

Une boucle, toujours la même, et **jamais dans un autre ordre** :

```
hypothèse falsifiable
  → préenregistrement (protocole/experiences.py : hypothèse, métrique, règle de décision, MDE attendu)
  → candidate isolée (moteur/contrats.py)
  → criblage espace-R (M2)  →  batterie S1-S9
  → verdict : confirmée / infirmée / INDÉCIDABLE
  → si elle survit : confirmation freqtrade (M3), puis hold-out — une seule fois
```

L'issue **indécidable** est légitime et sera la plus fréquente. Le premier test d'A5 côté
ARIT l'a montré : 7 signaux marginaux pour un MDE de +1,53 R.

### R1-R6 — les hypothèses déjà identifiées

| # | Hypothèse | Statut | Origine | Effort |
|---|---|---|---|---|
| ~~R1~~ | **Le trailing stop détruit les shorts.** | 🟡 **mesurée 19/08 — INDÉCIDABLE** | mesure du 18/08 — **seul écart du lot à dépasser son MDE**, mais sous-groupe trouvé après coup ⇒ **à préenregistrer avant de mesurer** | S |
| ~~R2~~ | **Mean-reversion** (z-score 48 bougies, seuil 2) | 🔴 **mesurée 19/08 — INFIRMÉE** | `DECISIONS.md` | M |
| **R3** | **Portage / funding** — 86 % du profit de MacroFlip venait de là | ⛔ préenregistrée, **bloquée par D5** | § F1 | M |
| **R4** | **Macro seule**, sans couche technique | ⛔ préenregistrée, **bloquée par D6** | § F1 | M |
| **R5** | **Spot vs perpétuel** — à reposer proprement, avec le hold-out | ⛔ préenregistrée, **bloquée par D7** | § F1 · `BUILD_NOTES` 17/08 | M |
| ~~R6~~ | **`news_window`** — que vaut ce qu'elle bloque ? | 🟡 **mesurée 19/08 — hypothèse NON MESURABLE** | mesure du 18/08 · lien direct avec **C1-bis** | S |

⚠️ **R1 et R6 se mesurent sur les données déjà présentes**, sans écrire une seule candidate.
Ce sont donc les deux moins chers, et les deux premiers à préenregistrer.
— *Fait le 19/08. Les six hypothèses sont préenregistrées, compteur cumulé à **36 essais**.*

### Ce que les mesures du 19/08 ont donné

**R1 — indécidable, et c'est la bonne réponse.** Test apparié sur les 21 shorts du train :
même entrée, même stop, seule la sortie change. La barrière fixe rend **+0,5272 R de plus
par short** (p = 0,0175, IC bootstrap [+0,049 ; +1,006]), mais le **MDE vaut 0,7463 R**.
L'écart est sous le seuil de détection de l'échantillon : la p-value passe, la puissance
non. Il ne survit pas non plus à Benjamini-Hochberg sur la famille de 8 (seuil 0,0125).
Côté long, rien : +0,1282 R pour un MDE de 0,7552, p = 0,27.
*Validation croisée du portage au passage* : −0,4683 R côté trailing, exactement le chiffre
publié le 18/08, et +0,0589 R en barrière fixe contre +0,0637 annoncé.

**R6 — l'hypothèse n'était pas mesurable, et il a fallu la mesurer pour le savoir.**
Les « 756 signaux bloqués » sont **756 lignes de journal**, soit **63 signaux distincts**
(dette T4 : ~13 `gate_check` par signal). Pire : **53 de ces 63 sont aussi acceptés
ailleurs**. `news_window` ne sépare pas une population de signaux d'une autre — elle
retarde un signal, puis le laisse passer quand la fenêtre de news retombe. Les deux groupes
de l'hypothèse n'existent pas ; il reste 10 signaux exploitables.
⇒ **Le chiffre « 91,75 % de tout ce qui est rejeté » décrit des lignes de journal, pas des
signaux.** À corriger partout où il est cité.

**R2 — infirmée, nettement.** 790 trades sur BTC/ETH en 4h, R moyen **−0,2326** pour un MDE
de 0,1450, win rate 27 %. Les neuf portes échouent. Le retour à la moyenne nu, sans filtre
de régime, n'a pas d'edge sur cet univers — ce qui ne dit rien d'une mean-reversion filtrée,
qui serait une autre candidate avec son propre préenregistrement.

---

## P — le pont MCP (double sens)

| # | Chantier | Statut | Effort |
|---|---|---|---|
| ~~P1~~ | ~~Bouton du dashboard qui lance `claude "prompt"` avec le contexte du run~~ | ✅ fermé 19/08 | S |
| ~~P2~~ | ~~Serveur MCP stdio, 7 outils~~ | ✅ fermé 19/08 | M |
| ~~P3~~ | ~~`beta_run_backtest` refuse un run sans préenregistrement~~ | ✅ fermé 19/08 | S |
| ~~P5~~ | ~~**Brancher** le pont : `.mcp.json`, `beta.py mcp`, épreuve stdio réelle, déclaration LM Studio~~ | ✅ fermé 19/08 | S |

### P5 — ce que « à tester » a trouvé

Le pont existait depuis le matin mais **n'était déclaré à aucun client** : pas de
`.mcp.json`, `mcpServers` vide côté Claude Code comme côté LM Studio. Un pont que rien ne
traverse.

`scripts/epreuve_mcp.py` le traverse pour de vrai — sous-processus, JSON-RPC ligne à ligne —
et a trouvé du premier coup un défaut que `tests/test_ponts.py` ne pouvait pas voir :
**le serveur écrivait en cp1252**. Les tests appellent `traiter()` en direct, qui rend des
objets Python ; dès qu'on passe par un tube, le premier tiret cadratin d'une description
d'outil sort en `0x97` et le client échoue à décoder la ligne — donc n'obtient **jamais** la
liste des outils. Corrigé à la source (`serveur.forcer_utf8()`), pas dans la configuration
du client : un serveur dont le correctif vit dans le `PYTHONIOENCODING` de l'appelant est
cassé pour tout client qui ne l'a pas mis. Test de non-régression : le seul du dépôt qui
lance un vrai sous-processus.

Trouvé au passage et corrigé : `beta_run_backtest` portait une **liste de paires en dur**
(`BTC, ETH, SOL, BNB`), alors que `univers.py` dit qu'une liste de paires écrite ailleurs est
un bug — c'est exactement ce qui fait tourner un backtest sur 4 paires en croyant en couvrir 6.

⚠️ **Rouvert par Jonas le 19/08** (« tous les chantiers M, S, R et P »). Le pipeline
**YouTube → stratégie générée** (`P4`) reste reporté, lui : une vidéo est une source
d'**hypothèses**, jamais d'edge.

Lancement du serveur MCP :
`& C:/Users/jofar/venvs/arit/Scripts/python.exe -m beta.mcp.serveur`

---

## A — l'atelier de candidates (ouvert et fermé le 19/08, demande de Jonas)

Demande, mot pour mot : « une possibilité de tester d'autres stratégies, et une **option
locale** pour coder ces stratégies à la main ou avec un modèle local sur Ollama ou LM Studio ».

Le problème que l'atelier résout n'est pas *produire du code de stratégie* — un modèle de
7 milliards de paramètres en produit dix par minute. C'est **empêcher que ce code, écrit
vite, entre dans le banc en emportant du look-ahead avec lui**.

> **Une candidate écrite par une machine est une source d'HYPOTHÈSES, jamais d'edge.**
> Même règle que P4 (YouTube). Elle entre au banc par la même porte que les autres :
> préenregistrement, compteur d'essais, batterie S1-S9. L'atelier abaisse le coût
> d'**écrire** une candidate, jamais le seuil pour en **confirmer** une.

| # | Chantier | Statut | Effort | Ce que ça fait |
|---|---|---|---|---|
| ~~A1~~ | ~~`atelier/gabarit.py` + `beta.py atelier nouveau`~~ | ✅ fermé 19/08 | S | la voie « à la main » : un squelette qui porte le contrat, et qui **ne signale rien** — donc que l'épreuve refuse tant que la règle n'est pas écrite |
| ~~A2~~ | ~~`atelier/sas.py` — contrôle statique AST, **avant tout import**~~ | ✅ fermé 19/08 | M | imports en liste blanche, pas d'`open`/`exec`, `creer()` présent, aucun effet de bord à l'import, `shift(-n)` et `center=True` refusés |
| ~~A3~~ | ~~`atelier/epreuve.py` — l'épreuve en **sous-processus avec chronomètre**~~ | ✅ fermé 19/08 | M | contrat, déterminisme, **causalité**, non-dégénérescence. Un `while True` d'un 7B est tué, il ne gèle pas le dashboard |
| ~~A4~~ | ~~`atelier/depot.py` — le chemin unique vers `beta/candidates/`~~ | ✅ fermé 19/08 | S | valide sur un fichier **temporaire** : une nouvelle version refusée ne détruit pas la candidate en place |
| ~~A5~~ | ~~`atelier/local.py` — Ollama (11434) et LM Studio (1234), `urllib` seul~~ | ✅ fermé 19/08 | M | auto-détection, prompt portant le contrat, **boucle de réparation** : le refus du sas repart au modèle |
| ~~A6~~ | ~~Onglet **Atelier** au dashboard + `beta.py atelier`~~ | ✅ fermé 19/08 | M | éditeur, modèle local, sas, dépôt. Liste blanche de gestes, rien d'exécuté avant le sas |

### Le couple qui justifie tout l'étage

Deux tests disent la même chose depuis les deux côtés, et c'est le résultat le plus utile de
la journée :

- `test_le_sas_ne_voit_pas_une_normalisation_globale` — une candidate qui divise par
  `close.mean()` **passe** le contrôle statique. Aucun motif interdit n'y figure.
- `test_l_epreuve_attrape_la_normalisation_globale_que_le_sas_a_laissee_passer` — la même
  candidate est **refusée** par l'épreuve de causalité, qui voit 110 signaux du passé changer
  quand on tronque la série.

⇒ **Une liste de motifs interdits attrape ce qu'elle connaît ; la causalité attrape ce qu'on
n'avait pas prévu.** `signaux(df[:t])` doit rendre exactement `signaux(df)[:t]` : une
fonction causale ne peut pas produire autre chose sur un préfixe, puisque chaque ligne ne
dépend que de son passé. C'est vrai de tout look-ahead, y compris ceux qu'aucune liste ne
prévoit.

⚠️ **Le sas n'est pas un bac à sable.** Qui peut écrire dans `beta/candidates/` peut déjà
exécuter du code sur cette machine. Il attrape des **erreurs**, pas un adversaire. On relit
le code déposé — surtout celui qu'un modèle vient d'écrire.

### Vérifié en vrai, pas seulement en test

`qwen2.5:7b` sur Ollama, prompt « croisement de deux moyennes mobiles » : candidate conforme
et **causale** du premier essai (`rolling` + `shift(1)` positif), sas et épreuve passés,
réserve correctement levée sur l'hypothèse non préenregistrée. Le fichier de démonstration a
été retiré — il n'avait pas de préenregistrement, donc rien à mesurer.

---

## I — la boîte à idées (ouverte et fermée le 19/08, demande de Jonas)

Question de Jonas : **« où je peux suggérer des idées ? »** Réponse honnête avant ce soir :
nulle part de confortable. Éditer `scripts/preenregistrer.py` demandait déjà de savoir
formuler métrique + règle de décision + MDE ; `beta_register_edge` **préenregistre**, donc
avance le compteur définitivement ; et une idée dite en conversation finissait dans
`DECISIONS.md`, qui n'est pas fait pour ça.

Le fond du problème : **préenregistrer coûte cher, donc on ne note rien, donc on perd tout.**
D'où deux étages et un seul point de bascule.

```
IDEES.jsonl          gratuit, sans forme imposée — on y jette tout
    |
    | promouvoir()   <- LE moment où ça coûte : le compteur avance d'un cran
    v
EXPERIMENTS.jsonl    hypothèse falsifiable, métrique primaire, règle de décision
```

| # | Chantier | Statut | Effort |
|---|---|---|---|
| ~~I1~~ | ~~`protocole/idees.py` + `IDEES.jsonl` — ajouter / lister / écarter / promouvoir~~ | ✅ fermé 19/08 | S |
| ~~I2~~ | ~~`beta.py idee`, encart dans l'onglet Protocole, outils MCP `beta_suggest_idea` et `beta_ideas`~~ | ✅ fermé 19/08 | S |

Ce que la **promotion** force à écrire est exactement ce qui manque à une idée pour devenir
mesurable. Une idée qu'on n'arrive pas à promouvoir n'est pas une mauvaise idée : c'est une
idée qu'on n'a pas encore su rendre falsifiable, et le dire est déjà un résultat.

⚠️ Une idée **écartée** ne disparaît jamais du fichier, et son motif est obligatoire : savoir
ce qu'on a décidé de **ne pas** tester, et pourquoi, vaut autant que savoir ce qu'on a testé.

⚠️ Côté MCP, les deux outils sont volontairement asymétriques dans leur description :
`beta_suggest_idea` annonce « GRATUIT », `beta_register_edge` annonce qu'il avance le
compteur et renvoie vers l'autre. Un agent choisit son outil sur sa description — sans cette
asymétrie, il préenregistrerait dix idées pour en mesurer une, et ruinerait la batterie pour
les neuf autres. Vérifié par test.

---

## C — le banc COMPARATIF (ouvert et fermé le 19/08, correction de Jonas)

Correction de Jonas, mot pour mot : **« un banc de multitesting, ce n'est pas que à
l'intérieur d'une stratégie, c'est aussi comparer plusieurs stratégies entre elles »**. Il
avait raison, et c'était plus grave que décrit : la machinerie comparative existait (S7, S9,
`pipeline.cribler` en deux passes) mais **n'avait jamais comparé quoi que ce soit** — une
seule candidate existe, donc S7 rendait `nan` et S9 passait « faute d'objet ». Aucune vue ne
mettait deux stratégies côte à côte, et `diversification.matrice()` n'était appelée nulle
part hors des tests.

| # | Chantier | Statut | Effort | Ce que ça montre |
|---|---|---|---|---|
| ~~C1~~ | ~~`stats/comparaison.py` — classement, S7, matrice, redondances~~ | ✅ fermé 19/08 | M | qui est devant, et si le devant veut dire quelque chose |
| ~~C2~~ | ~~**AritV1 en référence** : sa courbe reconstruite avec la MÊME convention de sizing~~ | ✅ fermé 19/08 | S | « est-ce mieux que ce qui tourne déjà ? », que S8 ne posait pas |
| ~~C3~~ | ~~Onglet **Comparaison** : classement, courbes superposées, matrice, S7~~ | ✅ fermé 19/08 | M | la comparaison devient lisible, pas seulement calculée |
| ~~C4~~ | ~~`beta.py comparer` — relit `data/runs/`, ne relance rien~~ | ✅ fermé 19/08 | S | deux stratégies mesurées à trois semaines d'écart se comparent sans être remesurées |

**Trois décisions de conception qui portent le tout :**

1. **La comparaison relit `data/runs/`, elle ne dépend pas d'un criblage.** Exiger que deux
   stratégies soient mesurées dans le même lot pour être comparables, c'est garantir que la
   comparaison ne se fait jamais.
2. **Un seul run par candidate, le plus récent de son split.** Deux runs de la même
   stratégie ne sont pas deux stratégies : les compter double gonflerait l'univers de S7
   avec une copie de lui-même, et la matrice afficherait fièrement 1,00 entre une candidate
   et elle-même.
3. **Le classement est trié sur le R moyen, jamais sur l'issue.** Trier par verdict mettrait
   en tête les candidates qui ont eu la chance qu'une porte ne tourne pas.

⚠️ **AritV1 se compare par sa COURBE, jamais par son R par trade.** Ses sorties sont les
siennes (trailing, portes de gestion, protections freqtrade) ; celles d'une candidate
viennent de la triple barrière du moteur. Les moyenner ensemble serait une faute. Sa courbe
est donc reconstruite avec le **même sizing** que les candidates (risque fixe de 1 %, sans
composition) — sinon l'écart mesurerait la convention de sizing avant de mesurer la
stratégie. La réserve est écrite dans chaque classement, et une seconde prévient que ses
52 trades rendent son Sharpe journalier instable.

### Premier résultat comparatif du banc

R2 contre AritV1, 1 419 jours communs : **corrélation 0,008** — décorrélées, ce qui est la
moitié qui compte de la demande F1 (« diversifier les formes d'investissement ») — mais
**−296 pts de rendement**. Décorrélée et perdante n'est pas une candidate : c'est une mesure
de plus qui dit non.

**Vérifié par test, et c'est le seul contrôle qui compte pour un banc comparatif** : sur
vingt séries de bruit pur, S7 **ne sacre pas** la meilleure (p > 0,05) ; avec une vraie
gagnante glissée dedans, il la **voit** (p ≤ 0,05, et c'est bien elle qu'il nomme).

---

## Dettes connues

| # | Dette | Statut | Conséquence si on l'oublie |
|---|---|---|---|
| ~~T1~~ | ~~Repo distant privé non créé~~ | ✅ fermée 19/08 — `github.com/jofari/BETA-`, rebasé sur le commit initial et poussé | — |
| **T2** | **venv partagé avec ARIT** (`C:\Users\jofar\venvs\arit`) | 🔴 ouverte | une mise à jour pour ARIT casse BETA, ou l'inverse |
| **T3** | **Bornes de fin hétérogènes** — ~~LINK/XRP au 18/08, les 4 paires d'ARIT au 04/08~~ ⇒ **mise à jour 11/09 : LINK/XRP au 11/09, les 4 paires d'ARIT au 24/08** (écart de 18 jours, contre 14 avant) | 🔴 ouverte | un run multi-paires s'arrête à la borne commune sans le dire ; visible dans le dashboard, à ne pas oublier au moment de conclure |
| **T4** | **`ts_utc` du journal d'ARIT ment** sur les événements `gestion` (heure d'exécution du backtest, pas de la bougie). Contourné côté BETA par `signal_id`. ⚠️ **La correction appartient à ARIT** : inscrite là-bas le 19/08 sous **T4-ARIT** (`ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` § MISE À JOUR DU 2026-08-19) — cause exacte : `ev_gestion()` ne pose pas de `ts_utc`, `write()` retombe sur `_now_iso()` | 🔴 ouverte (contournée ici, **non corrigée** à la source) — **revérifiée le 11/09 dans `journal.py` d'ARIT : `ev_gestion` ne pose toujours pas de `ts_utc`** | à corriger **à la source**, côté ARIT, sinon chaque nouveau consommateur retombera dedans |
| **T5** | **Le pont freqtrade n'a pas ses données** — `--datadir` pointe sur `data/raw`, où seuls LINK et XRP sont en feather ; BTC/ETH/SOL/BNB ne vivent qu'en parquet dans le lake | 🔴 ouverte | la confirmation portefeuille (M3) ne peut tourner que sur 2 paires sur 6. Faire lire `ARIT2.0/user_data/data/` à freqtrade lui ferait écrire dans le dossier d'ARIT — **interdit par l'invariant n° 1** — donc à résoudre par un export feather depuis le lake |
| **T6** | **Chemins synthétiques rejoués sur une seule paire** (la première du run) | 🟠 ouverte, assumée | le coût est linéaire en nombre de paires ; la réserve est écrite dans chaque verdict, elle n'est donc pas silencieuse |
| ~~T9~~ | ~~**S1 n'est JAMAIS exécutée par le pipeline.**~~ `pipeline.executer` ne passe pas `famille=` à `batterie.evaluer`, donc `portes["S1_benjamini_hochberg"]` reste `None`. Or `issue()` n'accorde CONFIRMEE que si **les neuf** portes ont tourné. ⇒ **aucune candidate ne peut être confirmée aujourd'hui : le plafond du banc est INDECIDABLE.** Vérifié sur le run `e9238689db9b`. Corriger demande de décider ce qu'est la famille pour un criblage — le lot du run, ou les hypothèses déclarées (`famille_taille`) comme le fait `scripts/mesurer.py`. Deux seuils différents, donc un arbitrage, cousin de A1 | ✅ **fermée 20/08** — `cribler()` construit la famille du lot et la passe à `batterie.evaluer` | — |
| ~~T10~~ | ~~**Le criblage ne clôt pas l'expérience.**~~ R2 est mesurée (INFIRMEE) mais `EXPERIMENTS.jsonl` la dit toujours `preenregistre` : `pipeline` écrit le verdict dans `data/runs/` et `RUNS.jsonl`, jamais `experiences.clore()`. R1 et R6 ne sont closes que parce que `scripts/mesurer.py` le fait à la main | ✅ **fermée 20/08** — `pipeline` appelle `marquer_mesuree()` : statut `mesure`, la clôture reste un geste explicite | — |
| ~~T8~~ | ~~**Le compteur d'essais compte les HYPOTHÈSES, pas les MESURES.**~~ `compteur()` = 30 + nombre d'ids distincts dans `EXPERIMENTS.jsonl`. Tant qu'il y avait une candidate par hypothèse les deux nombres coïncidaient ; l'atelier casse l'égalité — dix candidates sous R7, c'est dix tests et **un seul point de compteur**. `RUNS.jsonl` (racine, append-only, ajouté le 19/08) **mesure** l'écart, `beta.py doctor` l'affiche, et **rien ne change encore** : faire porter N par les runs durcirait rétroactivement tous les verdicts déjà rendus. ⇒ arbitrage de Jonas, `DECISIONS.md` § A1 | ✅ **fermée 20/08** — arbitrage A1 tranché (b), `compteur()` porte les mesures. N vaut toujours 36 : rien n'est réécrit | — |
| **T11** | **Les runs de `data/runs/` ne couvrent pas tous la même fenêtre** — ceux d'avant le 11/09 ont été mesurés sur un lake qui s'arrêtait au 04/08 (4 paires) et au 18/08 (LINK/XRP) | 🟠 ouverte, assumée | aucune mesure ne ment — la comparaison de courbes aligne sur la période commune (`stats/comparaison.py:_ecart_contre`) et S7 tronque à la plus courte (`stats/multitest.py:_matrice`, **par index, pas par date**) — mais un run rejoué aujourd'hui n'est plus le jumeau exact de celui d'août, alors que `run_id` est déterministe sur l'hypothèse et le code |
| **T7** | **L'équity à risque fixe non composé peut passer sous zéro** — R2 finit à −83 750 sur 100 000 | 🟠 ouverte, assumée | mathématiquement cohérent, physiquement impossible. Le choix rend deux candidates comparables entre elles ; le compounding se mesure côté freqtrade (M3), une seule fois |


---

## D5-D7 — les données qui manquent, et qui bloquent trois hypothèses

Ouverts le 19/08. Ce ne sont plus des chantiers d'outillage : le banc d'essai fonctionne,
ce sont ses **entrées** qui manquent. Trois hypothèses préenregistrées sont à l'arrêt
faute de séries, et aucune ne peut être mesurée en attendant.

| # | Chantier | Débloque | Effort | Comment |
|---|---|---|---|---|
| **D5** | **Taux de financement** des perpétuels, 6 paires, même profondeur d'historique que l'OHLCV | **R3** (portage / funding) | M → **S/M depuis le 11/09** | ⚡ **4 paires sur 6 sont déjà sur le disque d'ARIT** : `{BTC,ETH,SOL,BNB}_USDT_USDT-1h-funding_rate.feather`, même dossier que l'OHLCV importé ⇒ import en lecture seule, zéro réseau. Restent LINK et XRP par `ccxt.fetch_funding_rate_history`. Table de plus au lake, avec son catalogue de trous |
| **D6** | **Séries macro** (DXY, taux, fear & greed) au pas journalier | **R4** (macro seule) | ~~M~~ → **S depuis le 11/09** | ⚡ **plus besoin de les extraire du journal** : ARIT les a **en clair sur disque** depuis le 24/08 dans `ARIT2.0/user_data/data/macro/` (`dxy.csv`, `taux_fed.csv`, `fear_greed.json`, `nasdaq100.csv`, `stablecoins.json`, `funding_BTCUSDT.json`, `funding_ETHUSDT.json`, `btc_daily.json`). Lecture seule, aucun réseau, invariant n° 1 intact |
| **D7** | **Séries spot** des mêmes 6 paires | **R5** (spot vs perpétuel) | S | `freqtrade download-data --trading-mode spot`, le chemin existe déjà dans `lake/telechargement.py` |

⚠️ **D6 avant D5.** Les features macro sont déjà sur le disque, dans le journal d'ARIT :
c'est le seul des trois qui ne demande aucun appel réseau. À faire en premier pour cette
seule raison.

## AR — l'auto-recherche (ouverte et fermée le 20/08, demande de Jonas)

Demande, mot pour mot : « j'aimerais connecter une première auto-recherche ».

L'outillage était déjà là — atelier (A1-A6), pont MCP (P1-P5), moteur, batterie. Ce qui
manquait n'était pas de la plomberie : **trois dettes rendaient la première boucle
malhonnête**, et elles ont été fermées d'abord (T8, T9, T10 ci-dessus). Lancer la boucle
avant, c'était produire des verdicts à jeter.

| # | Chantier | Statut | Effort | Ce que ça fait |
|---|---|---|---|---|
| ~~AR1~~ | ~~`recherche/auto.py` — étage GRATUIT (`proposer`)~~ | ✅ fermé 20/08 | S | le modèle local note des hypothèses dans `IDEES.jsonl`, **le compteur ne bouge pas**. Rien n'est mesuré, rien n'est préenregistré |
| ~~AR2~~ | ~~`recherche/auto.py` — étage COÛTEUX (`lancer`)~~ | ✅ fermé 20/08, **exécuté pour de vrai le 20/08** (lot R7 ci-dessous) | M | une candidate écrite par intention, sas + épreuve + dépôt, puis criblage du **lot entier** en une fois |
| ~~AR3~~ | ~~`beta.py auto proposer` / `auto cribler`~~ | ✅ fermé 20/08 | S | les deux étages séparés jusque dans la ligne de commande |
| ~~AR4~~ | ~~`tests/test_auto.py`~~ | ✅ fermé 20/08 | M | 30 tests, dont **8 sur ce que la boucle refuse** |

### Les trois verrous, et pourquoi ils sont dans le code plutôt que dans la doctrine

1. **La boucle ne préenregistre JAMAIS.** Elle exige une hypothèse déjà écrite et refuse de
   démarrer sinon. C'est la séparation que le pont MCP fait déjà entre `beta_suggest_idea`
   (gratuit) et `beta_register_edge` (coûteux) : il n'y a aucune raison que la boucle locale
   dispose d'un chemin que l'agent distant n'a pas. Un test lit le source du module et
   vérifie qu'aucun appel à `preenregistrer()` n'y figure.
2. **Le budget est déclaré AVANT de générer**, borné par la `famille_taille` du
   préenregistrement. Écrire dix candidates puis déclarer une famille de dix revient à ne
   pas corriger du tout : le *m* de Benjamini-Hochberg doit être fixe avant de voir les
   p-values, sinon il s'ajuste tout seul à ce qui arrange.
3. **Le modèle local n'invente pas les hypothèses, il écrit des variantes.** L'intention
   vient de Jonas ou d'une idée promue ; ce que la boucle automatise, c'est le passage de
   l'intention au code — la partie où une machine est utile et où elle ne décide rien.

⚠️ **Le sas n'est toujours pas un bac à sable** (§ A). Ce qu'un modèle a écrit et que la
boucle a déposé dans `beta/candidates/` est **à relire**. La commande le rappelle à chaque
fin de lot.

### Le premier vrai lot — 20/08, et ce qu'il a appris

`auto cribler --experience R7 --intentions intentions/R7.txt --timeframe 4h`, ollama /
qwen2.5:7b, 6 paires, 4h. **Tout ce qui devait tenir a tenu** : 4 intentions déclarées
avant génération, budget borné par `famille_taille` = 4, N figé à 39 pour tout le lot,
S1 exécutée, R7 passée à `mesure` au registre, 2 runs journalisés, compteur 37 → 38.
Deux candidates refusées par le sas (`aucun signal sur la tranche témoin`, `KeyError: 20`),
deux mesurées, **les deux INFIRMEE**.

| candidate | n | R moyen | MDE | portes échouées |
|---|---|---|---|---|
| `auto_r7_01` | 2 961 | −0,1161 | 0,0777 | S1, S2, S3, S4, S6, S7, S8 |
| `auto_r7_03` | 102 | +0,3936 | 0,4687 | S2, S7, S8 |

⚠️ **Le résultat du lot n'est pas dans ce tableau.** À la relecture — celle que la commande
réclame à chaque fin de lot — **aucune des deux candidates n'implémente R7** :

- `auto_r7_01` écrit `meche_basse = (open - close).abs().min() - low` : `.min()` sur une
  Series rend un **scalaire**, donc la « mèche » est une constante moins le low, et
  l'« ATR » est cette même quantité décalée d'un cran. Le code signale sur ~99 % des
  bougies sur série témoin. Ce n'est pas un détecteur de cascade, c'est un détecteur de
  rien ;
- `auto_r7_03` déclenche sur `close − close.shift(1) > 3·ATR` — un **écart de clôture**,
  pas une mèche — et prend le sens du **momentum**, alors que l'hypothèse dit retour à la
  moyenne. Il teste le contraire de ce qui est écrit au préenregistrement.

Les deux verdicts INFIRMEE sont des verdicts **valides** — le banc a fait son travail, il a
tué — mais ils ne mesurent pas R7. Ils ont coûté 2 crans de compteur, définitivement, pour
mesurer du code écrit de travers. **C'est le vrai enseignement du premier lot, et il vaut
mieux que les chiffres.**

| # | Dette découverte | Statut | Ce que ça coûte |
|---|---|---|---|
| **T12** | **Le sas valide du code qui ne teste pas l'hypothèse.** Il attrape le look-ahead, l'état caché, le chargement de données — des erreurs de **protocole**. Il ne peut rien dire d'une erreur de **sens** : `auto_r7_03` est causal, isolé, sans état, et mesure autre chose que ce qui est préenregistré | 🔴 ouverte | chaque candidate hors sujet consomme un cran de compteur et durcit le seuil de toutes les autres. C'est le coût le plus bête possible |
| **T13** | **`.min()` / `.max()` / `.mean()` sur toute la série ne sont pas dans les motifs du sas**, et l'épreuve de causalité ne les a **pas** attrapés ici — par accident numérique : le code est si cassé que ses signaux sont quasi constants, donc tronquer la série ne les change pas. La garde de forme et la garde de comportement ont raté le même trou en même temps | 🔴 ouverte | un vrai look-ahead statistique global peut passer les deux étages |
| **T14** | **qwen2.5:7b ne traduit pas une intention en français en stratégie correcte.** 2 refus sur 4, et 2 contresens sur les 2 qui passent : **0/4 utilisable** | 🔴 ouverte, mesurée | l'atelier abaisse le coût d'écrire une candidate, pas celui d'en écrire une **juste**. Tant que ce taux tient, la boucle produit surtout de la dette de compteur |

**Ce qu'il ne faut pas en conclure.** Ni que la boucle est inutile — elle a refusé, mesuré,
journalisé et compté exactement comme prévu — ni que R7 est infirmée : **R7 n'a pas été
testée**. Elle est au registre en `mesure` avec deux runs qui ne la concernent pas, et
c'est une trace honnête de ce qui s'est réellement passé.

Les deux réserves ouvertes en même temps ont été **levées le 20/08**, et une troisième est
apparue en les levant :

| # | Réserve | Statut |
|---|---|---|
| ~~AR-a~~ | ~~`lancer()` criblait `registre.par_hypothese()`, donc **toutes** les candidates de l'hypothèse, pas seulement le lot écrit — le contrôle `budget <= famille_taille` ne bornait pas ce qui était réellement criblé~~ | ✅ **fermée 20/08** — `_lot_ecrit()` ne charge que les modules déposés par ce lot, et écarte celles qui déclarent une autre hypothèse |
| ~~AR-b~~ | ~~le `run_id` de `scripts/mesurer.py` n'était déterministe que **dans la journée** (`{id}-mesure-{date}`) : remesurer R1 le lendemain coûtait un cran de compteur sans que rien n'ait changé~~ | ✅ **fermée 20/08** — haché sur l'**empreinte du code de la mesure**, même convention que `Candidate.empreinte`. Il ne monte que si le code a changé, et alors c'est bien un nouveau test |
| ~~T11~~ | ~~**Le registre mesurait l'ANCIEN code après un dépôt `--ecraser`.**~~ Trouvée en fermant AR-a, jamais soupçonnée avant | ✅ **fermée 20/08** — voir ci-dessous |

**T11 est la plus vicieuse des trois**, et c'est celle qu'on ne cherchait pas. `registre.
charger()` faisait un `import_module` : un module déjà importé restait en mémoire avec son
code précédent, donc le criblage mesurait la version d'avant **en publiant l'empreinte de
la nouvelle**. Un verdict faux, et signé. `ecraser=True` étant le défaut de la boucle, le
cas se serait présenté dès la deuxième relance.

Un `reload` ne suffisait pas : le cache de bytecode valide une entrée sur
(mtime **en secondes**, taille en octets) de la source. Deux variantes générées à la chaîne,
écrites dans la même seconde et de même longueur, lui sont **indiscernables** — et le piège
survit à un redémarrage du processus. Le `.pyc` est donc supprimé avant chaque chargement.
Le test qui l'attrape échouait exactement pour cette raison : deux versions de même taille.

### Ce que la fermeture de T9 a changé, concrètement

Vérifié sur un re-criblage réel de R2 le 20/08 : premier passage `[non exécutée]
S1_benjamini_hochberg`, second passage `[ÉCHEC]`. **La porte tourne enfin** — R2 reste
infirmée, mais pour la première fois le banc a un chemin vers CONFIRMEE au lieu d'un
plafond à INDÉCIDABLE. Le criblage a aussi fait passer R2 de `preenregistre` à `mesure` au
registre (T10), et le compteur est resté à 36 — `run_id` déterministe, donc pas d'essai
fabriqué par une remesure à l'identique (A1).

---

## Ce qui reste, après le 19/08 (soir)

1. ~~**T8 / `DECISIONS.md` § A1**~~ — ✅ **tranché le 20/08 : (b), N porte les mesures.**
   L'atelier peut tourner en série sans que la batterie perde son sens.
2. **D5-D7** — sans quoi R3, R4 et R5 restent à l'arrêt.
3. **T5** — sans quoi le verdict portefeuille ne couvre que 2 paires sur 6.
4. ~~**T9 / T10**~~ — ✅ **fermées le 20/08.** S1 s'exécute sur la famille du lot, et
   le registre dit enfin ce qui a été mesuré. Le banc a un chemin vers CONFIRMEE.
5. **Une DEUXIÈME candidate.** Le moteur en accepte autant qu'on veut, l'atelier sait les
   écrire, le banc comparatif sait les mettre en regard — et il n'en existe toujours
   **qu'une**. Tant que c'est le cas, S7 n'a pas d'objet, S9 non plus, et la moitié
   comparative du banc tourne à vide. Deux idées attendent dans `IDEES.jsonl` (I1 funding
   extrême, I2 cascade de liquidations) ; **les promouvoir est un geste de Jonas**, parce
   que c'est lui qui décide ce qui vaut un cran de compteur.
   Le goulot n'est plus l'outillage : c'est le nombre d'hypothèses falsifiables qu'on est
   prêt à écrire avant de regarder les chiffres.

---

## O — l'observabilité à distance (ouverte le 20/08, décision de Jonas sur G2)

**Demande, mot pour mot** : « intègre le suivi à distance dans le projet BETA si possible,
sinon dans un autre dashboard, mais **il faut pouvoir suivre ça sans avoir accès au PC**
(bientôt on aura un VPS à disposition ce qui simplifiera la tâche) ».

C'est un **déplacement volontaire de la frontière** posée le 19/08, qui disait « F2 / G2 / G8
restent chez ARIT ». La version précisée : **ARIT produit les événements, BETA les affiche.**
Ce qui reste chez ARIT, c'est la **relance** du dry-run et sa survie aux redémarrages — le bot,
pas sa fenêtre. **BETA continue de ne jamais écrire dans `ARIT2.0`** (invariant n° 1 intact :
le bloc O est en lecture seule sur le journal et sur `user_data/state/`).

### ⚠️ Le piège qui commande toute la conception

`ARIT2.0/services/watchdog.py` surveille déjà le heartbeat et alerte si le silence dépasse
10 min. **Il meurt avec la session Windows.** Un dashboard hébergé sur la même machine hérite
exactement du même angle mort :

> **Le silence y est indiscernable de la santé.** Une page qui ne répond pas peut vouloir dire
> « bot arrêté », « PC éteint », ou « tout va bien mais le réseau est coupé ».

⇒ Tant que le VPS (ARIT `G8`) n'existe pas, le seul suivi distant honnête est un **push
sortant** avec un **signal de vie positif et périodique** — jamais une page à consulter. Le
webhook Discord existe déjà et Jonas le lit ; les limites sont connues (`webhook discord
(embeds et limites)` : **4096 caractères ou rien**, tableaux Markdown non rendus).

| # | Chantier | Effort | Ce que ça fait |
|---|---|---|---|
| **O1** | **Battement sortant** — un push périodique qui dit « je suis vivant, voici l'état », depuis la machine qui héberge le bot | S | Transforme l'absence de nouvelles en information. Sans O1, O2 et O3 mentent par omission |
| **O2** | **Lecteur d'état ARIT en lecture seule** — `user_data/state/heartbeat`, `logs/decisions/*.jsonl`, `macro_state.json` → une vue « santé + dernières évaluations » | M | BETA sait déjà lire le journal d'ARIT (c'est sa table `evaluations`). Réutiliser, ne pas réécrire |
| **O3** | **Onglet « Live » du dashboard**, patte graphique existante | S | La consultation confortable **une fois** qu'on est devant un écran — jamais le canal d'alerte |

⚠️ **Aucune exposition publique sans arbitrage explicite de Jonas.** Le dashboard tourne sur
`127.0.0.1:7474` et affiche des données privées (positions, équité, signaux). Le rendre
joignable de l'extérieur — port ouvert, tunnel, hébergement — est une **décision de sécurité**,
pas un détail d'implémentation : elle attend une réponse, elle ne se prend pas par défaut.
En attendant, **O1 seul** (push Discord) donne déjà « suivre sans accès au PC » sans rien
exposer.

### Ce qui reste à trancher

| # | Question | Défaut proposé |
|---|---|---|
| **O-a** | **Le canal.** Push Discord seul (rien d'exposé), ou aussi une page joignable de l'extérieur ? | **Discord seul** tant qu'il n'y a pas de VPS |
| **O-b** | **La cadence du battement.** Toutes les heures ? 4 h ? Une fois par jour ? | **4 h**, + une alerte immédiate sur événement (entrée, sortie, circuit breaker) |
| **O-c** | **Où tourne O1** tant qu'il n'y a pas de VPS — sur le PC (meurt avec lui, mais son silence devient un signal) ou dans une routine cloud ? | **Sur le PC**, avec le silence traité comme une panne côté lecteur |

---

## MISE À JOUR DU 2026-09-11 — ce qu'ARIT a appris pendant que BETA dormait

BETA est figé depuis le 21/08 (dernier commit `c03f5ab`, R8 infirmée). ARIT, lui, a produit
**20 commits entre le 20/08 et le 07/09**, dont quatre sessions de recherche qui touchent
directement des hypothèses préenregistrées ici. Ce bloc verse ces données dans BETA : le lake
d'abord, les hypothèses ensuite, les dettes pour finir.

⚠️ **Rien de ce qui suit n'est une mesure BETA.** Ce sont des résultats obtenus **ailleurs**,
sur 4 actifs (jamais LINK ni XRP), avec des sorties qui ne sont pas la triple barrière du
moteur. Ils déplacent ce qu'on **croit**, pas ce qu'on a **établi** — et ils ne consomment
aucun cran de compteur, qui reste à **41**.

### 1. Le lake a été rafraîchi (11/09)

`scripts/build_lake.py`, import ARIT + delta réseau. Ce qui change :

| paires | borne de fin avant | borne de fin après | d'où |
|---|---|---|---|
| BTC · ETH · SOL · BNB | 2026-08-04 | **2026-08-24** | ARIT a re-téléchargé ses feathers le 24/08 (import, zéro réseau) |
| LINK · XRP | 2026-08-18 | **2026-09-11** | `freqtrade download-data`, delta seulement |

Couverture **100 % partout, aucune série suspecte**, aucun trou. Repères : BTC 4h passe de
15 131 à 15 251 bougies, BTC 5m de 726 304 à 732 054.

⚠️ **T3 n'est pas fermée, elle a bougé** : l'écart entre les deux groupes passe de 14 à
**18 jours** (24/08 contre 11/09). Un run multi-paires s'arrête toujours à la borne commune —
`beta.py doctor` l'affiche désormais au **2026-08-23**, la veille de la borne intraday, parce
que c'est la série `1d` d'ARIT qui s'arrête là.

⚠️ Tout ce qui vient d'entrer est postérieur au **01/01/2025**, donc tombe en **hold-out**.
Le hold-out n'est pas brûlé pour autant — personne ne l'a regardé — mais les runs de
`data/runs/` mesurés avant aujourd'hui l'ont été sur une fenêtre plus courte (⇒ **T11**).

### 2. Ce que les mesures d'ARIT font aux hypothèses préenregistrées ici

**R3 — portage / funding : sa prémisse est attaquée.** R3 a été préenregistrée sur « 86 % du
profit de MacroFlip venait du funding ». ARIT a mesuré le funding sur 4 actifs, 2019-2026
(`research/pertinence_donnees_2026-09-05/RAPPORT.md` § 2) : **IC Spearman funding → retour
futur entre −0,06 et +0,001**, soit inerte. Le seul effet net est le squeeze des shorts aux
extrêmes négatifs, **visible sur BTC seul** (+1,88 % à 7 j) et estompé ailleurs. Le rapport
d'ARIT écrit lui-même que le chiffre des 86 % est « à revérifier ». ⇒ arbitrage **B-a**
(`DECISIONS.md`) — R3 reste préenregistrée tant que Jonas n'a pas tranché : on ne retire pas
une hypothèse du registre sur un résultat obtenu ailleurs.

**R4 — macro seule : D6 est débloqué, et l'hypothèse devient plus intéressante, pas moins.**
Les séries macro ne sont plus à extraire du journal : ARIT les a **sur disque en clair**
depuis le 24/08, dans `ARIT2.0/user_data/data/macro/` — `dxy.csv`, `taux_fed.csv`,
`fear_greed.json`, `nasdaq100.csv`, `stablecoins.json`, `funding_BTCUSDT.json`,
`funding_ETHUSDT.json`, `btc_daily.json`. Lecture seule, aucun réseau, invariant n° 1 intact.
Et le 05/09, ARIT a **retiré son multiplicateur macro** (B1, option (b) : TREND ⇒ ×1,0) au
motif que la macro est une donnée faible. ⇒ BETA est désormais le seul endroit où la question
« la macro seule vaut-elle quelque chose ? » peut recevoir une réponse mesurée (arbitrage **B-b**).

**R6 — `news_window` : la boucle s'est fermée côté ARIT.** Le 06/09, ARIT a **neutralisé sa
porte news en backtest** (`skip_news`), pour deux motifs qui recoupent exactement ce que R6
avait trouvé le 19/08 : `macro_state` n'est pas point-in-time, et la source est incomplète.
Le chiffre « 91,75 % de tout ce qui est rejeté » reste à corriger partout où il est cité —
c'étaient des lignes de journal, pas des signaux.

**D5 — funding : la moitié est gratuite.** ARIT a sur disque
`{BTC,ETH,SOL,BNB}_USDT_USDT-1h-funding_rate.feather`, même dossier que l'OHLCV importé.
4 paires sur 6 sans un appel réseau ; LINK et XRP resteraient à télécharger. Ça ne ferme pas
D5 — un lake à trous déclarés exige le même catalogue pour cette table que pour les autres —
mais ça en divise le coût.

### 3. Le résultat qui vaut pour le banc, et qu'aucune mesure BETA n'a

**Le momentum de prix 14-60 jours bat le buy-and-hold sur les 4 actifs** (Sharpe ~1,0 contre
0,55-0,83), **et il survit hors échantillon** (train < 2023 → holdout ≥ 2023 : BTC 1,03 → 0,98,
ETH 1,30 → 0,83, SOL 1,69 → 0,89, BNB 1,14 → 0,78). Le pic est un **plateau** entre 14 et
60 jours, pas un point isolé de balayage — c'est ce qui distingue un effet d'un artefact de
grille.

ARIT en conclut « momentum = beta, pas d'alpha », parce qu'il compare à un buy-and-hold
long-only. **BETA a exactement l'outil qui tranche autrement** : S8 (B&H imposé), la triple
barrière, et **6 paires dont 2 qui n'ont jamais servi à cette mesure**. C'est la deuxième
candidate qui manque au banc depuis le 19/08 — celle sans laquelle S7 et S9 tournent à vide.
Notée **I16** (gratuit) ; la promouvoir est un geste de Jonas (arbitrage **B-c**).

Trois autres idées versées depuis la même session ARIT, toutes gratuites :

| # | Idée | Pourquoi elle n'est pas promue d'office |
|---|---|---|
| **I13** | **Conditionnement de régime** plutôt que chasse à l'indicateur — 6 indicateurs testés, 6 fois le même méta-pattern : IC ≈ 0, contrarien aux extrêmes, régime-dépendant | Multiplie les degrés de liberté, donc les faux gagnants. Exige une partition de régimes **écrite avant**, sinon S1 et S2 ne protègent plus de rien |
| **I14** | **Croissance de l'offre de stablecoins** — IC +0,11 à 30 j, et **indépendante du prix** (IC partiel +0,117 après contrôle du momentum) | Échoue **déjà** hors échantillon (train +0,223 → holdout −0,094), cause plausible : la supply a plafonné vers 323 Md$. La promouvoir = payer un cran pour re-mesurer un échec connu |
| **I15** | **Congestion du mempool** — seul on-chain dont l'IC survive au contrôle du momentum (+0,28 brut → **+0,07** partiel) | Probablement sous le MDE du banc à 6 paires. À vérifier avant, c'est le genre d'idée que le MDE tue en une ligne |

⚠️ **Le leurre à retenir de cette session ARIT** : les adresses actives affichent l'IC brut le
plus fort de toute l'étude (**+0,31**) et tombent à **+0,03** une fois le momentum contrôlé —
90 % de redondance avec le prix. Tout signal externe candidat ici doit passer ce contrôle
**avant** de coûter un cran de compteur.

Et la leçon de méthode, qui est la nôtre : l'IC suggérait un filtre de volatilité, le backtest
l'a **infirmé** (Sharpe 1,22 → 0,55). **Un IC élevé n'est pas un P&L.**

### 4. Dettes — ce qui a été vérifié aujourd'hui

- **T4 est toujours ouverte à la source.** Vérifié dans
  `ARIT2.0/user_data/strategies/arit_lib/journal.py` le 11/09 : `ev_gestion` ne pose toujours
  pas de `ts_utc` (« `ts_utc` via `write()` », l. 395), là où `ev_signal`, `ev_gate` et
  `ev_sortie` le posent. Le contournement BETA par `signal_id` reste nécessaire.
- **T11 — nouvelle** : les runs de `data/runs/` antérieurs au 11/09 couvrent une fenêtre plus
  courte que ceux d'après. Vérifié en lisant le code plutôt qu'en le supposant : la comparaison
  de courbes aligne déjà sur la **période commune** (`stats/comparaison.py:_ecart_contre`) et S7
  tronque à la plus courte (`stats/multitest.py:_matrice`) — **par index, pas par date**. Donc
  rien ne ment ; ce qui change, c'est qu'un run rejoué aujourd'hui n'est plus le jumeau exact de
  celui d'août, alors que `run_id` est déterministe sur l'hypothèse et le code.

### 5. Ce que ça ne change pas

Le banc n'a toujours **qu'une seule candidate mesurée**, S7 et S9 tournent donc toujours à
vide, et aucune des quatre idées ci-dessus ne change ça tant qu'elle n'est pas promue. Le
goulot reste ce qu'il était le 20/08 : **le nombre d'hypothèses falsifiables qu'on est prêt à
écrire avant de regarder les chiffres** — pas l'outillage, et maintenant plus tout à fait les
données.
