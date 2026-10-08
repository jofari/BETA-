# DECISIONS.md — BETA : décisions OUVERTES de Jonas

> **But** : un arbitrage de Jonas ne doit jamais vivre uniquement dans une conversation.
> Ce fichier ne contient QUE ce qui attend encore quelque chose — une réponse de Jonas, ou du
> code à écrire. Il se lit en entier en début de session, avant tout code.
>
> **Même règle de tenue qu'ARIT** (`ARIT2.0/DECISIONS.md`, règle du 17/08) : une décision
> appliquée, fermée ou abandonnée **disparaît d'ici dans la même session**, après avoir déposé
> ce qu'elle laisse de durable à sa destination pérenne (travail restant → `CHANTIERS.md`,
> piège ou mesure → les notes du dépôt). La trace des fermées est dans `git log -p -- DECISIONS.md`.
>
> **Frontière avec ARIT** (19/08) : les décisions qui portent sur **AritV1 en production**
> (levier, vétos macro, calendrier, dry-run, VPS, ablations de scores) restent dans
> `ARIT2.0/DECISIONS.md`. Celles qui portent sur **le banc et la recherche d'autres
> stratégies** sont ici. Aucune ne vit aux deux endroits.
>
> **L'état d'avancement n'est pas ici** : il est dans `CHANTIERS.md`, qui fait foi.

---

## F1 — ouverture du banc d'essai : ACTÉ le 2026-08-18

**L'idée (Jonas, 12/08)** : un banc permettant de tester **d'autres stratégies que AritV1**,
pour (1) trouver celle qui a le meilleur rendement et (2) **diversifier les formes
d'investissement**. Motif : l'entrée d'AritV1 n'a aucun edge directionnel mesurable — 78
signaux en 5 ans, p = 0,38 / 0,30 contre le modèle nul.

