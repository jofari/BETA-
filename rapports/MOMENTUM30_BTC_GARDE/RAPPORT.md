# Momentum trente jours sur le BTC avec garde de baisse — rapport du programme — 2026-11-19

**Verdict au registre : MOMENTUM30_BTC_GARDE INFIRMÉE.** Issue attendue : infirmee ; conforme : oui.
**Exploration, pas recherche** : période déjà vue par MOMENTUM30_BTC, hypothèse de Claude, relecture de Jonas en attente.
État du calcul : 9 contrôles sur 9 passés (pastille = état du calcul, pas jugement du résultat). Code `204e238`, run `8dc5d22facd5`.

## Préenregistrement (mot pour mot, registre)
- Id `MOMENTUM30_BTC_GARDE`, famille invest, préenregistrée le 2026-11-19 (N invest = 63), issue attendue : infirmee.
- Hypothèse : Sur le perpetuel BTC/USDT Binance en quotidien, l'exposition du momentum trente jours de MOMENTUM30_BTC coupee par une garde de baisse de 20 % (sortie quand la cloture tombe 20 % sous le plus haut de l'episode investi, retour seulement au signal neuf suivant) bat le buy-and-hold du meme perpetuel sur les rendements du 09/10/2019 au 31/12/2024, tous couts deduits, en Sharpe, en CAGR et en drawdown maximal, a un drawdown maximal moins profond que le meme momentum sans garde et un Sharpe au moins egal au sien, et son placement dans le temps bat les deux nulls du test invest (p retenue < 0,05).
- Règle de décision : confirmée = (a) Sharpe_garde > Sharpe_hold ET (b) CAGR_garde >= CAGR_hold ET (c) MDD_garde moins profond que MDD_hold ET (d) MDD_garde moins profond que MDD du momentum sans garde ET (e) Sharpe_garde >= Sharpe du momentum sans garde, ET p retenue des deux nulls (decalage circulaire, melange des segments ; Sharpe ; B = 1000 ; p = la plus grande) < 0,05 ; indécidable = les cinq conditions vraies ET 0,05 <= p retenue < 0,20, ou p incalculable ; infirmée = une des cinq conditions fausse, ou p retenue >= 0,20.
- Décidé par : Claude, 2026-11-19, a la demande de Jonas (« je te lance un backtest de cette theorie, entre-la dans BETA en candidate invest ») ; hypothese, regles et seuil = proposition de Claude ; nuit entre gel et lancement sautee ; relecture de Jonas en attente
- Déjà connu : MOMENTUM30_BTC mesuree le 10/11 sur EXACTEMENT cette periode : CONFIRMEE, Sharpe 1,16 / CAGR +55 % / MDD -47 % contre hold 0,80 / +38 % / -79 %, p retenue 0,027 ; tableaux par annee et sous-periodes lus ; drawdowns episode par episode NON calcules, le seuil de 20 % n'en vient pas (budget -25 % des voies C moins 5 points d'ecart d'une journee). Diagnostic de la veille des voies C du 19/11. Connaissance generale de l'histoire du BTC (mars 2020, mai 2021, 2022), nommee. Litterature verifiee le 19/11 : Kaminski-Lo 2014 (contre sauf inertie), Han-Zhou-Zhu 2014 (pour, avant frais, actions). Aucun chiffre de cette strategie ni de ses variantes calcule avant le gel. EXPLORATION : periode deja vue par MOMENTUM30_BTC.
- Empreintes gelées : {'spec': 'de4da4a9dde68f93', 'code': 'caab1564b90490bb', 'code_base': '7ef4d7985b440c5a'} (vérifiées avant la mesure).

## Données lues
- BTC perpétuel 1d : 1942 bougies du 2019-09-08 au 2024-12-31 ; rendements du 2019-10-09 au 2024-12-31 (1911 jours) ; 7882 règlements de funding.
- Empreintes : clôtures `157135862b7937f2`, funding journalier `bf900c0af03e8697`, DFF `287e941600d99919`.

