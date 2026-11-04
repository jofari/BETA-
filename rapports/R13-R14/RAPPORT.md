# Fade open NY sur l'or (5m) · Fade open NY sur le Nasdaq-100 (1h) — rapport du programme

- Écrit par le programme (`scripts/rapport_experience.py R13 R14 --eprouver`, module `beta/rapport/experience.py`, commit `b962b07`), le 04/11/2026 13:32 UTC.
- Sources : `EXPERIMENTS.jsonl` (préenregistrement, mesures, clôture), `RUNS.jsonl`, `data/runs/<run>/` (`verdict.json`, `batterie.json`, `trades.parquet`, `epreuve.json`).
- Aucun chiffre tapé à la main. Arrondis faits par le programme : R à 4 décimales ici (2 dans le résumé Discord), pourcentages à 2 décimales, taux à 1 décimale ; valeurs exactes dans les fichiers cités.
- État du calcul : 🟢 verdict au registre et 42 contrôles sur 42 passés. La pastille dit l'état du calcul, pas un jugement du résultat.

## Fade open NY sur l'or (5m) (registre : R13)

### Verdict du programme

**INFIRMÉE** — ligne de clôture du registre, datée du 04/11/2026 ; conforme à l'issue attendue : oui.

Issues des variantes (moteur) : stop 0,5x amplitude : INFIRMÉE ; stop 1,0x amplitude : INFIRMÉE ; stop 1,5x amplitude : INFIRMÉE.

Texte de la clôture, tel qu'au registre :

> r13_ny_or_stop_050 : infirmee, n=395, R moyen=-0.5652905604868422, MDE=0.23691191987101856, portes echouees=8, non executees=0 ; r13_ny_or_stop_100 : infirmee, n=395, R moyen=-0.26522414202324207, MDE=0.1527642687174138, portes echouees=8, non executees=0 ; r13_ny_or_stop_150 : infirmee, n=395, R moyen=-0.1942666314962306, MDE=0.10899201054796834, portes echouees=8, non executees=0

### Préenregistrement (tel qu'écrit avant la mesure)

- Écrit le 04/11/2026 ; empreinte de la ligne `17e9e4a2ec4fc4e8` ; N au préenregistrement : 94 ; famille du compteur : trading ; split autorisé : train.
- Famille déclarée : 3 ; issue attendue : INFIRMÉE ; MDE attendu : non déclaré.
- Décidé par : « Jonas, 2026-11-04 : memes parametres que R8, or 5m + Nasdaq 1h, les 3 stops »
- Dérivé de : « R8 »

**Hypothèse**

> R8 a l'identique sur l'OR COMPTANT (XAU/USD, Dukascopy BID, 5m) : les 45 premieres minutes de la seance americaine (09:30-10:15 New York, changements d'heure compris) sont une prise de liquidite ; entrer a la cloture de 10:15 dans le sens OPPOSE au corps de la fenetre, stop a 0,5x / 1x / 1,5x son amplitude, cible 3 R, horizon 72 bougies 5m, a un R moyen strictement positif, couts deduits.

**Métrique primaire**

> R moyen par trade (triple barriere du moteur, take_profit_r=3.0, horizon 72 bougies 5m, couts aller-retour deduits), par variante, lot des 3 variantes

**Règle de décision**

- `confirmee` : « au moins une des 3 variantes CONFIRMEE par le moteur : R moyen > 0, p survivant a Benjamini-Hochberg sur la famille de 3, et les dix portes S1-S10 franchies (S8 : buy-and-hold du meme actif sur la meme periode ; S10 : PBO du lot < 20 %) »
- `infirmee` : « aucune variante confirmee ni indecidable : R moyen <= 0, ou une porte echoue »
- `indecidable` : « aucune variante confirmee, et au moins une indecidable (moins de 30 signaux apres elimination des chevauchements, ou porte non executable) »
- `verdict_par_le_programme` : « scripts/mesurer_r13_r14.py applique cette regle aux issues rendues par pipeline.cribler et clot l'experience lui-meme »
- `suite_si_confirmee` : « AUCUN passage au reel : preenregistrement d'un paper sur le perpetuel TradFi (XAUUSDT / QQQUSDT), decision de Jonas. Le hold-out 2025+ reste scelle pour ces actifs. »

**Règles déclarées** (`regles`)

- `actif` : XAU_SPOT (data/marches, beta.marches.intraday)
- `timeframe` : 5m
- `periode` : 2023-06-21 (1re bougie 5m) -> 2024-12-31, FIGEE : le rattrapage de l'or vers 2003 n'elargit PAS cette mesure (un elargissement = un nouvel id)
- `candidates` : ["r13_ny_or_stop_050", "r13_ny_or_stop_100", "r13_ny_or_stop_150"]
- `take_profit_r` : 3.0
- `horizon_bougies` : 72

**Déjà connu au préenregistrement**

> R8 (21/08, remesuree le 19/09 aux couts corriges) : la MEME regle sur les 6 cryptos en 5m est INFIRMEE, 8 portes sur 9 echouees, R moyen -0,29 / -0,16 / -0,12 (stops 0,5x / 1x / 1,5x) sur 10 744 trades, negative 5 annees sur 6, MFE moyen +1,48 R contre une cible a 3 R, 66 % de sorties au stop. Ces chiffres sont connus de Jonas et de Claude au moment d'ecrire ceci ; c'est pour cela que les PARAMETRES sont ceux de R8 tels quels (aucun reglage choisi apres avoir vu les cryptos), et les 3 variantes gardees (Jonas : « les 3 »). Regarde AVANT ce preenregistrement, sur le train seulement et sans aucun rendement : la couverture des series (dates, nombre de bougies, heures des bougies 1h du NDX), et le nombre de signaux de la regle avec l'epreuve de causalite (signaux(df[:t]) == signaux(df)[:t], 25 coupures, OK). Les series intraday de l'or et du NDX n'ont servi a aucune mesure de BETA avant ceci (Temps 1 et Test invest n'ont lu que du QUOTIDIEN). Couts = ceux du moteur pour un perpetuel Binance (0,10 % aller-retour + 0,02 % de slippage + spread d'un tick) : c'est le prix de l'instrument qu'on traderait (XAUUSDT, QQQUSDT), pas celui de l'indice, qui ne se trade pas. Pas de funding (serie comptant / indice) : sous-estime un peu le cout d'une position tenue au plus 6 h. Issue attendue : infirmee (prior R8). Or : 395 signaux sur la periode (193 longs).

### Données et paramètres de la mesure

- Série lue (ligne de clôture) : 108 528 bougies, du 21/06/2023 au 31/12/2024 21:55 UTC, empreinte `2b385177304526f9`.
- Paires : XAU_SPOT ; timeframe 5m ; split train ; début demandé 2023-06-21 ; fin demandée aucune (bornée au train).
- Barrières : take_profit_r = 3,0000 ; horizon_bougies = 72 ; stop_atr (si la candidate ne donne pas de stop) = 2,0000.
- Coûts : frais_pct = 0,1000 ; slippage_pct = 0,0200 ; cout_aller_retour_pct = 0,1200 ; spread = oui (modèle tick) ; funding = oui.
- Paramètres de `r13_ny_or_stop_050` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 615, "bougies_attendues": 9, "fraction_stop": 0.5}
- Paramètres de `r13_ny_or_stop_100` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 615, "bougies_attendues": 9, "fraction_stop": 1.0}
- Paramètres de `r13_ny_or_stop_150` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 615, "bougies_attendues": 9, "fraction_stop": 1.5}

