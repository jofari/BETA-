# Temps 1 — fiabilité du test de justesse (T1F)

Calculé le 2026-10-24T13:58:01+00:00 UTC. Rapport écrit par `scripts/temps1_fiabilite.py`, sans interprétation au-delà du verdict mécanique. Le verdict de T1J n'est pas modifié.

## 1. Empreintes

- **Code** : `590688e`. Modules de T1J réutilisés, vérifiés identiques au commit `8afdbe7` : __init__.py, regles.py, donnees.py, detecteurs.py, juge.py, mesures.py, verdict.py, campagne.py.
- **Données** : `a3d6d80952500d57`, celles de T1J. Règles de T1J : `c0959f429d9dcf8f`.
- **Préenregistrement** : `temps1_fiabilite/PREENREGISTREMENT.md` `45453a1f81288806` ; règles `77b7f85b49132d77` ; registre : `EXPERIMENTS.jsonl`, id `T1F`, diagnostic.
- **Compteur** (aucun essai) : global 147 → 147, invest 54 → 54, trading actif 93 → 93.
- **Tirages** : 1000 par couple et par test, graine 0. Périodes mesurées (celles de T1J) : S&P 500 1998-07-17 → 2022-10-12 (6100 séances) ; Nasdaq-100 2000-03-27 → 2022-12-28 (5726 séances) ; or (LBMA PM) 1993-03-10 → 2022-11-03 (7698 séances) ; BTC (DS1) 2013-10-02 → 2025-10-06 (4387 séances).

## 2. Test 1 — permutation des durées par état (verdict de fiabilité)

p_latence = part des tirages dont la médiane de f_entrée est ≤ celle du détecteur observé ; p_justesse = part des tirages dont la justesse est ≥ celle du détecteur observé. Lecture D4 : p < 0,05 réel ; 0,05 ≤ p < 0,20 non concluant ; p ≥ 0,20 indistinguable du hasard.

