# VC6 V2 — préenregistrement

- **Écrit le** : 02/11/2026 (UTC), après le gel de la spec et avant tout calcul de la V2 sur les vraies données.
- **Id au registre** : `VC6_V2`, famille invest, 2 essais : « V2 – HAR sans régime » et « V2 – poche baissière sous HAR ». Compteur invest 59 → 61 (spec).
- **Règles** : `VC6_V2/spec_figee.md` (spec de Jonas du 02/11/2026, mot pour mot). Les valeurs que le code lit sont dans `beta/vc6_v2/regles.py`. Les empreintes de ces règles, de ce texte et de la spec sont écrites au registre ; le code refuse de tourner si l'une a changé.
- **Cadre** : backtest de diagnostic sur des données déjà vues. Il peut éliminer des choix, pas les valider. Les runs des essais attendent le GO de Jonas (deuxième prompt).
- **Pourquoi maintenant** : le test c calcule le Sharpe et l'Ulcer observés de « V2 – HAR sans régime » (sans témoin ni nulls). Invariant 4 de BETA : aucun chiffre ne sort sans préenregistrement. L'expérience est donc journalisée avant les tests de cohérence, comme la V1 l'avait été avant son moteur.

## Prompt de Jonas du 02/11/2026, étape C et fin, mot pour mot

=== PROMPT ÉTAPE C ===
ÉTAPE C — Moteur et tests de cohérence (aucun run d'essai)
Code les deux essais, puis fais passer ces tests :
a. « V2 – poche baissière sous HAR » avec E_BTC forcé à 1 dans la poche baissière : il reproduit exactement la « Variante expo vol » de la V1 (valeur finale et Ulcer).
b. « V2 – HAR sans régime » avec Ei forcé à 1, sans frais : il reproduit le panier 50/25/25 rééquilibré chaque jour (test b de la V1).
c. Anticipation : remplacer σ̂ par la volatilité réalisée du jour t+1 doit améliorer le Sharpe et l'Ulcer de « V2 – HAR sans régime ». Si ni l'un ni l'autre ne s'améliore, l'alignement des dates est suspect.
d. Null : un décalage circulaire de 0 jour redonne exactement le résultat observé.
Si un test échoue, tu t'arrêtes et tu me montres l'écart.

STOP. Tu me rends :
- CONCLUSION.md ;
- le rapport V1 corrigé (sections 6 et 8, avec le contrôle des frais) ;
- le chemin de VC6_V2/spec_figee.md ;
- le résultat des 4 tests.
Puis tu attends mon GO.
=== FIN PROMPT ===

## Applications (comment le code lit la spec, écrites avant tout calcul)

La spec reprend tout ce qu'elle ne modifie pas de la V1. Les applications de la V1 (`VC6_V1/temps2/PREENREGISTREMENT.md`) s'appliquent donc telles quelles ; ce qui suit dit lesquelles, et comment le code lit les points nouveaux. Aucune nouvelle règle de décision. Les points marqués *(test)* ne servent qu'aux tests de cohérence.

### Données et dates (V1, applications 1 à 6 et 9)
1. **Clôture du jour D** de BTC, ETH et SOL : barre 5 min du perpétuel ouverte en D à 23:55 UTC. Rendement du jour D = C(D) / C(D − 1) − 1.
2. **Décision** à la clôture du jour t, appliquée au rendement du jour t + 1. Aucune donnée postérieure à la clôture de t, sauf dans le test c, qui le fait exprès.
3. **σ̂i(t)** = √(365 × h_i(t)), h = prévision HAR après replis du « Contrôle HAR », calculée par `beta.controle_har` sur les copies figées. Robustesse : écart-type 30 jours des rendements log de Bitstamp.
4. **Période principale** : rendements du 01/06/2021 au 31/10/2026 (1 979 jours) ; première décision à la clôture du 31/05/2021. **Position de départ** : la cible de ce jour, sans rampe et sans frais d'entrée.
5. **Funding du jour t** : règlements de ]t 00:00 ; t + 1 00:00] UTC. Funding annualisé = leur somme × 365.

### « V2 – HAR sans régime »
6. Chaque jour, pour chaque poche : cible Ei = clip(0,25 / σ̂i ; 0,2 ; 2), puis plafond de 1 si le funding annualisé dépasse 20 %, puis sécurité de liquidation (marge 0,5 % ; si 1/Ei − 0,005 < 3 × σ̂i/√365, alors Ei = 1/(0,005 + 3 × σ̂i/√365)), dans cet ordre (V1, applications 8 et 10). Position x_i = w_i × Ei, w = 50 %, 25 %, 25 %. Le reste du capital est en cash, à rendement nul.
7. Pas de mode, pas de rampe, pas de poche baissière. **Bande de 10 %** chaque jour, poche par poche : la position ne change que si |cible − actuelle| > 10 % × actuelle (V1, application 13).
8. **Frais** : 10 pb × Σ des variations de la position nette de chaque actif (V1, application 14). **Financement** du jour t + 1 : Σ max(Ei − 1 ; 0) × w_i × somme des règlements de i ce jour-là ; un funding négatif est reçu (V1, application 11).