### Résultats par variante (moteur, `verdict.json`)

| Variante | Run | Issue | Signaux mesurés | Trades retenus | R moyen | R médian | σ(R) | MDE | Taux de gain | Profit factor | MFE moyen | MAE moyen | Durée médiane (h) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | `8bfb719165c8` | INFIRMÉE | 395 | 395 | −0,5653 | −1,3707 | 1,4968 | 0,2369 | 31,1 % | 0,4807 | +1,2848 | −0,9151 | 1,83 |
| stop 1,0x amplitude | `53aae4e0be16` | INFIRMÉE | 395 | 395 | −0,2652 | −0,3099 | 0,9651 | 0,1528 | 34,7 % | 0,5204 | +0,7994 | −0,6293 | 6,00 |
| stop 1,5x amplitude | `f621f8eb0240` | INFIRMÉE | 395 | 395 | −0,1943 | −0,1589 | 0,6886 | 0,1090 | 36,5 % | 0,5195 | +0,5524 | −0,4756 | 6,00 |

« Signaux mesurés » vient de la réserve écrite par le moteur à chaque run ; « Trades retenus » = après élimination des chevauchements (`metriques.n`).

### R brut, coûts, R net (recalculés par le programme depuis `trades.parquet`)

Moyennes par trade, en R. Informatif : la métrique primaire est le R net, et aucune règle de décision ne porte sur le R brut.

| Variante | Trades | R brut | Coûts (total) | dont frais | dont spread | dont funding | R net |
|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 395 | +0,0948 | 0,6601 | 0,6599 | 0,0003 | +0,0000 | −0,5653 |
| stop 1,0x amplitude | 395 | +0,0648 | 0,3301 | 0,3299 | 0,0001 | +0,0000 | −0,2652 |
| stop 1,5x amplitude | 395 | +0,0258 | 0,2200 | 0,2200 | 0,0001 | +0,0000 | −0,1943 |

### Sorties, par raison (`trades.parquet`)

| Variante | Sortie | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | stop (SL) | 219 | 55,4 % | −1,6781 | −367,50 | 0,0 % |
| stop 0,5x amplitude | cible (TP) | 58 | 14,7 % | +2,2242 | +129,00 | 98,3 % |
| stop 0,5x amplitude | horizon | 118 | 29,9 % | +0,1288 | +15,20 | 55,9 % |
| stop 1,0x amplitude | stop (SL) | 103 | 26,1 % | −1,3620 | −140,28 | 0,0 % |
| stop 1,0x amplitude | cible (TP) | 14 | 3,5 % | +2,5153 | +35,21 | 100,0 % |
| stop 1,0x amplitude | horizon | 278 | 70,4 % | +0,0011 | +0,30 | 44,2 % |
| stop 1,5x amplitude | stop (SL) | 58 | 14,7 % | −1,2720 | −73,77 | 0,0 % |
| stop 1,5x amplitude | cible (TP) | 2 | 0,5 % | +2,7758 | +5,55 | 100,0 % |
| stop 1,5x amplitude | horizon | 335 | 84,8 % | −0,0254 | −8,51 | 42,4 % |