| détecteur | actif | f_entrée observée | f_entrée aléatoire, médiane [5 % ; 95 %] | p_latence | justesse observée | justesse aléatoire, médiane [5 % ; 95 %] | p_justesse | lecture D4 (latence / justesse) | fausses alertes / an : observées, aléatoires (médiane) |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | S&P 500 | 0,34 | 0,21 [0,01 ; 0,68] | 0,716 | 0,82 | 0,50 [0,39 ; 0,64] | 0,000 | indistinguable du hasard / réel | 2,56 ; 2,89 |
| SMA200 | Nasdaq-100 | 0,37 | 0,23 [0,00 ; 0,93] | 0,712 | 0,80 | 0,51 [0,38 ; 0,66] | 0,000 | indistinguable du hasard / réel | 2,55 ; 2,94 |
| SMA200 | témoin actions | 0,36 | 0,24 [0,06 ; 0,61] | 0,708 | 0,81 | 0,51 [0,42 ; 0,61] | 0,000 | indistinguable du hasard / réel | 2,55 ; 2,92 |
| SMA200 | or (LBMA PM) | 0,66 | 0,17 [0,00 ; 0,51] | 0,986 | 0,73 | 0,50 [0,40 ; 0,60] | 0,000 | indistinguable du hasard / réel | 2,09 ; 2,50 |
| SMA200 | BTC (DS1) | 0,64 | 0,29 [0,00 ; 0,70] | 0,912 | 0,74 | 0,51 [0,35 ; 0,66] | 0,007 | indistinguable du hasard / réel | 1,83 ; 2,25 |
| MOM126 | S&P 500 | 0,34 | 0,23 [0,01 ; 0,76] | 0,656 | 0,79 | 0,50 [0,39 ; 0,64] | 0,001 | indistinguable du hasard / réel | 2,06 ; 2,23 |
| MOM126 | Nasdaq-100 | 0,43 | 0,24 [0,00 ; 0,97] | 0,732 | 0,79 | 0,51 [0,38 ; 0,66] | 0,000 | indistinguable du hasard / réel | 2,55 ; 2,77 |
| MOM126 | témoin actions | 0,39 | 0,27 [0,05 ; 0,68] | 0,679 | 0,79 | 0,51 [0,42 ; 0,62] | 0,000 | indistinguable du hasard / réel | 2,31 ; 2,48 |
| MOM126 | or (LBMA PM) | 0,48 | 0,14 [0,00 ; 0,45] | 0,965 | 0,69 | 0,50 [0,41 ; 0,58] | 0,001 | indistinguable du hasard / réel | 2,39 ; 2,43 |
| MOM126 | BTC (DS1) | 0,59 | 0,26 [0,00 ; 0,62] | 0,925 | 0,71 | 0,50 [0,38 ; 0,63] | 0,004 | indistinguable du hasard / réel | 3,25 ; 3,66 |
| C1_V1 | S&P 500 | 0,12 | 0,19 [0,05 ; 0,41] | 0,247 | 0,65 | 0,54 [0,50 ; 0,60] | 0,000 | indistinguable du hasard / réel | 6,27 ; 6,93 |
| C1_V1 | Nasdaq-100 | 0,15 | 0,18 [0,03 ; 0,41] | 0,353 | 0,64 | 0,55 [0,50 ; 0,61] | 0,007 | indistinguable du hasard / réel | 6,11 ; 6,81 |
| C1_V1 | témoin actions | 0,13 | 0,20 [0,09 ; 0,35] | 0,171 | 0,65 | 0,55 [0,51 ; 0,58] | 0,000 | non concluant / réel | 6,19 ; 6,85 |
| C1_V1 | or (LBMA PM) | 0,14 | 0,27 [0,11 ; 0,46] | 0,107 | 0,48 | 0,53 [0,49 ; 0,56] | 0,996 | non concluant / indistinguable du hasard | 4,08 ; 4,22 |
| C1_V1 | BTC (DS1) | 0,36 | 0,34 [0,12 ; 0,51] | 0,580 | 0,53 | 0,52 [0,48 ; 0,56] | 0,294 | indistinguable du hasard / indistinguable du hasard | 6,24 ; 6,74 |
| C1_V2 | S&P 500 | 0,19 | 0,19 [0,03 ; 0,56] | 0,506 | 0,72 | 0,51 [0,43 ; 0,60] | 0,000 | indistinguable du hasard / réel | 3,71 ; 4,66 |
| C1_V2 | Nasdaq-100 | 0,12 | 0,20 [0,01 ; 0,69] | 0,324 | 0,71 | 0,52 [0,43 ; 0,61] | 0,001 | indistinguable du hasard / réel | 3,03 ; 4,18 |
| C1_V2 | témoin actions | 0,15 | 0,21 [0,06 ; 0,49] | 0,298 | 0,71 | 0,51 [0,45 ; 0,58] | 0,000 | indistinguable du hasard / réel | 3,37 ; 4,42 |
| C1_V2 | or (LBMA PM) | 0,05 | 0,32 [0,10 ; 0,65] | 0,033 | 0,50 | 0,52 [0,46 ; 0,59] | 0,686 | réel / indistinguable du hasard | 2,43 ; 2,60 |
| C1_V2 | BTC (DS1) | 0,59 | 0,44 [0,11 ; 0,70] | 0,803 | 0,51 | 0,51 [0,44 ; 0,58] | 0,414 | indistinguable du hasard / indistinguable du hasard | 3,25 ; 3,16 |

## 3. Test 1 bis — décalage circulaire (robustesse, rapporté)

