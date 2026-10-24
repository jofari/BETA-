# Temps 1 — test de justesse des détecteurs de régime (T1J)

## Clarifications avant calcul

Décidées par Jonas le **24/10/2026**, après la découverte (`temps1_justesse/DISCOVERY.md`, commit
`7be0fe1`), **avant tout calcul de détecteur, de juge ou de mesure**.

**A. Les ratés dans la médiane de f_entrée.** Un bear raté (aucune bascule bear avant le creux)
compte **f = 1** dans la médiane et dans le pire cas. Le nombre de ratés reste rapporté à part.

**B. Un épisode à cheval sur deux périodes.** Le juge tourne sur tout l'historique. Un épisode
n'appartient à une période que si **ses deux bornes** (pic et creux) y sont toutes les deux. Les
épisodes à cheval sont listés, et aucune mesure ne les utilise.

**C. Épisodes neutres.** P début = **clôture de la veille du premier jour neutre**, P fin =
clôture du dernier jour neutre (n rendements pour √n).

**D. Le gagnant principal.** Si plusieurs candidats sont retenus, le gagnant principal est celui
qui a **la plus petite moyenne des médianes de f_entrée sur le témoin actions et sur l'or**. À
égalité, c'est le meilleur pire cas moyen qui l'emporte. **Tous les candidats retenus à l'étape A
passent quand même à l'étape B (BTC).**

**E. USD/JPY (DEXJPUS) : vrai calendrier de parution.** ALFRED est indisponible, et le H.10 paraît
une fois par semaine. Une valeur de la semaine S devient utilisable à la clôture du **mardi
suivant**, c'est-à-dire le 2e jour ouvré Fed après le vendredi de S. Si le lundi est férié, c'est
le mercredi.

**F. Essais informatifs.** Les variantes du juge (15 %, 25 %, σ unique) **ne sont pas des
essais** : ce sont les mêmes détecteurs mesurés autrement. Elles sont rapportées, sans être
comptées. Essais informatifs = bande SMA (4 fenêtres × 3 actifs = 12) + fenêtres σ 21 et 126 de
C1_V1 (2 × 3 actifs = 6) = **18**, sur une ligne à part.

### Compteur et essais du verdict (24/10/2026)

- **Les deux valeurs ne se remplacent pas.** Le préenregistrement gelé dit **117** : c'est le
  compteur **global** au gel. BETA a aujourd'hui deux compteurs, et ce rapport donne les deux avec
  leur nom exact :
  - **global** (`experiences.compteur_total`, trading + invest) : 131 avant ce test, parce que T1A
    l'a porté de 117 à 131 le 21/10 ;
  - **invest** (`experiences.compteur(famille="invest")`) : 38 avant ce test. C'est celui qui
    correspond aux tests de détecteurs (T1A y est), donc celui qui est incrémenté.
- **Essais du verdict : 16.** SMA200 compte aussi, et le BTC aussi : 4 détecteurs (SMA200,
  MOM126, C1_V1, C1_V2) × 3 actifs labo (S&P 500, Nasdaq-100, or) = 12, plus les 4 détecteurs
  sur le BTC = 4.
- **Détail affiché avant le lancement** : global 131 → 147, invest 38 → 54, trading actif 93
  inchangé.

### Précisions complémentaires (24/10/2026, demandées avant le gel)

- **Variantes σ 21 et σ 126 de C1_V1.** Pour V, la moyenne du VIX change de fenêtre **avec** σ :
  VIX > moyenne 21 + 2 × σ21, ou moyenne 126 + 2 × σ126. Pour Y, T et G, σ63 devient σ21 ou σ126.
- **« Résultat solide » (règle 5).** Il faut **le même gagnant principal ET la même liste de
  candidats retenus** sous les 3 variantes du juge.
- **Ratés de sortie.** Même règle que A : un raté de sortie compte **f = 1** dans la médiane et le
  pire cas de f_sortie, et le nombre de ratés est rapporté à part.

<!-- FIN DES CLARIFICATIONS : tout ce qui suit est ecrit par le programme (scripts/temps1_justesse.py) -->

# Résultats — calculés le 2026-10-24T13:21:08+00:00 UTC

Code `8afdbe7`, règles `c0959f429d9dcf8f`, clarifications `0c91e1292ba97235`, données `a3d6d80952500d57`. Préenregistrement : `EXPERIMENTS.jsonl`, id `T1J`. Rapport écrit par `scripts/temps1_justesse.py`, sans interprétation au-delà du verdict mécanique.

## 1. Compteur d'essais

- **Valeur au gel du préenregistrement (22/10/2026)** : compteur global **117**. Elle est rapportée telle quelle, sans être remplacée.
- **Compteur global** (`experiences.compteur_total`, trading + invest) : 131 avant T1J, 132 au lancement (T1J préenregistrée, sans mesure), **147 après la journalisation**.
- **Compteur invest** (`experiences.compteur(famille="invest")`, celui des tests de détecteurs, incrémenté) : 38 avant T1J, 39 au lancement, **54 après la journalisation**.
- Compteur trading actif : 93, inchangé.
- **Essais du verdict** : 4 détecteurs × 3 actifs labo + 4 détecteurs × BTC = 16, journalisés avant le premier calcul (16 nouveaux à ce lancement).
- **Essais informatifs** (ligne à part, aucun compteur) : bande SMA 12 + variantes σ 21 et σ 126 de C1_V1 6 = **18**. Les variantes du juge sont rapportées, mais ne sont pas des essais.

