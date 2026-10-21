# Temps 1, étape A (laboratoire) — rapport T1A

Calculé le 2026-10-21 18:30 UTC, code `fb1a755`, données `34591fd0a0c5b4f8` (dernière séance commune : 2026-10-20). Préenregistrement : `EXPERIMENTS.jsonl`, id `T1A`. Phase 1 : `temps1/DISCOVERY.md`. Détail complet : `temps1/RAPPORT_ETAPE_A.csv` (une ligne par détecteur × actif × période) et `temps1/RAPPORT_ETAPE_A_episodes.csv`.

## 1. Compteur d'essais

| avant T1A | après le préenregistrement | après les 14 couples (journalisés avant le premier calcul) |
|---|---|---|
| 117 | 118 | 131 |

## 2. Couverture des données

| série | source | début | fin | obs. | trous > 5 séances |
|---|---|---|---|---|---|
| SPX | yahoo `^GSPC` | 1927-12-30 | 2026-10-20 | 24818 | 1 |
| NDX | yahoo `^NDX` | 1985-10-01 | 2026-10-20 | 10343 | 0 |
| VIX | yahoo `^VIX` | 1990-01-02 | 2026-10-20 | 9270 | 0 |
| XAU_LBMA | wgc `LBMA Gold Price PM, USD/oz` | 1970-01-01 | 2026-10-20 | 14740 | 0 |
| DEXJPUS | fred `DEXJPUS` (valeurs : frb_h10) | 1971-01-04 | 2026-10-16 | 13984 | 1 |

Séances de l'actif cible comblées par la dernière valeur connue (labo / informative) :

| actif cible | série | séances comblées labo | plus longue suite labo | séances comblées informative | plus longue suite informative |
|---|---|---|---|---|---|
| S&P 500 | SPX | 0 | 0 | 0 | 0 |
| S&P 500 | VIX | 0 | 0 | 0 | 0 |
| S&P 500 | XAU_LBMA | 35 | 2 | 16 | 2 |
| S&P 500 | DEXJPUS | 79 | 1 | 7 | 2 |
| Nasdaq-100 | NDX | 0 | 0 | 0 | 0 |
| Nasdaq-100 | SPX | 0 | 0 | 0 | 0 |
| Nasdaq-100 | VIX | 0 | 0 | 0 | 0 |
| Nasdaq-100 | XAU_LBMA | 35 | 2 | 16 | 2 |
| Nasdaq-100 | DEXJPUS | 79 | 1 | 7 | 2 |

DEXJPUS, point-in-time : mode **decalage_2_jours_ouvres** — 0 observation(s) datée(s) par ALFRED, 13984 au décalage de 2 jours ouvrés (sur 13984).

## 3. Tableau principal — période labo (1991-01-01 → 2023-12-31)

| détecteur | actif | Ulcer | Ulcer témoin | Ulcer SMA200 | p retenue | porte 1 | porte 2 | porte 3 |
|---|---|---|---|---|---|---|---|---|
| SMA200 | S&P 500 | 0,1171 | 0,1319 | 0,1171 | 0,105 | échoue | passe | n/a |
| SMA200 | Nasdaq-100 | 0,2962 | 0,3334 | 0,2962 | 0,210 | échoue | passe | n/a |
| SMA126 | S&P 500 | 0,1974 | 0,1287 | 0,1171 | 0,727 | n/a | n/a | n/a |
| SMA126 | Nasdaq-100 | 0,3029 | 0,3265 | 0,2962 | 0,233 | n/a | n/a | n/a |
| SMA168 | S&P 500 | 0,1484 | 0,1308 | 0,1171 | 0,305 | n/a | n/a | n/a |
| SMA168 | Nasdaq-100 | 0,2932 | 0,3309 | 0,2962 | 0,175 | n/a | n/a | n/a |
| SMA210 | S&P 500 | 0,1064 | 0,1321 | 0,1171 | 0,054 | n/a | n/a | n/a |
| SMA210 | Nasdaq-100 | 0,2329 | 0,3341 | 0,2962 | 0,105 | n/a | n/a | n/a |
| SMA252 | S&P 500 | 0,1052 | 0,1340 | 0,1171 | 0,051 | n/a | n/a | n/a |
| SMA252 | Nasdaq-100 | 0,1968 | 0,3384 | 0,2962 | 0,066 | n/a | n/a | n/a |
| MOM126 | S&P 500 | 0,0972 | 0,1303 | 0,1171 | 0,042 | passe | passe | passe |
| MOM126 | Nasdaq-100 | 0,2569 | 0,3302 | 0,2962 | 0,132 | échoue | passe | passe |
| COUCHE1 | S&P 500 | 0,2053 | 0,1335 | 0,1171 | 0,790 | échoue | échoue | échoue |
| COUCHE1 | Nasdaq-100 | 0,4521 | 0,3351 | 0,2962 | 0,866 | échoue | échoue | échoue |