| détecteur | actif | f_entrée observée | f_entrée aléatoire, médiane [5 % ; 95 %] | p_latence | justesse observée | justesse aléatoire, médiane [5 % ; 95 %] | p_justesse | lecture D4 (latence / justesse) | fausses alertes / an : observées, aléatoires (médiane) |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | S&P 500 | 0,34 | 0,26 [0,01 ; 1,00] | 0,595 | 0,82 | 0,49 [0,38 ; 0,62] | 0,001 | indistinguable du hasard / réel | 2,56 ; 2,97 |
| SMA200 | Nasdaq-100 | 0,37 | 0,29 [0,00 ; 1,00] | 0,621 | 0,80 | 0,48 [0,38 ; 0,66] | 0,010 | indistinguable du hasard / réel | 2,55 ; 3,12 |
| SMA200 | témoin actions | 0,36 | 0,31 [0,02 ; 0,81] | 0,586 | 0,81 | 0,47 [0,39 ; 0,64] | 0,008 | indistinguable du hasard / réel | 2,55 ; 3,01 |
| SMA200 | or (LBMA PM) | 0,66 | 0,15 [0,00 ; 0,56] | 0,984 | 0,73 | 0,48 [0,39 ; 0,61] | 0,011 | indistinguable du hasard / réel | 2,09 ; 2,50 |
| SMA200 | BTC (DS1) | 0,64 | 0,35 [0,00 ; 0,68] | 0,920 | 0,74 | 0,44 [0,33 ; 0,73] | 0,048 | indistinguable du hasard / réel | 1,83 ; 2,25 |
| MOM126 | S&P 500 | 0,34 | 0,29 [0,00 ; 1,00] | 0,565 | 0,79 | 0,49 [0,38 ; 0,62] | 0,007 | indistinguable du hasard / réel | 2,06 ; 2,31 |
| MOM126 | Nasdaq-100 | 0,43 | 0,30 [0,00 ; 1,00] | 0,634 | 0,79 | 0,49 [0,38 ; 0,66] | 0,010 | indistinguable du hasard / réel | 2,55 ; 2,86 |
| MOM126 | témoin actions | 0,39 | 0,35 [0,02 ; 0,78] | 0,564 | 0,79 | 0,48 [0,39 ; 0,62] | 0,009 | indistinguable du hasard / réel | 2,31 ; 2,59 |
| MOM126 | or (LBMA PM) | 0,48 | 0,15 [0,00 ; 0,50] | 0,945 | 0,69 | 0,48 [0,40 ; 0,60] | 0,012 | indistinguable du hasard / réel | 2,39 ; 2,50 |
| MOM126 | BTC (DS1) | 0,59 | 0,28 [0,00 ; 0,62] | 0,921 | 0,71 | 0,45 [0,36 ; 0,71] | 0,055 | indistinguable du hasard / non concluant | 3,25 ; 3,58 |
| C1_V1 | S&P 500 | 0,12 | 0,20 [0,04 ; 0,49] | 0,220 | 0,65 | 0,53 [0,49 ; 0,61] | 0,013 | indistinguable du hasard / réel | 6,27 ; 6,60 |
| C1_V1 | Nasdaq-100 | 0,15 | 0,19 [0,03 ; 0,39] | 0,339 | 0,64 | 0,53 [0,48 ; 0,61] | 0,006 | indistinguable du hasard / réel | 6,11 ; 6,33 |
| C1_V1 | témoin actions | 0,13 | 0,21 [0,09 ; 0,36] | 0,166 | 0,65 | 0,53 [0,49 ; 0,60] | 0,006 | non concluant / réel | 6,19 ; 6,44 |
| C1_V1 | or (LBMA PM) | 0,14 | 0,27 [0,12 ; 0,44] | 0,069 | 0,48 | 0,53 [0,49 ; 0,57] | 0,995 | non concluant / indistinguable du hasard | 4,08 ; 4,59 |
| C1_V1 | BTC (DS1) | 0,36 | 0,31 [0,08 ; 0,49] | 0,681 | 0,53 | 0,52 [0,48 ; 0,57] | 0,349 | indistinguable du hasard / indistinguable du hasard | 6,24 ; 6,49 |
| C1_V2 | S&P 500 | 0,19 | 0,23 [0,01 ; 0,77] | 0,430 | 0,72 | 0,50 [0,42 ; 0,67] | 0,036 | indistinguable du hasard / réel | 3,71 ; 4,74 |
| C1_V2 | Nasdaq-100 | 0,12 | 0,27 [0,00 ; 0,82] | 0,248 | 0,71 | 0,49 [0,41 ; 0,67] | 0,036 | indistinguable du hasard / réel | 3,03 ; 4,35 |
| C1_V2 | témoin actions | 0,15 | 0,27 [0,03 ; 0,66] | 0,258 | 0,71 | 0,50 [0,42 ; 0,67] | 0,035 | indistinguable du hasard / réel | 3,37 ; 4,59 |
| C1_V2 | or (LBMA PM) | 0,05 | 0,31 [0,08 ; 0,58] | 0,038 | 0,50 | 0,52 [0,45 ; 0,58] | 0,671 | réel / indistinguable du hasard | 2,43 ; 2,77 |
| C1_V2 | BTC (DS1) | 0,59 | 0,48 [0,14 ; 0,80] | 0,761 | 0,51 | 0,51 [0,44 ; 0,60] | 0,470 | indistinguable du hasard / indistinguable du hasard | 3,25 ; 3,16 |

