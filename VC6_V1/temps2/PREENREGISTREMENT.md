# VC6 V1 — « Temps 2 » : préenregistrement

- **Écrit le** : 02/11/2026 (UTC), avant tout code du moteur VC6 et tout calcul de variante.
- **Id au registre** : `VC6_V1_TEMPS2`, famille invest, 5 essais (4 variantes + le test annexe).
- **Règles** : `VC6_V1/spec_figee.md`, spec et addendums jusqu'à celui du 02/11/2026 inclus. Les valeurs que le code lit sont dans `beta/vc6/regles.py` ; l'empreinte de ces règles et celle de ce texte sont écrites au registre. La campagne refuse de tourner si l'une ou l'autre a changé.
- **Cadre** : backtest de diagnostic. Les données crypto ont déjà été vues, donc ce run peut éliminer des choix, pas les valider. Une correction après un résultat devient une V2 datée.

## Prompt de Jonas du 02/11/2026, mot pour mot

=== PROMPT GO PHASE 3 ===
GO phase 3 : « Temps 2 ». Relis spec_figee.md et les conclusions des phases 1 et 2.

AVANT TOUT CALCUL
1. Écris ma prédiction, mot pour mot et datée du 31/10/2026, dans VC6_V1/prediction_jonas.md :
   « Le levier va être mal utilisé, et au moins une variante va soit surperformer mais se faire tuer au drawdown, soit être trop calme et se faire tuer sur la performance mais survivre. HAR ne sera pas un grand changement par rapport à l'écart-type 30 jours. Les modèles de volatilité, censés être le centre de la stratégie, ne seront pas très efficaces, faute de poids dans la décision. Ne pas utiliser plusieurs SMA, ni l'écart entre la SMA et le prix, peut être une erreur. La variante la plus risquée dépassera 40 % de drawdown max. »
   Ajoute en dessous la lecture chiffrée :
   - HAR ≈ écart-type 30 jours si sa QLIKE moyenne est à moins de 10 % de celle de l'écart-type 30 jours sur au moins 2 actifs sur 3 ;
   - volatilité peu efficace si la « Variante expo vol » échoue à la règle de décision 1 ;
   - levier mal utilisé si, sur le « Test annexe – cible 40 % », les phases en levier rapportent moins que le financement payé pendant ces phases ;
   - drawdown confirmé si au moins une variante ou le test annexe dépasse 40 % de drawdown max ;
   - SMA unique : pas testable ici, lue à travers le retard de sortie et le coût des aller-retours (voir rapport).
2. Ajoute 5 essais au compteur de la famille invest (4 variantes + le test annexe) et note la nouvelle valeur.
3. Moteur VC6 : code-le, ou complète l'existant, strictement selon spec_figee.md. Puis fais passer ces tests de cohérence AVANT tout run de variante :
   a. BTC seul, exposition 1, sans levier, sans frais : le moteur reproduit une stratégie SMA 200 calculée à part dans un petit script indépendant (écart de valeur finale < 0,1 %) ;
   b. exposition 1 en permanence, sans régime, sans frais : le moteur reproduit le panier 50/25/25 rééquilibré chaque jour, calculé à part ;
   c. anticipation : appliquer volontairement la décision du jour t au rendement du jour t doit AMÉLIORER les résultats ; sinon, l'alignement des dates est faux ;
   d. frais : un aller-retour complet de 100 % du capital coûte bien 2 × 10 pb ;
   e. funding : sur une semaine en levier tirée au hasard, le financement déduit correspond au calcul fait à la main.
   Si un test échoue, tu t'arrêtes et tu me montres l'écart. Les résultats des 5 tests vont en tête du rapport.

ORDRE DES RUNS
1. « Variante expo fixe » et « Variante expo vol », chacune avec son « Témoin expo constante ».
2. « Test annexe – cible 40 % » avec son « Témoin expo constante ». Non éligible aux règles de décision : seulement rapporté.
3. Désigne la meilleure entre « Variante expo fixe » et « Variante expo vol » selon la règle de décision 2 (ratio rendement annualisé / Ulcer). Si aucune n'est utile, prends celle qui a le ratio rendement / Ulcer le plus haut et note-le.
4. « Variante poche or » et « Variante poche mixte » sur ce sizing.
5. Robustesse : BTC seul depuis 2014. Si les bougies 5 min ne remontent pas à 2014, utilise l'écart-type 30 jours comme σ̂ pour ce test, et écris-le en tête de la section robustesse.
6. Pour chaque essai : nulls circulaire et segments (règle D4), Sharpe déflaté avec le compteur à jour, PBO (module S10).

