# VC6 V1 — spécification figée

- **Figée le** : 01/11/2026 (UTC), avant tout code et tout calcul de VC6.
- **Date de fin des données** : **31/10/2026**, dernière clôture UTC complète au moment du gel (01/11/2026, 17:03 UTC).
- **Source** : prompt de Jonas du 01/11/2026 (« On lance le backtest V1 de VC6 »), étape B. La spec est recopiée mot pour mot entre les marqueurs `=== SPEC VC6 V1 ===` et `=== FIN SPEC ===`.
- **Cadre, cité du même prompt** : « C'est un backtest de DIAGNOSTIC : les données crypto ont déjà été vues, donc ce run peut éliminer des choix, pas les valider. Les règles sont figées avant le run. Toute correction après un résultat devient une V2 datée. »

=== SPEC VC6 V1 ===
Univers : BTC, ETH, SOL. Poids des poches : 50 % BTC, 25 % ETH, 25 % SOL.
Décision chaque jour à la clôture UTC du jour t, appliquée au rendement du jour t+1. Aucune donnée de t+1 n'est utilisée pour décider.

Mode global : baissier si la clôture du BTC < SMA 200 du BTC, sinon haussier.

Mode haussier :
- La poche i est investie si la clôture de i ≥ sa propre SMA 200. Si i n'a pas passé le « Temps 1 – complément », on utilise la SMA 200 du BTC. Sinon la poche est en cash.
- Exposition d'une poche investie : Ei = clip(0,25 / σ̂i ; 0,2 ; 2). σ̂i = volatilité prévue retenue au « Contrôle HAR », annualisée en √365.
- Filtre de financement : si le funding annualisé de i > 20 %, Ei est plafonnée à 1. Funding annualisé = funding moyen par paiement du jour × nombre de paiements par jour × 365.
- Levier (Ei > 1) : via perpétuels, financement payé déduit. Base au comptant ; écart perp/comptant ignoré. Pas de levier « inversé » : le levier ne vient que de la formule ci-dessus.
- Sécurité de liquidation : distance au prix de liquidation ≈ 1/Ei − marge de maintenance. Elle doit rester ≥ 3 × σ̂i quotidienne (σ̂i / √365). Sinon Ei est réduite au maximum qui respecte la règle. Compte les jours où la règle contraint.

Mode baissier :
- Toutes les poches sortent.
- 25 % du capital va dans la poche baissière (BTC, or ou mixte selon la variante), sans levier.
- Cette poche est conservée jusqu'au retour en mode haussier.

Transitions de mode : rampe de 5 jours, 1/5 de l'écart par jour, dans les deux sens.
Bande : hors rampe, une exposition ne change que si l'écart entre cible et exposition actuelle dépasse 10 % de l'exposition actuelle. Pas de bande pendant la rampe.
Frais : 10 pb sur chaque montant échangé, slippage inclus.
Or : marché fermé le week-end → dernier cours connu, rendement nul ces jours-là.

Variantes (4 essais, famille invest) :
- « Variante expo fixe » : Ei = 1 ; poche baissière = 25 % BTC.
- « Variante expo vol » : Ei = clip(0,25/σ̂i ; 0,2 ; 2) ; poche baissière = 25 % BTC.
- « Variante poche or » : sizing de la meilleure des deux précédentes ; poche baissière = 25 % or.
- « Variante poche mixte » : sizing de la meilleure ; poche baissière = 12,5 % BTC + 12,5 % or.

Test annexe (1 essai de plus, famille invest, soit 5 au total) :
- « Test annexe – cible 40 % » : même règle que la « Variante expo vol », avec Ei = clip(0,40/σ̂i ; 0,2 ; 2) ; poche baissière = 25 % BTC ; avec son propre « Témoin expo constante ».
- Non éligible aux règles de décision : seulement rapporté (exposition moyenne, jours en levier, rendement, drawdown et financement pendant les phases en levier).

Témoin (pas un essai) : « Témoin expo constante » = exposition constante égale à l'exposition moyenne de la variante comparée, répartie selon les poids des poches.