Couples du verdict et leurs identifiants de run (`RUNS.jsonl`) :

| détecteur | actif | run |
|---|---|---|
| SMA200 | S&P 500 | `ff1ec8b373a0` |
| SMA200 | Nasdaq-100 | `3223af628d54` |
| SMA200 | or (LBMA PM) | `306f1be3bd00` |
| MOM126 | S&P 500 | `360bdb208f5b` |
| MOM126 | Nasdaq-100 | `4d4c5a958f28` |
| MOM126 | or (LBMA PM) | `3fa093ab737a` |
| C1_V1 | S&P 500 | `53d5f1d4aa38` |
| C1_V1 | Nasdaq-100 | `473202ce8fc9` |
| C1_V1 | or (LBMA PM) | `6ce59822a8d8` |
| C1_V2 | S&P 500 | `27ca4b85493f` |
| C1_V2 | Nasdaq-100 | `b92667b0cc80` |
| C1_V2 | or (LBMA PM) | `ab6c15154154` |
| SMA200 | BTC (DS1) | `db5133552767` |
| MOM126 | BTC (DS1) | `d53a33a79a87` |
| C1_V1 | BTC (DS1) | `65c03058dcea` |
| C1_V2 | BTC (DS1) | `726d71ce72e6` |

## 2. Couverture des données

| série | série `beta.marches` | début | fin | observations | trous > 5 séances | séances US comblées (labo + préchauffe / 2024 → fin) |
|---|---|---|---|---|---|---|
| SPX | `SPX` | 1927-12-30 | 2026-10-23 | 24 821 | 1 | — |
| NDX | `NDX` | 1985-10-01 | 2026-10-23 | 10 346 | 0 | — |
| OR | `XAU_LBMA` | 1970-01-01 | 2026-10-22 | 14 742 | 0 | 35 / 16 |
| BTC | `BTC_DS1` | 2011-08-18 | 2026-10-23 | 5 546 | 0 | — |
| VIX | `VIXCLS` | 1990-01-02 | 2026-10-22 | 9 301 | 0 | 3 / 1 |
| USDJPY | `DEXJPUS` | 1971-01-04 | 2026-10-16 | 13 984 | 1 | 82 / 10 |

Empreinte des données : `a3d6d80952500d57`. Les séances US comblées sont celles où la série n'a pas d'observation du jour : la couche 1 y lit la dernière valeur connue. Le BTC, le S&P 500, le Nasdaq-100 et l'or sont jugés sur leurs propres dates, sans comblement.

**USD/JPY (clarification E)** : ALFRED indisponible ; vrai calendrier (Jonas 24/10, E) : une observation de la semaine S (lundi-vendredi) devient utilisable a la cloture du 2e jour ouvre Fed strictement apres le vendredi de S (mardi en temps normal, mercredi si le lundi est ferie ; jours ouvres = lundi-vendredi hors feries federaux US).

**Épreuve de causalité** : signaux recalculés avec les seules données connues à 8 dates de coupure, puis comparés aux signaux calculés sur tout l'historique. Aucun écart.

## 3. Les bears du juge

σ_S&P_ref (S&P 500, labo 1991-2023, annualisée) = **18,26 %**. Un bear marqué « à cheval » n'a qu'une borne dans la période : aucune mesure ne l'utilise (B).

### S&P 500

Juge à partir du 1930-01-01. Dernier pivot sur tout l'historique : creux du 2025-04-08 ; le cycle qui suit est en cours, exclu.

**labo 1991-2023** : θ_baisse de 10,1 % à 35,0 %, θ_hausse de 11,3 % à 53,8 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 1998-07-17 | 1998-08-31 | -19,3 % | oui |
| 2000-03-24 | 2002-10-09 | -49,1 % | oui |
| 2007-10-09 | 2009-03-09 | -56,8 % | oui |
| 2018-09-20 | 2018-12-24 | -19,8 % | oui |
| 2020-02-19 | 2020-03-23 | -33,9 % | oui |
| 2022-01-03 | 2022-10-12 | -25,4 % | oui |

**2024 → fin (informatif)** : θ_baisse de 14,5 % à 21,2 %, θ_hausse de 17,0 % à 26,9 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 2025-02-19 | 2025-04-08 | -18,9 % | oui |

### Nasdaq-100

Juge à partir du 1987-10-01. Dernier pivot sur tout l'historique : creux du 2025-04-08 ; le cycle qui suit est en cours, exclu.

**labo 1991-2023** : θ_baisse de 14,9 % à 49,6 %, θ_hausse de 17,5 % à 98,5 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 2000-03-27 | 2002-10-07 | -82,9 % | oui |
| 2007-10-31 | 2008-11-20 | -53,7 % | oui |
| 2018-08-29 | 2018-12-24 | -23,0 % | oui |
| 2020-02-19 | 2020-03-20 | -28,0 % | oui |
| 2021-11-19 | 2022-12-28 | -35,6 % | oui |