RAPPORT : VC6_V1/rapport_temps2.md
- Résultats des 5 tests de cohérence du moteur.
- Tableau des mesures pour chaque variante, le test annexe, chaque témoin, le panier buy and hold et l'ETF monde (avec le ratio rendement / Ulcer).
- Les 4 règles de décision appliquées, une ligne par règle, avec les chiffres.
- La grille du verdict VC6, pour info.
- Levier, pour chaque variante et le test annexe : exposition moyenne, nombre de jours avec Ei > 1, rendement et drawdown pendant ces phases, financement payé pendant ces phases.
- SMA 200 : pour chaque grand bear, nombre de jours entre le plus haut du BTC et la bascule en baissier, et perte subie pendant ce délai ; nombre d'aller-retours autour de la SMA 200 (bascules annulées en moins de 30 jours) et leur coût total.
- Tableau « où ça coince » :
  - les 5 pires drawdowns datés : début, creux, récupération, profondeur, mode et exposition au début ;
  - contribution de chaque poche au rendement et au drawdown ;
  - coût total des frais et du financement ;
  - nombre de jours passés en rampe ;
  - jours de conflit (BTC baissier alors qu'ETH ou SOL est au-dessus de sa SMA 200) et leur effet.
- Red team : pour chaque point, dis si les résultats le confirment, chiffre à l'appui.
  1. Cible de 25 % trop proche de la limite de drawdown de 25 %, avec levier jusqu'à ×2.
  2. Sortie lente sur 5 jours pendant un krach.
  3. Peu d'historique pour SOL.
  4. Un seul grand bear (2022).
  5. Sortie forcée par le BTC.
  6. Poche baissière BTC sans multiplicateur.
- Comparaison des résultats avec ma prédiction, point par point, selon la lecture chiffrée : confirmée, infirmée ou non mesurable.

INTERDIT : modifier une règle, un seuil ou une période après avoir vu un résultat.
Si tu trouves un bug, tu t'arrêtes et tu me le signales. La correction sera une V2 datée.
=== FIN PROMPT ===

## Applications (comment le code lit la spec, écrites avant tout calcul)

La spec ne précise pas certains points de mécanique. Voici la lecture retenue pour chacun, sans nouvelle règle de décision. Les points marqués *(rapport)* ne servent qu'au rapport et ne décident rien.

### Données et dates
1. **Clôture du jour D** des perpétuels BTC, ETH et SOL : celle de la barre 5 min ouverte en D à 23:55 UTC (amendement du 01/11, décision 2 du 01/11 pour le BTC). Rendement du jour D = C(D) / C(D − 1) − 1.
2. **Décision à la clôture du jour t**, appliquée au rendement du jour t + 1. Aucune donnée postérieure à la clôture de t.
3. **SMA 200** : moyenne des 200 dernières clôtures, jour t compris. Mode baissier si C_BTC(t) < SMA200_BTC(t), sinon haussier.
4. **σ̂i(t)** = √(365 × h_i(t)), où h_i(t) est la prévision HAR après replis du « Contrôle HAR » (variance journalière moyenne des 5 jours suivants), calculée par les fonctions de `beta.controle_har` sur les mêmes copies figées.
5. **Période principale** : rendements du 01/06/2021 au 31/10/2026 ; première décision à la clôture du 31/05/2021.
6. **Position de départ** : la cible du mode du 31/05/2021, sans rampe et sans frais d'entrée, comme le moteur invest existant et comme les témoins.

### Exposition et positions
7. **Positions** en fraction du capital : poche i en haussier, x_i = w_i × Ei (w = 50 %, 25 %, 25 %) ; en baissier, x_i = 0 et la poche baissière vaut 25 % (BTC), 25 % (or) ou 12,5 % BTC + 12,5 % or. Le reste du capital est en cash, à rendement nul. L'exposition est une fraction du capital, remise chaque jour (rééquilibrage implicite, comme `beta.invest.moteur`) ; seuls les changements d'exposition décidés paient des frais.
8. **Ordre de calcul de Ei** : Ei = clip(cible / σ̂i ; 0,2 ; 2) (« Variante expo fixe » : Ei = 1), puis plafond de 1 si le funding annualisé dépasse 20 %, puis sécurité de liquidation.
9. **Funding du jour t** : les règlements de ]t 00:00 ; t + 1 00:00] UTC (le règlement de 00:00 paie les 8 heures qui le précèdent, voir l'inventaire). Funding annualisé = moyenne de ces règlements × leur nombre × 365.
10. **Sécurité de liquidation** : marge = 0,5 % (addendum du 02/11). Si 1/Ei − 0,005 < 3 × σ̂i/√365, alors Ei = 1/(0,005 + 3 × σ̂i/√365). Un jour contraint = un jour où cette réduction s'applique à au moins une poche (compté par poche et au total).
11. **Financement payé** le jour t + 1 : Σ_i max(Ei − 1 ; 0) × w_i × (somme signée des règlements de i dans ]t + 1 00:00 ; t + 2 00:00]). Un funding négatif est reçu.

