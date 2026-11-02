# VC6 V2 — tests de cohérence du moteur (avant tout run)

- Écrit par le programme (`scripts/vc6_v2.py --coherence`, commit `87247d2`), règles `e39ad1cdaa14326e`, préenregistrement `VC6_V2/PREENREGISTREMENT.md` (gel vérifié avant de lancer).
- Période principale : rendements du 2021-06-01 au 2026-10-31 (1979 jours).
- Compteurs : invest **61** (59 + 2 essais), global 154, trading 93.
- Aucun run d'essai : ni témoin, ni null tiré au hasard, ni règle de décision. Les runs attendent le GO de Jonas.
- **Résultat : les 4 tests passent.**

| test | résultat | passe |
|---|---|---|
| a. « V2 – poche baissière sous HAR », E_BTC forcé à 1, contre la « Variante expo vol » de la V1 | valeur finale 1,685975 contre 1,685975 ; Ulcer 13,8990 % contre 13,8990 % ; rendements des 1979 jours identiques au bit près au moteur de la V1 : oui, à la mesure de la V1 : oui (écart maximal 0.0e+00) | oui |
| b. « V2 – HAR sans régime », Ei forcé à 1, sans frais, contre le panier 50/25/25 rééquilibré chaque jour calculé à part | valeur finale 2,470541 contre 2,470541 ; écart 0,0000 % (seuil 0,1 %) ; Ei = 1 tous les jours : oui | oui |
| c. Anticipation, « V2 – HAR sans régime » : σ̂ remplacé par la volatilité réalisée du jour t + 1 | Sharpe 0,59 → 0,68 ; Ulcer 17,47 % → 15,31 % ; les deux s'améliorent ; jours sans RV, σ̂ gardé : BTC 0, ETH 0, SOL 0 | oui |
| d. Null, décalage circulaire de 0 jour, contre le résultat observé | « V2 – HAR sans régime » (null des positions) : rendements identiques au bit près oui, Ulcer identique oui ; ordre identité des 32 blocs de 63 jours : oui ; « V2 – poche baissière sous HAR » (null du mode) : série du mode inchangée oui, rendements identiques au bit près oui, Ulcer identique oui | oui |

- Test a : référence = le moteur de la V1 sur les mêmes entrées et les rendements que la V1 a mesurés le 02/11 (`data/vc6_temps2/resultats.pkl`, vérifiés par le correctif du 02/11).
- Test b : calcul à part = `VC6_V1/temps2/verif_independante.py`, le script du test b de la V1, qui n'importe rien de BETA.
- Test c : il calcule le Sharpe et l'Ulcer observés de « V2 – HAR sans régime », sans témoin ni nulls ; ces deux chiffres sont donc connus avant le GO (c'est pourquoi la V2 est préenregistrée avant les tests).
- Test d : il ne rend que des égalités, pas les chiffres des essais.