**2024 → fin (informatif)** : θ_baisse de 19,9 % à 27,6 %, θ_hausse de 24,8 % à 38,1 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 2025-02-19 | 2025-04-08 | -22,9 % | oui |

### or (LBMA PM)

Juge à partir du 1972-01-01. Dernier pivot sur tout l'historique : pic du 2026-01-29 ; le cycle qui suit est en cours, exclu.

**labo 1991-2023** : θ_baisse de 7,3 % à 27,6 %, θ_hausse de 7,9 % à 38,2 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 1990-08-21 | 1993-03-10 | -21,2 % | à cheval |
| 1993-08-02 | 1993-09-14 | -15,3 % | oui |
| 1996-02-05 | 1999-07-20 | -39,1 % | oui |
| 1999-10-05 | 2001-04-02 | -21,4 % | oui |
| 2003-02-05 | 2003-04-07 | -16,3 % | oui |
| 2006-05-12 | 2006-10-06 | -22,7 % | oui |
| 2008-03-14 | 2008-10-24 | -28,7 % | oui |
| 2011-09-05 | 2015-12-17 | -44,6 % | oui |
| 2016-07-06 | 2016-12-20 | -17,6 % | oui |
| 2018-01-25 | 2018-08-17 | -13,0 % | oui |
| 2020-03-06 | 2020-03-19 | -12,4 % | oui |
| 2020-08-06 | 2022-11-03 | -21,2 % | oui |

**2024 → fin (informatif)** : θ_baisse de 14,8 % à 24,4 %, θ_hausse de 17,4 % à 32,3 %.

*Aucun bear complet.*

Bear en cours depuis le pic du 2026-01-29 (-25,1 % à la dernière date), exclu.

### BTC (DS1)

Juge à partir du 2013-10-01. Dernier pivot sur tout l'historique : pic du 2025-10-06 ; le cycle qui suit est en cours, exclu.

**étape B** : θ_baisse de 36,4 % à 72,3 %, θ_hausse de 57,2 % à 260,7 %.

| pic | creux | baisse | dans la période |
|---|---|---|---|
| 2013-12-04 | 2015-01-14 | -84,9 % | oui |
| 2017-12-16 | 2018-12-15 | -83,4 % | oui |
| 2019-06-26 | 2020-03-12 | -62,5 % | oui |
| 2021-11-08 | 2022-11-21 | -76,7 % | oui |

Bear en cours depuis le pic du 2025-10-06 (-35,0 % à la dernière date), exclu.

## 4. Tableau principal — labo 1991-2023

f_entrée : 0 = bascule bear au sommet, 1 = au creux ; un raté compte 1 (A). f_sortie : 0 = bascule bull au creux, 1 = au pic suivant ; un raté compte 1. Toutes les mesures portent sur la période mesurée du juge (B).

### témoin actions (moyenne S&P 500 et Nasdaq-100)

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,36 | 0,64 | 0 / 5,5 | 2,55 | 0,81 | 0,18 | 7,79 | 0 / 4,5 | référence |
| MOM126 | 0,39 | 0,76 | 0 / 5,5 | 2,31 | 0,79 | 0,20 | 6,70 | 0 / 4,5 | aucune domination |
| C1_V1 | 0,13 | 0,25 | 0 / 5,5 | 6,19 | 0,65 | 0,19 | 23,89 | 0 / 4,5 | aucune domination |
| C1_V2 | 0,15 | 0,48 | 0 / 5,5 | 3,37 | 0,71 | 0,29 | 15,18 | 0 / 4,5 | aucune domination |

### or (LBMA PM)

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,66 | 0,94 | 0 / 11 | 2,09 | 0,73 | 0,14 | 9,85 | 0 / 11 | référence |
| MOM126 | 0,48 | 1,00 | 2 / 11 | 2,39 | 0,69 | 0,15 | 9,65 | 0 / 11 | aucune domination |
| C1_V1 | 0,14 | 0,87 | 0 / 11 | 4,08 | 0,48 | 0,00 | 23,98 | 0 / 11 | aucune domination |
| C1_V2 | 0,05 | 0,55 | 0 / 11 | 2,43 | 0,50 | 0,00 | 14,23 | 0 / 11 | aucune domination |

Période mesurée : 1993-03-10 → 2022-11-03 (29,7 ans).

### S&P 500

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,34 | 0,63 | 0 / 6 | 2,56 | 0,82 | 0,19 | 7,63 | 0 / 5 | référence |
| MOM126 | 0,34 | 0,63 | 0 / 6 | 2,06 | 0,79 | 0,27 | 5,98 | 0 / 5 | aucune domination |
| C1_V1 | 0,12 | 0,26 | 0 / 6 | 6,27 | 0,65 | 0,15 | 24,05 | 0 / 5 | aucune domination |
| C1_V2 | 0,19 | 0,47 | 0 / 6 | 3,71 | 0,72 | 0,36 | 15,64 | 0 / 5 | aucune domination |

Période mesurée : 1998-07-17 → 2022-10-12 (24,2 ans).