n/a : porte non applicable — porte 3 pour SMA200 elle-même ; aucune porte pour les fenêtres de la bande (règle 2 : pas de choix de fenêtre).

## 4. Bande SMA — les cinq fenêtres côte à côte (labo)

| actif | métrique | SMA126 | SMA168 | SMA200 | SMA210 | SMA252 |
|---|---|---|---|---|---|---|
| S&P 500 | Ulcer | 0,1974 | 0,1484 | 0,1171 | 0,1064 | 0,1052 |
| S&P 500 | Ulcer témoin | 0,1287 | 0,1308 | 0,1319 | 0,1321 | 0,1340 |
| S&P 500 | p retenue | 0,727 | 0,305 | 0,105 | 0,054 | 0,051 |
| S&P 500 | MDD | -46,1 % | -38,2 % | -31,9 % | -28,8 % | -28,2 % |
| S&P 500 | CAGR | +4,7 % | +5,7 % | +6,5 % | +6,9 % | +7,0 % |
| S&P 500 | exposition moyenne | 0,795 | 0,807 | 0,814 | 0,815 | 0,826 |
| S&P 500 | changements | 366 | 295 | 229 | 225 | 187 |
| Nasdaq-100 | Ulcer | 0,3029 | 0,2932 | 0,2962 | 0,2329 | 0,1968 |
| Nasdaq-100 | Ulcer témoin | 0,3265 | 0,3309 | 0,3334 | 0,3341 | 0,3384 |
| Nasdaq-100 | p retenue | 0,233 | 0,175 | 0,210 | 0,105 | 0,066 |
| Nasdaq-100 | MDD | -63,1 % | -66,8 % | -63,9 % | -56,6 % | -48,8 % |
| Nasdaq-100 | CAGR | +11,3 % | +12,3 % | +12,4 % | +12,9 % | +13,8 % |
| Nasdaq-100 | exposition moyenne | 0,800 | 0,812 | 0,818 | 0,820 | 0,832 |
| Nasdaq-100 | changements | 342 | 247 | 239 | 227 | 189 |

## 5. Période informative (2024-01-01 → 2026-10-20) — déjà vu, ne décide rien