Références, rapportées à risque égal (même volatilité réalisée que la variante) :
- panier buy and hold 50 % BTC, 25 % ETH, 25 % SOL, sans rééquilibrage ;
- ETF monde.

Période principale : 01/06/2021 → date de fin figée.
Robustesse : « Variante expo fixe » et « Variante expo vol » sur le BTC seul (une poche à 100 %) depuis 2014. Si les bougies 5 min ne remontent pas assez loin, σ̂ = écart-type 30 jours pour ce test, et c'est écrit dans le rapport.

Mesure principale : Ulcer Index.
Mesures rapportées : drawdown max, rendement annualisé, Sharpe (√365), ratio rendement annualisé / Ulcer, exposition moyenne, changements par an, financement payé, frais payés, jours contraints par la sécurité de liquidation.
Tests : chaque variante contre son « Témoin expo constante » ; nulls circulaire et segments (règle D4).

Décision :
1. Utile = Ulcer < témoin, avec p < 0,05.
2. « Variante expo vol » retenue si elle est utile et que son ratio rendement annualisé / Ulcer est supérieur à celui de « Variante expo fixe ». L'Ulcer brut baisse mécaniquement avec l'exposition, il ne départage pas seul.
3. « Variante poche or » ou « Variante poche mixte » remplace la poche BTC si : Ulcer plus bas, et rendement annualisé ≥ celui de la meilleure variante à poche BTC − 2 points.
4. Si aucune variante de sizing n'est utile → conclusion : exposition constante × HAR.

Verdict VC6, pour info seulement : Sharpe > 1 ; drawdown max < 25 % ; bat le panier buy and hold à risque égal ; bat l'ETF monde à risque égal.
=== FIN SPEC ===

## Données figées (étape A)

Copies tronquées à la date de fin, écrites le 2026-11-01 à 17:03:25 UTC par `VC6_V1/etape_a_inventaire.py` (lecture seule des sources). Elles vivent dans `data/vc6_v1/sources_figees/`, hors git comme tout `data/`. Le détail (origine, trous, contrôles) est dans `VC6_V1/sources_figees.json` et `VC6_V1/INVENTAIRE_DONNEES.md`.

Bornes : séries journalières jusqu'au 31/10/2026 inclus (or et ETF : dernière séance le 30/10/2026, un vendredi) ; bougies 5 min ouvertes avant le 01/11/2026 00:00 UTC ; funding réglé jusqu'au 01/11/2026 00:00 UTC inclus, instant de la clôture du 31/10, ce règlement paie la période du 31/10 de 16:00 à 24:00.