| Point | Décision du 18/08 |
|---|---|
| **Ouverture** | F1 est **ouvert**. Nom du projet : **BETA**. |
| **Prérequis B2/B5/B6** | levés — **B6 fermé le 18/08** (`ARIT2.0/research/EXPERIMENTS.jsonl`, verrou matériel). Plus aucun verrou méthodologique devant le banc. |
| **Périmètre immédiat** | **les données, et rien d'autre**. « Je veux juste des data pour le moment, pas de nouvelles stratégies automatiques derrière, nous pourrons les réanalyser. » ⇒ le pipeline YouTube → stratégie générée est **reporté**, pas annulé. |
| **Dépendances** | BETA **peut utiliser les pip sécurisés** (pandas/numpy/scipy/pyarrow/duckdb). L'invariant zéro-pip d'ALPHA ne s'applique pas ; le front reste sans CDN. |
| **Univers** | **6 paires** : BTC, ETH, SOL, BNB (habituelles) **+ LINK et XRP**. Critère d'ajout : **l'ancienneté du contrat perpétuel**, pas la popularité — le goulot est le nombre de signaux, donc c'est l'historique qui commande. |
| **Téléchargement** | les 4 habituelles sont **déjà sur disque** — ne lancer que les 2 nouvelles. Les téléchargements peuvent être **simultanés** dans BETA (repère : 27 min pour 4 paires en séquentiel). |
| **Emplacement** | **nouveau dossier hors ARIT2.0, repo git séparé et PRIVÉ.** |
| **Patte graphique** | celle d'ALPHA (`ALPHA/web/style.css`), thème sombre, tokens CSS. |
| **MCP** | double sens : dashboard → Claude Code (comme `ALPHA/alpha/actions.py:160`) **et** Claude Code → BETA (serveur MCP stdio exposant le catalogue, les runs, le registre d'expériences). ✅ **codé et branché le 19/08** (P1-P3, P5) — le pipeline YouTube (P4) reste seul reporté. |

### Le moteur — tranché le 18/08 : **hybride**

**Moteur maison en espace-R pour cribler** (des centaines de candidates, avec la batterie
statistique complète), **freqtrade pour confirmer** les 2-3 survivantes en conditions
réalistes. Pourquoi aucun des deux seul ne suffisait :

| | Moteur maison (espace-R, vectorisé) | freqtrade |
|---|---|---|
| Monte-Carlo / bootstrap (1 000 runs) | faisable | **irréalisable** avec `--timeframe-detail 5m` |
| Proximité avec ARIT | il faut re-porter la géométrie SL/TP | **native** — même produit, mêmes protections |
| Frais, slots, sizing, compounding | **non simulés** (limite déjà assumée par `replay_entries.py`) | simulés |
| Code à écrire | portage de `ARIT2.0/analysis/dataset.py:_issue` | quasi nul |

⚠️ Conséquence à ne pas perdre de vue : la phase de criblage **ne mesure ni les frais, ni les
slots, ni le compounding**. Un chiffre issu du criblage n'est donc **jamais** un verdict
portefeuille ; seule la phase freqtrade en produit un.

### Les trois risques, redits parce qu'ils ne disparaissent pas

1. **P-hacking industrialisé** — un banc est une machine à multiplier les tests, et il en
   produira d'autant plus de faux gagnants qu'il est efficace. B6 est fermé, mais le
   **compteur d'essais cumulatif** (parti de 30) et le **hold-out scellé** doivent être dans
   BETA dès le premier lot, pas ajoutés après. ⚠️ Ordre imposé : **S1 (Benjamini-Hochberg),
   S2 (Sharpe dégonflé) et S8 (buy-and-hold) avant la première comparaison de candidates.**
2. **Interdit n° 5 d'ARIT** — comparer des stratégies ≠ optimiser des seuils. Le banc ne doit
   jamais devenir un contournement de l'interdiction d'hyperopter G1-G7 et les poids.
   **BETA ne modifie jamais `ARIT2.0`** : il le lit.
3. **Référence imposée** — **buy-and-hold** de la même période pour toute candidate (ex-Q9
   d'ARIT, devenu S8) : ce qui ne bat pas le hold mesure le marché, pas un edge.

**Ce qui reste à faire n'est pas listé ici** : blocs M (moteur), S (multi-test), R (recherche
d'edge), P (MCP) et A (atelier) dans `CHANTIERS.md`. **Feu vert de Jonas le 19/08 sur M1-M4
et sur le pont MCP**, plus l'ouverture de l'atelier (§ A) : « une possibilité de tester
d'autres stratégies, et une option locale pour les coder à la main ou avec un modèle local
sur Ollama ou LM Studio ». Les deux hypothèses les moins chères, **R1** (le
trailing stop détruit les shorts) et **R6** (`news_window`), se mesurent sur les données déjà
présentes, sans écrire une seule candidate : ce sont les deux premières à préenregistrer.

---

## A1 — ce que compte N : les hypothèses, ou les mesures ? **TRANCHÉE le 20/08 — (b)**

**Découvert le 19/08 en construisant l'atelier.** `experiences.compteur()` vaut
`30 + nombre d'ids distincts dans EXPERIMENTS.jsonl` : il compte les **hypothèses
préenregistrées**, pas les **mesures effectuées**. C'est ce N qui alimente S1
(Benjamini-Hochberg) et S2 (Sharpe dégonflé) — donc c'est lui qui fixe la sévérité de toute
la batterie.

Tant qu'il y avait une candidate par hypothèse, les deux nombres étaient égaux et la
question ne se posait pas. **L'atelier casse l'égalité** : dix candidates écrites sous
l'hypothèse R7, ce sont dix tests, et **un seul point de compteur**. L'écart est exactement
la quantité de p-hacking qu'un banc rapide rend possible sans qu'elle se voie.

État au 19/08 : **1 run mesuré pour 6 hypothèses déclarées** — l'écart n'existe pas encore.

| Option | Ce que ça donne | Coût |
|---|---|---|
| **(a)** laisser N = hypothèses | statu quo. Le premier lot de l'atelier rendra les seuils trop généreux, donc les verdicts trop flatteurs | gratuit, et faux dès la 2ᵉ candidate d'une même hypothèse |
| **(b)** N = `30 + runs mesurés` (`RUNS.jsonl`) | honnête : chaque mesure paie son coût statistique, ce qui est le sens même du compteur cumulatif | **durcit rétroactivement** les seuils. Les trois verdicts du 19/08 ont été rendus avec N = 36 ; il faudrait dire qu'ils l'ont été, pas les réécrire |
| **(c)** N = hypothèses, **et une candidate par hypothèse imposée** | garde le compteur juste en interdisant le cas qui le casse | rend l'atelier beaucoup moins utile : chaque variante demande un préenregistrement complet |

**Ma recommandation : (b)**, parce que c'est la seule qui reste vraie quand le banc
accélère, et parce que l'invariant n° 4 dit « N doit compter TOUS les essais, y compris ceux
qu'on n'a jamais rapportés ». Un compteur qu'on n'incrémente que lorsqu'on écrit une
hypothèse *nouvelle* est exactement le compteur que le fléau des tests multiples exploite.
Les verdicts déjà rendus resteraient publiés **avec leur N d'époque**, écrit à côté — on ne
réécrit pas un résultat, on date sa sévérité.

### Décision de Jonas, 20/08 : **(b) — N porte les mesures**

Appliquée dans `experiences.compteur()`. La formule retenue est un raffinement de (b), et
il lève l'objection qui rendait (b) coûteuse :

    N = 30  +  mesures distinctes (RUNS.jsonl)  +  hypothèses préenregistrées sans aucune mesure

Un essai est **l'un ou l'autre, jamais compté deux fois** : une hypothèse en attente a
consommé un droit de regard (on la compte d'avance, c'est le sens conservateur) ; dès
qu'elle est mesurée, ce sont ses mesures qui comptent, et il peut y en avoir dix.

**Conséquence numérique le jour du changement : N = 36, exactement ce que valait l'ancienne
formule.** Les trois verdicts du 19/08 ont donc été rendus au bon N — *rien n'est réécrit,
rien n'est rétroactivement durci*, ce qui était le seul vrai coût de (b) au tableau
ci-dessus. Ce qui change commence au premier lot de l'atelier : dix candidates sous une même
hypothèse comptent désormais pour dix, et non pour une.

Deux propriétés vérifiées par des tests (`tests/test_auto.py`) :
- **monotone** — le compteur ne redescend jamais, quel que soit l'ordre des écritures ;
- **stable au re-criblage** — `run_id` est déterministe, donc relancer le même criblage à
  l'identique ne fabrique pas un essai de plus. Seul un vrai nouveau test coûte un cran.

Deux effets de bord assumés, tous deux dans le sens sévère :
- pendant un criblage, **N est figé à `compteur() + taille du lot`** : le lot est payé
  d'avance, avant qu'aucun résultat ne soit connu, et les dix candidates d'un même lot sont
  jugées au même seuil. Sans ce gel, la dernière du lot serait jugée plus durement que la
  première pour la seule raison qu'elle est passée après ;
- `scripts/mesurer.py` journalise désormais ses mesures (R1, R6) : une mesure hors pipeline
  était gratuite au compteur alors qu'elle consommait bien un essai. Son `run_id` est haché
  sur l'**empreinte du code de la mesure** (corrigé le 20/08 ; la première version datait
  l'identifiant, donc relancer le script le lendemain fabriquait un essai). Un compteur qui
  monte parce que le temps passe ne mesure plus rien.

---

## B-a / B-b / B-c — ce que les mesures d'ARIT du 05-06/09 mettent sur la table

> Ouverts le 2026-09-11, en versant dans BETA les résultats de la chasse à l'edge d'ARIT
> (`ARIT2.0/research/pertinence_donnees_2026-09-05/` et `research/resultats_edge_2026-09-06.md`).
> Détail et chiffres : `CHANTIERS.md` § MISE À JOUR DU 2026-09-11.
> Lettres et non numéros : `B1` désigne déjà autre chose chez ARIT, et confondre les deux
> registres coûterait plus cher que la laideur de la notation.

⚠️ **Aucune de ces trois questions ne se tranche par une mesure** — c'est bien pour ça
qu'elles sont ici. Elles décident **ce qu'on paie**, et ce qu'on paie, c'est le compteur
d'essais (41 aujourd'hui) : chaque promotion durcit rétroactivement le seuil de toutes les
autres hypothèses.

### B-a — R3 (portage / funding) : la mesurer quand même, ou l'écarter ?

R3 a été préenregistrée le 19/08 sur une prémisse : « **86 % du profit de MacroFlip venait du
funding** ». ARIT vient de mesurer le funding sur 4 actifs et 7 ans : **IC entre −0,06 et
+0,001**, inerte, avec pour seul effet net un squeeze des shorts **sur BTC seul**. Le rapport
d'ARIT écrit lui-même que les 86 % sont « à revérifier ».

| option | ce que ça veut dire | le coût |
|---|---|---|
| **(a)** la mesurer quand même | l'hypothèse est au registre, elle se mesure ; un résultat obtenu ailleurs, sur d'autres sorties et sans LINK/XRP, ne la réfute pas | D5 (allégé : 4 paires sur 6 sont sur le disque d'ARIT) + un cran de compteur déjà payé |
| **(b)** l'écarter, motif écrit | on ne dépense pas une mesure pour une prémisse dont la source dit qu'elle est fausse | le compteur ne redescend pas ; l'essai reste payé |

**Défaut proposé : (a)**, mais **après** B-c. Écarter une hypothèse du registre sur la foi
d'un résultat extérieur, c'est exactement le geste que le préenregistrement existe pour
empêcher — sauf que le préenregistrement protège contre le fait de *garder* ce qui arrange,
pas contre le fait de *jeter* ce qui coûte. ⇒ à toi.

### B-b — R4 (macro seule) : D6 est débloqué, au moment où ARIT enterre la macro

Les séries macro sont sur le disque d'ARIT **en clair** depuis le 24/08 (`user_data/data/macro/`) :
R4 n'est plus bloquée, et le coût de D6 tombe de M à S. Simultanément, ARIT a **retiré son
multiplicateur macro** le 05/09 (B1, option (b)) au motif que la macro est une donnée faible.

⇒ Deux lectures opposées, et c'est un choix, pas un calcul : soit la macro est enterrée et R4
ne vaut plus une mesure, soit **BETA est précisément le seul endroit où la question peut
recevoir une réponse propre** — ARIT n'a jamais mesuré la macro *seule*, il a mesuré une macro
mêlée à cinq scores et à une porte de conviction.

**Défaut proposé : mesurer R4**, parce que c'est la seule des trois qui répond à une question
qu'ARIT ne peut pas se poser chez lui.

### B-c — I16 (momentum 14-60 j) : la promouvoir en candidate n° 2 ?

C'est le seul résultat de la session ARIT qui **survit hors échantillon sur les 4 actifs**
(Sharpe holdout 0,78 à 0,98, contre un B&H à 0,55-0,83). ARIT conclut « c'est du beta, pas de
l'alpha » parce qu'il compare à un buy-and-hold long-only ; BETA a S8, la triple barrière, et
**deux paires (LINK, XRP) qui n'ont jamais servi à cette mesure**.

Et c'est surtout la **deuxième candidate** qui manque au banc depuis le 19/08 : sans elle, S7
(reality check du maximum) et S9 (corrélation des équity) n'ont pas d'objet — la moitié
comparative du banc tourne à vide depuis trois semaines.

⚠️ Condition non négociable si tu promeus : **un seul lookback, choisi d'avance** (30 j,
sommet du plateau). Les chiffres cités viennent d'un balayage de cinq lookbacks fait ailleurs ;
promouvoir « le meilleur des cinq » ferait entrer le snooping d'ARIT dans le registre de BETA.

**Défaut proposé : promouvoir**, avec lookback 30 j figé et MDE affiché avant toute p-value.
## A2 — nature de l'edge : alpha (niveau 3) vs ARP (niveau 2) — **TRANCHÉE — (A)**, config figée le 03/10

**Découvert le 22/09, après une semaine de mesures hors échantillon + 3 allers-retours avec Claude Code (opus).**

**Le constat mesuré** : les indicateurs lents → direction (à tout horizon 1-21j, crypto + indices, optimisés train/test) ne produisent **aucun alpha** (niveau 3). Deux corrections majeures :
1. Le « Sharpe 1,25 » de la diversification inverse-vol était **fictif à ~⅔** : il reposait sur 5 indices non tradables (pas de broker actions). Le tradable réel (6 perps crypto, corr ~0,62) sort à **Sharpe 0,45 OOS, drawdown −61 %**.
2. L'alpha de niveau 3 est **structurellement** hors d'atteinte d'un particulier swing (latence, donnée, capacité) — pas une question d'expérience.

**Ce qui reste atteignable** : un portefeuille d'ARP (primes de risque alternatives), **niveau 2** — 3 jambes (trend TSMOM, coupe transversale momentum/reversal, carry funding), vol-ciblées, Sharpe réaliste **0,4-0,7 net**. Jugé sur **a priori externe** + **suivi live** — jamais sur une p-value (t = Sharpe×√années : à 0,6 sur 7 ans, t ≈ 1,6, indétectable).

**La décision qui attend Jonas** :
- **(A)** Assumer le niveau 2 : construire le portefeuille ARP 3-jambes vol-ciblé. Livrable principal = ramener le drawdown de −61 % à ~−25 % (gestion du risque, prouvable).
- **(B)** Changer d'enveloppe pour rouvrir le niveau 3 : queue illiquide, funding multi-venues, effets de listing. Contredit la doctrine « le plus ancien », plus dur, cimetière propre.
- **(C)** Arrêter de chercher un edge, indexer, rendre le temps ailleurs.

**Recommandation (Hermes + Claude) : (A) maintenant, (B) comme pari latéral dans ~6 mois, jamais les deux en même temps.** (C) reste légitime.

**Retentissement sur BETA** : le rôle de la batterie change — elle cesse de *confirmer* un edge (impossible à Sharpe ≤0,7) pour devenir l'outil qui *élimine le manifestement faux* ; l'acceptation d'une candidate se fait sur a priori externe + suivi live forward.

---

### Suite de A2 — la voie C figée et mise en suivi forward (03/10)

Jonas a choisi **(A)**. Le 03/10, la gestion a été optimisée sur le train seul
(`beta/strategies/voie_c_optim.py`, 5 760 configs), puis passée aux garde-fous
(`voie_c_verif.py`) : **causalité OK, mais DSR ≈ 0 avec N ≈ 5 870** — le gain du réglage
fin (+0,15 de Sharpe) est indiscernable du bruit. Ce qui tient : le vol-targeting ramène le
maxDD de −77 % à ~−22 %. Sharpe réaliste attendu : **0,5-0,7**.

**Config FIGÉE le 2026-10-03** (`scripts/voie_c_suivi.py`, empreinte `d0a971b8c4261d60`) :
cible 20 % · σ glissante 30 j · levier [0,25 ; 2] · hystérésis du levier 0,25 · quotidien ·
bande 20 %. Lmax 2 plutôt que 3 : même Sharpe train à 20 %, moins de risque de liquidation.

**Suivi** : `SUIVI_VOIE_C.jsonl` (racine, ajout seul), timer `beta-suivi` à 00:45 UTC. Les
journées du 06/09 au 02/10 n'avaient été chargées par aucun script de la voie C avant le gel
→ journalisées « rattrapage » ; à partir du 03/10, « live ». **Aucun ordre passé.** Changer
de config = nouveau journal, et une ligne ici. Pas de verdict avant ~6 mois de live.

---

### Suite de A2 (bis) — la voie C2 : long uniquement, régime BTC à votes (07/10)

**Déclencheur** : diagnostic du 07/10 sur la config figée (données ≤ 05/09) — la jambe carry
fait ~90 % du turnover (classement quotidien de 6 funding, composition changée 63-77 % des
jours) et coûte plus en frais qu'elle n'encaisse de funding. Jonas en a tiré une refonte, et
l'a fixée **règle par règle, avant toute mesure**, le 07/10. La voie C2 a vocation à vivre
dans ARIT, devenu multi-stratégies (ARIT `DECISIONS.md`, 28/09 et 07/10), où elle
**remplace AritV1**.

**Cadre** : long uniquement · perpétuels USDT-M · levier max 2 · les 6 paires · frais du
barème ARIT (taker 5 pb + slippage 5 pb BTC/ETH, 10 pb les 4 autres, par côté) · funding des
longs déduit · pas de coupe-circuit journalier · aucune règle par trade d'AritV1.

**Le régime** — 5 votes, chaque jour, données ≤ J−1 (FRED ≤ J−2 : publication J+1 ~20 h UTC) :

| Vote | +1 | −1 | 0 |
|---|---|---|---|
| Momentum BTC | rendement 126 j > 0 | < 0 | — |
| Taux réel 10 ans (DFII10) | baisse ≥ 0,10 pt sur 60 obs. | hausse ≥ 0,10 pt | sinon / périmé |
| Inflation anticipée 10 ans (T10YIE) | hausse ≥ 0,10 pt sur 60 obs. | baisse ≥ 0,10 pt | sinon / périmé |
| NASDAQ-100 (c6/c7 d'ARIT) | **jamais** (A4) | sous son plus bas de 20 sessions ET BTC couplé | sinon / périmé |
| Fear & Greed (seuils ARIT figés) | ≥ 45 | < 25 | sinon / périmé |

Somme ≥ +2 ⇒ **haussier** · ≤ −2 ⇒ **baissier** · entre les deux ⇒ **veille**.

**Les positions** :
- **haussier** : (inverse-vol 180 j + tendance propre long uniquement) / 2 × levier du
  vol-targeting de la config figée (cible 20 %, σ 30 j, levier 0,25-2, hystérésis 0,25,
  bande 20 %), quotidien ;
- **baissier** (épisode, jusqu'au prochain haussier) : au signal, poche BTC amenée à 25 % du
  plus haut de l'équité (achat ou vente), plafonnée à 100 % du capital du jour, puis elle
  flotte ; alts −50 % au signal, puis chaque alt sort en entier quand SON rendement 126 j
  est négatif ; aucun rachat avant le retour en haussier ;
- **veille** : aucun ajout ; l'exposition peut seulement baisser, au prorata, si le brut
  voulu par le moteur haussier passe sous le brut tenu de plus que la bande.

**Mesure** : préenregistrées le 07/10 — **VC2** (complète, empreinte `744700fa7d8980fc`) et
**VC2T** (témoin sans macro, `7880a72b6e116005`), famille de 2, compteur 57 → 59. Script :
`scripts/preenregistrer_vc2.py`. Backtest 2021-06-12 → 2026-09-05, **informatif** (fenêtre
déjà vue). Porte : maxDD net ≥ −25 % ET Sharpe net > hold BTC ET causalité. L'écart
VC2 − VC2T mesure ce que la macro apporte (attendu : indécidable).
**Forward** : rattrapage du 06/09 au 06/10, **live à partir du 07/10** ; dry-run de 6 mois,
critères maxDD ≤ 25 %, vol réalisée 10-30 %, puis slippage ≤ 2× modèle et zéro incident dès
que l'exécution existe. Le suivi de la config figée du 03/10 continue en parallèle.

**Reste ouvert** : le châssis d'exécution — propre à chaque stratégie selon Jonas, à trancher
avant un dry-run avec ordres.

**Mesure du 07/10 — VC2 et VC2T INFIRMÉES par leur règle préenregistrée**
(`scripts/mesurer_vc2.py`, un run chacune, compteur inchangé à 59) :

| | Sharpe net | CAGR | maxDD | turnover |
|---|---|---|---|---|
| VC2 (5 votes) | 0,72 | 20,7 % | **−34,8 %** | 2,7x/an |
| VC2T (momentum seul) | 0,78 | 23,7 % | **−38,2 %** | 5,9x/an |
| hold BTC | 0,33 | 7,5 % | −78,0 % | — |
| voie C figée (5 pb, sans slippage) | 1,11 | 33,4 % | −21,4 % | — |

Le Sharpe bat largement le hold ; c'est le **budget de drawdown (−25 %) qui casse**, sur la
baisse du 08/11/2021 au 21/11/2022. Décomposition exacte (refaite le 07/10, même run) :
**−16,8 points pendant le retard du signal** (08/11 → 19/12/2021, alts −11,8), **−15,4 points
sur la poche BTC, constituée par un ACHAT au signal** (BTC 7 % → 30 % du capital, puis
−66 %), −2,6 de reste. La poche « 25 % du plus haut » est un achat dans 9 épisodes sur 9
(25 sur 26 pour VC2T), car le moteur ne tient qu'environ 15 % de BTC en haussier.
*Corrigé le 07/10 : la première version de ce paragraphe disait « la poche (~21 % de
l'équité) flotte dans les −77 % de BTC et fait ~70 % de la perte », et concluait que plancher
BTC et budget étaient incompatibles — c'était faux, la poche était un achat.* Apport de la
macro : −2,7 %/an, IC 95 % [−8,0 ; +2,9] ⇒ indécidable. **Pas de forward** (la règle
l'interdit).

---

### Suite de A2 (ter) — VC3 : poche « maximum », en spot (07/10)

**Décisions de Jonas après la mesure de VC2**, question par question :
- **12:59 UTC — la poche BTC est un MAXIMUM** : au signal baissier, BTC = min(BTC tenu, 25 %
  du plus haut de l'équité). La règle ne fait plus que vendre, jamais acheter. C'est la
  lecture de ses propres mots (« un allègement, jamais une vente complète ») ;
- **13:07 UTC — spot, cible 20 %** : le levier de VC2 n'a jamais servi (brut max 1,00, 0,60
  en médiane haussière), mais les perpétuels coûtaient 2,7 %/an de funding. Spot = aucun
  funding, exposition brute plafonnée à 1 (pas d'emprunt), frais spot 0,10 % par côté + le
  même slippage. Jonas pensait que « le problème, c'est peut-être de ne pas se servir du
  levier » : le levier ne détecte rien, il multiplie, et viser plus de risque aurait demandé
  de relever le budget (cible 30 % ≈ −35 % sur 2022 en calcul grossier) ;
- **13:13 UTC — « teste aussi l'overfitting potentiel avec beta »** : batterie
  anti-surapprentissage écrite dans le préenregistrement, seuils compris, avant la mesure.

Tout le reste de C2 est inchangé (5 votes, seuils, moteur haussier, alts, veille). Prix : les
clôtures des perpétuels du lake servent de proxy du spot ; écart vérifié contre l'API spot
Binance sur la fenêtre (≤ 10 pb cumulés par paire, seule exception SOL le 09/11/2022, FTX).

**Préenregistrement** (commit `b342ea0`, `scripts/preenregistrer_vc3.py`) : **VC3**, empreinte
`7adef08a837a8c50`, seule, sans témoin, compteur 59 → 60. Porte : maxDD net ≥ −25 % ET Sharpe
net > hold BTC **spot** ET causalité ET **R1** (la médiane de 10 voisins de calendrier passe
aussi la porte). R2 à R4 informent ou alertent.

**Mesure du 07/10 — VC3 CONFIRMÉE, de justesse, avec deux alertes** (`scripts/mesurer_vc3.py`,
run `02a300c116bb` ; les 10 voisins sont journalisés, compteur 60 → 70) :

| | Sharpe net | CAGR | maxDD | turnover |
|---|---|---|---|---|
| **VC3** (poche max, spot) | **0,80** | 22,1 % | **−23,2 %** | 2,2x/an |
| VC3 hors échantillon (≥ 01/07/2024) | 0,72 | 19,0 % | −19,6 % | 1,9x/an |
| hold BTC spot (la porte) | 0,45 | 15,6 % | −76,7 % | — |
| VC2 (perpétuels, poche achetée) | 0,72 | 20,7 % | −34,8 % | 2,7x/an |
| voie C figée (5 pb, sans slippage) | 1,11 | 33,4 % | −21,4 % | — |

La batterie anti-surapprentissage :
- **R1 plateau (porte) — passe, mais de peu.** Médiane des 10 voisins : maxDD −24,3 %, Sharpe
  0,75. **4 voisins sur 10 crèvent le budget, tous sur les fenêtres de momentum** (vote BTC
  90/180 j : −25,9 / −29,4 % ; moteur 90/180 j : −25,8 / −27,6 %). Les fenêtres des alts, de
  la σ et la bande ne bougent presque rien. Le budget tient donc à la fenêtre de 126 j, des
  deux côtés.
- **R2 Sharpe dégonflé** : DSR 0,42 à N = 70, 0,06 à N = 5 880 (avec la grille de la voie C
  dont VC3 hérite le moteur). Le Sharpe ne résiste pas au nombre d'essais, comme attendu.
- **R3 — ALERTE.** Bootstrap par blocs : maxDD médian −28 %, P(maxDD < −25 %) = 66 à 68 %
  selon la longueur de bloc. Écart de Sharpe au hold BTC : +0,35, IC 95 % [−0,31 ; +0,98].
- **R4 — ALERTE.** 2024 fait 50 % du gain (en log). Par année : 2021 +2,8 % · 2022 −5,0 % ·
  2023 +56,9 % · 2024 +69,5 % · 2025 +10,2 % · 2026 (au 05/09) −0,6 %.

**Lecture** : VC3 n'est pas tuée, elle n'est pas validée. Le gain réel par rapport à VC2 est
d'avoir cessé d'acheter du BTC au signal baissier (−35 % → −23 %). Mais la marge sous le
budget est mince, elle dépend de la fenêtre de 126 j, et son propre bootstrap la dépasse
deux fois sur trois. Dans une vraie baisse, il faut s'attendre plutôt à −30 % qu'à −23 %.
**Forward** : admise au dry-run de 6 mois, rattrapage du 06/09 au 07/10, live dès le 08/10,
critères préenregistrés (maxDD ≤ 25 %, vol réalisée 10-30 %).

**Suivi installé le 08/10** : `scripts/c2_suivi.py --id VC3`, timer `beta-suivi-vc3` à
00:50 UTC → `SUIVI_VC3.jsonl` (racine, ajout seul). Config et dates relues dans le registre,
empreinte épinglée. Chaque journée close : état, 5 votes, position tenue, rendement net, holds
BTC spot et équipondéré ; la dernière ligne porte la consigne du lendemain, calculée par la
même chaîne prolongée d'un jour (vérifié chaque jour : la prolongation ne change aucune
journée close). Journal initial : 32 jours de rattrapage (06/09 → 07/10) ; première journée
live le 08/10, écrite le 09/10. MaxDD live sous −25 % = unité en « failed » : c'est une
alarme, pas une panne, et la suite est une décision de Jonas. **Aucun ordre passé.**

---

### Paper trading des trois voies C (Jonas, 08/10)

**Demande** : « déployer les 3 voies C en paper pour voir les résultats sur du long terme ».
Choix de Jonas (08/10) : la **voie C figée**, **VC2** et **VC3**, en **exécution simulée
contre le vrai carnet** — plutôt que le seul suivi au cours de clôture, ou le testnet Binance
(prix et liquidité artificiels).

- **VC2 suivie à titre informatif** (`c2_suivi.py --id VC2`, timer `beta-suivi-vc2`,
  `SUIVI_VC2.jsonl`). Elle reste INFIRMÉE par sa règle : aucun critère de dry-run, et un bon
  forward ne la réhabilite pas — il faudrait un nouveau préenregistrement, avec ce résultat
  dans `deja_connu`. Même précaution pour le choix final : retenir après coup la meilleure des
  trois en paper serait une sélection de plus, à compter comme telle.
- **Le paper** (`beta/paper.py`, `scripts/paper.py`, timer `beta-paper` à 01:00 UTC →
  `PAPER_VOIE_C.jsonl`, `PAPER_VC2.jsonl`, `PAPER_VC3.jsonl`) : 10 000 USDT fictifs par voie
  (taille du canari). Chaque jour, la consigne de chaque suivi est exécutée au marché contre le
  carnet Binance du moment (perpétuels pour C et VC2, spot pour VC3), avec les pas de lot, les
  minimums, les frais du barème et le funding réellement réglé. Par ordre : l'écart au milieu
  du carnet (coût de la liquidité) et à l'ouverture de 00:00 UTC (liquidité + délai), à
  comparer au slippage du modèle — le critère « ≤ 2× le modèle » du dry-run. Aucune clé,
  aucun ordre : routes publiques seulement. Le premier jour construit toute la position (voie
  C : la cible du moteur), les suivants ne touchent que ce que le modèle change.
- **Premier jour : 09/10 à 01:00 UTC.** Essai réel le 08/10 dans un répertoire jetable : à
  10 k, chaque ordre se remplit au premier niveau, 0 à 0,4 pb du milieu (le modèle suppose 5 à
  10 pb) ; le pas de 0,001 BTC en perpétuels décale le poids de BTC d'environ 0,3 point.
- **Ce que le paper ne dit pas** : la marge et la liquidation (non simulées, brut ≤ 2), la
  file d'attente et les pannes d'un vrai châssis. Le châssis d'exécution reste ouvert (ARIT).

---

## En attente de Jonas

| # | Objet | État | Depuis |
|---|---|---|---|
| ~~**A1**~~ | ~~Ce que compte N : hypothèses ou mesures~~ | ✅ **tranchée 20/08 — (b)**, appliquée | 19/08 |
| **B-a** | R3 (funding) : la mesurer quand même, ou l'écarter ? Sa prémisse (86 % du profit de MacroFlip) est attaquée par les mesures ARIT du 05/09 | 🔴 ouverte | 11/09 |
| **B-b** | R4 (macro seule) : D6 est débloqué le jour où ARIT enterre la macro — mesurer, ou classer ? | 🔴 ouverte | 11/09 |
| **B-c** | I16 (momentum 14-60 j) : la promouvoir en **candidate n° 2** du banc, lookback 30 j figé ? | 🔴 ouverte | 11/09 |
| ~~**A2**~~ | ~~Nature de l'edge : alpha vs ARP (options A/B/C)~~ | ✅ **tranchée — (A)**, suivi forward depuis le 03/10 | 22/09 |