## Résultat (tous coûts déduits : 6 pb par bascule, funding, cash au DFF)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
garde 20 %              +585.1 %  +44.4 %    1.02  -55.2 %    27.6   0.55   142
momentum sans garde     +896.9 %  +55.1 %    1.16  -47.4 %    20.3   0.57   142
hold perpétuel          +449.7 %  +38.5 %    0.80  -78.9 %    43.8   1.00     0
témoin expo cste        +258.6 %  +27.6 %    0.80  -53.5 %    25.2   0.55     0
```
Sharpe quotidien net de rf × √365 ; MDD et Ulcer en % ; expo = exposition moyenne ; basc. = bascules.
Garde : 2 déclenchement(s), 38 jours coupés. Coûts : frais +8.5 %, funding +56.0 %. Sharpe déflaté au compteur invest (63) : 0.487 (informatif).

## Règle de décision, condition par condition
- (a) Sharpe garde > hold : 1.019 contre 0.795 → oui
- (b) CAGR garde ≥ hold : +44.4 % contre +38.5 % → oui
- (c) MDD garde moins profond que hold : -55.2 % contre -78.9 % → oui
- (d) MDD garde moins profond que sans garde : -55.2 % contre -47.4 % → NON
- (e) Sharpe garde ≥ sans garde : 1.019 contre 1.163 → NON
- nulls (Sharpe, B = 1000) : p circulaire 0.041, p segments 0.060 → **p retenue 0.060** (non concluant)

**→ INFIRMÉE** (`moteur.verdict`).

## Déclenchements de la garde
- coupé du 2021-01-22 au 2021-02-06 (16 j)
- coupé du 2021-03-01 au 2021-03-22 (22 j)

## Par année civile (sans effet)
```
année        garde   sans g.      hold   expo  basc.
2019       -10.3 %   -10.3 %   -12.0 %   0.36      4
2020      +276.4 %  +276.4 %  +302.7 %   0.69     19
2021        +3.0 %   +49.9 %   +59.6 %   0.45     27
2022       -40.3 %   -40.3 %   -64.2 %   0.34     38
2023      +153.9 %  +153.9 %  +155.9 %   0.67     17
2024       +29.9 %   +29.9 %  +121.1 %   0.64     37
```

## Sous-périodes (sans effet)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
garde 2019-10-09        +107.7 %  +25.4 %    0.72  -55.2 %    29.8   0.48    88
sans  2019-10-09        +202.2 %  +40.8 %    0.96  -47.4 %    21.5   0.52    88
hold  2019-10-09         +18.4 %   +5.4 %    0.44  -78.9 %    40.1   1.00     0
garde 2023-01-01        +229.9 %  +81.5 %    1.55  -36.4 %    12.6   0.65    54
sans  2023-01-01        +229.9 %  +81.5 %    1.55  -36.4 %    12.6   0.65    54
hold  2023-01-01        +364.2 % +115.2 %    1.71  -29.4 %    11.6   1.00     0
```

## Robustesse (sans effet, aucune variante n'est choisie)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
seuil 15 %              +642.9 %  +46.7 %    1.08  -48.9 %    22.0   0.53   142
seuil 25 %              +685.8 %  +48.3 %    1.07  -48.6 %    22.0   0.56   142
comptant garde         +1097.6 %  +60.7 %    1.27  -46.0 %    20.4   0.55   142
comptant sans garde    +1724.2 %  +74.1 %    1.42  -46.0 %    19.1   0.57   142
hold comptant          +1045.4 %  +59.3 %    1.01  -76.7 %    39.8   1.00     0
frais 12 pb             +529.2 %  +42.1 %    0.98  -56.9 %    28.7   0.55   142
```

## Contrôles de cohérence
- ✅ hold sans cout = ratio des clotures — 10.4536303109 contre 10.4536303109
- ✅ decalage circulaire de 0 jour = observe — 1.1632895964 = 1.1632895964
- ✅ causalite : exposition(prefixe) = prefixe(exposition), 3 coupures — coupures 400, 1000, N-1
- ✅ aucun NaN dans E, R_B, phi, rf
- ✅ 3 reglements de funding par jour — 0 jour(s) hors norme
- ✅ causalite de la garde : exposition(prefixe) = prefixe(exposition), 3 coupures — coupures 400, 1000, N-1
- ✅ garde : n'ajoute jamais d'exposition au momentum (e_garde <= e_base)
- ✅ garde : coupe = base - garde, jour par jour
- ✅ aucun NaN dans l'exposition gardee

## Compteur d'essais
- MOMENTUM30_BTC_GARDE (invest) : N = 63 au préenregistrement ; aujourd'hui : invest 63, trading 99.

## Fichiers
- `MOMENTUM30_BTC_GARDE/PREENREGISTREMENT.md` (gelé), `beta/momentum30_btc_garde/moteur.py`, `scripts/mesurer_momentum30_btc_garde.py`, `data/momentum30_btc_garde/resultats.json`.
