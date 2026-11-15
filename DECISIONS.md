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
>
> **Rangé le 15/11/2026** : les sections closes (F1, A1, A2 et les voies C, audits, compteurs, S6,
> S8, S10, TI1, Temps 1, R13 et R14) sont dans `archives/DECISIONS_closes_2026-11-15.md`, mot
> pour mot. Un renvoi « `DECISIONS.md` § … » écrit avant cette date (code, préenregistrements
> figés, `CHANTIERS.md`) se lit désormais dans ce fichier d'archives.

---


## En attente de Jonas

Tout ce qui attend une réponse, en une table. Le détail des sections closes est dans
`archives/DECISIONS_closes_2026-11-15.md` (texte d'origine, déplacé le 15/11/2026).

| # | Objet | Depuis | Détail |
|---|---|---|---|
| **B-a** | R3 (funding) : la mesurer quand même, ou l'écarter ? | 11/09 | § B-a ci-dessous |
| **B-c** | I16 (momentum 14-60 j) en candidate n° 2 du banc de trading. Le momentum 30 j a été mesuré le 10/11 en **test invest** (MOMENTUM30_BTC), pas dans le moteur de trading : dire si cela ferme B-c | 11/09 | § B-c et § MOMENTUM30_BTC ci-dessous |
| **Gardes de ruine** | Voies C : garde quand le dénominateur d'un ratio est ≤ 0 (S8 corrigée le 15/10 ; les voies C attendent) | 15/10 | `/root/rapports/2026-10-15_ratios-denominateurs.md` (VPS) |
| **TI1** | Clore TI1 : « aucun vote ne protège mieux que le hasard ; socle, DFII10, NASDAQ, F&G non concluants en stress test » (revérifié le 21/10, 0 écart) | 21/10 | archives, § 2026-10-20 |
| **Temps 1, étape A** | Relancer avec les dates ALFRED de DEXJPUS ? Ce serait une nouvelle mesure (+14 au compteur invest) | 21/10 | archives, § 2026-10-21 |
| **Lake hors freqtrade** | Sortir le lake crypto de freqtrade (proposé le 21/10 ; touche l'invariant n° 1 de lecture d'ARIT) | 21/10 | `/root/rapports/2026-10-21_temps1-et-marches.md` (VPS) |
| **S10 incalculable** | « On ignore S10 si elle est incalculable » (28/10) : à confirmer avant de changer la règle du 26/10 (« non exécutée → indécidable ») | 28/10 | archives, § 2026-10-26 |
| **D** | Règle d'agrégation d'un lot de variantes (« au moins une sur 3 »), écrite par Claude pour R13 et R14 sans validation | 04/11 | archives, § Rapport écrit par le programme |
| **MDE avant mesure** | Faut-il que le programme calcule un plus petit effet détectable AVANT la mesure (demande un σ(R) supposé) ? | 04/11 | archives, même § |
| **Portes 2 à 9** | Audit des portes du 05/11 : les correctifs de calcul sont dans `main` (`1cac36f`) ; restent huit changements de RÈGLE — S8 à volatilité égale, même fenêtre, test de Memmel · S4 jugée sur le drawdown · S2 avec la variance empirique des Sharpe · S1 à q = 0,05 · S10 incalculable · S9 contre les seules candidates retenues · S5 sur toutes les paires · S7 contre zéro ou contre le hold | 05/11 | `/root/rapports/2026-11-05_audit-portes-batterie.md` (VPS) ; outils prêts : § 15/11 ci-dessous |
| **MOMENTUM30_BTC** | Relire le préenregistrement et qualifier (recherche ou exploration), puis décider de la suite (paper, ouverture unique du hold-out 2025+) | 10/11 | § ci-dessous |
| **Fiche de robustesse** | Brancher la fiche informative du 15/11 dans le rapport d'expérience du programme, ou la garder à part ? | 15/11 | § 15/11 ci-dessous |

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
## Momentum trente jours sur le BTC — MOMENTUM30_BTC (10/11/2026)

Jonas : « à l'aide de toutes les données et de tous les tests effectués dans BETA, théorise et
teste une stratégie rentable sur le BTC (je veux voir ce que tu arrives à faire) et fais-la
passer dans BETA ». Claude a suivi le skill de recherche (question, littérature vérifiée,
mécanisme, données, prédiction, préenregistrement, mesure), avec **deux entorses nommées** :
hypothèse et règles écrites par Claude (« proposition de Claude »), et nuit entre gel et
lancement sautée. Dossier `MOMENTUM30_BTC/` (`RECHERCHE.md`, `PREENREGISTREMENT.md`), moteur
`beta/momentum30_btc/moteur.py`, scripts `preenregistrer_momentum30_btc.py` et
`mesurer_momentum30_btc.py`, rapport `rapports/MOMENTUM30_BTC/`.

Ce qui a été mesuré : exposition long-only sur le perpétuel BTC en quotidien, 1 si le rendement
des 30 derniers jours est > 0, sinon 0, décidée à la clôture et appliquée le lendemain, contre le
hold du même perpétuel, rendements du 09/10/2019 au 31/12/2024, frais 6 pb par bascule, funding
réel, cash au DFF. Famille invest, un essai, compteur invest 61 → 62. Règle : Sharpe, CAGR et
MDD meilleurs que le hold ET p retenue des deux nulls du test invest < 0,05.

**Verdict du programme : CONFIRMÉE** (issue attendue : infirmée) — stratégie Sharpe 1,16 / CAGR
+55 % / MDD −47 % contre hold 0,80 / +38 % / −79 % ; p retenue 0,027.

**Ouvert — attend Jonas** : (1) relire le préenregistrement et qualifier le résultat (recherche
ou exploration : tant qu'il n'a pas relu, c'est une exploration, un résultat d'exploration ne
prouve rien) ; (2) suite éventuelle : paper BTC perpétuel et/ou ouverture unique du hold-out
2025+, sans aucun réglage avant. Aucun réglage n'a été fait ni ne sera fait sans décision.


## 2026-11-15 — Deux formules corrigées, outils informatifs ajoutés (Claude, sur « je te fais confiance »)

Jonas, le 15/11 : « pour ce qui concerne BETA je te fais confiance pour réellement revoir les
formules et leur pertinence et ajouter tous les outils de backtest que tu trouves réellement
pertinents et de niveau professionnel ». **Aucune règle de décision n'a changé** : ni seuil, ni
porte, ni issue. Aucune mesure nouvelle, aucun essai consommé, hold-out non lu.

**Corrigé (affichage, pas les portes)** :
- `espace_r` : `prix_sortie` et `rendement_pct` prenaient la clôture de la bougie de sortie même
  quand le stop ou la cible étaient touchés ; un stop touché dans une bougie qui reclôture plus
  haut valait −1 R et un rendement positif. Ils se lisent maintenant au prix de la barrière. Le R,
  donc toutes les portes et tous les verdicts, n'était pas touché ; le profit factor et le
  rendement moyen (calculés sur `rendement_pct`) l'étaient. Les runs déjà stockés gardent leurs
  anciennes valeurs d'affichage.
- `comparaison` (onglet Comparaison, écart à AritV1) : le Sharpe et l'écart de rendement passaient
  par un pourcentage de la veille sur une courbe à risque fixe — le défaut corrigé dans S8 le
  15/10 et dans S9 le 05/11, resté ici.

**Ajouté, INFORMATIF (ni porte ni verdict, aucun seuil)** — `beta/stats/CLAUDE.md` les décrit :
`sharpe.py` (erreur-type, PSR, longueur minimale, durée minimale de backtest après N essais,
correction de Lo, écart de deux Sharpe par Memmel et par bootstrap), `risque.py` (Sortino, Omega,
VaR et CVaR, table des drawdowns, drawdown rejoué par blocs, alpha et bêta contre le hold en
Newey-West, comparaison à volatilité égale), `robustesse.py` (concentration des gains, stress des
coûts, par année, sans une paire), `selection.py` (SPA de Hansen, Romano-Wolf).
`python scripts/fiche_robustesse.py <run_id>` relit un run enregistré et écrit sa fiche.

**Relu sans y toucher** : MDE, DSR, bootstrap, reality check, Monte-Carlo, walk-forward, PBO,
synthétiques, coûts du moteur — conformes à leurs sources. Un écart noté, non corrigé parce qu'il
changerait des chiffres publiés : dans `invest/metriques.standard`, le Sharpe divise l'excédent
moyen par l'écart-type du rendement brut (et non de l'excédent) ; l'effet est de l'ordre de la
cinquième décimale.

**Ouvert** : (1) brancher la fiche dans le rapport d'expérience, ou non ; (2) les décisions 2 à 9
de l'audit des portes ont maintenant leurs outils (Memmel et volatilité égale pour S8, PSR et
durée minimale pour S2, drawdown par blocs pour S4, SPA pour S7) — les règles restent à décider.
