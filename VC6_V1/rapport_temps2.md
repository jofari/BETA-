# VC6 V1 — rapport du « Temps 2 »

- Écrit par le programme (`scripts/vc6_temps2.py`, commit `fd965b5`), règles `e1a40b41393ae196`, préenregistrement `VC6_V1/temps2/PREENREGISTREMENT.md`.
- Période principale : rendements du 2021-06-01 au 2026-10-31 (1979 jours).
- Compteurs : invest **59** (54 + 5 essais), global 152, trading 93. Sharpe déflaté au N invest = 59.
- Backtest de diagnostic : il peut éliminer des choix, pas les valider.

## ⚠️ Anomalies relevées à la relecture (02/11/2026, Claude, après le calcul)

Cette section n'est pas écrite par le programme. Rien n'a été corrigé, selon la consigne : la correction sera une V2 datée.

1. **Bug, section 6 « Aller-retours » (mesure de rapport, application 28).** Les fenêtres de deux aller-retours qui se suivent se chevauchent (par exemple 2021-08-09 → 08-12, puis 08-12 → 08-13). Leurs frais et leurs écarts au témoin sont donc additionnés plusieurs fois. Preuve : les frais des aller-retours de la « Variante expo fixe » (3,408 %) dépassent ses frais totaux (1,97 %, section 2). Le nombre (40 bascules annulées en moins de 30 jours) est juste ; les deux colonnes de coût sont fausses.
2. **Bug, section 8 « Grands bears depuis 2014 » (mesure de rapport, application 27).** La bascule en baissier est cherchée après le plus haut sans s'arrêter à la fin de l'épisode. Trois épisodes de 2017 (plus haut le 04/01, le 11/06 et le 01/09) reçoivent ainsi la bascule du 05/02/2018, avec des délais de 397, 239 et 157 jours et des « baisses » de +516,6 %, +132,7 % et +39,7 %. Les cinq autres lignes de cette table, ainsi que les deux lignes de la période principale, ont leur bascule à l'intérieur de l'épisode.
3. **Pas un bug, vérifié.** Le « Test annexe – cible 40 % » n'a aucun jour en levier. Sur 16 jours haussiers, le σ̂ du BTC est sous 40 % (de 38,4 % à 40,0 %), donc la cible de Ei dépasse 1 (au plus 1,041). Mais l'exposition en place est de 0,974, et l'écart reste sous la bande de 10 % : la position ne change pas. C'est la règle de la spec appliquée telle quelle.
4. **Lecture à nuancer, red team point 2.** La conclusion automatique « infirmé » ne lit que la « Variante expo fixe » (−1,71 %). La « Variante expo vol » (+3,65 %) et le test annexe (+4,42 %) montrent au contraire un coût de la rampe. Les trois chiffres sont dans la ligne.

Aucune de ces anomalies ne touche le moteur, les 5 essais, les nulls, la PBO, les règles de décision ni la grille du verdict.

## 1. Tests de cohérence du moteur (avant tout run)

| test | moteur | calcul à part | écart | passe |
|---|---|---|---|---|
| a1. BTC seul, SMA 200, exposition 1, bascule immédiate, sans frais | 2,340241 | 2,340241 | 0,0000 % | oui |
| a2. BTC seul, exposition 1, rampe 5 jours, poche baissière 25 % BTC, sans frais | 2,252071 | 2,252071 | 0,0000 % | oui |
| b. Panier 50/25/25 rééquilibré chaque jour, sans régime ni frais | 2,470541 | 2,470541 | 0,0000 % | oui |
| c. Anticipation (BTC seul, SMA 200, bascule immediate, sans frais) : valeur finale normale → anticipée ; Ulcer | 2,340 → 15,826 | Ulcer 22,58 % → 10,81 % | amélioration attendue | oui |
| c. Anticipation (BTC, ETH, SOL 50/25/25, regime, rampe 1 jour, sans poche baissiere ni frais) : valeur finale normale → anticipée ; Ulcer | 4,147 → 34,354 | Ulcer 22,88 % → 10,54 % | amélioration attendue | oui |
| d. Aller-retour de 100 % du capital (rendements nuls) | frais 0,002000, valeur 0,998001 | 0,002000 ; 0,998001 | 0 | oui |
| e. Funding, semaine du 2026-02-19 au 2026-02-25 (tirée parmi 1663 semaines à Ei = 2, graine 0) | -2.931450000000e-04 | -2.931450000000e-04 | 1.1e-19 | oui |

