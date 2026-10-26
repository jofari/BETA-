# PBO de la grille de la voie C (PBOC) — rapport du programme — 2026-10-26

## Empreintes
- Code : `f1e9659` · règles : `690f0b8ce68f409b` · préenregistrement (`pbo_voie_c/PREENREGISTREMENT.md`) : `49d952e7b38cebdb`
- Données de la voie C : `d8b8b1a57a6a9bef`
- Calcul du 2026-10-26T10:06:44+00:00 au 2026-10-26T10:12:49+00:00

## Contrôle positif (décide)
Grille N(0, 1) de 1904 × 960, graine 0, avantage de Sharpe 3 (√252) ajouté chaque jour à la colonne 0. Réussi si PBO ≤ 10,0 %.
- PBO : **0,0 %** (12870 combinaisons, 960 configurations)
- Rang OOS relatif w de n* : min 20,0 % · 5 % 99,9 % · 25 % 99,9 % · médiane 99,9 % · 75 % 99,9 % · 95 % 99,9 % · max 99,9 %
- Combinaisons par décile de w : 0-10 % : 0 · 10-20 % : 1 · 20-30 % : 0 · 30-40 % : 0 · 40-50 % : 0 · 50-60 % : 0 · 60-70 % : 0 · 70-80 % : 0 · 80-90 % : 0 · 90-100 % : 12869
- Logit λ : moyenne 6,866, min -1,388 · 5 % 6,867 · 25 % 6,867 · médiane 6,867 · 75 % 6,867 · 95 % 6,867 · max 6,867
- Sharpe IS de n* : médiane 3,72 ; Sharpe OOS de n* : médiane 3,72
- Configurations distinctes choisies comme n* : 2
- Part des combinaisons où n* est la colonne 0 : 100,0 % ; Sharpe réalisé de la colonne 0 : 3,72
- **Contrôle positif : réussi**

### Informatif (ne décide rien) : avantage de Sharpe 1, même grille
- PBO : **16,3 %** (12870 combinaisons, 960 configurations)
- Rang OOS relatif w de n* : min 0,1 % · 5 % 14,8 % · 25 % 70,6 % · médiane 95,9 % · 75 % 99,6 % · 95 % 99,9 % · max 99,9 %
- Combinaisons par décile de w : 0-10 % : 426 · 10-20 % : 465 · 20-30 % : 417 · 30-40 % : 370 · 40-50 % : 417 · 50-60 % : 477 · 60-70 % : 608 · 70-80 % : 925 · 80-90 % : 1328 · 90-100 % : 7437
- Logit λ : moyenne 3,010, min -6,867 · 5 % -1,752 · 25 % 0,874 · médiane 3,150 · 75 % 5,478 · 95 % 6,867 · max 6,867
- Sharpe IS de n* : médiane 1,88 ; Sharpe OOS de n* : médiane 0,91
- Configurations distinctes choisies comme n* : 94
- Part des combinaisons où n* est la colonne 0 : 48,2 % ; Sharpe réalisé de la colonne 0 : 1,70

## Contrôle négatif (décide)
100 graines neuves (1001 à 1100), même taille, sans avantage. Réussi si la moyenne des PBO est dans [45,0 % ; 55,0 %].
- Moyenne : **52,3 %** (erreur-type 0,9 %)
- PBO par graine : min 27,0 % · 5 % 37,1 % · 25 % 48,0 % · médiane 51,9 % · 75 % 56,7 % · 95 % 68,3 % · max 77,1 %
- **Contrôle négatif : réussi**

### Rapporté (ne décide rien) : graine 0 seule, sans avantage
- PBO : **38,2 %** (12870 combinaisons, 960 configurations)
- Rang OOS relatif w de n* : min 0,1 % · 5 % 4,9 % · 25 % 31,7 % · médiane 66,9 % · 75 % 87,5 % · 95 % 96,3 % · max 99,4 %
- Combinaisons par décile de w : 0-10 % : 1119 · 10-20 % : 957 · 20-30 % : 967 · 30-40 % : 984 · 40-50 % : 889 · 50-60 % : 848 · 60-70 % : 985 · 70-80 % : 1353 · 80-90 % : 2208 · 90-100 % : 2560
- Logit λ : moyenne 0,491, min -6,867 · 5 % -2,968 · 25 % -0,766 · médiane 0,704 · 75 % 1,947 · 95 % 3,246 · max 5,070
- Sharpe IS de n* : médiane 1,71 ; Sharpe OOS de n* : médiane 0,23
- Configurations distinctes choisies comme n* : 138