| source | série | première ligne | dernière ligne de la copie | lignes | SHA-256 de la copie figée | SHA-256 du fichier vivant au gel |
|---|---|---|---|---|---|---|
| BTC, clôture journalière, Bitstamp comptant (DS1 bougies_1d) | `data/vc6_v1/sources_figees/BTC_bitstamp_1d.parquet` | 2011-08-18 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 5554 | `5cd3f419ce33e215201e9d1e8f40cba458baba9645a38df26b8403c504f435dd` | — (lu dans la base DS1, pas de fichier) |
| BTC, clôture journalière, Coinbase comptant (DS1 bougies_1d) | `data/vc6_v1/sources_figees/BTC_coinbase_1d.parquet` | 2015-07-20 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 4122 | `38d90695d9e37909c8c864b0fd3553d1bf32a2b99b55c3704bc8e651b39970e5` | — (lu dans la base DS1, pas de fichier) |
| BTC, bougie 1d, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/BTC_perp_1d.parquet` | 2019-09-08 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 2611 | `1bd26426c4cf103bb4b19766aa0a67cefbfe18d9532fe0997592935cab25cb93` | `8c6350fbff8d889a0d8f43fbcdd585178de48ba8a1141463bde453211d338974` |
| ETH, bougie 1d, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/ETH_perp_1d.parquet` | 2019-11-27 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 2531 | `19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f` | `241889172daf6fa4cd189c0aa901f9dbbd4abf789b27b8c9ebd8f83f36ff2022` |
| SOL, bougie 1d, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/SOL_perp_1d.parquet` | 2020-09-14 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 2239 | `58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42` | `5a47a6df6c697742c5ae3f27a698c37a93a69482e8d76a5aba88e52d505af606` |
| BTC, bougies 5 min, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/BTC_perp_5m.parquet` | 2019-09-08 17:55:00 UTC | 2026-10-31 23:55:00 UTC | 751753 | `42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618` | `72f2751ae48a649481b7bb5710a386778e95d9ec1050d79989ee81706b399e50` |
| ETH, bougies 5 min, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/ETH_perp_5m.parquet` | 2019-11-27 07:45:00 UTC | 2026-10-31 23:55:00 UTC | 728835 | `5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f` | `3aec45a799ad71bb270bfda169f48f52de9c6b98b7f3f1d418c071384f86dfe2` |
| SOL, bougies 5 min, perpétuel Binance USDT-M (lake) | `data/vc6_v1/sources_figees/SOL_perp_5m.parquet` | 2020-09-14 07:00:00 UTC | 2026-10-31 23:55:00 UTC | 644748 | `0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d` | `96460738d99889533b87861a131685ae1ee5a442352c226682d7bec379c5312a` |
| BTC, funding du perpétuel Binance USDT-M | `data/vc6_v1/sources_figees/BTC_funding.parquet` | 2019-09-10 08:00:00 UTC | 2026-11-01 00:00:00 UTC | 7827 | `bd970babd9c36149e0c6b9e295be90bd01d4cb4cc650be5a95ea0484fe0bc006` | `f7efa592b132b319cedbfa12cf69a65bfe933662de1ee63558cd730e86304c6b` |
| ETH, funding du perpétuel Binance USDT-M | `data/vc6_v1/sources_figees/ETH_funding.parquet` | 2019-11-27 08:00:00 UTC | 2026-11-01 00:00:00 UTC | 7593 | `335f28b5d669c78c354aed3a3fd0334eb86d07dff889ca3d997bc3d6b94413a6` | `1394939d7b5035b2112e98a1fab07c62d4eebb8563e6476b5fa2fc016a00a662` |
| SOL, funding du perpétuel Binance USDT-M | `data/vc6_v1/sources_figees/SOL_funding.parquet` | 2020-09-13 16:00:00 UTC | 2026-11-01 00:00:00 UTC | 6794 | `4c17b7a34a5e6a4d0730c399a2d5dc757a8b56aa461a07663618d0089bfc6757` | `47f490826cfaa03f2e701191024f78874e370a5dc4ed472206473eeef88aff41` |
| or, fixing LBMA PM (World Gold Council, beta.marches) | `data/vc6_v1/sources_figees/XAU_LBMA_1d.parquet` | 1970-01-01 00:00:00 UTC | 2026-10-30 00:00:00 UTC | 14748 | `8f7c1cc5bffc3d76049391eb2530baf0a0c9e2215e0ab06d17651c1104dfd0bb` | `8f7c1cc5bffc3d76049391eb2530baf0a0c9e2215e0ab06d17651c1104dfd0bb` |
| or, comptant Dukascopy BID agrégé par jour UTC (beta.marches) | `data/vc6_v1/sources_figees/XAU_SPOT_1d.parquet` | 2003-05-05 00:00:00 UTC | 2026-10-30 00:00:00 UTC | 7316 | `4ec3b0f04a72f838db89177618096078c8184b2feed25497997aa718d38be542` | `4ec3b0f04a72f838db89177618096078c8184b2feed25497997aa718d38be542` |
| or, future COMEX continu GC=F (yfinance, lake) | `data/vc6_v1/sources_figees/XAUUSD_GCF_1d.parquet` | 2010-01-04 00:00:00 UTC | 2026-10-30 00:00:00 UTC | 4233 | `a29a114213acee565cbc19314fc765e93a1c26263c69feb436b39faf8f3024ea` | `5633998c50f14cb6089dbabe3ddaabfc631f6334ebecc33642dcd65128c568fb` |
| or, perpétuel TradFi Binance XAUUSDT (lake) | `data/vc6_v1/sources_figees/XAU_perp_1d.parquet` | 2025-12-11 00:00:00 UTC | 2026-10-31 00:00:00 UTC | 325 | `5ccfff01be70ff1fc2011b38869a39bbcd9c26c226c840fc012ce51859babdcf` | `1089ae9ba1971dc88192c22a5c1bb0a0f9358705eea47d27859d0ff8e06cd67a` |
| ETF monde : iShares MSCI World ETF URTH (yfinance, lake MSCIWORLD) | `data/vc6_v1/sources_figees/URTH_1d.parquet` | 2012-01-12 00:00:00 UTC | 2026-10-30 00:00:00 UTC | 3722 | `266aec60912cf63e2cf6ef669f6d1a5849f6be8a0f66a084b1a9cfe3589bbdf4` | `f022fd5c3149c64d55c71a6223bc1e31c0d6f0877eaea31b962bbcea6e388add` |

**Sources absentes, signalées sans remplacement** : marge de maintenance des perpétuels (aucune série dans BETA ni dans DS1) ; ACWI (seul l'ETF MSCI World URTH est présent).

## Addendum du 01/11/2026 — décision de Jonas après le « Temps 1 – complément ETH et SOL »

Inscrit le 01/11/2026 à 18:32 UTC, à la demande de Jonas. Il vient après le rapport du « Temps 1 – complément ETH et SOL » (`VC6_V1/temps1_complement_eth_sol/RAPPORT_COMPLEMENT.md`, mesure du commit `54fa777`) et avant tout code du « Contrôle HAR ». Son texte est recopié mot pour mot entre les marqueurs. La spec ci-dessus n'est pas modifiée.

=== ADDENDUM DU 01/11/2026 — DÉCISION DE JONAS ===
1. ETH : non retenu (p_justesse 0,313). SOL : indécidable, donc non retenu (règle 7 appliquée telle quelle, aucun changement du juge). ETH et SOL suivent le régime de la SMA 200 du BTC : chaque poche est investie si le mode global est haussier, sinon elle sort.
2. Données : ETH et SOL sont valorisés sur la clôture du perpétuel Binance USDT-M (pas de comptant disponible). L'écart perpétuel/comptant est ignoré, comme prévu dans la spec.
3. Ajout au rapport du Temps 2 (mesure seulement, aucune règle modifiée) : jours où le BTC est haussier alors qu'ETH ou SOL est sous sa propre SMA 200, avec la perte de chaque poche sur ces jours, par poche et au total.

Noms : dans tous les fichiers et rapports, écris en entier « Temps 1 – justesse », « Temps 1 – fiabilité », « Temps 1 – complément ETH et SOL ». Aucune abréviation.
=== FIN ADDENDUM ===

Les clôtures du point 2 sont les copies figées `ETH_perp_1d.parquet` et `SOL_perp_1d.parquet` de la table « Données figées ».

## Addendum du 01/11/2026 — σ̂ retenu au « Contrôle HAR »

Écrit par le programme (`scripts/controle_har.py --addendum`) à partir de la synthèse de la mesure du 2026-11-01T19:09:55+00:00 UTC : règles `04fc671b86f15a5c`, données `7005202023796717`, code `aefc6d5`. Règle 5 du prompt du « Contrôle HAR » (`VC6_V1/controle_har/PREENREGISTREMENT.md`). Rapport : `VC6_V1/controle_har/RAPPORT_CONTROLE_HAR.md`.

| actif | QLIKE HAR | QLIKE écart-type 30 jours | jours évalués | σ̂ retenu |
|---|---|---|---|---|
| BTC | 0,2372 | 0,4040 | 1876 | HAR |
| ETH | 0,2799 | 0,4923 | 1796 | HAR |
| SOL | 0,3694 | 0,5955 | 1504 | HAR |

- **HAR** : prévision HAR de la variance journalière moyenne des 5 jours suivants, avec ses replis (écart-type 30 jours avant 730 jours de RV et les jours de prévision ≤ 0).
- **Écart-type 30 jours** : écart-type d'échantillon des 30 derniers rendements log journaliers, au carré.
- La spec annualise σ̂i en √365.

## Addendum du 02/11/2026 — décisions de Jonas du 01/11/2026 avant la phase 3

Inscrit le 02/11/2026, à la demande de Jonas, après le « Contrôle HAR » et avant tout code de la phase 3. Son texte est recopié mot pour mot entre les marqueurs. La spec ci-dessus n'est pas modifiée.

=== ADDENDUM DU 01/11/2026 — DÉCISIONS DE JONAS AVANT LA PHASE 3 ===
1. Contrôle HAR : σ̂ = HAR pour BTC, ETH et SOL (règle 5), avec les replis prévus. Pas de PBO pour ce test de mesure.
2. Série du BTC pour le mode global : clôture du perpétuel Binance USDT-M (barre 5 min de 23:55) pour la période principale, comme ETH et SOL. Bitstamp au comptant uniquement pour la robustesse BTC seul depuis 2014, avec σ̂ = écart-type 30 jours (les bougies 5 min commencent en 2019).
3. Ajouts au rapport du Temps 2 (mesures seulement, aucune règle modifiée) :
   - sur les jours où une poche est investie, sa volatilité réalisée comparée à sa cible (25 % ou 40 %), par variante et pour le test annexe ;
   - sur la période commune, nombre de jours où le mode global diffère entre le perpétuel et Bitstamp.
=== FIN ADDENDUM ===

Les séries du point 2 sont les copies figées `BTC_perp_5m.parquet` (période principale) et `BTC_bitstamp_1d.parquet` (robustesse) de la table « Données figées ».

## Inventaire des données de la phase 3 (02/11/2026)

Écrit à partir de `VC6_V1/phase3_inventaire.json`, produit par `VC6_V1/phase3_inventaire.py` (lecture seule des copies figées, SHA-256 contrôlé contre `VC6_V1/sources_figees.json`). Période principale : 01/06/2021 → 31/10/2026.

| donnée | copie figée | début | fin | trous sur la période principale | SHA-256 = gel |
|---|---|---|---|---|---|
| funding BTC | `BTC_funding` | 10/09/2019 08:00 | 01/11/2026 00:00 | 5 938 règlements, aucun écart > 8 h, aucun jour sans règlement | oui |
| funding ETH | `ETH_funding` | 27/11/2019 08:00 | 01/11/2026 00:00 | 5 938 règlements, aucun écart > 8 h, aucun jour sans règlement | oui |
| funding SOL | `SOL_funding` | 13/09/2020 16:00 | 01/11/2026 00:00 | 6 013 règlements, aucun écart > 8 h ; 101 intervalles < 8 h (krach de FTX, 09-18/11/2022) | oui |
| marge de maintenance | — | — | — | **ABSENTE** : aucun fichier dans `data/`, aucune table ni colonne dans la base DS1 | — |
| or, fixing LBMA PM | `XAU_LBMA_1d` | 01/01/1970 | 30/10/2026 | 54 jours lun-ven sans valeur, 13 écarts > 4 jours (6 au plus) | oui |
| or, comptant Dukascopy | `XAU_SPOT_1d` | 05/05/2003 | 30/10/2026 | 6 jours lun-ven sans valeur, aucun écart > 4 jours ; 278 valeurs le dimanche soir | oui |
| or, future COMEX GC=F | `XAUUSD_GCF_1d` | 04/01/2010 | 30/10/2026 | 49 jours lun-ven sans valeur, aucun écart > 4 jours ; 8 séances à volume nul | oui |
| or, perpétuel Binance | `XAU_perp_1d` | 11/12/2025 | 31/10/2026 | ne couvre pas la période principale | oui |
| ETF monde URTH | `URTH_1d` | 12/01/2012 | 30/10/2026 | 52 jours lun-ven sans valeur, aucun écart > 4 jours | oui |

**Verdict du programme : `phase3_possible = false`, donnée manquante : marge de maintenance.** Phase 3 non lancée.

Non tranché, relevé sans être bloquant pour l'inventaire : la source d'or à utiliser (quatre présentes, trois couvrent la période principale) ; funding et marge avant 2019 pour la robustesse BTC seul depuis 2014.