### Rampe, bande, frais
12. **Rampe** : quand le mode bascule à la clôture de t, les expositions des décisions t, t + 1, …, t + 4 (k = 1 à 5) valent E_départ + k/5 × (cible_k − E_départ). E_départ est l'exposition en vigueur avant la bascule ; cible_k est la cible du nouveau mode, recalculée chaque jour (σ̂, funding). À k = 5, l'exposition est la cible. Une nouvelle bascule pendant une rampe repart de l'exposition en vigueur. Pas de bande pendant la rampe. La poche baissière suit la même rampe (de 0 à 25 % ou de 25 % à 0).
13. **Bande**, hors rampe, poche par poche : la nouvelle exposition est la cible si |cible − actuelle| > 10 % × actuelle, sinon l'actuelle reste.
14. **Frais** : 10 pb × Σ par actif de |variation de la position nette de l'actif| (en BTC, la poche BTC et la part BTC de la poche baissière sont additionnées : on n'achète pas et ne vend pas le même actif le même jour). Ils sont payés le jour où la nouvelle position s'applique.
15. **Or** : clôture `XAU_SPOT` du jour UTC (addendum du 02/11). Samedi, dimanche et jours sans valeur : dernier cours connu, rendement nul. Les valeurs du dimanche soir sont ignorées.