## Voie C
- Fenêtre d'évaluation : 2021-06-20 → 2026-09-05, 1904 jours, 16 blocs de 119
- Configurations : **5760 avant**, 960 groupes (option b, cible 20% gardée), 36 doublon(s) exact(s) retiré(s), **924 après**
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 1 bande 0% = 20% glissant 20 j L[0 ; 1] pas 1 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 1 bande 5% = 20% glissant 20 j L[0 ; 1] pas 1 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 1 bande 10% = 20% glissant 20 j L[0 ; 1] pas 1 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 3 bande 0% = 20% glissant 20 j L[0 ; 1] pas 3 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 7 bande 0% = 20% glissant 20 j L[0 ; 1] pas 7 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 7 bande 5% = 20% glissant 20 j L[0 ; 1] pas 7 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 1] pas 7 bande 10% = 20% glissant 20 j L[0 ; 1] pas 7 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 1 bande 0% = 20% glissant 20 j L[0 ; 1.5] pas 1 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 1 bande 5% = 20% glissant 20 j L[0 ; 1.5] pas 1 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 1 bande 10% = 20% glissant 20 j L[0 ; 1.5] pas 1 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 3 bande 0% = 20% glissant 20 j L[0 ; 1.5] pas 3 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 7 bande 0% = 20% glissant 20 j L[0 ; 1.5] pas 7 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 7 bande 5% = 20% glissant 20 j L[0 ; 1.5] pas 7 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 1.5] pas 7 bande 10% = 20% glissant 20 j L[0 ; 1.5] pas 7 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 1 bande 0% = 20% glissant 20 j L[0 ; 2] pas 1 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 1 bande 5% = 20% glissant 20 j L[0 ; 2] pas 1 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 1 bande 10% = 20% glissant 20 j L[0 ; 2] pas 1 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 3 bande 0% = 20% glissant 20 j L[0 ; 2] pas 3 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 7 bande 0% = 20% glissant 20 j L[0 ; 2] pas 7 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 7 bande 5% = 20% glissant 20 j L[0 ; 2] pas 7 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 2] pas 7 bande 10% = 20% glissant 20 j L[0 ; 2] pas 7 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 1 bande 0% = 20% glissant 20 j L[0 ; 3] pas 1 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 1 bande 5% = 20% glissant 20 j L[0 ; 3] pas 1 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 1 bande 10% = 20% glissant 20 j L[0 ; 3] pas 1 bande 10%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 3 bande 0% = 20% glissant 20 j L[0 ; 3] pas 3 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 7 bande 0% = 20% glissant 20 j L[0 ; 3] pas 7 bande 0%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 7 bande 5% = 20% glissant 20 j L[0 ; 3] pas 7 bande 5%
  - doublon : 20% glissant 20 j L[0.33 ; 3] pas 7 bande 10% = 20% glissant 20 j L[0 ; 3] pas 7 bande 10%
  - doublon : 20% ewma 20 j L[0.33 ; 1] pas 7 bande 0% = 20% ewma 20 j L[0 ; 1] pas 7 bande 0%
  - doublon : 20% ewma 20 j L[0.33 ; 1] pas 7 bande 5% = 20% ewma 20 j L[0 ; 1] pas 7 bande 5%
  - doublon : 20% ewma 20 j L[0.33 ; 1.5] pas 7 bande 0% = 20% ewma 20 j L[0 ; 1.5] pas 7 bande 0%
  - doublon : 20% ewma 20 j L[0.33 ; 1.5] pas 7 bande 5% = 20% ewma 20 j L[0 ; 1.5] pas 7 bande 5%
  - doublon : 20% ewma 20 j L[0.33 ; 2] pas 7 bande 0% = 20% ewma 20 j L[0 ; 2] pas 7 bande 0%
  - doublon : 20% ewma 20 j L[0.33 ; 2] pas 7 bande 5% = 20% ewma 20 j L[0 ; 2] pas 7 bande 5%
  - doublon : 20% ewma 20 j L[0.33 ; 3] pas 7 bande 0% = 20% ewma 20 j L[0 ; 3] pas 7 bande 0%
  - doublon : 20% ewma 20 j L[0.33 ; 3] pas 7 bande 5% = 20% ewma 20 j L[0 ; 3] pas 7 bande 5%
- PBO : **9,9 %** (12870 combinaisons, 924 configurations)
- Rang OOS relatif w de n* : min 0,8 % · 5 % 38,7 % · 25 % 79,3 % · médiane 94,6 % · 75 % 98,1 % · 95 % 99,5 % · max 99,9 %
- Combinaisons par décile de w : 0-10 % : 7 · 10-20 % : 68 · 20-30 % : 252 · 30-40 % : 374 · 40-50 % : 576 · 50-60 % : 683 · 60-70 % : 707 · 70-80 % : 631 · 80-90 % : 1591 · 90-100 % : 7981
- Logit λ : moyenne 2,625, min -4,876 · 5 % -0,459 · 25 % 1,343 · médiane 2,873 · 75 % 3,948 · 95 % 5,215 · max 6,829
- Sharpe IS de n* : médiane 1,45 ; Sharpe OOS de n* : médiane 1,21
- Configurations distinctes choisies comme n* : 73
- Configurations le plus souvent choisies comme n* :
  - 20% glissant 30 j L[0 ; 3] pas 3 bande 20% : 23,9 % des combinaisons
  - 20% glissant 45 j L[0 ; 3] pas 3 bande 20% : 23,8 % des combinaisons
  - 20% glissant 30 j L[0 ; 2] pas 3 bande 20% : 14,2 % des combinaisons
  - 20% glissant 45 j L[0 ; 2] pas 3 bande 20% : 10,1 % des combinaisons
  - 20% glissant 90 j L[0 ; 3] pas 3 bande 10% : 5,3 % des combinaisons
  - 20% glissant 30 j L[0 ; 1] pas 3 bande 20% : 3,1 % des combinaisons
  - 20% glissant 90 j L[0 ; 3] pas 3 bande 0% : 2,7 % des combinaisons
  - 20% glissant 30 j L[0 ; 1.5] pas 3 bande 20% : 1,5 % des combinaisons
  - 20% glissant 90 j L[0 ; 3] pas 3 bande 5% : 1,2 % des combinaisons
  - 20% glissant 90 j L[0 ; 3] pas 1 bande 0% : 1,0 % des combinaisons

## Verdict mécanique
PBO = 9,9 %, seuil 20,0 % : **la voie C reste candidate**.

## Compteur
Diagnostic, aucun essai : global 147 → 147, invest 54 → 54, trading 93 → 93.

Rapport écrit par le programme (`beta/pbo_voie_c/rapport.py`), sans interprétation.