### « V2 – poche baissière sous HAR »
9. Même moteur que la « Variante expo vol » de la V1 (applications 3, 7 à 14 de la V1 ; mode global baissier si C_BTC(t) < SMA 200 du BTC, jour t compris ; ETH et SOL suivent le BTC), sauf la poche baissière.
10. **Poche baissière** : en mode baissier, sa cible du jour t est 25 % × E_BTC(t), avec E_BTC(t) = clip(0,25 / σ̂_BTC(t) ; 0,2 ; 1) et σ̂_BTC le même σ̂ que celui de la poche BTC. Pas de levier : elle ne paie aucun financement. Le filtre de financement plafonne à 1, il est sans effet sur E_BTC ≤ 1. La sécurité de liquidation ne pourrait contraindre une exposition de 1 qu'au-dessus de σ̂ ≈ 634 % ; le moteur s'arrête si σ̂_BTC dépasse ce seuil (cas non prévu), sinon elle est sans effet. Ni l'un ni l'autre n'est donc appliqué à la poche baissière.
11. **Rampe** (V1, application 12) : quand le mode bascule à la clôture de t, les positions des décisions t à t + 4 valent départ + k/5 × (cible_k − départ), k = 1 à 5, la cible étant recalculée chaque jour. Pour la poche baissière, la cible du jour est 25 % × E_BTC de ce jour. Une nouvelle bascule pendant une rampe repart de la position en vigueur.
12. **Bande sur la poche baissière**, hors rampe : sa position ne change que si |cible − actuelle| > 10 % × actuelle (spec). Dans la V1, la même règle portait déjà sur toutes les lignes ; avec une poche baissière constante, elle n'y changeait rien.
13. **Frais** sur la position nette du BTC : poche BTC + poche baissière (V1, application 14).

### Témoins et références
14. **« Témoin expo constante »** de chaque essai : Ē = moyenne, sur les jours de la période, de l'exposition totale Σx (poche baissière comprise) ; x_i = Ē × w_i chaque jour sur BTC, ETH et SOL ; financement si Ē > 1 ; pas de frais (V1, application 16, même fonction).
15. **Références à risque égal** (verdict, pour info) : panier buy and hold 50/25/25 sans rééquilibrage (clôtures des perpétuels), ETF monde URTH (rendement nul les jours sans séance), et la « Variante expo vol » de la V1, recalculée par le moteur de la V1 sur les mêmes données. Chacune est multipliée par k = volatilité réalisée de l'essai / volatilité réalisée de la référence. « Bat » = rendement annualisé plus haut à risque égal (V1, application 25).

### Nulls
16. **« V2 – HAR sans régime »** : la série tirée est celle des positions tenues x_i(t) = w_i × Ei(t), après filtre, sécurité et bande, aux décisions D_0 … D_{N−1}, les trois poches ensemble (N = 1 979 sur la période principale).
    - circulaire : x'(t) = x((t + k) mod N), k entier tiré uniformément dans [90 ; N − 90] (même tirage que `beta.invest.nulls.decalage_circulaire`) ;
    - segments : x est découpée à partir de D_0 en blocs consécutifs de 63 jours ; le dernier bloc est plus court (1 979 = 31 × 63 + 26) ; les 32 blocs sont remis dans un ordre tiré au hasard (permutation uniforme) ;
    - chaque tirage recalcule le rendement net sur les vrais rendements, avec la fonction du moteur : frais sur les variations de la série tirée (aucun frais le premier jour), financement aux vraies dates sur max(Ei − 1 ; 0). La bande, le filtre et la sécurité ne sont pas réappliqués : ils sont déjà dans la série tirée.
17. **« V2 – poche baissière sous HAR »** : le null de la V1 (application 17 de la V1). La série du mode (haussier ou baissier) aux décisions D_0 … D_{N−1} est décalée (circulaire, k dans [90 ; N − 90]) ou ses segments sont mélangés (`beta.invest.nulls.melange_segments`) ; chaque tirage refait tout le moteur : rampe, bande, poche baissière avec E_BTC à ses vraies dates.
18. **B = 1 000** tirages par null, graine 0 (flux `beta.invest.nulls.flux(0, "VC6_V2", essai, null)`), métrique Ulcer. **p** = (1 + nombre de tirages dont l'Ulcer est ≤ l'observé) / (1 + B) : la fonction de la V1 (`beta.invest.nulls.p_value`), c'est-à-dire la « part des tirages » de la spec en comptant l'observé comme un tirage. Avec B = 1 000, elle est < 0,05 exactement quand la part brute (nombre / 1 000) l'est : au plus 49 tirages ≤ l'observé. **p retenue** = la plus grande des deux (D4).

