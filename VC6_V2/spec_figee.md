# VC6 V2 — spécification figée

- **Figée le** : 02/11/2026 (UTC), avant tout code et tout calcul de la V2.
- **Date de fin des données** : **31/10/2026**. Mêmes copies figées que la V1 (`data/vc6_v1/sources_figees/`, écrites le 01/11/2026 à 17:03:25 UTC) ; leurs SHA-256 sont recalculés plus bas.
- **Source** : prompt de Jonas du 02/11/2026 (« VC6 V1 est terminée. On prépare la V2 »), étape B. La spec est recopiée mot pour mot entre les marqueurs `=== SPEC VC6 V2 ===` et `=== FIN SPEC ===`.
- **Cadre, cité du même prompt** : « VC6 V1 est terminée. On prépare la V2 : deux essais seulement, chacun visant une découverte de la V1. Backtest de DIAGNOSTIC, sur les mêmes données déjà vues. Règles figées avant le run. Tu n'improvises aucune règle : si un point n'est pas couvert ici, tu t'arrêtes et tu me poses la question. Deux prompts : tu ne lances JAMAIS les runs des essais sans mon GO. »
- **Conclusion de la V1** : `VC6_V1/CONCLUSION.md` ; rapport corrigé : `VC6_V1/rapport_temps2_corrige.md`.

=== SPEC VC6 V2 ===
Tout ce qui n'est pas modifié ci-dessous est repris de VC6_V1/spec_figee.md et de ses addenda :
- univers BTC, ETH, SOL ; poids 50/25/25 ;
- σ̂ = HAR avec ses replis ; Ei = clip(0,25/σ̂i ; 0,2 ; 2) ;
- filtre de financement, sécurité de liquidation, bande de 10 %, frais de 10 pb ;
- clôture = barre 5 min de 23:55 du perpétuel Binance ;
- période principale 01/06/2021 → 31/10/2026 ;
- robustesse BTC seul depuis 2014 sur Bitstamp, avec σ̂ = écart-type 30 jours et funding fixe de 0,01 % par 8 h avant le 10/09/2019.

Essai 1 — « V2 – HAR sans régime »
- Pas de SMA 200, pas de mode global, pas de poche baissière, pas de rampe.
- Chaque poche est investie en permanence : Ei = clip(0,25/σ̂i ; 0,2 ; 2), avec filtre de financement, sécurité de liquidation et bande de 10 %.
- Null (il teste le signal de volatilité, pas le régime) :
  - circulaire : la série des expositions Ei(t) des trois poches est décalée d'un même k jours par rapport aux rendements, k tiré dans [90 ; N − 90] ;
  - segments : la série des Ei(t) est découpée en blocs consécutifs de 63 jours, permutés au hasard (les trois poches ensemble) ;
  - B = 1 000 tirages chacun, graine 0, métrique = Ulcer ; p = part des tirages dont l'Ulcer est ≤ l'observé ; p retenue = la plus haute des deux (règle D4).

Essai 2 — « V2 – poche baissière sous HAR »
- Identique à la « Variante expo vol » de la V1 (régime SMA 200 du BTC, rampe de 5 jours, ETH et SOL suivent le BTC), sauf la poche baissière :
  poche baissière = 25 % du capital × E_BTC, avec E_BTC = clip(0,25/σ̂_BTC ; 0,2 ; 1). Pas de levier dans la poche baissière.
- La bande de 10 % s'applique aussi à la poche baissière, hors rampe.
- Null : celui de la V1 (série du mode, circulaire et segments, règle D4).

Témoins (pas des essais) : « Témoin expo constante » de chaque essai = exposition constante égale à son exposition moyenne, répartie 50/25/25.
Références, à risque égal : panier buy and hold 50/25/25, ETF monde (URTH), « Variante expo vol » de la V1.

Compteur : 2 essais, famille invest (59 → 61).

Décision :
1. Utile = Ulcer < celui de son témoin, avec p retenue < 0,05.
2. Configuration retenue pour la suite :
   - un seul essai utile → cet essai ;
   - les deux utiles → celui qui a le ratio rendement annualisé / Ulcer le plus haut ;
   - aucun utile → VC6 rejetée, aucune configuration retenue ; le paper ne sert qu'à roder l'exécution.
3. Rapporté, sans effet sur la décision : « V2 – poche baissière sous HAR » comparé à la « Variante expo vol » de la V1 (Ulcer, drawdown max, rendement annualisé, contribution de la poche baissière pendant le drawdown max).

Verdict VC6, pour info : Sharpe > 1 ; drawdown max < 25 % ; bat le panier à risque égal ; bat l'ETF monde à risque égal.
=== FIN SPEC ===

## Données figées (mêmes copies que la V1)

