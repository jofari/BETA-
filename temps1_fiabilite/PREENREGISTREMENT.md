# Prompt Claude Code — BETA / Temps 1 – fiabilité du test de justesse

> Préenregistré le 24/10/2026, avant tout calcul de fiabilité. Ce test ne modifie ni les règles ni le verdict de « Temps 1 – justesse » (rapport `temps1_justesse/RAPPORT_JUSTESSE.md`, code `8afdbe7`). Il vérifie si ses résultats sont dus à une vraie détection ou au hasard.

---

## Question

Les détecteurs C1_V1 et C1_V2 ont une latence d'entrée (f_entrée) bien plus faible que la SMA 200, mais ils basculent environ 3 fois plus souvent. Un détecteur qui est souvent en bear peut se trouver en bear au moment d'un pic par simple hasard, ce qui donne f = 0.

**Est-ce que C1_V1 et C1_V2 détectent les bears plus tôt qu'un détecteur aléatoire qui aurait exactement la même agitation ?**

## Règles absolues

1. Ne modifie rien de `temps1_justesse/` (code, données, rapport, verdict). Nouveau module `temps1_fiabilite/`, qui réutilise le juge, les signaux et les mesures du commit `8afdbe7` sans les recoder.
2. Aucun nouveau détecteur, aucun paramètre optimisé. Les signaux testés sont exactement ceux de `temps1_justesse`.
3. Compteur : ce test ne crée aucune nouvelle configuration de détecteur. Il n'ajoute **aucun essai**. Il est journalisé dans `EXPERIMENTS.jsonl` (id `T1F`) comme diagnostic, famille régime / invest.
4. Ambiguïté ou impossibilité → tu t'arrêtes et tu l'écris. Tu ne choisis jamais toi-même.
5. Code et tests committés avant le premier calcul ; le rapport affiche le hash. Tous les chiffres sont générés par le script, graine 0.

## Détecteurs et actifs

- Détecteurs : SMA200, MOM126, C1_V1, C1_V2 (SMA200 et MOM126 servent de comparaison : le même test leur est appliqué).
- Actifs : S&P 500, Nasdaq-100, or (période labo 1991-2023, mêmes périodes mesurées que `temps1_justesse`) et BTC (étape B).
- Juge : le juge principal de `temps1_justesse` (baisse de référence 20 %, σ 2 ans recalculé chaque trimestre). Les bears utilisés sont exactement ceux du rapport.

## Test 1 — Détecteur aléatoire de même agitation (verdict de fiabilité)

Pour chaque détecteur × actif, construire **1 000 signaux aléatoires** (graine 0) par **permutation des épisodes** :
- découper le signal observé en épisodes consécutifs de même état (bear, bull, neutre) ;
- mélanger l'ordre de ces épisodes, en gardant la durée et l'état de chacun ;
- cela conserve exactement la part de jours bear / bull / neutre, le nombre de bascules et la distribution des durées. Seule la position dans le temps change.

Pour chaque signal aléatoire, calculer avec les mêmes fonctions que `temps1_justesse` : médiane de f_entrée (ratés = 1), fausses alertes par an, justesse équilibrée.

Mesures :
- **p_latence** = part des signaux aléatoires dont la médiane de f_entrée est ≤ celle du détecteur observé ;
- **p_justesse** = part des signaux aléatoires dont la justesse est ≥ celle du détecteur observé ;
- rapporter aussi la médiane et l'intervalle 5 % – 95 % de la f_entrée aléatoire.

Lecture (règle D4 de BETA, inchangée) : p < 0,05 = réel ; 0,05 ≤ p < 0,20 = non concluant ; p ≥ 0,20 = indistinguable du hasard.