### Nasdaq-100

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,37 | 0,65 | 0 / 5 | 2,55 | 0,80 | 0,18 | 7,95 | 0 / 4 | référence |
| MOM126 | 0,43 | 0,90 | 0 / 5 | 2,55 | 0,79 | 0,13 | 7,43 | 0 / 4 | dominé par SMA200 |
| C1_V1 | 0,15 | 0,23 | 0 / 5 | 6,11 | 0,64 | 0,23 | 23,73 | 0 / 4 | aucune domination |
| C1_V2 | 0,12 | 0,49 | 0 / 5 | 3,03 | 0,71 | 0,22 | 14,72 | 0 / 4 | aucune domination |

Période mesurée : 2000-03-27 → 2022-12-28 (22,8 ans).

## 5. Détecteur × épisode — labo

f_entrée de chaque bear du juge, avec le retard en jours civils et en séances entre le pic et la bascule bear. Puis f_sortie de chaque bull complet.

### S&P 500 — entrées

| pic | creux | baisse | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|---|
| 1998-07-17 | 1998-08-31 | -19,3 % | 0,63 (41 j, 29 s.) | 0,63 (41 j, 29 s.) | 0,20 (6 j, 4 s.) | 0,25 (11 j, 7 s.) |
| 2000-03-24 | 2002-10-09 | -49,1 % | 0,23 (21 j, 15 s.) | 0,16 (56 j, 39 s.) | 0,04 (11 j, 7 s.) | 0,05 (6 j, 4 s.) |
| 2007-10-09 | 2009-03-09 | -56,8 % | 0,10 (29 j, 21 s.) | 0,07 (27 j, 19 s.) | 0,10 (29 j, 21 s.) | 0,10 (29 j, 21 s.) |
| 2018-09-20 | 2018-12-24 | -19,8 % | 0,35 (21 j, 15 s.) | 0,47 (34 j, 24 s.) | 0,08 (15 j, 11 s.) | 0,47 (34 j, 24 s.) |
| 2020-02-19 | 2020-03-23 | -33,9 % | 0,35 (8 j, 6 s.) | 0,36 (16 j, 12 s.) | 0,14 (5 j, 3 s.) | 0,14 (5 j, 3 s.) |
| 2022-01-03 | 2022-10-12 | -25,4 % | 0,33 (18 j, 13 s.) | 0,33 (18 j, 13 s.) | 0,26 (17 j, 12 s.) | 0,26 (17 j, 12 s.) |

### S&P 500 — sorties

| creux | pic suivant | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 1998-08-31 | 2000-03-24 | 0,19 | 0,27 | 0,06 | 0,36 |
| 2002-10-09 | 2007-10-09 | 0,15 | 0,19 | 0,15 | 0,12 |
| 2009-03-09 | 2018-09-20 | 0,12 | 0,09 | 0,12 | 0,12 |
| 2018-12-24 | 2020-02-19 | 0,38 | 0,52 | 0,38 | 0,38 |
| 2020-03-23 | 2022-01-03 | 0,31 | 0,35 | 0,31 | 0,37 |

### Nasdaq-100 — entrées

| pic | creux | baisse | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|---|
| 2000-03-27 | 2002-10-07 | -82,9 % | 0,37 (44 j, 31 s.) | 0,43 (57 j, 40 s.) | 0,17 (8 j, 6 s.) | 0,12 (3 j, 3 s.) |
| 2007-10-31 | 2008-11-20 | -53,7 % | 0,23 (65 j, 44 s.) | 0,23 (65 j, 44 s.) | 0,06 (7 j, 5 s.) | 0,06 (7 j, 5 s.) |
| 2018-08-29 | 2018-12-24 | -23,0 % | 0,40 (43 j, 30 s.) | 0,47 (75 j, 52 s.) | 0,15 (37 j, 26 s.) | 0,49 (56 j, 39 s.) |
| 2020-02-19 | 2020-03-20 | -28,0 % | 0,65 (19 j, 13 s.) | 0,90 (22 j, 16 s.) | 0,23 (5 j, 3 s.) | 0,23 (5 j, 3 s.) |
| 2021-11-19 | 2022-12-28 | -35,6 % | 0,29 (62 j, 41 s.) | 0,29 (62 j, 41 s.) | 0,09 (7 j, 4 s.) | 0,09 (7 j, 4 s.) |

### Nasdaq-100 — sorties

| creux | pic suivant | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 2002-10-07 | 2007-10-31 | 0,22 | 0,16 | 0,20 | 0,15 |
| 2008-11-20 | 2018-08-29 | 0,05 | 0,05 | 0,01 | 0,08 |
| 2018-12-24 | 2020-02-19 | 0,30 | 0,45 | 0,29 | 0,29 |
| 2020-03-20 | 2021-11-19 | 0,13 | 0,09 | 0,26 | 0,30 |

### or (LBMA PM) — entrées

