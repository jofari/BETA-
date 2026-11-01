# VC6 V1 — étape A : découverte et inventaire des données

Faite le 01/11/2026 (UTC). **Aucun code de BETA n'a été modifié** pendant cette étape. Les
chiffres de la section 2 viennent du script `VC6_V1/etape_a_inventaire.py`, qui lit les sources
en lecture seule et écrit seulement les copies figées (`data/vc6_v1/sources_figees/`). Sa sortie
complète est dans `VC6_V1/sources_figees.json`.

## 1. Le code existant

### Temps 1 – justesse (T1J, mesurée le 24/10/2026)

- Module `beta/temps1_justesse/` :
  - `regles.py` : règles gelées (empreinte `c0959f429d9dcf8f`) ;
  - `donnees.py` : lecture des séries `beta.marches` ;
  - `detecteurs.py` : détecteurs, dont la SMA 200 (`sma(close, 200)` : bear si clôture < SMA 200) ;
  - `juge.py` : le juge (`juger`, `premier_trimestre`, `sigma_sp_ref`) ;
  - `mesures.py` : `mesurer`, qui calcule f_entrée, f_sortie, fausses alertes, bascules et justesse ;
  - `verdict.py`, `campagne.py`, `rapport.py`.
- Commits : code `8afdbe7`, mesure `c52aa87`. Commande : `scripts/temps1_justesse.py`.
  Préenregistrement : `scripts/preenregistrer_t1j.py`, id `T1J`. Rapport :
  `temps1_justesse/RAPPORT_JUSTESSE.md`.

### Temps 1 – fiabilité (T1F, diagnostic mesuré le 24/10/2026)

- Module `beta/temps1_fiabilite/` :
  - `regles.py` : empreinte `77b7f85b49132d77` ;
  - `nulls.py` : le test contre le hasard de même agitation. Test 1 : durées permutées entre
    épisodes du même état. Test 1 bis : décalage circulaire dans [90, N − 90] ;
  - `campagne.py` : tirages, p_latence, p_justesse, test 2 ;
  - `rapport.py`.
- Commit du code `590688e`. Préenregistrement : `temps1_fiabilite/PREENREGISTREMENT.md`.
  Commande : `scripts/temps1_fiabilite.py`. Rapport : `temps1_fiabilite/RAPPORT_FIABILITE.md`.
- Aucun de ces deux modules n'a changé depuis ces commits (`git log`).

### Nulls circulaire et segments (règle D4)

- `beta/invest/nulls.py` :
  - `decalage_circulaire` : τ uniforme dans [m, N − m], m = 90 ;
  - `melange_segments` : les segments de valeur constante sont remélangés, sans jamais en recoller
    deux de même valeur ;
  - `p_value` : (1 + nombre de tirages au moins aussi bons) / (1 + B) ;
  - `p_retenue` : la pire des deux p, puisqu'il faut battre les deux nulls ;
  - `verdict` : réel si p < 0,05, non concluant si p < 0,20, hasard sinon ;
  - `bh_q` : Benjamini-Hochberg, informatif ;
  - `flux` : graines dérivées par clé.