Le calcul à part des tests a et b est `VC6_V1/temps2/verif_independante.py`. Il n'importe rien de BETA. Le test e refait la somme à la main sur les règlements bruts de chaque jour.

## 2. Mesures

| série | Ulcer | drawdown max | rendement annualisé | Sharpe √365 | rendement / Ulcer | Sharpe déflaté | exposition moyenne | changements / an | financement payé | frais payés | jours contraints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Variante expo fixe | 27,16 % | −46,0 % | 26,5 % | 0,77 | 0,98 | 0,290 | 0,646 | 30,6 | 0,00 % | 1,97 % | 0 |
| Témoin expo constante (Variante expo fixe) | 32,91 % | −65,7 % | 16,6 % | 0,58 | 0,50 | — | 0,646 | 0,0 | 0,00 % | 0,00 % | — |
| Variante expo vol | 13,90 % | −28,1 % | 10,1 % | 0,64 | 0,73 | 0,195 | 0,321 | 63,6 | 0,00 % | 0,99 % | 0 |
| Témoin expo constante (Variante expo vol) | 17,58 % | −39,2 % | 10,2 % | 0,58 | 0,58 | — | 0,321 | 0,0 | 0,00 % | 0,00 % | — |
| Test annexe – cible 40 % | 18,12 % | −32,8 % | 14,2 % | 0,66 | 0,79 | 0,207 | 0,442 | 67,9 | 0,00 % | 1,79 % | 0 |
| Témoin expo constante (Test annexe – cible 40 %) | 23,59 % | −50,5 % | 13,1 % | 0,58 | 0,55 | — | 0,442 | 0,0 | 0,00 % | 0,00 % | — |
| Variante poche or | 23,21 % | −42,5 % | 26,8 % | 0,78 | 1,15 | 0,302 | 0,646 | 30,6 | 0,00 % | 3,29 % | 0 |
| Témoin expo constante (Variante poche or) | 32,91 % | −65,7 % | 16,6 % | 0,58 | 0,50 | — | 0,646 | 0,0 | 0,00 % | 0,00 % | — |
| Variante poche mixte | 24,80 % | −41,2 % | 26,8 % | 0,78 | 1,08 | 0,300 | 0,646 | 30,6 | 0,00 % | 2,63 % | 0 |
| Témoin expo constante (Variante poche mixte) | 32,91 % | −65,7 % | 16,6 % | 0,58 | 0,50 | — | 0,646 | 0,0 | 0,00 % | 0,00 % | — |
| Panier buy and hold 50/25/25 | 52,28 % | −87,6 % | 13,4 % | 0,53 | 0,26 | — | 1,000 | 0,0 | — | 0,00 % | — |
| ETF monde (URTH) | 9,01 % | −26,9 % | 9,4 % | 0,64 | 1,05 | — | 1,000 | 0,0 | — | 0,00 % | — |

Nulls D4 (B = 1 000 tirages chacun, signal = série du mode, métrique = Ulcer) :

| essai | Ulcer | Ulcer du témoin | p circulaire | p segments | p retenue | verdict D4 | Ulcer nul médian (circulaire / segments) |
|---|---|---|---|---|---|---|---|
| Variante expo fixe | 27,16 % | 32,91 % | 0,148 | 0,267 | 0,267 | hasard | 36,95 % / 36,28 % |
| Variante expo vol | 13,90 % | 17,58 % | 0,154 | 0,250 | 0,250 | hasard | 15,50 % / 15,13 % |
| Test annexe – cible 40 % | 18,12 % | 23,59 % | 0,156 | 0,287 | 0,287 | hasard | 21,83 % / 20,95 % |
| Variante poche or | 23,21 % | 32,91 % | 0,124 | 0,213 | 0,213 | hasard | 37,11 % / 35,67 % |
| Variante poche mixte | 24,80 % | 32,91 % | 0,135 | 0,273 | 0,273 | hasard | 36,40 % / 34,56 % |