| pic | creux | baisse | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|---|
| 1993-08-02 | 1993-09-14 | -15,3 % | 0,87 (37 j, 27 s.) | raté (1) | 0,87 (37 j, 27 s.) | 0,55 (15 j, 11 s.) |
| 1996-02-05 | 1999-07-20 | -39,1 % | 0,15 (99 j, 71 s.) | 0,17 (121 j, 87 s.) | 0,07 (9 j, 7 s.) | 0,44 (470 j, 336 s.) |
| 1999-10-05 | 2001-04-02 | -21,4 % | 0,71 (62 j, 44 s.) | 0,54 (169 j, 121 s.) | 0,14 (10 j, 8 s.) | 0,05 (8 j, 6 s.) |
| 2003-02-05 | 2003-04-07 | -16,3 % | 0,85 (56 j, 40 s.) | raté (1) | 0,14 (2 j, 2 s.) | 0,00 (0 j, 0 s.) |
| 2006-05-12 | 2006-10-06 | -22,7 % | 0,83 (122 j, 86 s.) | 0,87 (144 j, 102 s.) | 0,00 (0 j, 0 s.) | 0,20 (4 j, 2 s.) |
| 2008-03-14 | 2008-10-24 | -28,7 % | 0,41 (144 j, 102 s.) | 0,28 (133 j, 95 s.) | 0,00 (0 j, 0 s.) | 0,00 (0 j, 0 s.) |
| 2011-09-05 | 2015-12-17 | -44,6 % | 0,35 (100 j, 72 s.) | 0,43 (119 j, 85 s.) | 0,24 (18 j, 14 s.) | 0,00 (0 j, 0 s.) |
| 2016-07-06 | 2016-12-20 | -17,6 % | 0,46 (92 j, 66 s.) | 0,42 (110 j, 78 s.) | 0,18 (69 j, 49 s.) | 0,00 (0 j, 0 s.) |
| 2018-01-25 | 2018-08-17 | -13,0 % | 0,34 (110 j, 78 s.) | 0,17 (33 j, 23 s.) | 0,06 (4 j, 2 s.) | 0,12 (11 j, 7 s.) |
| 2020-03-06 | 2020-03-19 | -12,4 % | 0,94 (10 j, 6 s.) | 0,94 (10 j, 6 s.) | 0,00 (0 j, 0 s.) | 0,00 (0 j, 0 s.) |
| 2020-08-06 | 2022-11-03 | -21,2 % | 0,66 (113 j, 80 s.) | 0,48 (172 j, 116 s.) | 0,29 (28 j, 19 s.) | 0,22 (26 j, 17 s.) |

### or (LBMA PM) — sorties

| creux | pic suivant | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 1993-03-10 | 1993-08-02 | 0,18 | 0,16 | 0,00 | 0,04 |
| 1993-09-14 | 1996-02-05 | 0,14 | 0,00 | 0,06 | 0,00 |
| 1999-07-20 | 1999-10-05 | 0,39 | 0,39 | 0,00 | 0,00 |
| 2001-04-02 | 2003-02-05 | 0,09 | 0,08 | 0,00 | 0,02 |
| 2003-04-07 | 2006-05-12 | 0,04 | 0,00 | 0,00 | 0,01 |
| 2006-10-06 | 2008-03-14 | 0,11 | 0,18 | 0,00 | 0,00 |
| 2008-10-24 | 2011-09-05 | 0,13 | 0,15 | 0,02 | 0,20 |
| 2015-12-17 | 2016-07-06 | 0,26 | 0,13 | 0,08 | 0,00 |
| 2016-12-20 | 2018-01-25 | 0,58 | 0,61 | 0,00 | 0,00 |
| 2018-08-17 | 2020-03-06 | 0,15 | 0,16 | 0,00 | 0,00 |
| 2020-03-19 | 2020-08-06 | 0,09 | 0,09 | 0,37 | 0,35 |

## 6. Bande SMA et variantes de fenêtre de C1_V1 (informatif)

### 6.1 Bande SMA : les cinq fenêtres côte à côte

Aucun choix de fenêtre : la bande est rapportée, elle ne décide rien.

**témoin actions**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA126 | 0,26 | 0,57 | 0 / 5,5 | 4,09 | 0,79 | 0,19 | 11,28 | 0 / 4,5 | aucune domination |
| SMA168 | 0,34 | 0,58 | 0 / 5,5 | 2,99 | 0,81 | 0,21 | 8,82 | 0 / 4,5 | aucune domination |
| SMA200 | 0,36 | 0,64 | 0 / 5,5 | 2,55 | 0,81 | 0,18 | 7,79 | 0 / 4,5 | référence |
| SMA210 | 0,37 | 0,64 | 0 / 5,5 | 2,40 | 0,81 | 0,18 | 7,28 | 0 / 4,5 | aucune domination |
| SMA252 | 0,39 | 0,67 | 0 / 5,5 | 1,91 | 0,81 | 0,17 | 6,12 | 0 / 4,5 | aucune domination |

**or (LBMA PM)**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA126 | 0,47 | 0,96 | 0 / 11 | 2,77 | 0,72 | 0,14 | 11,26 | 0 / 11 | aucune domination |
| SMA168 | 0,60 | 0,94 | 0 / 11 | 2,36 | 0,73 | 0,13 | 10,86 | 0 / 11 | aucune domination |
| SMA200 | 0,66 | 0,94 | 0 / 11 | 2,09 | 0,73 | 0,14 | 9,85 | 0 / 11 | référence |
| SMA210 | 0,66 | 1,00 | 1 / 11 | 2,16 | 0,72 | 0,13 | 9,98 | 0 / 11 | dominé par SMA200 |
| SMA252 | 0,64 | 1,00 | 1 / 11 | 1,72 | 0,72 | 0,14 | 8,03 | 0 / 11 | domine SMA200 |