- Ils sont appliqués à l'Ulcer contre le témoin d'exposition constante dans le Test invest (TI1) :
  `beta/invest/campagne.py` (`_nulls`, `evaluer`), `beta/invest/moteur.py` (`temoin_constant`,
  `rendement`, `funding_panier`), `beta/invest/metriques.py` (`standard`, avec l'Ulcer).
- T1F lit aussi D4 par `beta.invest.nulls.verdict`.

### Compteur d'essais de la famille invest

`beta/protocole/experiences.py`, `compteur(famille="invest")`. Valeur lue le 01/11/2026 :
- **invest : 54** ;
- global (`compteur_total`) : 147 ;
- trading actif : 93.

### Sharpe déflaté et PBO (S10)

- Sharpe déflaté, porte S2 : `beta/stats/multitest.py` (`sharpe_degonfle(rendements, n_essais)`,
  `sharpe_attendu_du_maximum`), appelé par `beta/stats/batterie.py`.
- PBO, porte S10 :
  - `beta/stats/cscv.py` (`pbo`, CSCV) ;
  - `beta/stats/pbo.py` (`calculer` : S = 16 blocs contigus, Sharpe, 252 périodes par an) ;
  - seuil `batterie.SEUIL_PBO` = 0,20.
- Côté invest (invariant 13) : `preenregistrer(..., n_configurations > 1)` refuse une règle de
  décision sans clé `pbo`.

## 2. Inventaire des données

Les séries crypto du lake sont des **perpétuels Binance USDT-M**. Dates en UTC.

### Clôtures journalières BTC, ETH, SOL

| série | origine | début réel | fin réelle | trous |
|---|---|---|---|---|
| BTC comptant Bitstamp | DS1, table `bougies_1d` (lue par `beta.marches` sous le nom `BTC_DS1`) | 18/08/2011 | 31/10/2026 dans la base ; 30/10/2026 dans `data/marches/BTC_DS1-1d.parquet`, recopié chaque soir à 23:10 UTC | 0 jour manquant. 33 jours à volume nul (30 en 2011, 3 en 2015, le dernier le 08/01/2015) |
| BTC comptant Coinbase | DS1, table `bougies_1d` | 20/07/2015 | 31/10/2026 | 0 jour manquant |
| BTC perpétuel | lake `BTC_USDT_USDT-1d` | 08/09/2019 | 31/10/2026 | 0 jour manquant |
| ETH perpétuel | lake `ETH_USDT_USDT-1d` | 27/11/2019 | 31/10/2026 | 0 jour manquant |
| SOL perpétuel | lake `SOL_USDT_USDT-1d` | 14/09/2020 | 31/10/2026 | 0 jour manquant |

- **Aucune clôture ETH ni SOL au comptant**, ni dans BETA ni dans DS1. DS1 n'a que le BTC
  (Bitstamp et Coinbase).
- Le parquet `BTC_DS1` et la base DS1 sont identiques sur leurs 5 553 dates communes (écart
  maximal 0).

### Bougies 5 min BTC, ETH, SOL

| série | début réel | fin réelle | trous |
|---|---|---|---|
| BTC perpétuel (lake) | 08/09/2019 17:55 | 01/11/2026 00:15 (copie figée : 31/10/2026 23:55) | 0 barre manquante sur 751 753. 86 barres plates à volume nul : 55 aux trois premiers jours de cotation (08-10/09/2019), et des arrêts de Binance le 02/03/2021 (11), le 01/05/2022 (5), le 28/05/2022 (7), le 12/09/2023 (3), le 28/10/2024 (2) et le 29/08/2025 (3) |
| ETH perpétuel (lake) | 27/11/2019 07:45 | idem | 0 barre manquante sur 728 835. 72 barres à volume nul : 41 aux premiers jours de cotation (27-29/11/2019), plus les mêmes arrêts |
| SOL perpétuel (lake) | 14/09/2020 07:00 | idem | 0 barre manquante sur 644 748. 47 barres à volume nul : mêmes arrêts, plus 16 le 28/10/2024 et 2 le 29/01/2025 |

- **Les bougies 5 min du BTC ne remontent PAS à 2014.** La plus ancienne date du 08/09/2019 à
  17:55 UTC, à la cotation du perpétuel.
- BETA et DS1 n'ont aucune autre série 5 min du BTC. DS1 n'a que des bougies 1d. L'historique
  public Binance (`vision`) a des aggTrades agrégés à la minute, mais seulement depuis le
  31/12/2019 et seulement sur le perpétuel.
- Contrôle : pour les trois paires, la bougie 1d du 31/10/2026 est l'agrégat exact des 288 barres
  5 min de ce jour (clôture, plus haut, plus bas, volume).

### Funding des perpétuels BTC, ETH, SOL

| série | début réel | fin réelle | trous |
|---|---|---|---|
| BTC | 10/09/2019 08:00 | 01/11/2026 00:00 | 7 827 règlements, tous à 8 h d'écart (00:00, 08:00, 16:00), aucun écart > 8 h |
| ETH | 27/11/2019 08:00 | 01/11/2026 00:00 | 7 593 règlements, tous à 8 h d'écart, aucun écart > 8 h |
| SOL | 13/09/2020 16:00 | 01/11/2026 00:00 | 6 794 règlements, à 8 h d'écart sauf pendant le krach de FTX (voir ci-dessous) ; aucun écart > 8 h |

- Pendant le krach de FTX, du 09/11/2022 20:00 au 18/11/2022 08:00, le funding SOL a été réglé
  plus souvent : 98 intervalles de 2 h et 3 de 4 h. Le taux a atteint 2 % par règlement en valeur
  absolue, le 09/11/2022 à 20:00.
- Il n'y a aucun funding avant la cotation des perpétuels : rien pour le BTC avant le 10/09/2019.

### Marge de maintenance des perpétuels (exchange de référence)

**ABSENTE.** BETA et DS1 n'ont aucune série ni table de marge de maintenance.
- Les scripts de recherche VC6 du 19-20/10, hors dépôt (`/root/rapports/2026-10-20_relecture-vc6/`),
  utilisaient une constante écrite à la main : 0,4 % pour le BTC ou 0,5 %. Ce n'est pas une source.
- Binance publie ses paliers (par tranche de notionnel) via une API authentifiée. Je ne connais pas
  d'historique public : **à vérifier**.

### Or (XAU) journalier : quatre sources, aucune choisie

| série | origine | début réel | fin réelle | trous |
|---|---|---|---|---|
| `XAU_LBMA` | fixing LBMA PM, World Gold Council (`beta.marches`) | 01/01/1970 | 30/10/2026 | 79 jours lun-ven sans valeur. 18 écarts de plus de 4 jours (fin d'année, Pâques), 6 jours au plus. Aucune valeur le week-end |
| `XAU_SPOT` | comptant Dukascopy BID, agrégé par jour UTC (`beta.marches`) | 05/05/2003 | 30/10/2026 | 20 jours lun-ven sans valeur, aucun écart de plus de 4 jours. 1 206 valeurs un week-end : le dimanche soir, quand le marché rouvre |
| `XAUUSD` | yfinance GC=F, future COMEX continu (lake) | 04/01/2010 | 30/10/2026 | 157 jours lun-ven sans valeur (fériés US). 1 écart de plus de 4 jours (26-31/10/2012, ouragan Sandy). 40 jours à volume nul |
| `XAU` perpétuel | Binance XAUUSDT (lake) | 11/12/2025 | 31/10/2026 | 7 j / 7, 0 jour manquant |

### ETF monde (MSCI World ou ACWI) journalier

| série | origine | début réel | fin réelle | trous |
|---|---|---|---|---|
| URTH | iShares MSCI World ETF, yfinance (lake `MSCIWORLD`) | 12/01/2012 | 30/10/2026 | 140 jours lun-ven sans valeur (fériés US). 1 écart de plus de 4 jours (Sandy, 2012) |

- Les premières années de URTH sont illiquides. 198 séances ont un volume nul (150 en 2012, 40 en
  2013, 7 en 2014, 1 en 2015, la dernière le 16/10/2015) et 281 barres sont plates (OHLC égaux).
- **ACWI : absent**, ni dans le lake ni dans `beta.marches`. L'indice MSCI World lui-même n'y est
  pas non plus.

## 3. Date de fin figée et hash

- **Date de fin des données : 31/10/2026**, dernière clôture UTC complète au moment du gel
  (01/11/2026, 17:03 UTC).
- Copies figées dans `data/vc6_v1/sources_figees/`, hors git comme tout `data/`.
- SHA-256 de chaque copie, et de chaque fichier source tel qu'il était au gel : table de
  `VC6_V1/spec_figee.md` et `VC6_V1/sources_figees.json`.
- Le BTC Bitstamp est copié depuis la base DS1, qui a déjà le 31/10. Il est lu par la même
  fonction que `beta.marches` (`sources.ds1_bougies_1d`). Le parquet `BTC_DS1` n'aura le 31/10
  qu'après le passage de 23:10 UTC.

## 4. Points relevés pour la suite (rien n'est tranché)

1. **Marge de maintenance absente.** La règle « sécurité de liquidation » en a besoin.
2. **ACWI absent.** URTH est présent, et la spec dit « MSCI World ou ACWI ».
3. **« Contrôle HAR » introuvable.**
   - Aucune étape de ce nom n'existe dans BETA, `DECISIONS.md`, `CHANTIERS.md`, les rapports ou
     les sessions précédentes.
   - Il n'existe que deux scripts de recherche, non préenregistrés, du 16 au 20/10 :
     - `beta/strategies/voie_c6_indicateurs.py` : HAR-RV et EGARCH sur l'OHLC journalier,
       Garman-Klass, fenêtre glissante de 250 jours ;
     - `beta/strategies/voie_c6_vol.py` : QLIKE et Diebold-Mariano contre la vol 30 jours.
   - Aucun n'utilise les bougies 5 min. σ̂i n'est donc pas encore défini.
4. **ETH et SOL n'existent qu'en perpétuel.** Pour ces deux actifs, la seule « clôture » est
   celle du perpétuel.
5. **Trois sources de BTC journalier** : Bitstamp au comptant (2011+), Coinbase (2015+) et le
   perpétuel Binance (2019+). T1J a jugé le BTC sur Bitstamp. La spec ne dit pas laquelle fixe
   le mode global.
6. **Quatre sources d'or**, et la spec ne dit pas laquelle utiliser.
7. **Robustesse BTC depuis 2014.**
   - Il n'y a pas de 5 min avant le 08/09/2019. La spec prévoit ce cas : écart-type 30 jours.
   - Il n'y a pas non plus de funding avant le 10/09/2019, ni de marge de maintenance. Ce cas
     n'est pas prévu : le filtre de financement, le coût du levier et la sécurité de liquidation
     de la « Variante expo vol » sont donc à trancher avant 2019.
8. **PBO (invariant 13).**
   - La spec choisit entre réglages : « sizing de la meilleure des deux », remplacement de la
     poche baissière.
   - Or `preenregistrer()` refuse un préenregistrement invest qui choisit parmi plusieurs
     réglages sans clé `pbo` dans sa règle de décision.
   - La spec ne parle pas de PBO.
9. Les années illiquides de URTH (2012-2015) ne touchent pas la période principale (2021+).
