# Contrôle HAR (VC6 V1, phase 2)

Calculé le 2026-11-01T19:09:55+00:00 UTC. Rapport écrit par `scripts/controle_har.py`, sans interprétation au-delà de la règle 5. Préenregistrement : `PREENREGISTREMENT.md` (même dossier). Test de mesure : aucun essai ajouté au compteur.

## 1. Tableau par actif

QLIKE moyenne contre la moyenne des RV 5 min des 5 jours suivants (plus bas = meilleur), sur les jours où le HAR a ses 730 jours de RV. Les deux prévisions sont évaluées sur les mêmes jours. Le p de Diebold-Mariano est donné pour information.

| actif | QLIKE HAR | QLIKE écart-type 30 jours | p de Diebold-Mariano | jours évalués | jours exclus | prévisions ≤ 0 remplacées |
|---|---|---|---|---|---|---|
| BTC | 0,2372 | 0,4040 | 0,030 | 1876 | 1 (0 dans la période évaluée) | 0 |
| ETH | 0,2799 | 0,4923 | 0,174 | 1796 | 1 (0 dans la période évaluée) | 0 |
| SOL | 0,3694 | 0,5955 | 0,105 | 1504 | 1 (0 dans la période évaluée) | 0 |

## 2. σ̂ retenu par actif (règle 5)

Règle 5 : si le HAR a une QLIKE moyenne plus haute que l'écart-type 30 jours pour un actif, σ̂ de cet actif = écart-type 30 jours ; sinon σ̂ = HAR. La spec annualise σ̂ en √365.

- **BTC : σ̂ = HAR** (QLIKE moyenne du HAR 0,2372 ≤ 0,4040 pour l'écart-type 30 jours). Repli : écart-type 30 jours avant 730 jours de RV (jusqu'à la veille du 07/09/2021) et les jours de prévision ≤ 0.
- **ETH : σ̂ = HAR** (QLIKE moyenne du HAR 0,2799 ≤ 0,4923 pour l'écart-type 30 jours). Repli : écart-type 30 jours avant 730 jours de RV (jusqu'à la veille du 26/11/2021) et les jours de prévision ≤ 0.
- **SOL : σ̂ = HAR** (QLIKE moyenne du HAR 0,3694 ≤ 0,5955 pour l'écart-type 30 jours). Repli : écart-type 30 jours avant 730 jours de RV (jusqu'à la veille du 14/09/2022) et les jours de prévision ≤ 0.

## 3. Périodes et comptes

Les jours exclus ont plus de 10 % des 288 barres 5 min manquantes : ils n'ont pas de RV. Les barres à volume nul sont des barres présentes, comptées ici sans rien changer. La période évaluée va de la première origine évaluée à la dernière cible.

| actif | barres 5 min (UTC) | jours avec RV | HAR estimé dès le | origines évaluées | dernière cible | jours exclus | barres à volume nul (total ; période évaluée) | prévisions ≤ 0 (jours évalués ; tous les jours du HAR) |
|---|---|---|---|---|---|---|---|---|
| BTC | 2019-09-08 17:55 → 2026-10-31 23:55 (751753) | 2610 | 07/09/2021 | 07/09/2021 → 26/10/2026 | 31/10/2026 | 08/09/2019 (73 barres) | 86 ; 20 | 0 ; 0 |
| ETH | 2019-11-27 07:45 → 2026-10-31 23:55 (728835) | 2530 | 26/11/2021 | 26/11/2021 → 26/10/2026 | 31/10/2026 | 27/11/2019 (195 barres) | 72 ; 20 | 0 ; 0 |
| SOL | 2020-09-14 07:00 → 2026-10-31 23:55 (644748) | 2238 | 14/09/2022 | 14/09/2022 → 26/10/2026 | 31/10/2026 | 14/09/2020 (204 barres) | 47 ; 24 | 0 ; 0 |

## 4. Diebold-Mariano (information, ne décide rien)

d = QLIKE HAR − QLIKE écart-type 30 jours, jour par jour ; variance de Newey-West (noyau de Bartlett) ; p bilatérale. Statistique < 0 : le HAR a la perte moyenne la plus basse.

| actif | jours | retard | statistique | p |
|---|---|---|---|---|
| BTC | 1876 | 7 | −2,17 | 0,030 |
| ETH | 1796 | 7 | −1,36 | 0,174 |
| SOL | 1504 | 7 | −1,62 | 0,105 |