**S&P 500**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA126 | 0,23 | 0,50 | 0 / 6 | 4,00 | 0,80 | 0,23 | 11,26 | 0 / 5 | aucune domination |
| SMA168 | 0,34 | 0,51 | 0 / 6 | 3,42 | 0,81 | 0,25 | 9,70 | 0 / 5 | dominé par SMA200 |
| SMA200 | 0,34 | 0,63 | 0 / 6 | 2,56 | 0,82 | 0,19 | 7,63 | 0 / 5 | référence |
| SMA210 | 0,34 | 0,63 | 0 / 6 | 2,52 | 0,82 | 0,19 | 7,30 | 0 / 5 | domine SMA200 |
| SMA252 | 0,35 | 0,70 | 0 / 6 | 1,94 | 0,82 | 0,18 | 6,31 | 0 / 5 | aucune domination |

**Nasdaq-100**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA126 | 0,30 | 0,65 | 0 / 5 | 4,18 | 0,79 | 0,16 | 11,29 | 0 / 4 | aucune domination |
| SMA168 | 0,35 | 0,65 | 0 / 5 | 2,55 | 0,80 | 0,16 | 7,95 | 0 / 4 | domine SMA200 |
| SMA200 | 0,37 | 0,65 | 0 / 5 | 2,55 | 0,80 | 0,18 | 7,95 | 0 / 4 | référence |
| SMA210 | 0,40 | 0,65 | 0 / 5 | 2,29 | 0,80 | 0,16 | 7,25 | 0 / 4 | aucune domination |
| SMA252 | 0,43 | 0,65 | 0 / 5 | 1,89 | 0,80 | 0,15 | 5,93 | 0 / 4 | aucune domination |

### 6.2 C1_V1 avec des fenêtres σ de 21 et 126 séances

Moyenne et σ changent ensemble pour V ; σ seul pour Y, T et G (précision du 24/10).

**témoin actions**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| C1_V1_S21 | 0,14 | 0,22 | 0 / 5,5 | 8,34 | 0,62 | 0,13 | 30,41 | 0 / 4,5 | aucune domination |
| C1_V1 | 0,13 | 0,25 | 0 / 5,5 | 6,19 | 0,65 | 0,19 | 23,89 | 0 / 4,5 | aucune domination |
| C1_V1_S126 | 0,15 | 0,25 | 0 / 5,5 | 5,21 | 0,63 | 0,19 | 21,49 | 0 / 4,5 | aucune domination |

**or (LBMA PM)**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| C1_V1_S21 | 0,14 | 1,00 | 1 / 11 | 5,50 | 0,47 | 0,00 | 28,94 | 0 / 11 | aucune domination |
| C1_V1 | 0,14 | 0,87 | 0 / 11 | 4,08 | 0,48 | 0,00 | 23,98 | 0 / 11 | aucune domination |
| C1_V1_S126 | 0,07 | 1,00 | 2 / 11 | 3,74 | 0,49 | 0,00 | 21,65 | 0 / 11 | aucune domination |

**S&P 500**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| C1_V1_S21 | 0,11 | 0,20 | 0 / 6 | 8,25 | 0,62 | 0,15 | 30,32 | 0 / 5 | aucune domination |
| C1_V1 | 0,12 | 0,26 | 0 / 6 | 6,27 | 0,65 | 0,15 | 24,05 | 0 / 5 | aucune domination |
| C1_V1_S126 | 0,12 | 0,26 | 0 / 6 | 5,28 | 0,63 | 0,15 | 21,50 | 0 / 5 | aucune domination |

**Nasdaq-100**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| C1_V1_S21 | 0,17 | 0,23 | 0 / 5 | 8,44 | 0,63 | 0,10 | 30,50 | 0 / 4 | aucune domination |
| C1_V1 | 0,15 | 0,23 | 0 / 5 | 6,11 | 0,64 | 0,23 | 23,73 | 0 / 4 | aucune domination |
| C1_V1_S126 | 0,17 | 0,23 | 0 / 5 | 5,14 | 0,62 | 0,23 | 21,49 | 0 / 4 | aucune domination |

## 7. Épisodes neutres de C1_V1 et C1_V2 contre le hasard

Un épisode neutre est juste si |ln(P fin / P veille)| ≤ σ_jour × √n (C). Hasard : 1000 épisodes par paire détecteur × actif, de mêmes durées, à des dates tirées au hasard dans la période mesurée (graine 0).

| détecteur | actif | jours neutres | épisodes neutres | taux juste (détecteur) | taux juste (hasard) |
|---|---|---|---|---|---|
| C1_V1 | S&P 500 | 1081 | 133 | 66,2 % | 76,8 % |
| C1_V1 | Nasdaq-100 | 1055 | 126 | 67,5 % | 76,1 % |
| C1_V1 | or (LBMA PM) | 1193 | 148 | 62,8 % | 72,4 % |
| C1_V1 | BTC (DS1) | 342 | 44 | 81,8 % | 76,5 % |
| C1_V2 | S&P 500 | 491 | 83 | 72,3 % | 75,9 % |
| C1_V2 | Nasdaq-100 | 484 | 77 | 72,7 % | 74,6 % |
| C1_V2 | or (LBMA PM) | 576 | 91 | 74,7 % | 73,8 % |
| C1_V2 | BTC (DS1) | 183 | 26 | 80,8 % | 75,7 % |