### Par sens (`trades.parquet`)

| Variante | Sens | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | long | 193 | 48,9 % | −0,6071 | −117,18 | 31,1 % |
| stop 0,5x amplitude | court | 202 | 51,1 % | −0,5253 | −106,11 | 31,2 % |
| stop 1,0x amplitude | long | 193 | 48,9 % | −0,3319 | −64,06 | 34,2 % |
| stop 1,0x amplitude | court | 202 | 51,1 % | −0,2015 | −40,71 | 35,1 % |
| stop 1,5x amplitude | long | 193 | 48,9 % | −0,2328 | −44,93 | 35,8 % |
| stop 1,5x amplitude | court | 202 | 51,1 % | −0,1574 | −31,80 | 37,1 % |

### Par année de sortie (`trades.parquet`)

| Variante | Année | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 2023 | 136 | 34,4 % | −0,4907 | −66,73 | 30,1 % |
| stop 0,5x amplitude | 2024 | 259 | 65,6 % | −0,6045 | −156,56 | 31,7 % |
| stop 1,0x amplitude | 2023 | 136 | 34,4 % | −0,2121 | −28,85 | 33,1 % |
| stop 1,0x amplitude | 2024 | 259 | 65,6 % | −0,2931 | −75,91 | 35,5 % |
| stop 1,5x amplitude | 2023 | 136 | 34,4 % | −0,1657 | −22,53 | 34,6 % |
| stop 1,5x amplitude | 2024 | 259 | 65,6 % | −0,2093 | −54,20 | 37,5 % |

### Batterie, porte par porte (`verdict.json` et `batterie.json`)

| Porte | stop 0,5x amplitude | stop 1,0x amplitude | stop 1,5x amplitude |
|---|---|---|---|
| S1 · Benjamini-Hochberg | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S2 · Sharpe dégonflé | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S3 · bootstrap par blocs | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S4 · Monte-Carlo | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S5 · chemins synthétiques | ok | ok | ok |
| S6 · walk-forward purgé | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S7 · reality check | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S8 · buy-and-hold | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S9 · diversification | ok | ok | ok |
| S10 · PBO (CSCV) | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| Portes échouées | 8 sur 10 | 8 sur 10 | 8 sur 10 |