## 5. Niveaux moyens sur les jours évalués (information)

Moyenne des variances journalières, lue en volatilité annualisée √(moyenne × 365).

| actif | cible (RV 5 min, 5 jours suivants) | prévision HAR | prévision écart-type 30 jours |
|---|---|---|---|
| BTC | 53,2 % | 59,4 % | 51,9 % |
| ETH | 68,7 % | 77,3 % | 68,7 % |
| SOL | 99,8 % | 114,4 % | 93,8 % |

## 6. Dernière estimation du HAR (information)

MCO avec constante sur les lignes entièrement dans la fenêtre des 730 derniers jours de RV.

| actif | jour | lignes | constante | RV du jour | moyenne 5 jours | moyenne 22 jours |
|---|---|---|---|---|---|---|
| BTC | 31/10/2026 | 704 | 2,925e-04 | 0,115 | 0,301 | 0,065 |
| ETH | 31/10/2026 | 704 | 7,157e-04 | 0,153 | 0,209 | 0,055 |
| SOL | 31/10/2026 | 704 | 1,359e-03 | 0,043 | 0,131 | 0,079 |

## 7. Empreintes et données

- **Code** : `aefc6d5`. **Règles** : `04fc671b86f15a5c` ; préenregistrement `PREENREGISTREMENT.md` `d2eee18886abb7b9` ; registre : `EXPERIMENTS.jsonl`, test de mesure (diagnostic).
- **Compteur** (aucun essai) : global 147 → 147, invest 54 → 54, trading actif 93 → 93.
- **Empreinte des valeurs lues** : `7005202023796717` ; date de fin figée : 31/10/2026.
- **Clôture du jour** : celle de la barre 5 min de 23:55 (amendement du 01/11/2026, décision de Jonas). Les copies 1d ne servent qu'au contrôle ; jours où leur clôture diffère : BTC : 24/09/2019 ; ETH : 11/12/2019 ; SOL : aucun.

| actif | bougies 5 min | SHA-256 vérifié | clôtures 1d | SHA-256 vérifié | clôtures |
|---|---|---|---|---|---|
| BTC | `data/vc6_v1/sources_figees/BTC_perp_5m.parquet` | `42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618` | `data/vc6_v1/sources_figees/BTC_perp_1d.parquet` | `1bd26426c4cf103bb4b19766aa0a67cefbfe18d9532fe0997592935cab25cb93` | 2019-09-08 → 2026-10-31 (2611) |
| ETH | `data/vc6_v1/sources_figees/ETH_perp_5m.parquet` | `5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f` | `data/vc6_v1/sources_figees/ETH_perp_1d.parquet` | `19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f` | 2019-11-27 → 2026-10-31 (2531) |
| SOL | `data/vc6_v1/sources_figees/SOL_perp_5m.parquet` | `0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d` | `data/vc6_v1/sources_figees/SOL_perp_1d.parquet` | `58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42` | 2020-09-14 → 2026-10-31 (2239) |

## 8. Épreuve de causalité

Prévisions du HAR (brute et après replis) et de l'écart-type 30 jours recalculées avec les seules données connues à chaque coupure (31/12/2021, 31/12/2022, 31/12/2023, 31/12/2024, 31/12/2025), comparées à celles calculées sur tout l'historique.
- BTC : aucun écart.
- ETH : aucun écart.
- SOL : aucun écart.

## 9. Ce que le programme a appliqué sans que le prompt le dise mot pour mot

Détail et raisons : applications 1 à 15 de `PREENREGISTREMENT.md`.
- **Données** : perpétuels Binance USDT-M, seules bougies 5 min de BETA et DS1 ; rendements journaliers tirés de la barre 5 min de 23:55 (amendement du 01/11, décision de Jonas). Pour le BTC, la série du mode global (Bitstamp ou perpétuel) reste à trancher en phase 3.
- **HAR** : constante comprise (Corsi 2009) ; fenêtre = RV des 730 derniers jours, lignes entièrement dedans (704 au plus).
- **Écart-type 30 jours** : écart-type d'échantillon (ddof = 1), au carré.
- **PBO (invariant 13)** : non calculée. Le prompt règle le choix par sa règle 5 et en fait un test de mesure ; c'est à Jonas de dire s'il en veut une.