## 8. Étape B — BTC

Sur tout l'historique jugé du BTC. Ce résultat peut éliminer un candidat, jamais le valider seul.

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,64 | 0,77 | 0 / 4 | 1,83 | 0,74 | 0,04 | 6,74 | 0 / 5 | référence |
| MOM126 | 0,59 | 0,69 | 0 / 4 | 3,25 | 0,71 | 0,04 | 10,74 | 0 / 5 | aucune domination |
| C1_V1 | 0,36 | 0,50 | 0 / 4 | 6,24 | 0,53 | 0,00 | 24,23 | 0 / 5 | aucune domination |
| C1_V2 | 0,59 | 0,77 | 0 / 4 | 3,25 | 0,51 | 0,00 | 11,66 | 0 / 5 | aucune domination |

Période mesurée : 2013-10-02 → 2025-10-06 (12,0 ans).

### Entrées

| pic | creux | baisse | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|---|
| 2013-12-04 | 2015-01-14 | -84,9 % | 0,68 (113 j, 113 s.) | 0,57 (110 j, 110 s.) | 0,37 (51 j, 51 s.) | 0,77 (315 j, 315 s.) |
| 2017-12-16 | 2018-12-15 | -83,4 % | 0,77 (51 j, 51 s.) | 0,69 (100 j, 100 s.) | 0,50 (32 j, 32 s.) | 0,77 (51 j, 51 s.) |
| 2019-06-26 | 2020-03-12 | -62,5 % | 0,60 (92 j, 92 s.) | 0,60 (95 j, 95 s.) | 0,35 (35 j, 35 s.) | 0,40 (243 j, 243 s.) |
| 2021-11-08 | 2022-11-21 | -76,7 % | 0,40 (35 j, 35 s.) | 0,41 (39 j, 39 s.) | 0,27 (18 j, 18 s.) | 0,27 (18 j, 18 s.) |

### Sorties

| creux | pic suivant | SMA200 | MOM126 | C1_V1 | C1_V2 |
|---|---|---|---|---|---|
| 2013-10-02 | 2013-12-04 | 0,01 | 0,02 | 0,00 | 0,00 |
| 2015-01-14 | 2017-12-16 | 0,00 | 0,00 | 0,00 | 0,00 |
| 2018-12-15 | 2019-06-26 | 0,18 | 0,09 | 0,00 | 0,00 |
| 2020-03-12 | 2021-11-08 | 0,06 | 0,04 | 0,07 | 0,08 |
| 2022-11-21 | 2025-10-06 | 0,04 | 0,05 | 0,00 | 0,00 |

## 9. Robustesse du juge (15 %, 25 %, σ unique)

Les mêmes détecteurs mesurés avec un autre juge : rapportés, pas comptés (F). Le résultat est **solide** si le gagnant ET la liste des retenus sont les mêmes sous les trois variantes (précision du 24/10).

| variante du juge | témoin (médiane f_entrée / FA par an) | or (idem) | BTC (idem) | verdict |
|---|---|---|---|---|
| baisse de référence 15 % | SMA200 0,42 / 2,26 ; MOM126 0,40 / 1,94 ; C1_V1 0,23 / 6,07 ; C1_V2 0,25 / 3,13 | SMA200 0,55 / 2,66 ; MOM126 0,54 / 2,83 ; C1_V1 0,14 / 4,62 ; C1_V2 0,06 / 2,63 | SMA200 0,64 / 1,57 ; MOM126 0,59 / 2,75 ; C1_V1 0,36 / 5,65 ; C1_V2 0,41 / 2,98 | candidat retenu : C1_V1 ; retenus : C1_V1 |
| baisse de référence 25 % | SMA200 0,35 / 2,47 ; MOM126 0,38 / 2,34 ; C1_V1 0,12 / 6,16 ; C1_V2 0,13 / 3,09 | SMA200 0,66 / 2,29 ; MOM126 0,48 / 2,73 ; C1_V1 0,14 / 4,52 ; C1_V2 0,20 / 2,60 | SMA200 0,68 / 2,25 ; MOM126 0,57 / 3,50 ; C1_V1 0,37 / 6,83 ; C1_V2 0,77 / 3,33 | candidat retenu : C1_V1 ; retenus : C1_V1 |
| σ unique | SMA200 0,27 / 2,67 ; MOM126 0,25 / 2,49 ; C1_V1 0,17 / 6,29 ; C1_V2 0,12 / 3,29 | SMA200 0,46 / 2,77 ; MOM126 0,43 / 3,07 ; C1_V1 0,07 / 4,89 ; C1_V2 0,00 / 2,77 | SMA200 0,68 / 1,67 ; MOM126 0,60 / 2,91 ; C1_V1 0,37 / 5,99 ; C1_V2 0,42 / 3,16 | candidat retenu : C1_V2 ; retenus : C1_V1, C1_V2 |

**Résultat solide : non**.

## 10. Tableau informatif 2024 → fin — **déjà vu, ne décide rien**