| détecteur | actif | Ulcer | Ulcer témoin | Ulcer SMA200 | p retenue | MDD | CAGR | expo moy. | épisodes ≥ 20 % |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | S&P 500 | 0,0341 | 0,0319 | 0,0341 | 0,816 | -12,1 % | +16,2 % | 0,94 | 0 |
| SMA200 | Nasdaq-100 | 0,0461 | 0,0469 | 0,0461 | 0,188 | -13,6 % | +19,5 % | 0,94 | 1 |
| SMA126 | S&P 500 | 0,0294 | 0,0312 | 0,0341 | 0,126 | -9,7 % | +16,2 % | 0,92 | 0 |
| SMA126 | Nasdaq-100 | 0,0525 | 0,0449 | 0,0461 | 0,776 | -13,1 % | +16,3 % | 0,90 | 1 |
| SMA168 | S&P 500 | 0,0320 | 0,0315 | 0,0341 | 0,148 | -10,7 % | +16,0 % | 0,93 | 0 |
| SMA168 | Nasdaq-100 | 0,0517 | 0,0463 | 0,0461 | 0,726 | -14,1 % | +17,5 % | 0,92 | 1 |
| SMA210 | S&P 500 | 0,0346 | 0,0320 | 0,0341 | 0,842 | -12,1 % | +15,7 % | 0,94 | 0 |
| SMA210 | Nasdaq-100 | 0,0552 | 0,0471 | 0,0461 | 0,961 | -17,0 % | +17,6 % | 0,94 | 1 |
| SMA252 | S&P 500 | 0,0479 | 0,0327 | 0,0341 | 1,000 | -16,3 % | +14,0 % | 0,96 | 0 |
| SMA252 | Nasdaq-100 | 0,0522 | 0,0480 | 0,0461 | 0,885 | -16,5 % | +19,3 % | 0,96 | 1 |
| MOM126 | S&P 500 | 0,0343 | 0,0312 | 0,0341 | 0,804 | -11,0 % | +14,7 % | 0,92 | 0 |
| MOM126 | Nasdaq-100 | 0,0506 | 0,0474 | 0,0461 | 0,611 | -14,9 % | +17,2 % | 0,95 | 1 |
| COUCHE1 | S&P 500 | 0,0375 | 0,0315 | 0,0341 | 0,891 | -13,1 % | +13,2 % | 0,93 | 0 |
| COUCHE1 | Nasdaq-100 | 0,0595 | 0,0464 | 0,0461 | 0,972 | -17,7 % | +15,3 % | 0,93 | 1 |

## 6. Verdict mécanique

**Aucun timing démontré** : aucun candidat ne franchit les trois portes sur les deux actifs, et SMA200 ne franchit pas les portes 1 et 2 sur les deux actifs.

## 7. Écarts au prompt

- **Nasdaq = Nasdaq-100 `^NDX`.** Le prompt dit « Nasdaq » ; Jonas a choisi le Nasdaq-100 le 21/10 (question posée avant tout code).
- **Or = fixing LBMA de l'après-midi, via le World Gold Council, pas yfinance.** Yahoo n'a pas l'or comptant, seulement le contrat à terme GC=F, et seulement depuis 2000 : COUCHE1 aurait été incalculable sur 1991-2001. Choix de Jonas le 21/10. Le fixing a lieu à 15:00 à Londres, ce n'est pas une clôture. Avant 2019, WGC remplit les fériés londoniens avec la valeur précédente, et ces jours comptent comme des fixings dans la SMA 200 de l'or.
- **Calendrier civil comblé.** C'est la seule façon de réutiliser le moteur TI1 sans le modifier : il annualise sur 365 jours et calcule ses captures sur des semaines de 7 jours. Les rendements sont nuls les jours sans séance. Aux dates de séance, la courbe est celle d'un calcul séance par séance (vérifié par un test). Ulcer, retards, durées, faux signaux (60 jours) et décalage des nulls (≥ 90 jours) se comptent donc en jours civils.
- **κ = 10 pb par unité de |ΔE|** (moteur tel quel). Un passage 1,0 → 0,25 coûte 7,5 pb, un passage 1,0 → 0,7 coûte 3 pb.
- **Indices de prix, dividendes exclus ; liquidités rémunérées à 0 ; pas de coût d'entrée.** Ce sont les conventions du moteur TI1, inchangées.
- **VIX.** La clôture de 16:15 ET sert à une décision prise à la clôture des actions (16:00 ET). C'est la même idéalisation « décidé à la clôture » que le moteur.
- **Préchauffe.** Elle porte sur chaque série lue, pas seulement sur l'actif cible : 252 observations avant la première décision, et au moins la fenêtre du détecteur.
- **Bande SMA126/168/210/252 sans portes.** Le prompt ne leur en donne pas ; les juger reviendrait à choisir une fenêtre (règle 2).
- **DEXJPUS, point-in-time en mode « decalage_2_jours_ouvres ».** 13984 observation(s) sur 13984 n'ont pas de date ALFRED informative : antérieures à l'archive, ou ALFRED indisponible. Elles reçoivent le décalage de 2 jours ouvrés US prévu par le prompt. ⚠️ Le H.10 est hebdomadaire (publié le lundi) : ce repli peut lire une valeur jusqu'à environ 5 jours ouvrés avant sa publication réelle.

