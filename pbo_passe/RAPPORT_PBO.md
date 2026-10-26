# PBO du passé (PBOR) — rapport du programme — 2026-10-26

## Empreintes
- Code : `ec2a19c` · règles : `43fbb227790b18bd` · préenregistrement (`pbo_passe/PREENREGISTREMENT.md`) : `7978a2c23d18e0f9`
- Calcul du 2026-10-26T22:26:26+00:00 au 2026-10-26T22:26:27+00:00

Diagnostic, rapport seul : aucun verdict déjà rendu n'est modifié. Méthode de la porte S10 (`beta/stats/pbo.py`) : CSCV, 16 blocs contigus, Sharpe, seuil PBO < 20,0 %.

## L1 — lot R10 du 08/09/2026

| Candidate | Run | Verdict rendu (inchangé) | Trades | Meilleure selon S7 |
|---|---|---|---|---|
| r10_conjonction | `c8a374a40a87` | infirmee | 326 | r10_disjonction |
| r10_disjonction | `274eb02a15ee` | infirmee | 1507 | r10_disjonction |

Rendement quotidien : somme des R des trades clôturés ce jour-là.
- Période : 2019-10-01 → 2025-01-01, 1920 jours (5 plus ancien(s) retiré(s) pour 16 blocs égaux, 120 jours par bloc)
- Configurations : 2 → 2 après retrait des doublons exacts
- PBO : **73,7 %** (12870 combinaisons)
- Rang OOS relatif w de n* : 5 % 33,3 % · 25 % 33,3 % · médiane 33,3 % · 75 % 66,7 % · 95 % 66,7 %
- Choisie comme n* (meilleure en apprentissage) : r10_conjonction 63,1 % · r10_disjonction 36,9 %
- Matrice des rendements : `7a9d547177382ef5`
- **PBO ≥ 20 % : la porte S10 aurait échoué**

## L2 — lot R8 du 19/09/2026

| Candidate | Run | Verdict rendu (inchangé) | Trades | Meilleure selon S7 |
|---|---|---|---|---|
| liquidity_ny_stop_050 | `36ed58e66266` | infirmee | 10744 | liquidity_ny_stop_150 |
| liquidity_ny_stop_100 | `96d03113b579` | infirmee | 10744 | liquidity_ny_stop_150 |
| liquidity_ny_stop_150 | `52423a324274` | infirmee | 10744 | liquidity_ny_stop_150 |

Rendement quotidien : somme des R des trades clôturés ce jour-là.
- Période : 2019-09-14 → 2024-12-31, 1936 jours (5 plus ancien(s) retiré(s) pour 16 blocs égaux, 121 jours par bloc)
- Configurations : 3 → 3 après retrait des doublons exacts
- PBO : **7,4 %** (12870 combinaisons)
- Rang OOS relatif w de n* : 5 % 50,0 % · 25 % 75,0 % · médiane 75,0 % · 75 % 75,0 % · 95 % 75,0 %
- Choisie comme n* (meilleure en apprentissage) : liquidity_ny_stop_150 96,3 % · liquidity_ny_stop_100 3,7 %
- Matrice des rendements : `0af5ac27bc3d8387`
- **PBO < 20 % : la porte S10 aurait été franchie**

## L3 — lot de 8 candidates du 19/09/2026

| Candidate | Run | Verdict rendu (inchangé) | Trades | Meilleure selon S7 |
|---|---|---|---|---|
| auto_r7_01 | `2ce411b82067` | infirmee | 2961 | auto_r7_03 |
| auto_r7_03 | `f57f95588500` | infirmee | 102 | auto_r7_03 |
| mean_reversion_z | `7eb7f9c2cb17` | infirmee | 2265 | auto_r7_03 |
| r10_conjonction | `f76121140b7c` | infirmee | 326 | auto_r7_03 |
| r10_disjonction | `21acf3928232` | infirmee | 1507 | auto_r7_03 |
| r11_credit_contrarian | `b3b0374c238e` | infirmee | 386 | auto_r7_03 |
| r4_fear_greed_contrarian | `f2217235b2ed` | infirmee | 801 | auto_r7_03 |
| r9_funding_contrarian | `58a1b966537e` | infirmee | 1118 | auto_r7_03 |

Rendement quotidien : somme des R des trades clôturés ce jour-là.
- Période : 2019-10-01 → 2025-01-01, 1920 jours (12 plus ancien(s) retiré(s) pour 16 blocs égaux)
- Configurations : 8 → 8 après retrait des doublons exacts
- PBO : **incalculable** — PBO incalculable : ecart-type nul ou non fini sur une moitie : Sharpe indefini
- Matrice des rendements : `55a8190d2260fc0b`
- **PBO incalculable : la porte S10 n'aurait pas été exécutée**

## Voie C — les 6 variantes du 22/09

`voie_c_voltarget.py` (`preparer` coupé au 2026-09-05, puis `variantes_selection`) : r_net quotidien, 5 bps, funding. Les 6 variantes existent toutes à partir du 2021-05-13.
- Période : 2021-05-19 → 2026-09-05, 1936 jours (6 plus ancien(s) retiré(s) pour 16 blocs égaux, 121 jours par bloc)
- Configurations : 6 → 6 après retrait des doublons exacts
- PBO : **0,0 %** (12870 combinaisons)
- Rang OOS relatif w de n* : 5 % 71,4 % · 25 % 71,4 % · médiane 71,4 % · 75 % 85,7 % · 95 % 85,7 %
- Choisie comme n* (meilleure en apprentissage) : vt 25% / 30j / quotidien 71,0 % · vt 25% / 60j / quotidien 29,0 %
- Matrice des rendements : `6b5fd6be405538e1`
- Variante retenue par la règle du 22/09 (meilleur Sharpe net du train, jusqu'au 2024-06-30) : vt 25% / 30j / quotidien
- **PBO < 20 % : la porte S10 aurait été franchie**

## Compteurs
- Avant : global 147, trading 93, invest 54 · après : global 147, trading 93, invest 54 (diagnostic)