**témoin actions**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,44 | 0,44 | 0 / 1 | 0,00 | — | — | 15,22 | 0 / 0 | référence |
| MOM126 | 0,49 | 0,49 | 0 / 1 | 0,00 | — | — | 22,83 | 0 / 0 | dominé par SMA200 |
| C1_V1 | 0,28 | 0,28 | 0 / 1 | 0,00 | — | — | 68,48 | 0 / 0 | domine SMA200 |
| C1_V2 | 0,50 | 0,50 | 0 / 1 | 0,00 | — | — | 38,05 | 0 / 0 | dominé par SMA200 |

**or (LBMA PM)**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | non mesurable | — | — | — | — | — | — | — | référence |
| MOM126 | non mesurable | — | — | — | — | — | — | — | — |
| C1_V1 | non mesurable | — | — | — | — | — | — | — | — |
| C1_V2 | non mesurable | — | — | — | — | — | — | — | — |

Non mesurable : moins de deux pivots du juge entre 2024-01-01 et 2026-10-22.

**S&P 500**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,46 | 0,46 | 0 / 1 | 0,00 | — | — | 22,83 | 0 / 0 | référence |
| MOM126 | 0,46 | 0,46 | 0 / 1 | 0,00 | — | — | 22,83 | 0 / 0 | domine SMA200 |
| C1_V1 | 0,24 | 0,24 | 0 / 1 | 0,00 | — | — | 68,48 | 0 / 0 | domine SMA200 |
| C1_V2 | 0,46 | 0,46 | 0 / 1 | 0,00 | — | — | 38,05 | 0 / 0 | aucune domination |

**Nasdaq-100**

| détecteur | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls | face à SMA200 |
|---|---|---|---|---|---|---|---|---|---|
| SMA200 | 0,42 | 0,42 | 0 / 1 | 0,00 | — | — | 7,61 | 0 / 0 | référence |
| MOM126 | 0,53 | 0,53 | 0 / 1 | 0,00 | — | — | 22,83 | 0 / 0 | dominé par SMA200 |
| C1_V1 | 0,32 | 0,32 | 0 / 1 | 0,00 | — | — | 68,48 | 0 / 0 | domine SMA200 |
| C1_V2 | 0,54 | 0,54 | 0 / 1 | 0,00 | — | — | 38,05 | 0 / 0 | dominé par SMA200 |

## 11. Verdict mécanique

| candidat | dominé par SMA200 (témoin) | épisodes où f_entrée < SMA200 (témoin) | dominé par SMA200 (or) | épisodes où f_entrée < SMA200 (or) | étape A | étape B (BTC) |
|---|---|---|---|---|---|---|
| MOM126 | non | 2 / 11 | non | 5 / 11 | non retenu | — |
| C1_V1 | non | 10 / 11 | non | 10 / 11 | retenu | passe |
| C1_V2 | non | 8 / 11 | non | 10 / 11 | retenu | passe |

Classement D (moyennes témoin / or) :

| candidat | médiane f_entrée moyenne | fausses alertes / an moyennes | pire cas moyen |
|---|---|---|---|
| C1_V1 | 0,14 | 5,14 | 0,56 |
| C1_V2 | 0,10 | 2,90 | 0,52 |

**Verdict : candidat retenu : C1_V2 ; retenus : C1_V1, C1_V2.**

**Résultat solide (variantes du juge) : non**.

## 12. Écarts au prompt et leurs raisons

- **BTC** : base DS1, table `bougies_1d`, source Bitstamp (clôture du jour civil UTC). DS1 n'avait aucune bougie : elle a été installée le 24/10 (décision 1 de Jonas).
- **VIX** : `VIXCLS` (FRED), comme demandé. Sa clôture de 16:15 ET est prise le jour même : c'est la lecture « publiée au plus tard en t » à la date près.
- **USD/JPY** : ALFRED est indisponible. On applique le vrai calendrier de parution du H.10 (clarification E) au lieu du décalage de 2 jours ouvrés du prompt, sur toute la période. Ce calendrier hebdomadaire n'a pas pu être vérifié avant 2026.
- **Compteur** : le prompt dit 117 au gel ; le compteur global valait 131 au lancement et l'invest 38. Les deux sont rapportés, sans remplacement (Jonas 24/10).
- **Essais** : 16 au verdict (SMA200 et BTC compris) et 18 informatifs, au lieu du « 1 par couple détecteur × actif jugé du verdict principal » du prompt (Jonas 24/10).
- **Période mesurée** : avec B, toutes les mesures (latences, fausses alertes, bascules, justesse, épisodes neutres) portent sur [premier pivot du juge dans la période, dernier pivot dans la période[. Les années des taux « par an » sont celles de cette période mesurée. La découverte (§ 3) parlait encore des jours civils de toute la période : c'est la conséquence de B et de l'exclusion du dernier cycle.
- **Fausses alertes** : un épisode bear du détecteur compte s'il commence dans la période mesurée. Il est faux s'il ne recoupe aucun bear du juge, à cheval ou en cours compris.
- **f_sortie** : un raté de sortie compte 1, comme A (précision du 24/10).
- **Variante σ unique** : le test des épisodes neutres y utilise le même σ unique, puisque σ_jour est défini par σ_actif. Cela ne touche pas le verdict.
- **Tableau 2024 → fin** : les 4 détecteurs du verdict seulement, sans la bande ni les variantes, pour ne pas multiplier les mesures non comptées.