**stop 0,5x amplitude** (`r13_ny_or_stop_050`, run `8bfb719165c8`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,0333 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,3777 ; sharpe_seuil = 0,1271 ; n_essais = 98 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 1,0000 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −223,2898 ; centile = 100,0000 ; seuil = −366,4863 ; synthetique_median = −413,1018 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,5575 ; ancre.oos_moyen = −0,5390 ; ancre.efficacite = 0,9668 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r13_ny_or_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 35,5877 ; candidate.rendement_total_pct = −222,6862 ; ecart_rendement_pct = −258,2739 ; ecart_sharpe = −7,5265
- S9 · diversification : correlation_max = −0,0421 ; avec = r13_ny_or_stop_150 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,8239 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.378 contre 0.127 attendu du maximum de 98 essais
- R moyen in-sample -0.5575 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -258.3 pts, ecart de Sharpe -7.53
- PBO du lot 82.4% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur XAU_SPOT seulement (phase, 200 chemins)
- 395 signaux mesures, 395 retenus apres elimination des chevauchements

**stop 1,0x amplitude** (`r13_ny_or_stop_100`, run `53aae4e0be16`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,0667 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,2748 ; sharpe_seuil = 0,1271 ; n_essais = 98 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 1,0000 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −104,7635 ; centile = 100,0000 ; seuil = −171,6105 ; synthetique_median = −220,4983 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,2581 ; ancre.oos_moyen = −0,2622 ; ancre.efficacite = 1,0161 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r13_ny_or_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 35,5877 ; candidate.rendement_total_pct = −104,7518 ; ecart_rendement_pct = −140,3395 ; ecart_sharpe = −5,9444
- S9 · diversification : correlation_max = 0,2600 ; avec = r13_ny_or_stop_150 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,8239 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.275 contre 0.127 attendu du maximum de 98 essais
- R moyen in-sample -0.2581 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -140.3 pts, ecart de Sharpe -5.94
- PBO du lot 82.4% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur XAU_SPOT seulement (phase, 200 chemins)
- 395 signaux mesures, 395 retenus apres elimination des chevauchements

**stop 1,5x amplitude** (`r13_ny_or_stop_150`, run `f621f8eb0240`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,1000 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,2821 ; sharpe_seuil = 0,1271 ; n_essais = 98 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 0,0000 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −76,7353 ; centile = 100,0000 ; seuil = −110,7702 ; synthetique_median = −147,1510 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,1856 ; ancre.oos_moyen = −0,1983 ; ancre.efficacite = 1,0684 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r13_ny_or_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 35,5877 ; candidate.rendement_total_pct = −76,7734 ; ecart_rendement_pct = −112,3611 ; ecart_sharpe = −6,0356
- S9 · diversification : correlation_max = 0,2600 ; avec = r13_ny_or_stop_100 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,8239 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.282 contre 0.127 attendu du maximum de 98 essais
- R moyen in-sample -0.1856 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -112.4 pts, ecart de Sharpe -6.04
- PBO du lot 82.4% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur XAU_SPOT seulement (phase, 200 chemins)
- 395 signaux mesures, 395 retenus apres elimination des chevauchements

### Buy-and-hold du même actif sur la même période (S8)

« Candidate » = la courbe du moteur (capital 100 000, 1 % du capital risqué par trade, non composée) ; elle peut passer sous zéro.

| Variante | Période du hold | Hold : rendement | Hold : Sharpe | Hold : drawdown max | Candidate : rendement | Candidate : Sharpe | Candidate : drawdown max | S8 franchie |
|---|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 21/06/2023 → 31/12/2024 | +35,59 % | 1,58 | −7,99 % | −222,69 % | −5,94 | −222,69 % | non |
| stop 1,0x amplitude | 21/06/2023 → 31/12/2024 | +35,59 % | 1,58 | −7,99 % | −104,75 % | −4,36 | −104,75 % | non |
| stop 1,5x amplitude | 21/06/2023 → 31/12/2024 | +35,59 % | 1,58 | −7,99 % | −76,77 % | −4,45 | −76,77 % | non |

### Épreuve de causalité sur la série mesurée

- stop 0,5x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — XAU_SPOT 5m : 108 528 bougies du 21/06/2023 au 31/12/2024 21:55 UTC, 395 signaux (193 longs, 202 courts), causalité ok, déterminisme ok
- stop 1,0x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — XAU_SPOT 5m : 108 528 bougies du 21/06/2023 au 31/12/2024 21:55 UTC, 395 signaux (193 longs, 202 courts), causalité ok, déterminisme ok
- stop 1,5x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — XAU_SPOT 5m : 108 528 bougies du 21/06/2023 au 31/12/2024 21:55 UTC, 395 signaux (193 longs, 202 courts), causalité ok, déterminisme ok

### Compteur d'essais

- Famille : trading.
- N au préenregistrement : 94 ; N figé pour juger le lot (S2) : 98 ; compteur inscrit à la clôture : 97 ; compteur aujourd'hui : 99.

### Traçabilité

| Run | Candidate | Empreinte du code | Lancé le | RUNS.jsonl |
|---|---|---|---|---|
| `8bfb719165c8` | `r13_ny_or_stop_050` | `b8dcacb10d31` | 04/11/2026 12:48 UTC | 04/11/2026 12:50 UTC |
| `53aae4e0be16` | `r13_ny_or_stop_100` | `8ca359af2b7d` | 04/11/2026 12:48 UTC | 04/11/2026 12:51 UTC |
| `f621f8eb0240` | `r13_ny_or_stop_150` | `9d915baf7cfd` | 04/11/2026 12:48 UTC | 04/11/2026 12:52 UTC |

Runs retenus : ceux de la ligne de clôture du registre.

### Contrôles de cohérence (refaits par le programme)

| Variante | Contrôle | Résultat | Détail |
|---|---|---|---|
| stop 0,5x amplitude | run présent dans data/runs | ok |  |
| stop 0,5x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 0,5x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 0,5x amplitude | nombre de trades recalculé = verdict.json | ok | 395 contre 395 |
| stop 0,5x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 0,5x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 4,4e-16 |
| stop 0,5x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |
| stop 1,0x amplitude | run présent dans data/runs | ok |  |
| stop 1,0x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 1,0x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 1,0x amplitude | nombre de trades recalculé = verdict.json | ok | 395 contre 395 |
| stop 1,0x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 1,0x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 2,2e-16 |
| stop 1,0x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |
| stop 1,5x amplitude | run présent dans data/runs | ok |  |
| stop 1,5x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 1,5x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 1,5x amplitude | nombre de trades recalculé = verdict.json | ok | 395 contre 395 |
| stop 1,5x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 1,5x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 1,1e-16 |
| stop 1,5x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |

## Fade open NY sur le Nasdaq-100 (1h) (registre : R14)

### Verdict du programme

**INFIRMÉE** — ligne de clôture du registre, datée du 04/11/2026 ; conforme à l'issue attendue : oui.

Issues des variantes (moteur) : stop 0,5x amplitude : INFIRMÉE ; stop 1,0x amplitude : INFIRMÉE ; stop 1,5x amplitude : INFIRMÉE.

Texte de la clôture, tel qu'au registre :

> r14_ny_ndx1h_stop_050 : infirmee, n=277, R moyen=-0.5996526888428048, MDE=0.25399243988627107, portes echouees=9, non executees=0 ; r14_ny_ndx1h_stop_100 : infirmee, n=276, R moyen=-0.3354354819480727, MDE=0.18582673115472848, portes echouees=10, non executees=0 ; r14_ny_ndx1h_stop_150 : infirmee, n=276, R moyen=-0.24654604447049733, MDE=0.13569852939709923, portes echouees=10, non executees=0

### Préenregistrement (tel qu'écrit avant la mesure)

- Écrit le 04/11/2026 ; empreinte de la ligne `eab7cf222ebcf2c5` ; N au préenregistrement : 95 ; famille du compteur : trading ; split autorisé : train.
- Famille déclarée : 3 ; issue attendue : INFIRMÉE ; MDE attendu : non déclaré.
- Décidé par : « Jonas, 2026-11-04 : memes parametres que R8, or 5m + Nasdaq 1h, les 3 stops »
- Dérivé de : « R8 »

**Hypothèse**

> R8 sur le NASDAQ-100 (^NDX, Yahoo) en 1h, seule resolution disponible avant 2025 : la premiere bougie horaire de la seance (09:30-10:30 New York, 60 min au lieu des 45 de R8) est une prise de liquidite ; entrer a sa cloture (10:30) dans le sens OPPOSE a son corps, stop a 0,5x / 1x / 1,5x son amplitude, cible 3 R, horizon 6 bougies 1h (les 6 h de R8, jusqu'a la cloture de 16:00), a un R moyen strictement positif, couts deduits.

**Métrique primaire**

> R moyen par trade (triple barriere du moteur, take_profit_r=3.0, horizon 6 bougies 1h, couts aller-retour deduits), par variante, lot des 3 variantes

**Règle de décision**

- `confirmee` : « au moins une des 3 variantes CONFIRMEE par le moteur : R moyen > 0, p survivant a Benjamini-Hochberg sur la famille de 3, et les dix portes S1-S10 franchies (S8 : buy-and-hold du meme actif sur la meme periode ; S10 : PBO du lot < 20 %) »
- `infirmee` : « aucune variante confirmee ni indecidable : R moyen <= 0, ou une porte echoue »
- `indecidable` : « aucune variante confirmee, et au moins une indecidable (moins de 30 signaux apres elimination des chevauchements, ou porte non executable) »
- `verdict_par_le_programme` : « scripts/mesurer_r13_r14.py applique cette regle aux issues rendues par pipeline.cribler et clot l'experience lui-meme »
- `suite_si_confirmee` : « AUCUN passage au reel : preenregistrement d'un paper sur le perpetuel TradFi (XAUUSDT / QQQUSDT), decision de Jonas. Le hold-out 2025+ reste scelle pour ces actifs. »

**Règles déclarées** (`regles`)

- `actif` : NDX (data/marches, beta.marches.intraday)
- `timeframe` : 1h
- `periode` : 2023-11-22 (1re bougie 1h) -> 2024-12-31, FIGEE
- `candidates` : ["r14_ny_ndx1h_stop_050", "r14_ny_ndx1h_stop_100", "r14_ny_ndx1h_stop_150"]
- `take_profit_r` : 3.0
- `horizon_bougies` : 6

**Déjà connu au préenregistrement**

> R8 (21/08, remesuree le 19/09 aux couts corriges) : la MEME regle sur les 6 cryptos en 5m est INFIRMEE, 8 portes sur 9 echouees, R moyen -0,29 / -0,16 / -0,12 (stops 0,5x / 1x / 1,5x) sur 10 744 trades, negative 5 annees sur 6, MFE moyen +1,48 R contre une cible a 3 R, 66 % de sorties au stop. Ces chiffres sont connus de Jonas et de Claude au moment d'ecrire ceci ; c'est pour cela que les PARAMETRES sont ceux de R8 tels quels (aucun reglage choisi apres avoir vu les cryptos), et les 3 variantes gardees (Jonas : « les 3 »). Regarde AVANT ce preenregistrement, sur le train seulement et sans aucun rendement : la couverture des series (dates, nombre de bougies, heures des bougies 1h du NDX), et le nombre de signaux de la regle avec l'epreuve de causalite (signaux(df[:t]) == signaux(df)[:t], 25 coupures, OK). Les series intraday de l'or et du NDX n'ont servi a aucune mesure de BETA avant ceci (Temps 1 et Test invest n'ont lu que du QUOTIDIEN). Couts = ceux du moteur pour un perpetuel Binance (0,10 % aller-retour + 0,02 % de slippage + spread d'un tick) : c'est le prix de l'instrument qu'on traderait (XAUUSDT, QQQUSDT), pas celui de l'indice, qui ne se trade pas. Pas de funding (serie comptant / indice) : sous-estime un peu le cout d'une position tenue au plus 6 h. Issue attendue : infirmee (prior R8). NDX : 278 signaux (131 longs) — a peine au-dessus de 30 par variante apres chevauchements, test PEU puissant. Variante IMPOSEE par la donnee et non choisie : fenetre de 60 min, barrieres lues en 1h (un stop et une cible touches dans la meme bougie se tranchent par la convention du moteur, plus souvent qu'en 5m).

### Données et paramètres de la mesure

- Série lue (ligne de clôture) : 1 930 bougies, du 22/11/2023 14:30 UTC au 31/12/2024 20:30 UTC, empreinte `2ce1d08485626763`.
- Paires : NDX ; timeframe 1h ; split train ; début demandé 2023-11-22 ; fin demandée aucune (bornée au train).
- Barrières : take_profit_r = 3,0000 ; horizon_bougies = 6 ; stop_atr (si la candidate ne donne pas de stop) = 2,0000.
- Coûts : frais_pct = 0,1000 ; slippage_pct = 0,0200 ; cout_aller_retour_pct = 0,1200 ; spread = oui (modèle tick) ; funding = oui.
- Paramètres de `r14_ny_ndx1h_stop_050` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 630, "bougies_attendues": 1, "fraction_stop": 0.5}
- Paramètres de `r14_ny_ndx1h_stop_100` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 630, "bougies_attendues": 1, "fraction_stop": 1.0}
- Paramètres de `r14_ny_ndx1h_stop_150` : {"fuseau": "America/New_York", "minute_debut": 570, "minute_fin": 630, "bougies_attendues": 1, "fraction_stop": 1.5}

### Résultats par variante (moteur, `verdict.json`)

| Variante | Run | Issue | Signaux mesurés | Trades retenus | R moyen | R médian | σ(R) | MDE | Taux de gain | Profit factor | MFE moyen | MAE moyen | Durée médiane (h) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | `544b3cd8a3bf` | INFIRMÉE | 278 | 277 | −0,5997 | −1,3318 | 1,3438 | 0,2540 | 28,2 % | 0,4666 | +1,1983 | −1,1371 | 3,00 |
| stop 1,0x amplitude | `eaa351a4c37a` | INFIRMÉE | 278 | 276 | −0,3354 | −0,4644 | 0,9814 | 0,1858 | 34,8 % | 0,4862 | +0,7231 | −0,7251 | 6,00 |
| stop 1,5x amplitude | `03d6d0620341` | INFIRMÉE | 278 | 276 | −0,2465 | −0,2433 | 0,7166 | 0,1357 | 35,5 % | 0,4574 | +0,5014 | −0,5401 | 6,00 |

« Signaux mesurés » vient de la réserve écrite par le moteur à chaque run ; « Trades retenus » = après élimination des chevauchements (`metriques.n`).

### R brut, coûts, R net (recalculés par le programme depuis `trades.parquet`)

Moyennes par trade, en R. Informatif : la métrique primaire est le R net, et aucune règle de décision ne porte sur le R brut.

| Variante | Trades | R brut | Coûts (total) | dont frais | dont spread | dont funding | R net |
|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 277 | −0,1250 | 0,4746 | 0,4381 | 0,0365 | +0,0000 | −0,5997 |
| stop 1,0x amplitude | 276 | −0,0981 | 0,2373 | 0,2190 | 0,0183 | +0,0000 | −0,3354 |
| stop 1,5x amplitude | 276 | −0,0884 | 0,1582 | 0,1460 | 0,0122 | +0,0000 | −0,2465 |

### Sorties, par raison (`trades.parquet`)

| Variante | Sortie | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | stop (SL) | 172 | 62,1 % | −1,4982 | −257,69 | 0,0 % |
| stop 0,5x amplitude | cible (TP) | 24 | 8,7 % | +2,3848 | +57,23 | 100,0 % |
| stop 0,5x amplitude | horizon | 81 | 29,2 % | +0,4241 | +34,35 | 66,7 % |
| stop 1,0x amplitude | stop (SL) | 94 | 34,1 % | −1,2739 | −119,75 | 0,0 % |
| stop 1,0x amplitude | cible (TP) | 8 | 2,9 % | +2,5879 | +20,70 | 100,0 % |
| stop 1,0x amplitude | horizon | 174 | 63,0 % | +0,0372 | +6,47 | 50,6 % |
| stop 1,5x amplitude | stop (SL) | 46 | 16,7 % | −1,1885 | −54,67 | 0,0 % |
| stop 1,5x amplitude | cible (TP) | 2 | 0,7 % | +2,6274 | +5,25 | 100,0 % |
| stop 1,5x amplitude | horizon | 228 | 82,6 % | −0,0817 | −18,63 | 42,1 % |

### Par sens (`trades.parquet`)

| Variante | Sens | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | long | 131 | 47,3 % | −0,5281 | −69,18 | 31,3 % |
| stop 0,5x amplitude | court | 146 | 52,7 % | −0,6639 | −96,93 | 25,3 % |
| stop 1,0x amplitude | long | 131 | 47,5 % | −0,2317 | −30,35 | 41,2 % |
| stop 1,0x amplitude | court | 145 | 52,5 % | −0,4292 | −62,23 | 29,0 % |
| stop 1,5x amplitude | long | 131 | 47,5 % | −0,2067 | −27,08 | 42,0 % |
| stop 1,5x amplitude | court | 145 | 52,5 % | −0,2825 | −40,97 | 29,7 % |

### Par année de sortie (`trades.parquet`)

| Variante | Année | Trades | Part | R moyen | R total | Taux de gain |
|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 2023 | 25 | 9,0 % | −0,4305 | −10,76 | 32,0 % |
| stop 0,5x amplitude | 2024 | 252 | 91,0 % | −0,6164 | −155,34 | 27,8 % |
| stop 1,0x amplitude | 2023 | 25 | 9,1 % | −0,1961 | −4,90 | 40,0 % |
| stop 1,0x amplitude | 2024 | 251 | 90,9 % | −0,3493 | −87,68 | 34,3 % |
| stop 1,5x amplitude | 2023 | 25 | 9,1 % | −0,0995 | −2,49 | 40,0 % |
| stop 1,5x amplitude | 2024 | 251 | 90,9 % | −0,2612 | −65,56 | 35,1 % |

### Batterie, porte par porte (`verdict.json` et `batterie.json`)

| Porte | stop 0,5x amplitude | stop 1,0x amplitude | stop 1,5x amplitude |
|---|---|---|---|
| S1 · Benjamini-Hochberg | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S2 · Sharpe dégonflé | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S3 · bootstrap par blocs | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S4 · Monte-Carlo | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S5 · chemins synthétiques | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S6 · walk-forward purgé | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S7 · reality check | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S8 · buy-and-hold | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| S9 · diversification | ok | **ÉCHEC** | **ÉCHEC** |
| S10 · PBO (CSCV) | **ÉCHEC** | **ÉCHEC** | **ÉCHEC** |
| Portes échouées | 9 sur 10 | 10 sur 10 | 10 sur 10 |

**stop 0,5x amplitude** (`r14_ny_ndx1h_stop_050`, run `544b3cd8a3bf`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,0333 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,4462 ; sharpe_seuil = 0,1523 ; n_essais = 100 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 1,0000 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −166,1038 ; centile = 21,5000 ; seuil = −91,7702 ; synthetique_median = −141,2085 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,6000 ; ancre.oos_moyen = −0,6076 ; ancre.efficacite = 1,0127 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r14_ny_ndx1h_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 31,2281 ; candidate.rendement_total_pct = −166,3870 ; ecart_rendement_pct = −197,6151 ; ecart_sharpe = −8,6082
- S9 · diversification : correlation_max = −0,0451 ; avec = r14_ny_ndx1h_stop_100 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,9526 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.446 contre 0.152 attendu du maximum de 100 essais
- R moyen in-sample -0.6000 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -197.6 pts, ecart de Sharpe -8.61
- resultat au 22e centile des marches synthetiques : indiscernable d'une serie sans structure
- PBO du lot 95.3% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur NDX seulement (phase, 200 chemins)
- 278 signaux mesures, 277 retenus apres elimination des chevauchements

**stop 1,0x amplitude** (`r14_ny_ndx1h_stop_100`, run `eaa351a4c37a`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,0667 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,3418 ; sharpe_seuil = 0,1526 ; n_essais = 100 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 0,0048 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −92,5802 ; centile = 38,0000 ; seuil = −37,9251 ; synthetique_median = −83,7709 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,2831 ; ancre.oos_moyen = −0,3584 ; ancre.efficacite = 1,2657 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r14_ny_ndx1h_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 31,2281 ; candidate.rendement_total_pct = −92,5643 ; ecart_rendement_pct = −123,7925 ; ecart_sharpe = −7,0731
- S9 · diversification : correlation_max = 0,8624 ; avec = r14_ny_ndx1h_stop_150 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,9526 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.342 contre 0.153 attendu du maximum de 100 essais
- R moyen in-sample -0.2831 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -123.8 pts, ecart de Sharpe -7.07
- resultat au 38e centile des marches synthetiques : indiscernable d'une serie sans structure
- correlee a 0.86 avec r14_ny_ndx1h_stop_150 : n'apporte pas de diversification
- PBO du lot 95.3% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur NDX seulement (phase, 200 chemins)
- 278 signaux mesures, 276 retenus apres elimination des chevauchements

**stop 1,5x amplitude** (`r14_ny_ndx1h_stop_150`, run `03d6d0620341`) — champs du moteur :

- S1 · Benjamini-Hochberg : p_brute = 1,0000 ; seuil_BH = 0,1000 ; signif_BH = non ; m_declare = 3
- S2 · Sharpe dégonflé : sharpe = −0,3440 ; sharpe_seuil = 0,1526 ; n_essais = 100 ; dsr = 0,0000
- S3 · bootstrap par blocs : p_value (ell = 5) = 1,0000 ; p_value (ell = 20) = 1,0000 ; p_value (ell = 50) = 1,0000
- S4 · Monte-Carlo : permutation.p_perte = 1,0000 ; permutation.p_ruine = 0,0000 ; permutation.p_drawdown_pire_que_seuil = 1,0000
- S5 · chemins synthétiques : observe = −68,0467 ; centile = 54,5000 ; seuil = −32,7318 ; synthetique_median = −70,8715 ; n_chemins = 200
- S6 · walk-forward purgé : ancre.is_moyen = −0,2164 ; ancre.oos_moyen = −0,2618 ; ancre.efficacite = 1,2097 ; ancre.plis_positifs = 0 ; cpcv.part_chemins_perdants = 1,0000
- S7 · reality check : p_value = 1,0000 ; meilleure = r14_ny_ndx1h_stop_100 ; n_candidates = 3
- S8 · buy-and-hold : hold.rendement_total_pct = 31,2281 ; candidate.rendement_total_pct = −68,0012 ; ecart_rendement_pct = −99,2294 ; ecart_sharpe = −7,1056
- S9 · diversification : correlation_max = 0,8624 ; avec = r14_ny_ndx1h_stop_100 ; seuil = 0,7000
- S10 · PBO (CSCV) : pbo = 0,9526 ; seuil = 0,2000 ; n_configs = 3

Réserves du moteur, mot pour mot :

- bootstrap instable ou non significatif — l=5: p=1.000, l=20: p=1.000, l=50: p=1.000
- Sharpe -0.344 contre 0.153 attendu du maximum de 100 essais
- R moyen in-sample -0.2164 <= 0 : efficacite OOS/IS sans objet, S6 echoue
- 100% des chemins CPCV finissent en perte
- ne bat pas le hold : ecart de rendement -99.2 pts, ecart de Sharpe -7.11
- resultat au 55e centile des marches synthetiques : indiscernable d'une serie sans structure
- correlee a 0.86 avec r14_ny_ndx1h_stop_100 : n'apporte pas de diversification
- PBO du lot 95.3% (seuil < 20%) : la meilleure du lot en apprentissage finit trop souvent dans la moitie basse hors echantillon
- chemins synthetiques rejoues sur NDX seulement (phase, 200 chemins)
- 278 signaux mesures, 276 retenus apres elimination des chevauchements

### Buy-and-hold du même actif sur la même période (S8)

« Candidate » = la courbe du moteur (capital 100 000, 1 % du capital risqué par trade, non composée) ; elle peut passer sous zéro.

| Variante | Période du hold | Hold : rendement | Hold : Sharpe | Hold : drawdown max | Candidate : rendement | Candidate : Sharpe | Candidate : drawdown max | S8 franchie |
|---|---|---|---|---|---|---|---|---|
| stop 0,5x amplitude | 22/11/2023 → 31/12/2024 | +31,23 % | 1,80 | −13,59 % | −166,39 % | −6,81 | −166,66 % | non |
| stop 1,0x amplitude | 22/11/2023 → 31/12/2024 | +31,23 % | 1,80 | −13,59 % | −92,56 % | −5,27 | −93,37 % | non |
| stop 1,5x amplitude | 22/11/2023 → 31/12/2024 | +31,23 % | 1,80 | −13,59 % | −68,00 % | −5,31 | −69,77 % | non |

### Épreuve de causalité sur la série mesurée

- stop 0,5x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — NDX 1h : 1 930 bougies du 22/11/2023 14:30 UTC au 31/12/2024 20:30 UTC, 278 signaux (131 longs, 147 courts), causalité ok, déterminisme ok
- stop 1,0x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — NDX 1h : 1 930 bougies du 22/11/2023 14:30 UTC au 31/12/2024 20:30 UTC, 278 signaux (131 longs, 147 courts), causalité ok, déterminisme ok
- stop 1,5x amplitude : non enregistrée avec le run (le moteur l'enregistre depuis le 04/11/2026).
  - Relancée par le programme le 04/11/2026 13:32 UTC (`beta.atelier.epreuve`, même série et même période que le run) : OK (code de la candidate : même empreinte que le run) — NDX 1h : 1 930 bougies du 22/11/2023 14:30 UTC au 31/12/2024 20:30 UTC, 278 signaux (131 longs, 147 courts), causalité ok, déterminisme ok

### Compteur d'essais

- Famille : trading.
- N au préenregistrement : 95 ; N figé pour juger le lot (S2) : 100 ; compteur inscrit à la clôture : 99 ; compteur aujourd'hui : 99.

### Traçabilité

| Run | Candidate | Empreinte du code | Lancé le | RUNS.jsonl |
|---|---|---|---|---|
| `544b3cd8a3bf` | `r14_ny_ndx1h_stop_050` | `180c537e9959` | 04/11/2026 12:52 UTC | 04/11/2026 12:53 UTC |
| `eaa351a4c37a` | `r14_ny_ndx1h_stop_100` | `96f342fd5cc4` | 04/11/2026 12:52 UTC | 04/11/2026 12:53 UTC |
| `03d6d0620341` | `r14_ny_ndx1h_stop_150` | `778193144971` | 04/11/2026 12:52 UTC | 04/11/2026 12:53 UTC |

Runs retenus : ceux de la ligne de clôture du registre.

### Contrôles de cohérence (refaits par le programme)

| Variante | Contrôle | Résultat | Détail |
|---|---|---|---|
| stop 0,5x amplitude | run présent dans data/runs | ok |  |
| stop 0,5x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 0,5x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 0,5x amplitude | nombre de trades recalculé = verdict.json | ok | 277 contre 277 |
| stop 0,5x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 0,5x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 2,2e-16 |
| stop 0,5x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |
| stop 1,0x amplitude | run présent dans data/runs | ok |  |
| stop 1,0x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 1,0x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 1,0x amplitude | nombre de trades recalculé = verdict.json | ok | 276 contre 276 |
| stop 1,0x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 1,0x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 1,1e-16 |
| stop 1,0x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |
| stop 1,5x amplitude | run présent dans data/runs | ok |  |
| stop 1,5x amplitude | run journalisé dans RUNS.jsonl (candidate, empreinte, issue) | ok | 1 ligne(s) |
| stop 1,5x amplitude | R moyen recalculé = verdict.json | ok | écart 0,0e+00 |
| stop 1,5x amplitude | nombre de trades recalculé = verdict.json | ok | 276 contre 276 |
| stop 1,5x amplitude | R net = R brut − coûts, trade par trade | ok | écart maximal 0,0e+00 |
| stop 1,5x amplitude | coûts = frais + spread + funding, trade par trade | ok | écart maximal 1,1e-16 |
| stop 1,5x amplitude | ligne de clôture = verdict.json (run, issue, R moyen, portes) | ok |  |

Rapport écrit par le programme (`beta/rapport/experience.py`), sans interprétation.