Écrit par `VC6_V2/hash_sources.py` : SHA-256 de chaque copie recalculé le 02/11/2026 et comparé au gel de la V1 (`VC6_V1/sources_figees.json`, `beta/vc6/regles.py`). Arrêt au premier écart ; aucun écart. Détail : `VC6_V2/sources_figees.json`.

| source | copie figée | première ligne | dernière ligne | lignes | SHA-256 recalculé le 02/11/2026 | = gel de la V1 | usage dans la V2 |
|---|---|---|---|---|---|---|---|
| lake BETA data/lake/BTC_USDT_USDT-5m.parquet (perpetuel Binance USDT-M, date = ouverture de la bougie) | `data/vc6_v1/sources_figees/BTC_perp_5m.parquet` | 2019-09-08 17:55 UTC | 2026-10-31 23:55 UTC | 751753 | `42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618` | oui | clôture de 23:55, σ̂ HAR, mode global (SMA 200), volatilité réalisée (test c) |
| lake BETA data/lake/ETH_USDT_USDT-5m.parquet (perpetuel Binance USDT-M, date = ouverture de la bougie) | `data/vc6_v1/sources_figees/ETH_perp_5m.parquet` | 2019-11-27 07:45 UTC | 2026-10-31 23:55 UTC | 728835 | `5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f` | oui | clôture de 23:55, σ̂ HAR, volatilité réalisée (test c) |
| lake BETA data/lake/SOL_USDT_USDT-5m.parquet (perpetuel Binance USDT-M, date = ouverture de la bougie) | `data/vc6_v1/sources_figees/SOL_perp_5m.parquet` | 2020-09-14 07:00 UTC | 2026-10-31 23:55 UTC | 644748 | `0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d` | oui | clôture de 23:55, σ̂ HAR, volatilité réalisée (test c) |
| data/raw/futures/BTC_USDT_USDT-1h-funding_rate.feather (freqtrade, Binance USDT-M ; date = instant de reglement) | `data/vc6_v1/sources_figees/BTC_funding.parquet` | 2019-09-10 08:00 UTC | 2026-11-01 00:00 UTC | 7827 | `bd970babd9c36149e0c6b9e295be90bd01d4cb4cc650be5a95ea0484fe0bc006` | oui | filtre de financement et financement payé |
| data/raw/futures/ETH_USDT_USDT-1h-funding_rate.feather (freqtrade, Binance USDT-M ; date = instant de reglement) | `data/vc6_v1/sources_figees/ETH_funding.parquet` | 2019-11-27 08:00 UTC | 2026-11-01 00:00 UTC | 7593 | `335f28b5d669c78c354aed3a3fd0334eb86d07dff889ca3d997bc3d6b94413a6` | oui | filtre de financement et financement payé |
| data/raw/futures/SOL_USDT_USDT-1h-funding_rate.feather (freqtrade, Binance USDT-M ; date = instant de reglement) | `data/vc6_v1/sources_figees/SOL_funding.parquet` | 2020-09-13 16:00 UTC | 2026-11-01 00:00 UTC | 6794 | `4c17b7a34a5e6a4d0730c399a2d5dc757a8b56aa461a07663618d0089bfc6757` | oui | filtre de financement et financement payé |
| DS1 table bougies_1d, source bitstamp, symbole BTCUSD (docker exec psql, lecture seule ; jour civil UTC clos) | `data/vc6_v1/sources_figees/BTC_bitstamp_1d.parquet` | 2011-08-18 00:00 UTC | 2026-10-31 00:00 UTC | 5554 | `5cd3f419ce33e215201e9d1e8f40cba458baba9645a38df26b8403c504f435dd` | oui | robustesse BTC seul depuis 2014 (clôtures, écart-type 30 jours) |
| lake BETA data/lake/MSCIWORLD-1d.parquet (yfinance URTH, iShares MSCI World ETF) | `data/vc6_v1/sources_figees/URTH_1d.parquet` | 2012-01-12 00:00 UTC | 2026-10-30 00:00 UTC | 3722 | `266aec60912cf63e2cf6ef669f6d1a5849f6be8a0f66a084b1a9cfe3589bbdf4` | oui | référence ETF monde |

Bornes, reprises du gel de la V1 : séries journalières jusqu'au 31/10/2026 inclus (ETF : dernière séance le 30/10/2026) ; bougies 5 min ouvertes avant le 01/11/2026 00:00 UTC ; funding réglé jusqu'au 01/11/2026 00:00 UTC inclus.

Les autres copies figées de la V1 (bougies 1d des perpétuels, Coinbase, or) ne sont pas lues par la V2.

## Empreinte de la spec

SHA-256 du bloc de la spec, de la ligne `=== SPEC VC6 V2 ===` à la ligne `=== FIN SPEC ===` comprises (UTF-8, lignes jointes par un saut de ligne) : `3ba39a7ead70322c91b1bd177881f7a200fb291c02bf338d592de409062c7763`.