### Décision
19. **Règle 1** : utile = Ulcer < Ulcer de son témoin ET p retenue < 0,05.
20. **Règle 2** : un seul essai utile → cet essai ; les deux → le plus haut ratio rendement annualisé / Ulcer (égalité exacte : cas non prévu, arrêt) ; aucun → « VC6 rejetée, aucune configuration retenue ; le paper ne sert qu'à roder l'exécution ».
21. **Règle 3** (rapportée, sans effet) : « V2 – poche baissière sous HAR » contre la « Variante expo vol » de la V1 : Ulcer, drawdown max, rendement annualisé, contribution de la poche baissière entre le plus haut et le creux du drawdown max de chacun (V1, application 30).
22. **PBO** (addendum de la V1 du 02/11, repris par la spec) : PBO par CSCV du choix entre les deux essais (`beta.stats.pbo`, 16 blocs, Sharpe, seuil 20 %), calculée et rapportée sans effet sur la décision.
23. **Mesures** : celles de la V1 (application 24), avec le Sharpe déflaté au compteur invest après l'ajout des 2 essais.

### Robustesse
24. **BTC seul depuis 2014** (V1, application 26) : clôtures Bitstamp, rendements du 01/01/2014 au 31/10/2026, une poche à 100 %, σ̂ = écart-type 30 jours, funding fixe de 0,01 % par règlement (3 par jour) avant le 10/09/2019 puis funding réel du perpétuel BTC, marge 0,5 %. Les deux essais y sont rejoués : « V2 – HAR sans régime » (E = clip(0,25 / σ̂ ; 0,2 ; 2) en permanence) et « V2 – poche baissière sous HAR » (régime SMA 200 de Bitstamp, rampe, poche baissière 25 % × clip(0,25 / σ̂ ; 0,2 ; 1)). Témoins et nulls calculés pour information ; la robustesse ne décide rien.

### Tests de cohérence *(test)*
25. **Test a** : « V2 – poche baissière sous HAR » avec E_BTC forcé à 1 doit donner des rendements quotidiens identiques au bit près à ceux du moteur de la V1 pour la « Variante expo vol », sur les mêmes entrées, et une valeur finale et un Ulcer égaux à ceux que la V1 a mesurés (`data/vc6_temps2/resultats.pkl`, vérifiés par le correctif du 02/11).
26. **Test b** : « V2 – HAR sans régime » avec Ei forcé à 1 et sans frais doit redonner la valeur finale du panier 50/25/25 rééquilibré chaque jour calculée à part par `VC6_V1/temps2/verif_independante.py` (le script du test b de la V1, qui n'importe rien de BETA), à moins de 0,1 % (critère de la V1).
27. **Test c** : pour chaque décision t et chaque poche, σ̂i(t) est remplacé par la volatilité réalisée du jour t + 1, √(365 × RV), RV = somme des carrés des rendements log 5 min du jour t + 1 (`beta.controle_har.har.rv_journaliere`, la cible du « Contrôle HAR »). Elle couvre exactement le rendement du jour t + 1. Le remplacement vaut partout où σ̂ intervient (sizing et sécurité). Un jour sans RV (exclu au « Contrôle HAR ») garde σ̂, et ces jours sont comptés. Le test passe si le Sharpe ET l'Ulcer s'améliorent ; il échoue si aucun des deux ne s'améliore (alignement suspect : arrêt) ; si un seul s'améliore, le cas n'est pas prévu : arrêt et question à Jonas.
28. **Test d** : un décalage circulaire de 0 jour doit redonner des rendements quotidiens identiques au bit près et le même Ulcer, pour les deux essais (null des positions pour « V2 – HAR sans régime », null du mode pour « V2 – poche baissière sous HAR »). En plus, pour « V2 – HAR sans régime », l'ordre identité des blocs de 63 jours doit aussi redonner le résultat observé. Le rapport du test d ne donne que ces égalités, pas les chiffres des essais.

## Déjà connu au moment du gel

- Tout le « Temps 2 » de la V1 et son correctif (`VC6_V1/rapport_temps2.md`, `VC6_V1/rapport_temps2_corrige.md`), dont, pour la « Variante expo vol » : Ulcer 13,90 % contre 17,58 % pour son témoin, p retenue 0,250 ; Ulcer nul médian (régime aléatoire) 15,50 % en circulaire et 15,13 % en segments ; drawdown max −28,1 %, dont −20,7 points pour la poche baissière BTC ; rendement annualisé 10,1 %. Aucun jour en levier à la cible de 25 %.
- Le panier 50/25/25 rééquilibré chaque jour sans frais vaut 2,470541 en fin de période (test b de la V1).
- σ̂ HAR annualisé sur la période principale (vu le 02/11 avant le « Temps 2 » de la V1) : BTC de 36 % à 132 %, ETH de 51 % à 206 %, SOL de 74 % à 590 %. Donc 0,25 / σ̂ ≤ 0,69 : sur la période principale, aucune poche ne peut passer en levier dans les deux essais, et le filtre de financement et la sécurité de liquidation n'y agissent pas. E_BTC de la poche baissière y reste entre 0,2 et 0,69.
- Aucun chiffre de « V2 – HAR sans régime » ni de « V2 – poche baissière sous HAR » n'a été calculé sur les vraies données. Le moteur V2 n'a tourné que sur des données synthétiques (`tests/test_vc6_v2.py`).