## 4. Test 2 — diagnostic des f = 0 (rapporté, ne décide rien)

État du détecteur au jour du pic de chaque bear du juge, en trois cas (« bear depuis n s. » : en bear depuis n ≥ 1 séance avant le pic ; « bascule au pic » : bascule bear le jour même ; « non » : pas en bear au pic). La f_entrée diagnostic ignore les épisodes bear commencés plus de 21 séances avant le pic (raté = 1, comme A). Cette variante n'est pas une règle.

### S&P 500

| pic | creux | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 1998-07-17 | 1998-08-31 | non · f 0,63 · diag 0,63 | non · f 0,63 · diag 0,63 | non · f 0,20 · diag 0,20 | non · f 0,25 · diag 0,25 |
| 2000-03-24 | 2002-10-09 | non · f 0,23 · diag 0,23 | non · f 0,16 · diag 0,16 | non · f 0,04 · diag 0,04 | non · f 0,05 · diag 0,05 |
| 2007-10-09 | 2009-03-09 | non · f 0,10 · diag 0,10 | non · f 0,07 · diag 0,07 | non · f 0,10 · diag 0,10 | non · f 0,10 · diag 0,10 |
| 2018-09-20 | 2018-12-24 | non · f 0,35 · diag 0,35 | non · f 0,47 · diag 0,47 | non · f 0,08 · diag 0,08 | non · f 0,47 · diag 0,47 |
| 2020-02-19 | 2020-03-23 | non · f 0,35 · diag 0,35 | non · f 0,36 · diag 0,36 | non · f 0,14 · diag 0,14 | non · f 0,14 · diag 0,14 |
| 2022-01-03 | 2022-10-12 | non · f 0,33 · diag 0,33 | non · f 0,33 · diag 0,33 | non · f 0,26 · diag 0,26 | non · f 0,26 · diag 0,26 |

### Nasdaq-100

| pic | creux | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 2000-03-27 | 2002-10-07 | non · f 0,37 · diag 0,37 | non · f 0,43 · diag 0,43 | non · f 0,17 · diag 0,17 | non · f 0,12 · diag 0,12 |
| 2007-10-31 | 2008-11-20 | non · f 0,23 · diag 0,23 | non · f 0,23 · diag 0,23 | non · f 0,06 · diag 0,06 | non · f 0,06 · diag 0,06 |
| 2018-08-29 | 2018-12-24 | non · f 0,40 · diag 0,40 | non · f 0,47 · diag 0,47 | non · f 0,15 · diag 0,15 | non · f 0,49 · diag 0,49 |
| 2020-02-19 | 2020-03-20 | non · f 0,65 · diag 0,65 | non · f 0,90 · diag 0,90 | non · f 0,23 · diag 0,23 | non · f 0,23 · diag 0,23 |
| 2021-11-19 | 2022-12-28 | non · f 0,29 · diag 0,29 | non · f 0,29 · diag 0,29 | non · f 0,09 · diag 0,09 | non · f 0,09 · diag 0,09 |