PBO (S10, 16 blocs, Sharpe), **rapportée sans effet** (addendum du 02/11) :

- quatre variantes : PBO = 88,7 % ; 4 configurations distinctes, 1968 jours ; sous le seuil de 20 % : non.
- sizing : PBO = 48,0 % ; 2 configurations distinctes, 1968 jours ; sous le seuil de 20 % : non.
- poche baissiere : PBO = 96,0 % ; 3 configurations distinctes, 1968 jours ; sous le seuil de 20 % : non.

## 3. Règles de décision

1. **Utile = Ulcer < témoin avec p < 0,05.** Variante expo fixe : Ulcer 27,16 % contre témoin 32,91 %, p 0,267 → pas utile ; Variante expo vol : Ulcer 13,90 % contre témoin 17,58 %, p 0,250 → pas utile ; Variante poche or : Ulcer 23,21 % contre témoin 32,91 %, p 0,213 → pas utile ; Variante poche mixte : Ulcer 24,80 % contre témoin 32,91 %, p 0,273 → pas utile. (Test annexe, non éligible : pas utile au même critère, rapporté seulement.)
2. **« Variante expo vol » retenue si utile et ratio > celui de « Variante expo fixe ».** Ratio rendement / Ulcer : expo vol 0,73, expo fixe 0,98 ; expo vol utile : non → retenue : non. Meilleure désignée : **Variante expo fixe** (aucune des deux n'est utile : plus haut ratio rendement / Ulcer).
3. **Poche or ou mixte si Ulcer plus bas et rendement ≥ meilleure à poche BTC − 2 points.** Variante poche or : Ulcer 23,21 % contre 27,16 % (plus bas), rendement annualisé 26,8 % contre seuil 24,5 % → remplace ; Variante poche mixte : Ulcer 24,80 % contre 27,16 % (plus bas), rendement annualisé 26,8 % contre seuil 24,5 % → remplace. Conclusion : **les deux : choix de Jonas**.
4. **Aucune variante de sizing utile → exposition constante × HAR.** Aucune utile : oui → conclusion : exposition constante × HAR.

## 4. Grille du verdict VC6 (pour info seulement)

| essai | Sharpe > 1 | drawdown max < 25 % | bat le panier à risque égal | bat l'ETF monde à risque égal |
|---|---|---|---|---|
| Variante expo fixe | 0,77 → non | −46,0 % → non | 26,5 % contre 14,2 % → oui | 26,5 % contre 20,1 % → oui |
| Variante expo vol | 0,64 → non | −28,1 % → non | 10,1 % contre 8,0 % → oui | 10,1 % contre 10,3 % → non |
| Test annexe – cible 40 % | 0,66 → non | −32,8 % → non | 14,2 % contre 10,6 % → oui | 14,2 % contre 13,9 % → oui |
| Variante poche or | 0,78 → non | −42,5 % → non | 26,8 % contre 14,0 % → oui | 26,8 % contre 19,7 % → oui |
| Variante poche mixte | 0,78 → non | −41,2 % → non | 26,8 % contre 14,1 % → oui | 26,8 % contre 19,8 % → oui |

« Bat » = rendement annualisé plus haut que la référence ramenée à la même volatilité réalisée (application 25).

## 5. Levier

| essai | exposition moyenne | jours avec Ei > 1 | rendement de ces jours | drawdown de ces jours | financement payé ces jours | gain de la part en levier |
|---|---|---|---|---|---|---|
| Variante expo fixe | 0,646 | 0 | 0,00 % | 0,00 % | 0,000 % | 0,000 % |
| Variante expo vol | 0,321 | 0 | 0,00 % | 0,00 % | 0,000 % | 0,000 % |
| Test annexe – cible 40 % | 0,442 | 0 | 0,00 % | 0,00 % | 0,000 % | 0,000 % |
| Variante poche or | 0,646 | 0 | 0,00 % | 0,00 % | 0,000 % | 0,000 % |
| Variante poche mixte | 0,646 | 0 | 0,00 % | 0,00 % | 0,000 % | 0,000 % |

## 6. SMA 200 : retard de sortie et aller-retours

Grands bears (baisse du BTC ≥ 30 % depuis son plus haut, période principale) :

| plus haut | creux | retour au plus haut | baisse du BTC | bascule en baissier | délai (jours) | baisse du BTC avant la bascule | perte des variantes avant la bascule |
|---|---|---|---|---|---|---|---|
| 2021-11-08 | 2022-11-21 | 2024-03-04 | −76,7 % | 2021-12-13 | 35 | −31,0 % | Variante expo fixe −30,0 % ; Variante expo vol −9,6 % ; Test annexe – cible 40 % −15,1 % ; Variante poche or −30,0 % ; Variante poche mixte −30,0 % |
| 2025-10-06 | 2026-06-30 | pas encore | −53,0 % | 2025-10-17 | 11 | −14,6 % | Variante expo fixe −17,2 % ; Variante expo vol −7,4 % ; Test annexe – cible 40 % −11,8 % ; Variante poche or −17,2 % ; Variante poche mixte −17,2 % |

Aller-retours autour de la SMA 200 (bascule annulée en moins de 30 jours ; le mode est le même pour toutes les variantes) : **40**.

| essai | frais des aller-retours | rendement contre le témoin sur ces fenêtres |
|---|---|---|
| Variante expo fixe | 3,408 % | −61,51 % |
| Variante expo vol | 0,885 % | −24,72 % |
| Test annexe – cible 40 % | 1,667 % | −50,51 % |
| Variante poche or | 5,680 % | −86,56 % |
| Variante poche mixte | 4,544 % | −73,99 % |

Détail : 2021-08-09 → 2021-08-12 (3 j, vers haussier) ; 2021-08-12 → 2021-08-13 (1 j, vers baissier) ; 2021-08-13 → 2021-08-17 (4 j, vers haussier) ; 2021-08-17 → 2021-08-19 (2 j, vers baissier) ; 2021-08-19 → 2021-09-10 (22 j, vers haussier) ; 2021-09-10 → 2021-09-12 (2 j, vers baissier) ; 2021-09-12 → 2021-09-13 (1 j, vers haussier) ; 2021-09-13 → 2021-09-14 (1 j, vers baissier) ; 2021-09-14 → 2021-09-20 (6 j, vers haussier) ; 2021-09-20 → 2021-10-01 (11 j, vers baissier) ; 2021-12-13 → 2021-12-14 (1 j, vers baissier) ; 2021-12-14 → 2021-12-17 (3 j, vers haussier) ; 2021-12-17 → 2021-12-21 (4 j, vers baissier) ; 2021-12-21 → 2021-12-28 (7 j, vers haussier) ; 2023-08-17 → 2023-08-29 (12 j, vers baissier) ; 2023-08-29 → 2023-08-30 (1 j, vers haussier) ; 2024-07-04 → 2024-07-13 (9 j, vers baissier) ; 2024-07-13 → 2024-08-03 (21 j, vers haussier) ; 2024-08-03 → 2024-08-23 (20 j, vers baissier) ; 2024-08-23 → 2024-08-26 (3 j, vers haussier) ; 2024-08-26 → 2024-09-24 (29 j, vers baissier) ; 2024-09-24 → 2024-09-25 (1 j, vers haussier) ; 2024-09-25 → 2024-09-26 (1 j, vers baissier) ; 2024-09-26 → 2024-09-30 (4 j, vers haussier) ; 2024-09-30 → 2024-10-14 (14 j, vers baissier) ; 2025-03-09 → 2025-03-12 (3 j, vers baissier) ; 2025-03-12 → 2025-03-13 (1 j, vers haussier) ; 2025-03-13 → 2025-03-14 (1 j, vers baissier) ; 2025-03-14 → 2025-03-16 (2 j, vers haussier) ; 2025-03-16 → 2025-03-19 (3 j, vers baissier) ; 2025-03-19 → 2025-03-20 (1 j, vers haussier) ; 2025-03-20 → 2025-03-23 (3 j, vers baissier) ; 2025-03-23 → 2025-03-28 (5 j, vers haussier) ; 2025-03-28 → 2025-04-22 (25 j, vers baissier) ; 2025-10-17 → 2025-10-19 (2 j, vers baissier) ; 2025-10-19 → 2025-10-22 (3 j, vers haussier) ; 2025-10-22 → 2025-10-23 (1 j, vers baissier) ; 2025-10-23 → 2025-10-30 (7 j, vers haussier) ; 2025-10-30 → 2025-10-31 (1 j, vers baissier) ; 2025-10-31 → 2025-11-03 (3 j, vers haussier).

## 7. Où ça coince

### Variante expo fixe

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2021-11-08 | 2023-03-09 | 2023-11-10 | −46,0 % | haussier | 1,000 |
| 2024-12-17 | 2025-04-08 | 2025-08-13 | −40,1 % | haussier | 1,000 |
| 2024-03-31 | 2024-10-03 | 2024-12-06 | −35,1 % | haussier | 1,000 |
| 2025-10-06 | 2026-06-30 | pas encore | −33,3 % | haussier | 1,000 |
| 2021-09-06 | 2021-09-21 | 2021-10-20 | −23,8 % | haussier | 1,000 |

Contributions (somme des rendements quotidiens) : poche BTC +53,4 % (pendant le drawdown max : −19,9 %) ; poche ETH +25,4 % (pendant le drawdown max : −7,5 %) ; poche SOL +88,3 % (pendant le drawdown max : −13,0 %) ; poche baissière BTC +10,7 % (pendant le drawdown max : −13,5 %) ; frais −2,0 % (pendant le drawdown max : −0,3 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Frais + financement : 1,97 %. Jours en rampe : 166. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa SMA 200) : 154 ; effet (ce que les poches auraient fait investies) : ETH 101 j, +5,6 % ; SOL 146 j, +5,8 % ; total +11,4 %. Jours inverses (BTC haussier, ETH ou SOL sous sa SMA 200) : 296 ; rendement des poches ces jours-là : ETH 160 j, +4,7 % ; SOL 235 j, +8,1 % ; total +12,8 %.

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : BTC 46,8 % sur 1112 j (cible 25 %) ; ETH 62,3 % sur 1112 j (cible 25 %) ; SOL 89,4 % sur 1112 j (cible 25 %).

### Variante expo vol

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2021-11-08 | 2022-11-21 | 2023-12-05 | −28,1 % | haussier | 0,328 |
| 2025-10-06 | 2026-06-30 | pas encore | −21,1 % | haussier | 0,462 |
| 2024-12-16 | 2025-04-08 | 2025-07-16 | −16,6 % | haussier | 0,433 |
| 2024-06-05 | 2024-09-06 | 2024-11-11 | −14,0 % | haussier | 0,443 |
| 2024-03-31 | 2024-05-01 | 2024-05-20 | −8,6 % | haussier | 0,401 |

Contributions (somme des rendements quotidiens) : poche BTC +23,0 % (pendant le drawdown max : −6,3 %) ; poche ETH +8,8 % (pendant le drawdown max : −2,1 %) ; poche SOL +19,0 % (pendant le drawdown max : −2,2 %) ; poche baissière BTC +10,7 % (pendant le drawdown max : −20,7 %) ; frais −1,0 % (pendant le drawdown max : −0,1 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Frais + financement : 0,99 %. Jours en rampe : 166. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa SMA 200) : 154 ; effet (ce que les poches auraient fait investies) : ETH 101 j, +2,5 % ; SOL 146 j, +1,0 % ; total +3,5 %. Jours inverses (BTC haussier, ETH ou SOL sous sa SMA 200) : 296 ; rendement des poches ces jours-là : ETH 160 j, +2,3 % ; SOL 235 j, +1,6 % ; total +4,0 %.

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : BTC 20,8 % sur 1112 j (cible 25 %) ; ETH 23,1 % sur 1112 j (cible 25 %) ; SOL 20,6 % sur 1112 j (cible 25 %).

### Test annexe – cible 40 %

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2021-11-08 | 2022-11-21 | 2023-12-01 | −32,8 % | haussier | 0,524 |
| 2025-10-06 | 2026-06-30 | pas encore | −26,5 % | haussier | 0,739 |
| 2024-12-16 | 2025-04-08 | 2025-07-21 | −25,5 % | haussier | 0,692 |
| 2024-06-05 | 2024-10-03 | 2024-11-21 | −23,0 % | haussier | 0,705 |
| 2024-03-13 | 2024-05-01 | 2024-06-05 | −13,8 % | haussier | 0,590 |

Contributions (somme des rendements quotidiens) : poche BTC +36,9 % (pendant le drawdown max : −10,1 %) ; poche ETH +14,1 % (pendant le drawdown max : −3,4 %) ; poche SOL +29,4 % (pendant le drawdown max : −3,5 %) ; poche baissière BTC +10,7 % (pendant le drawdown max : −20,7 %) ; frais −1,8 % (pendant le drawdown max : −0,1 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Frais + financement : 1,79 %. Jours en rampe : 166. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa SMA 200) : 154 ; effet (ce que les poches auraient fait investies) : ETH 101 j, +4,5 % ; SOL 146 j, +1,5 % ; total +6,0 %. Jours inverses (BTC haussier, ETH ou SOL sous sa SMA 200) : 296 ; rendement des poches ces jours-là : ETH 160 j, +3,7 % ; SOL 235 j, +2,6 % ; total +6,3 %.

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : BTC 33,3 % sur 1112 j (cible 40 %) ; ETH 36,9 % sur 1112 j (cible 40 %) ; SOL 32,0 % sur 1112 j (cible 40 %).

### Variante poche or

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2024-03-31 | 2025-04-08 | pas encore | −42,5 % | haussier | 1,000 |
| 2021-11-08 | 2023-03-09 | 2023-10-31 | −36,4 % | haussier | 1,000 |
| 2021-09-06 | 2021-09-21 | 2021-10-20 | −24,2 % | haussier | 1,000 |
| 2024-01-10 | 2024-01-23 | 2024-02-09 | −14,8 % | haussier | 1,000 |
| 2024-03-14 | 2024-03-19 | 2024-03-31 | −12,3 % | haussier | 1,000 |

Contributions (somme des rendements quotidiens) : poche BTC +53,4 % (pendant le drawdown max : −8,7 %) ; poche ETH +25,4 % (pendant le drawdown max : −19,8 %) ; poche SOL +88,3 % (pendant le drawdown max : −15,2 %) ; poche baissière XAU +10,4 % (pendant le drawdown max : +2,9 %) ; frais −3,3 % (pendant le drawdown max : −1,3 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Frais + financement : 3,29 %. Jours en rampe : 166. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa SMA 200) : 154 ; effet (ce que les poches auraient fait investies) : ETH 101 j, +5,6 % ; SOL 146 j, +5,8 % ; total +11,4 %. Jours inverses (BTC haussier, ETH ou SOL sous sa SMA 200) : 296 ; rendement des poches ces jours-là : ETH 160 j, +4,7 % ; SOL 235 j, +8,1 % ; total +12,8 %.

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : BTC 46,8 % sur 1112 j (cible 25 %) ; ETH 62,3 % sur 1112 j (cible 25 %) ; SOL 89,4 % sur 1112 j (cible 25 %).

### Variante poche mixte

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2021-11-08 | 2023-03-09 | 2023-11-08 | −41,2 % | haussier | 1,000 |
| 2024-03-31 | 2025-04-08 | 2025-09-12 | −40,6 % | haussier | 1,000 |
| 2025-10-06 | 2026-06-30 | pas encore | −28,8 % | haussier | 1,000 |
| 2021-09-06 | 2021-09-21 | 2021-10-20 | −24,0 % | haussier | 1,000 |
| 2024-01-10 | 2024-01-23 | 2024-02-09 | −14,8 % | haussier | 1,000 |

Contributions (somme des rendements quotidiens) : poche BTC +53,4 % (pendant le drawdown max : −19,9 %) ; poche ETH +25,4 % (pendant le drawdown max : −7,5 %) ; poche SOL +88,3 % (pendant le drawdown max : −13,0 %) ; poche baissière BTC +5,3 % (pendant le drawdown max : −6,8 %) ; poche baissière XAU +5,2 % (pendant le drawdown max : +0,9 %) ; frais −2,6 % (pendant le drawdown max : −0,4 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Frais + financement : 2,63 %. Jours en rampe : 166. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa SMA 200) : 154 ; effet (ce que les poches auraient fait investies) : ETH 101 j, +5,6 % ; SOL 146 j, +5,8 % ; total +11,4 %. Jours inverses (BTC haussier, ETH ou SOL sous sa SMA 200) : 296 ; rendement des poches ces jours-là : ETH 160 j, +4,7 % ; SOL 235 j, +8,1 % ; total +12,8 %.

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : BTC 46,8 % sur 1112 j (cible 25 %) ; ETH 62,3 % sur 1112 j (cible 25 %) ; SOL 89,4 % sur 1112 j (cible 25 %).

Mode global perpétuel contre Bitstamp, du 2020-03-25 au 2026-10-31 (2412 jours) : **0 jours différents**.

## 8. Robustesse : BTC seul depuis 2014

**σ̂ = écart-type 30 jours** des rendements log journaliers de Bitstamp au comptant pour ce test : les bougies 5 min ne remontent qu'au 08/09/2019. Funding fixe de 0,01 % par règlement de 8 h avant le 10/09/2019, puis funding réel du perpétuel BTC. Rendements du 2014-01-01 au 2026-10-31 (4687 jours). Poche unique 100 % BTC, poche baissière 25 % BTC.

| série | Ulcer | drawdown max | rendement annualisé | Sharpe √365 | rendement / Ulcer | Sharpe déflaté | exposition moyenne | changements / an | financement payé | frais payés | jours contraints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Variante expo fixe (BTC seul) | 39,81 % | −67,3 % | 48,8 % | 1,02 | 1,23 | 0,905 | 0,684 | 23,2 | 0,00 % | 3,61 % | 0 |
| Témoin expo constante (Variante expo fixe, BTC seul) | 33,51 % | −68,3 % | 34,8 % | 0,88 | 1,04 | — | 0,684 | 0,0 | 0,00 % | 0,00 % | — |
| Variante expo vol (BTC seul) | 16,80 % | −38,4 % | 27,9 % | 1,11 | 1,66 | 0,948 | 0,404 | 46,1 | 1,06 % | 4,21 % | 0 |
| Témoin expo constante (Variante expo vol, BTC seul) | 20,33 % | −47,0 % | 22,4 % | 0,88 | 1,10 | — | 0,404 | 0,0 | 0,00 % | 0,00 % | — |
| BTC buy and hold (Bitstamp) | 47,19 % | −83,4 % | 43,8 % | 0,88 | 0,93 | — | 1,000 | 0,0 | — | 0,00 % | — |

- Variante expo fixe (BTC seul) : p circulaire 0,501, p segments 0,522, p retenue 0,522 (hasard) ; utile au critère de la règle 1 : non ; jours en levier 0, financement de ces jours 0,000 %.
- Variante expo vol (BTC seul) : p circulaire 0,179, p segments 0,190, p retenue 0,190 (non concluant) ; utile au critère de la règle 1 : non ; jours en levier 140, financement de ces jours 1,063 %.

| plus haut | creux | baisse du BTC | bascule | délai (jours) | baisse avant la bascule |
|---|---|---|---|---|---|
| 2014-01-06 | 2015-01-14 | −81,4 % | 2014-03-27 | 80 | −48,3 % |
| 2017-01-04 | 2017-01-11 | −30,2 % | 2018-02-05 | 397 | 516,6 % |
| 2017-06-11 | 2017-07-16 | −35,1 % | 2018-02-05 | 239 | 132,7 % |
| 2017-09-01 | 2017-09-14 | −34,4 % | 2018-02-05 | 157 | 39,7 % |
| 2017-12-16 | 2018-12-15 | −83,4 % | 2018-02-05 | 51 | −64,2 % |
| 2021-04-13 | 2021-07-20 | −53,1 % | 2021-05-19 | 36 | −42,1 % |
| 2021-11-08 | 2022-11-21 | −76,7 % | 2021-12-13 | 35 | −30,8 % |
| 2025-10-06 | 2026-06-30 | −53,1 % | 2025-10-17 | 11 | −14,6 % |

## 9. Red team

1. **Cible de 25 % trop proche de la limite de drawdown de 25 %, levier jusqu'à ×2.** Drawdown max : « Variante expo vol » −28,1 %, « Test annexe – cible 40 % » −32,8 %. Jours avec Ei > 1 : 0 (expo vol), 0 (annexe). → confirmé pour la « Variante expo vol » (drawdown au-delà de 25 %) ; levier jamais utilisé à la cible de 25 %.
2. **Sortie lente sur 5 jours pendant un krach.** Coût total des rampes vers le baissier par rapport à une sortie immédiate : Variante expo fixe −1,71 % sur 24 rampes ; Variante expo vol +3,65 % sur 24 rampes ; Test annexe – cible 40 % +4,42 % sur 24 rampes. Pire rampe (expo fixe) : 2024-08-03, coût +5,04 %, BTC +1,6 % pendant la rampe. → infirmé sur la période (coût négatif ou nul).
3. **Peu d'historique pour SOL.** Première barre 5 min du perpétuel : 2020-09-14 07:00 UTC ; le HAR de SOL n'a ses 730 jours de RV que le 2022-09-14, il est remplacé avant par l'écart-type 30 jours (471 jours de décision de la période principale sur 1979). Volatilité réalisée de la poche SOL (expo vol) 20,6 % contre 25 % ; contribution de SOL +19,0 %. → confirmé comme limite (non mesurable comme effet).
4. **Un seul grand bear (2022).** Grands bears (≥ 30 %) sur la période principale : 2 ; depuis 2014 (Bitstamp) : 8. → infirmé sur la période principale.
5. **Sortie forcée par le BTC.** Jours de conflit : 154 ; ce qu'ETH et SOL auraient fait investis ces jours-là (expo vol) : +3,5 %. → confirmé (gain manqué).
6. **Poche baissière BTC sans multiplicateur.** Contribution de la poche baissière BTC (expo vol) : +10,7 % ; poche or (« Variante poche or ») : +10,4 %. → infirmé (la poche BTC gagne).

## 10. Comparaison avec la prédiction de Jonas (lecture chiffrée)

- **HAR ≈ écart-type 30 jours** : écart relatif des QLIKE moyennes (Contrôle HAR) BTC 41,3 %, ETH 43,1 %, SOL 38,0 % ; 0 actif(s) sur 3 à moins de 10 % → **infirmee**.
- **Volatilité peu efficace** (« Variante expo vol » échoue à la règle 1) : utile = non → **confirmee**.
- **Levier mal utilisé** (test annexe : gain de la part en levier < financement payé, sur 0 jours en levier) : gain 0,000 %, financement 0,000 % → **non mesurable**.
- **Drawdown > 40 %** pour au moins une variante ou le test annexe : Variante expo fixe −46,0 %, Variante expo vol −28,1 %, Test annexe – cible 40 % −32,8 %, Variante poche or −42,5 %, Variante poche mixte −41,2 % → **confirmee**.
- **SMA unique** : **non mesurable** ici ; voir le retard de sortie et les aller-retours (section 6).

