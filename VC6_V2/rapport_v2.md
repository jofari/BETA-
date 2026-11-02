# VC6 V2 — rapport des runs

- Écrit par le programme (`scripts/vc6_v2.py --go`, commit `762ca67`), règles `e39ad1cdaa14326e`, préenregistrement `VC6_V2/PREENREGISTREMENT.md`, spec `VC6_V2/spec_figee.md` (gel vérifié avant de lancer).
- Points de lecture validés par Jonas le 02/11/2026, tels quels (applications 10, 16, 18 et 24 du préenregistrement).
- Période principale : rendements du 2021-06-01 au 2026-10-31 (1979 jours). Robustesse : BTC seul, Bitstamp, rendements du 2014-01-01 au 2026-10-31 (4687 jours).
- Compteurs : invest **61** (59 + 2 essais, journalisés au préenregistrement ; rien d'ajouté au GO), global 154, trading 93. Sharpe déflaté au N invest = 61.
- Prédiction de Jonas : gardée par Jonas, hors du dépôt (`VC6_V2/prediction_jonas.md`) ; ce rapport n'a donc pas de section « prédiction ».
- Backtest de diagnostic : il peut éliminer des choix, pas les valider.

## 1. Tests de cohérence du moteur (relancés juste avant les runs)

| test | résultat | passe |
|---|---|---|
| a. « V2 – poche baissière sous HAR », E_BTC forcé à 1, contre la « Variante expo vol » de la V1 | valeur finale 1,685975 contre 1,685975 ; Ulcer 13,8990 % contre 13,8990 % ; rendements des 1979 jours identiques au bit près au moteur de la V1 : oui, à la mesure de la V1 : oui (écart maximal 0.0e+00) | oui |
| b. « V2 – HAR sans régime », Ei forcé à 1, sans frais, contre le panier 50/25/25 rééquilibré chaque jour calculé à part | valeur finale 2,470541 contre 2,470541 ; écart 0,0000 % (seuil 0,1 %) ; Ei = 1 tous les jours : oui | oui |
| c. Anticipation, « V2 – HAR sans régime » : σ̂ remplacé par la volatilité réalisée du jour t + 1 | Sharpe 0,59 → 0,68 ; Ulcer 17,47 % → 15,31 % ; les deux s'améliorent ; jours sans RV, σ̂ gardé : BTC 0, ETH 0, SOL 0 | oui |
| d. Null, décalage circulaire de 0 jour, contre le résultat observé | « V2 – HAR sans régime » (null des positions) : rendements identiques au bit près oui, Ulcer identique oui ; ordre identité des 32 blocs de 63 jours : oui ; « V2 – poche baissière sous HAR » (null du mode) : série du mode inchangée oui, rendements identiques au bit près oui, Ulcer identique oui | oui |

## 2. Mesures (période principale)

| série | Ulcer | drawdown max | rendement annualisé | Sharpe √365 | rendement / Ulcer | Sharpe déflaté | exposition moyenne | changements / an | financement payé | frais payés | jours contraints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V2 – HAR sans régime | 17,47 % | −35,6 % | 10,5 % | 0,59 | 0,60 | 0,164 | 0,368 | 65,8 | 0,00 % | 0,94 % | 0 |
| Témoin expo constante (V2 – HAR sans régime) | 19,94 % | −43,8 % | 11,4 % | 0,58 | 0,57 | — | 0,368 | 0,0 | 0,00 % | 0,00 % | — |
| V2 – poche baissière sous HAR | 10,30 % | −17,0 % | 9,6 % | 0,69 | 0,93 | 0,225 | 0,253 | 78,4 | 0,00 % | 1,30 % | 0 |
| Témoin expo constante (V2 – poche baissière sous HAR) | 14,02 % | −32,0 % | 8,3 % | 0,58 | 0,59 | — | 0,253 | 0,0 | 0,00 % | 0,00 % | — |
| Variante expo vol (V1) | 13,90 % | −28,1 % | 10,1 % | 0,64 | 0,73 | — | 0,321 | 63,6 | 0,00 % | 0,99 % | 0 |
| Panier buy and hold 50/25/25 | 52,28 % | −87,6 % | 13,4 % | 0,53 | 0,26 | — | 1,000 | 0,0 | — | 0,00 % | — |
| ETF monde (URTH) | 9,01 % | −26,9 % | 9,4 % | 0,64 | 1,05 | — | 1,000 | 0,0 | — | 0,00 % | — |

Nulls (B = 1 000 tirages chacun, graine 0, métrique = Ulcer, p retenue = la plus haute des deux) :

| essai | null | Ulcer | Ulcer du témoin | p circulaire | p segments | p retenue | verdict D4 | Ulcer nul médian (circulaire / segments) |
|---|---|---|---|---|---|---|---|---|
| V2 – HAR sans régime | positions (décalage circulaire ; blocs de 63 jours permutés) | 17,47 % | 19,94 % | 0,213 | 0,169 | 0,213 | hasard | 19,41 % / 19,26 % |
| V2 – poche baissière sous HAR | mode (décalage circulaire ; segments mélangés) | 10,30 % | 14,02 % | 0,173 | 0,252 | 0,252 | hasard | 13,31 % / 12,71 % |

PBO du choix entre les deux essais (S10, 16 blocs, Sharpe), **rapportée sans effet** : PBO = 78,0 % ; 2 configurations distinctes, 1968 jours ; sous le seuil de 20 % : non.

## 3. Règles de décision

1. **Utile = Ulcer < celui de son témoin, avec p retenue < 0,05.** « V2 – HAR sans régime » : Ulcer 17,47 % contre témoin 19,94 %, p retenue 0,213 → pas utile ; « V2 – poche baissière sous HAR » : Ulcer 10,30 % contre témoin 14,02 %, p retenue 0,252 → pas utile.
2. **Configuration retenue pour la suite.** Essais utiles : aucun. Ratio rendement annualisé / Ulcer : « V2 – HAR sans régime » 0,60 ; « V2 – poche baissière sous HAR » 0,93. Configuration retenue : **aucune** — VC6 rejetée, aucune configuration retenue ; le paper ne sert qu'à roder l'exécution.

## 4. Règle 3 (rapportée, sans effet sur la décision)

| série | Ulcer | drawdown max | rendement annualisé | contribution de la poche baissière pendant le drawdown max | contribution totale de la poche baissière |
|---|---|---|---|---|---|
| V2 – poche baissière sous HAR | 10,30 % | −17,0 % | 9,6 % | −7,4 % | +6,2 % |
| Variante expo vol (V1) | 13,90 % | −28,1 % | 10,1 % | −20,7 % | +10,7 % |

Contribution = somme des rendements quotidiens de la poche baissière, entre le plus haut et le creux du drawdown max de chaque série (V1, application 30).

## 5. Grille du verdict VC6 (pour info seulement)

| essai | Sharpe > 1 | drawdown max < 25 % | bat le panier à risque égal | bat l'ETF monde à risque égal |
|---|---|---|---|---|
| V2 – HAR sans régime | 0,59 → non | −35,6 % → non | 10,5 % contre 9,0 % → oui | 10,5 % contre 11,7 % → non |
| V2 – poche baissière sous HAR | 0,69 → non | −17,0 % → oui | 9,6 % contre 7,0 % → oui | 9,6 % contre 8,9 % → oui |

« Bat » = rendement annualisé plus haut que la référence ramenée à la même volatilité réalisée que l'essai.

## 6. Détail par essai (période principale)

### V2 – HAR sans régime

5 pires drawdowns :

| début | creux | récupération | profondeur | exposition au début |
|---|---|---|---|---|
| 2021-11-08 | 2022-11-09 | 2024-01-10 | −35,6 % | 0,328 |
| 2025-10-06 | 2026-06-25 | pas encore | −29,6 % | 0,476 |
| 2024-12-16 | 2025-04-08 | 2025-07-10 | −18,0 % | 0,433 |
| 2024-06-05 | 2024-09-06 | 2024-11-08 | −14,3 % | 0,441 |
| 2024-03-31 | 2024-05-01 | 2024-05-20 | −8,7 % | 0,405 |

Contributions (somme des rendements quotidiens) : poche BTC +36,3 % (pendant le drawdown max : −20,6 %) ; poche ETH +10,9 % (pendant le drawdown max : −7,4 %) ; poche SOL +19,2 % (pendant le drawdown max : −13,5 %) ; frais −0,9 % (pendant le drawdown max : −0,1 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible de 25 % : BTC 21,8 % sur 1979 j ; ETH 23,0 % sur 1979 j ; SOL 22,8 % sur 1979 j.

Jours avec Ei > 1 : 0 (financement payé ces jours-là : 0,000 % ; gain de la part en levier : 0,000 %). Frais payés : 0,94 % ; financement payé : 0,000 % ; jours contraints par la sécurité de liquidation : 0.

### V2 – poche baissière sous HAR

5 pires drawdowns :

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2021-11-08 | 2022-11-21 | 2023-11-08 | −17,0 % | haussier | 0,328 |
| 2024-12-16 | 2025-04-08 | 2025-07-21 | −16,4 % | haussier | 0,433 |
| 2024-06-05 | 2024-10-03 | 2024-11-21 | −16,1 % | haussier | 0,443 |
| 2025-10-06 | 2026-06-30 | pas encore | −16,0 % | haussier | 0,462 |
| 2024-03-31 | 2024-05-01 | 2024-05-20 | −8,6 % | haussier | 0,401 |

Contributions (somme des rendements quotidiens) : poche BTC +23,0 % (pendant le drawdown max : −6,3 %) ; poche ETH +8,8 % (pendant le drawdown max : −2,1 %) ; poche SOL +19,0 % (pendant le drawdown max : −2,2 %) ; poche baissière BTC +6,2 % (pendant le drawdown max : −7,4 %) ; frais −1,3 % (pendant le drawdown max : −0,1 %) ; financement −0,0 % (pendant le drawdown max : −0,0 %).

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible de 25 % : BTC 20,8 % sur 1112 j ; ETH 23,1 % sur 1112 j ; SOL 20,6 % sur 1112 j.

Jours avec Ei > 1 : 0 (financement payé ces jours-là : 0,000 % ; gain de la part en levier : 0,000 %). Frais payés : 1,30 % ; financement payé : 0,000 % ; jours contraints par la sécurité de liquidation : 0.

## 7. Robustesse : BTC seul depuis 2014 (information, ne décide rien)

σ̂ = écart-type 30 jours des rendements log journaliers de Bitstamp au comptant ; funding fixe de 0,01 % par règlement de 8 h avant le 10/09/2019, puis funding réel du perpétuel BTC ; une poche à 100 % ; poche baissière de « V2 – poche baissière sous HAR » = 25 % × clip(0,25/σ̂ ; 0,2 ; 1) (application 24).

| série | Ulcer | drawdown max | rendement annualisé | Sharpe √365 | rendement / Ulcer | Sharpe déflaté | exposition moyenne | changements / an | financement payé | frais payés | jours contraints |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V2 – HAR sans régime (BTC seul) | 21,23 % | −46,6 % | 28,1 % | 0,98 | 1,33 | 0,878 | 0,501 | 41,3 | 1,18 % | 5,23 % | 0 |
| Témoin expo constante (V2 – HAR sans régime, BTC seul) | 24,99 % | −55,4 % | 27,1 % | 0,88 | 1,08 | — | 0,501 | 0,0 | 0,00 % | 0,00 % | — |
| V2 – poche baissière sous HAR (BTC seul) | 16,65 % | −34,2 % | 27,3 % | 1,16 | 1,64 | 0,965 | 0,349 | 61,7 | 1,06 % | 5,21 % | 0 |
| Témoin expo constante (V2 – poche baissière sous HAR, BTC seul) | 17,65 % | −41,9 % | 19,6 % | 0,88 | 1,11 | — | 0,349 | 0,0 | 0,00 % | 0,00 % | — |
| Variante expo vol (V1, BTC seul) | 16,80 % | −38,4 % | 27,9 % | 1,11 | 1,66 | — | 0,404 | 46,1 | 1,06 % | 4,21 % | 0 |
| BTC acheté et conservé (Bitstamp) | 47,19 % | −83,4 % | 43,8 % | 0,88 | 0,93 | — | 1,000 | 0,0 | — | 0,00 % | — |
| ETF monde (URTH) | 7,87 % | −34,0 % | 8,7 % | 0,58 | 1,10 | — | 1,000 | 0,0 | — | 0,00 % | — |

| essai | null | Ulcer | Ulcer du témoin | p circulaire | p segments | p retenue | verdict D4 | Ulcer nul médian (circulaire / segments) |
|---|---|---|---|---|---|---|---|---|
| V2 – HAR sans régime (BTC seul) | positions (décalage circulaire ; blocs de 63 jours permutés) | 21,23 % | 24,99 % | 0,024 | 0,015 | 0,024 | reel | 28,43 % / 28,99 % |
| V2 – poche baissière sous HAR (BTC seul) | mode (décalage circulaire ; segments mélangés) | 16,65 % | 17,65 % | 0,310 | 0,400 | 0,400 | hasard | 18,08 % / 17,33 % |

Utile au critère de la règle 1 (information) : « V2 – HAR sans régime » oui ; « V2 – poche baissière sous HAR » non.

### V2 – HAR sans régime (BTC seul)

5 pires drawdowns :

| début | creux | récupération | profondeur | exposition au début |
|---|---|---|---|---|
| 2017-12-16 | 2018-12-15 | 2019-06-17 | −46,6 % | 0,215 |
| 2021-11-08 | 2022-12-19 | 2024-02-09 | −46,2 % | 0,457 |
| 2014-01-06 | 2015-01-14 | 2016-04-20 | −45,5 % | 0,200 |
| 2025-10-06 | 2026-06-30 | pas encore | −42,7 % | 0,894 |
| 2019-06-26 | 2020-03-12 | 2020-07-27 | −27,2 % | 0,382 |

Contributions (somme des rendements quotidiens) : poche BTC +381,8 % (pendant le drawdown max : −58,0 %) ; frais −5,2 % (pendant le drawdown max : −0,3 %) ; financement −1,2 % (pendant le drawdown max : −0,0 %).

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible de 25 % : BTC 29,8 % sur 4687 j.

Jours avec Ei > 1 : 173 (financement payé ces jours-là : 1,177 % ; gain de la part en levier : 14,899 %). Frais payés : 5,23 % ; financement payé : 1,177 % ; jours contraints par la sécurité de liquidation : 0.

### V2 – poche baissière sous HAR (BTC seul)

5 pires drawdowns :

| début | creux | récupération | profondeur | mode au début | exposition au début |
|---|---|---|---|---|---|
| 2014-01-06 | 2015-08-18 | 2015-12-11 | −34,2 % | haussier | 0,200 |
| 2019-06-26 | 2020-03-12 | 2020-10-21 | −28,4 % | haussier | 0,382 |
| 2021-04-13 | 2022-11-09 | 2023-12-05 | −28,2 % | haussier | 0,447 |
| 2017-12-16 | 2018-12-15 | 2019-05-11 | −23,8 % | haussier | 0,215 |
| 2025-10-06 | 2026-06-30 | pas encore | −22,1 % | haussier | 0,894 |

Contributions (somme des rendements quotidiens) : poche BTC +339,2 % (pendant le drawdown max : −37,0 %) ; poche baissière BTC +10,9 % (pendant le drawdown max : −2,1 %) ; frais −5,2 % (pendant le drawdown max : −0,6 %) ; financement −1,1 % (pendant le drawdown max : −0,0 %).

Volatilité réalisée des poches investies (Ei × r, √365) contre la cible de 25 % : BTC 28,9 % sur 2837 j.

Jours avec Ei > 1 : 140 (financement payé ces jours-là : 1,063 % ; gain de la part en levier : 13,366 %). Frais payés : 5,21 % ; financement payé : 1,063 % ; jours contraints par la sécurité de liquidation : 0.