Test 1 bis (robustesse, rapporté) : même test avec un **décalage circulaire** du signal (décalage aléatoire d'au moins 90 jours), qui conserve aussi l'ordre des épisodes.

## Test 2 — Diagnostic des f = 0 (rapporté, ne décide rien)

Pour chaque bear du juge et chaque détecteur :
- le détecteur était-il **déjà en bear le jour du pic** ? Si oui, depuis combien de séances ?
- part des f_entrée = 0 qui viennent d'un signal déjà en bear au pic ;
- f_entrée recalculée en ignorant les épisodes bear commencés plus de 21 séances avant le pic (diagnostic uniquement, cette variante n'est pas une nouvelle règle).

## Verdict de fiabilité (fixé maintenant)

- Un résultat de latence de C1_V1 ou C1_V2 est **fiable** s'il obtient p_latence < 0,05 au test 1 **sur le témoin actions ET sur l'or** (témoin = moyenne S&P 500 et Nasdaq-100, comme dans `temps1_justesse`).
- Il est **non concluant** si l'un des deux est entre 0,05 et 0,20 et aucun au-dessus.
- Il est **dû à l'agitation** si l'un des deux a p_latence ≥ 0,20.
- Le BTC est rapporté : il peut signaler un problème, il ne valide rien seul.
- Le verdict de `temps1_justesse` n'est pas modifié. Ce test dit seulement s'il est fiable.

## Rapport

`temps1_fiabilite/RAPPORT_FIABILITE.md`, écrit par le script :
1. Hash du code, des données et de ce préenregistrement.
2. Tableau test 1 : détecteur × actif, f_entrée observée, f_entrée aléatoire (médiane, 5 %–95 %), p_latence, justesse observée, justesse aléatoire, p_justesse, lecture D4.
3. Même tableau pour le test 1 bis.
4. Test 2 : tableau par épisode (déjà en bear au pic, depuis combien de séances), part des f = 0 concernées, f_entrée diagnostic.
5. Verdict de fiabilité mécanique.
6. Écarts au prompt.

Exporte aussi en CSV. Aucune interprétation au-delà du verdict mécanique.

---

## Clarifications avant calcul (24/10/2026)

Ajoutées le 24/10/2026, avant tout calcul de fiabilité. Ce sont les réponses de Jonas aux
ambiguïtés relevées en appliquant la règle 4.

**1. Permutation (test 1).** Un mélange brut de l'ordre des épisodes fait fusionner deux
épisodes voisins de même état, et ne conserve donc pas le nombre de bascules. Décision de
Jonas : **la suite des états observée est gardée (bear, bull, neutre dans le même ordre), et
les durées sont mélangées entre épisodes du même état.** Les parts de jours, le nombre de
bascules et les durées sont ainsi conservés exactement ; seules les positions changent.

**2. Plage.** La permutation (test 1) et le décalage (test 1 bis) portent sur **la période
mesurée de chaque actif dans `temps1_justesse`**, c'est-à-dire [premier pivot du juge dans la
période, dernier pivot dans la période[, là où toutes les mesures sont calculées. Hors de cette
plage, le signal reste celui observé.

**3. Témoin actions.** Le calcul se fait **tirage par tirage** : pour le tirage k, la valeur
aléatoire du témoin est la moyenne des valeurs S&P 500 et Nasdaq-100 du tirage k. p est la part
des 1 000 tirages au moins aussi bons que le témoin observé (moyenne des deux valeurs
observées).

**4. Décalage circulaire (test 1 bis).** Il est compté **en séances de l'actif**, tiré
uniformément dans **[90, N − 90]**, où N est la longueur de la plage. Le décalage est donc
d'au moins 90 séances dans les deux sens. Pour le BTC, séances = jours.

**Applications, sans choix de Claude :**
- **Compteur.** « Aucun essai » et « journalisé dans `EXPERIMENTS.jsonl` » étaient
  incompatibles avec le code de BETA, où toute expérience préenregistrée comptait +1 tant
  qu'elle n'avait pas de mesure. Le protocole reçoit une marque `diagnostic=True` que le
  compteur ignore. T1F la porte, en famille invest, et ne journalise aucun run dans
  `RUNS.jsonl`.
- **Test 2.** « Déjà en bear le jour du pic » est rapporté en trois cas, sans en retenir un
  seul :
  - en bear depuis au moins 1 séance avant le pic (avec le nombre de séances) ;
  - bascule bear le jour même du pic (0 séance) ;
  - pas en bear au pic.
  La part des f = 0 est donnée pour chaque cas. La f_entrée diagnostic suit la convention A de
  `temps1_justesse` (raté = 1).
- **Données.** T1F tourne sur exactement les données de T1J (empreinte `a3d6d80952500d57`), en
  coupant chaque série à sa date de fin dans T1J. Il vérifie que les bears, les périodes
  mesurées et les mesures observées sont ceux du rapport de T1J. Sinon, il s'arrête.
- **Graine 0.** Elle est appliquée par couple détecteur × actif et par test, comme les tirages
  de T1J.