### or (LBMA PM)

| pic | creux | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 1993-08-02 | 1993-09-14 | non · f 0,87 · diag 0,87 | non · f 1,00 · diag 1,00 | non · f 0,87 · diag 0,87 | non · f 0,55 · diag 0,55 |
| 1996-02-05 | 1999-07-20 | non · f 0,15 · diag 0,15 | non · f 0,17 · diag 0,17 | non · f 0,07 · diag 0,07 | non · f 0,44 · diag 0,44 |
| 1999-10-05 | 2001-04-02 | non · f 0,71 · diag 0,71 | non · f 0,54 · diag 0,54 | non · f 0,14 · diag 0,14 | non · f 0,05 · diag 0,05 |
| 2003-02-05 | 2003-04-07 | non · f 0,85 · diag 0,85 | non · f 1,00 · diag 1,00 | non · f 0,14 · diag 0,14 | bear depuis 15 s. · f 0,00 · diag 0,00 |
| 2006-05-12 | 2006-10-06 | non · f 0,83 · diag 0,83 | non · f 0,87 · diag 0,87 | bascule au pic · f 0,00 · diag 0,00 | non · f 0,20 · diag 0,20 |
| 2008-03-14 | 2008-10-24 | non · f 0,41 · diag 0,41 | non · f 0,28 · diag 0,28 | bascule au pic · f 0,00 · diag 0,00 | bear depuis 6 s. · f 0,00 · diag 0,00 |
| 2011-09-05 | 2015-12-17 | non · f 0,35 · diag 0,35 | non · f 0,43 · diag 0,43 | non · f 0,24 · diag 0,24 | bear depuis 22 s. · f 0,00 · diag 0,20 |
| 2016-07-06 | 2016-12-20 | non · f 0,46 · diag 0,46 | non · f 0,42 · diag 0,42 | non · f 0,18 · diag 0,18 | bear depuis 6 s. · f 0,00 · diag 0,00 |
| 2018-01-25 | 2018-08-17 | non · f 0,34 · diag 0,34 | non · f 0,17 · diag 0,17 | non · f 0,06 · diag 0,06 | non · f 0,12 · diag 0,12 |
| 2020-03-06 | 2020-03-19 | non · f 0,94 · diag 0,94 | non · f 0,94 · diag 0,94 | bear depuis 9 s. · f 0,00 · diag 0,00 | bear depuis 9 s. · f 0,00 · diag 0,00 |
| 2020-08-06 | 2022-11-03 | non · f 0,66 · diag 0,66 | non · f 0,48 · diag 0,48 | non · f 0,29 · diag 0,29 | non · f 0,22 · diag 0,22 |

### BTC (DS1)

| pic | creux | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 2013-12-04 | 2015-01-14 | non · f 0,68 · diag 0,68 | non · f 0,57 · diag 0,57 | non · f 0,37 · diag 0,37 | non · f 0,77 · diag 0,77 |
| 2017-12-16 | 2018-12-15 | non · f 0,77 · diag 0,77 | non · f 0,69 · diag 0,69 | non · f 0,50 · diag 0,50 | non · f 0,77 · diag 0,77 |
| 2019-06-26 | 2020-03-12 | non · f 0,60 · diag 0,60 | non · f 0,60 · diag 0,60 | non · f 0,35 · diag 0,35 | non · f 0,40 · diag 0,40 |
| 2021-11-08 | 2022-11-21 | non · f 0,40 · diag 0,40 | non · f 0,41 · diag 0,41 | non · f 0,27 · diag 0,27 | non · f 0,27 · diag 0,27 |

### Synthèse