## Annexe — métriques par détecteur × actif × période

| détecteur | actif | période | MDD | protection | retard moyen (j) | faux signaux (coût) | capture ↑ | capture ↓ | CAGR | expo | chgts | p circ. | p seg. |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| SMA200 | SPX | labo | -31,9 % | 0,44 | 18 | 99/114 (+76,2 %) | 0,71 | 0,71 | +6,5 % | 0,81 | 229 | 0,089 | 0,105 |
| SMA200 | SPX | informative | -12,1 % | — | — | 1/3 (+2,0 %) | 0,87 | 0,87 | +16,2 % | 0,94 | 6 | 0,685 | 0,816 |
| SMA200 | NDX | labo | -63,9 % | 0,22 | 42 | 97/119 (+143,0 %) | 0,75 | 0,73 | +12,4 % | 0,82 | 239 | 0,191 | 0,210 |
| SMA200 | NDX | informative | -13,6 % | 0,43 | 15 | 1/2 (+3,2 %) | 0,88 | 0,88 | +19,5 % | 0,94 | 4 | 0,077 | 0,188 |
| SMA126 | SPX | labo | -46,1 % | 0,40 | 13 | 158/183 (+148,2 %) | 0,68 | 0,71 | +4,7 % | 0,79 | 366 | 0,720 | 0,727 |
| SMA126 | SPX | informative | -9,7 % | — | — | 3/5 (+4,4 %) | 0,85 | 0,85 | +16,2 % | 0,92 | 10 | 0,084 | 0,126 |
| SMA126 | NDX | labo | -63,1 % | 0,29 | 34 | 139/171 (+168,1 %) | 0,72 | 0,71 | +11,3 % | 0,80 | 342 | 0,199 | 0,233 |
| SMA126 | NDX | informative | -13,1 % | 0,43 | 8 | 7/10 (+9,0 %) | 0,85 | 0,89 | +16,3 % | 0,90 | 20 | 0,776 | 0,699 |
| SMA168 | SPX | labo | -38,2 % | 0,43 | 18 | 124/147 (+112,1 %) | 0,69 | 0,71 | +5,7 % | 0,81 | 295 | 0,305 | 0,305 |
| SMA168 | SPX | informative | -10,7 % | — | — | 3/5 (+3,8 %) | 0,86 | 0,86 | +16,0 % | 0,93 | 10 | 0,092 | 0,148 |
| SMA168 | NDX | labo | -66,8 % | 0,23 | 36 | 102/123 (+163,8 %) | 0,74 | 0,72 | +12,3 % | 0,81 | 247 | 0,155 | 0,175 |
| SMA168 | NDX | informative | -14,1 % | 0,39 | 13 | 5/7 (+6,4 %) | 0,86 | 0,90 | +17,5 % | 0,92 | 14 | 0,726 | 0,677 |
| SMA210 | SPX | labo | -28,8 % | 0,46 | 18 | 97/112 (+64,1 %) | 0,72 | 0,71 | +6,9 % | 0,82 | 225 | 0,054 | 0,049 |
| SMA210 | SPX | informative | -12,1 % | — | — | 1/3 (+3,2 %) | 0,87 | 0,89 | +15,7 % | 0,94 | 6 | 0,806 | 0,842 |
| SMA210 | NDX | labo | -56,6 % | 0,24 | 44 | 90/113 (+134,6 %) | 0,75 | 0,72 | +12,9 % | 0,82 | 227 | 0,086 | 0,105 |
| SMA210 | NDX | informative | -17,0 % | 0,26 | 15 | 1/4 (+3,2 %) | 0,88 | 0,92 | +17,6 % | 0,94 | 8 | 0,931 | 0,961 |
| SMA252 | SPX | labo | -28,2 % | 0,43 | 20 | 78/93 (+62,5 %) | 0,73 | 0,72 | +7,0 % | 0,83 | 187 | 0,049 | 0,051 |
| SMA252 | SPX | informative | -16,3 % | — | — | 3/6 (+8,5 %) | 0,89 | 0,96 | +14,0 % | 0,96 | 12 | 1,000 | 0,995 |
| SMA252 | NDX | labo | -48,8 % | 0,27 | 47 | 77/94 (+106,7 %) | 0,77 | 0,73 | +13,8 % | 0,83 | 189 | 0,066 | 0,052 |
| SMA252 | NDX | informative | -16,5 % | 0,28 | 19 | 2/4 (+2,3 %) | 0,92 | 0,94 | +19,3 % | 0,96 | 8 | 0,885 | 0,871 |
| MOM126 | SPX | labo | -33,3 % | 0,49 | 29 | 93/107 (+59,9 %) | 0,72 | 0,70 | +7,3 % | 0,80 | 215 | 0,033 | 0,042 |
| MOM126 | SPX | informative | -11,0 % | — | — | 2/4 (+5,8 %) | 0,82 | 0,84 | +14,7 % | 0,92 | 8 | 0,804 | 0,708 |
| MOM126 | NDX | labo | -61,7 % | 0,17 | 51 | 88/110 (+144,2 %) | 0,74 | 0,72 | +12,1 % | 0,81 | 221 | 0,124 | 0,132 |
| MOM126 | NDX | informative | -14,9 % | 0,35 | 27 | 4/6 (+9,2 %) | 0,86 | 0,89 | +17,2 % | 0,95 | 12 | 0,611 | 0,553 |
| COUCHE1 | SPX | labo | -46,0 % | 0,33 | 14 | 169/191 (+112,1 %) | 0,70 | 0,74 | +4,8 % | 0,82 | 503 | 0,768 | 0,790 |
| COUCHE1 | SPX | informative | -13,1 % | — | — | 15/16 (+9,4 %) | 0,83 | 0,90 | +13,2 % | 0,93 | 35 | 0,879 | 0,891 |
| COUCHE1 | NDX | labo | -80,0 % | 0,20 | 15 | 143/191 (+133,1 %) | 0,73 | 0,77 | +8,5 % | 0,82 | 503 | 0,817 | 0,866 |
| COUCHE1 | NDX | informative | -17,7 % | 0,23 | 19 | 15/16 (+11,2 %) | 0,85 | 0,92 | +15,3 % | 0,93 | 35 | 0,961 | 0,972 |

Buy and hold de référence (même période) :

| actif | période | Ulcer | MDD | CAGR | épisodes ≥ 20 % |
|---|---|---|---|---|---|
| S&P 500 | labo | 0,1635 | -56,8 % | +8,4 % | 4 |
| S&P 500 | informative | 0,0340 | -18,9 % | +18,7 % | 0 |
| Nasdaq-100 | labo | 0,3994 | -82,9 % | +14,4 % | 5 |
| Nasdaq-100 | informative | 0,0501 | -22,9 % | +22,1 % | 1 |

Protection par épisode de baisse ≥ 20 % : `temps1/RAPPORT_ETAPE_A_episodes.csv`.