### Témoin, tests, décisions
16. **« Témoin expo constante »** : Ē = moyenne, sur les jours de la période, de l'exposition totale Σ x (poche baissière comprise) de la variante comparée ; x_i = Ē × w_i chaque jour, sur BTC, ETH et SOL ; même moteur (financement si Ē > 1).
17. **Nulls (règle D4)** : le signal tiré au hasard est la série du **mode** (haussier ou baissier) aux jours de décision. Décalage circulaire (m = 90 jours) et mélange de segments (`beta.invest.nulls`), B = 1 000 tirages chacun, graine 0, clés de flux par variante. Chaque tirage refait tout le moteur (rampe, bande, poche baissière, σ̂ à ses vraies dates). Métrique : Ulcer. p = (1 + #{Ulcer nul ≤ Ulcer observé}) / (1 + B) ; p retenue = la plus grande des deux.
18. **Règle 1** : utile = Ulcer < Ulcer du témoin ET p retenue < 0,05.
19. **Règle 2 et désignation de la meilleure** (ordre des runs, point 3) : si ni « Variante expo fixe » ni « Variante expo vol » n'est utile, la meilleure est celle qui a le plus haut ratio rendement annualisé / Ulcer, et c'est noté. Sinon, si « Variante expo vol » est utile et que son ratio dépasse celui de « Variante expo fixe », c'est « Variante expo vol ». Sinon, c'est « Variante expo fixe ».
20. **Règle 3** : comparée à la meilleure variante à poche BTC (point 19). Si une seule des deux variantes de poche remplit la règle, elle remplace la poche BTC. Si les deux la remplissent, les deux sont rapportées et le choix revient à Jonas (la spec ne dit pas laquelle prendre).
21. **Règle 4** : si ni « Variante expo fixe » ni « Variante expo vol » n'est utile, la conclusion est « exposition constante × HAR ».
22. **Sharpe déflaté** : `beta.stats.multitest.sharpe_degonfle`, au compteur invest après l'ajout des 5 essais.
23. **PBO** (addendum du 02/11, rapportée sans effet) : `beta.stats.pbo.calculer` (16 blocs, Sharpe, seuil 20 %) sur les rendements quotidiens : (a) le choix complet entre les 4 variantes ; (b) le choix du sizing (fixe, vol) ; (c) le choix de la poche baissière (BTC, or, mixte) sur le sizing retenu.

### Mesures
24. **Mesures** : Ulcer = racine de la moyenne des drawdowns au carré sur les jours de la période ; drawdown max ; rendement annualisé (365 jours) ; Sharpe √365, sans taux sans risque ; ratio rendement annualisé / Ulcer ; exposition moyenne (Σ x) ; changements par an = jours où au moins une position change / années ; financement payé ; frais payés ; jours contraints par la sécurité de liquidation.
25. **Références à risque égal** : panier buy and hold 50/25/25 (clôtures des perpétuels, sans rééquilibrage) et ETF monde URTH (seul ETF monde présent ; clôture de la séance américaine, rendement nul les jours sans séance), chacun multiplié par k = vol réalisée de la variante / vol réalisée de la référence. *(verdict, pour info)* « Bat » = rendement annualisé plus haut à risque égal.
26. **Robustesse BTC seul depuis 2014** : clôtures Bitstamp au comptant (DS1 `bougies_1d`), rendements du 01/01/2014 au 31/10/2026, une poche à 100 %, poche baissière 25 % BTC, σ̂ = écart-type 30 jours des rendements log journaliers de Bitstamp (annualisé √365 ; les bougies 5 min commencent le 08/09/2019). Funding fixe de 0,01 % par règlement, 3 par jour, avant le 10/09/2019, puis le funding réel du perpétuel BTC. Marge 0,5 %. Témoin et nulls calculés pour information.

### Rapport seulement
27. *(rapport)* **Grand bear** : épisode de baisse du BTC d'au moins 30 % depuis son plus haut (`beta.invest.metriques.episodes`, θ = 0,30), sur la période principale (perpétuel) et sur la robustesse (Bitstamp). Délai = jours entre le plus haut et la première bascule en baissier qui suit ; perte subie = baisse du BTC et perte de chaque variante entre le plus haut et cette bascule.
28. *(rapport)* **Aller-retour** : une bascule suivie de la bascule inverse moins de 30 jours plus tard. Coût = frais payés de la première bascule à la fin de la rampe qui suit la bascule inverse, et rendement de la variante comparé à celui du « Témoin expo constante » sur la même fenêtre.
29. *(rapport)* **5 pires drawdowns** : épisodes de la courbe de la variante, sans chevauchement, classés par profondeur.
30. *(rapport)* **Contribution d'une poche** : Σ x_i(t − 1) × r_i(t), sur toute la période et entre le plus haut et le creux du drawdown max ; frais et financement à part.
31. *(rapport)* **Jours de conflit** : BTC baissier alors qu'ETH ou SOL est au-dessus de sa propre SMA 200. Effet = Σ w_i × Ei cible × r_i du lendemain, c'est-à-dire ce que la poche aurait gagné ou perdu si elle avait été investie. Jours inverses (addendum du 01/11) : BTC haussier alors qu'ETH ou SOL est sous sa propre SMA 200, avec la perte de chaque poche ces jours-là, par poche et au total.
32. *(rapport)* **Volatilité réalisée d'une poche** (addendum du 01/11 au soir, point 3) : écart-type √365 de Ei × r_i sur les jours où la poche est investie, comparé à 25 % (40 % pour le test annexe).
33. *(rapport)* **Perpétuel contre Bitstamp** : jours de la période commune où les deux SMA 200 existent et où le mode global diffère.
34. *(rapport)* **Phases en levier** : jours où au moins une poche a Ei > 1. Rendement, drawdown (sur la courbe chaînée de ces jours) et financement de ces jours. Pour la lecture « levier mal utilisé » : gain de la part en levier, Σ max(Ei − 1 ; 0) w_i r_i, comparé au financement payé ces jours-là.
35. *(rapport)* **Sortie lente** : sur chaque rampe vers le baissier, perte de la rampe par rapport à une sortie immédiate, Σ (x en rampe − x cible) × r.

## Déjà connu au moment du gel

- Les prix crypto de 2019 à 2026 et les grandes baisses publiques du BTC (2014, 2018, 2022) sont connus de tous.
- Résultats des phases 1 et 2 : ETH et SOL non retenus au « Temps 1 – complément ETH et SOL » ; σ̂ = HAR pour les trois actifs (QLIKE HAR / écart-type 30 jours : BTC 0,2372 / 0,4040, ETH 0,2799 / 0,4923, SOL 0,3694 / 0,5955).
- **Vu le 02/11 en vérifiant la couverture des prévisions, avant tout run** : sur la période principale, aucune prévision σ̂ ne manque. σ̂ HAR annualisé : BTC entre 36 % et 132 % (médiane 53 %), ETH entre 51 % et 206 % (médiane 68 %), SOL entre 74 % et 590 % (médiane 110 %). Avec la cible de 25 %, 0,25/σ̂ ne dépasse donc jamais 1 : aucune poche ne passera en levier dans la « Variante expo vol ». Seul le test annexe (40 %) peut en créer, sur le BTC. Aucune règle n'a été changée après ce constat.
- Aucun chiffre de variante, de témoin ou de référence n'a été calculé.