| détecteur | actif | bears | f = 0 | f = 0 : bear avant le pic | f = 0 : bascule au pic | f = 0 : pas en bear | médiane f_entrée | médiane f diagnostic | ratés diagnostic |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | S&P 500 | 6 | 0 | — | — | — | 0,34 | 0,34 | 0 |
| SMA200 | Nasdaq-100 | 5 | 0 | — | — | — | 0,37 | 0,37 | 0 |
| SMA200 | or (LBMA PM) | 11 | 0 | — | — | — | 0,66 | 0,66 | 0 |
| SMA200 | BTC (DS1) | 4 | 0 | — | — | — | 0,64 | 0,64 | 0 |
| MOM126 | S&P 500 | 6 | 0 | — | — | — | 0,34 | 0,34 | 0 |
| MOM126 | Nasdaq-100 | 5 | 0 | — | — | — | 0,43 | 0,43 | 0 |
| MOM126 | or (LBMA PM) | 11 | 0 | — | — | — | 0,48 | 0,48 | 2 |
| MOM126 | BTC (DS1) | 4 | 0 | — | — | — | 0,59 | 0,59 | 0 |
| C1_V1 | S&P 500 | 6 | 0 | — | — | — | 0,12 | 0,12 | 0 |
| C1_V1 | Nasdaq-100 | 5 | 0 | — | — | — | 0,15 | 0,15 | 0 |
| C1_V1 | or (LBMA PM) | 11 | 3 | 33 % | 67 % | 0 % | 0,14 | 0,14 | 0 |
| C1_V1 | BTC (DS1) | 4 | 0 | — | — | — | 0,36 | 0,36 | 0 |
| C1_V2 | S&P 500 | 6 | 0 | — | — | — | 0,19 | 0,19 | 0 |
| C1_V2 | Nasdaq-100 | 5 | 0 | — | — | — | 0,12 | 0,12 | 0 |
| C1_V2 | or (LBMA PM) | 11 | 5 | 100 % | 0 % | 0 % | 0,05 | 0,12 | 0 |
| C1_V2 | BTC (DS1) | 4 | 0 | — | — | — | 0,59 | 0,59 | 0 |

## 5. Verdict de fiabilité mécanique

Fiable : p_latence < 0,05 au test 1 sur le témoin actions ET sur l'or. Dû à l'agitation : l'un des deux ≥ 0,20. Sinon non concluant. BTC rapporté : il ne valide rien seul.

| candidat | p_latence témoin | p_latence or | verdict | BTC : p_latence (lecture D4) |
|---|---|---|---|---|
| C1_V1 | 0,171 | 0,107 | **non concluant** | 0,580 (indistinguable du hasard) |
| C1_V2 | 0,298 | 0,033 | **dû à l'agitation** | 0,803 (indistinguable du hasard) |

## 6. Écarts au prompt

- **Permutation (test 1)** : le mélange brut de l'ordre des épisodes ne conserve pas les bascules, car deux épisodes voisins de même état fusionnent. Jonas a tranché (clarification 1) : la suite des états est gardée et les durées sont mélangées entre épisodes du même état.
- **Plage** : la permutation et le décalage portent sur la période mesurée de T1J (clarification 2). Hors de cette plage, le signal reste l'observé.
- **Témoin** : il est calculé tirage par tirage, avec la moyenne S&P 500 / Nasdaq-100 du même tirage (clarification 3).
- **Décalage (test 1 bis)** : en séances de l'actif, tiré uniformément dans [90, N − 90] (clarification 4).
- **Compteur** : une marque `diagnostic=True`, ignorée par le compteur, a été ajoutée au protocole pour concilier « aucun essai » et « journalisé dans `EXPERIMENTS.jsonl` ». Aucun run n'est journalisé.
- **Test 2** : « déjà en bear le jour du pic » est rapporté en trois cas, sans en retenir un seul.
- **Données** : celles de T1J, chaque série étant coupée à sa date de fin dans T1J. L'empreinte est vérifiée, comme les bears et les mesures observées de chaque couple.
- **Graine 0** : appliquée par couple détecteur × actif et par test. p n'a pas de correction +1 : c'est la part brute des 1 000 tirages, comme écrit. Les quantiles sont linéaires (numpy).
- **Fausses alertes** : calculées pour chaque tirage comme demandé, et rapportées dans une colonne en plus.
