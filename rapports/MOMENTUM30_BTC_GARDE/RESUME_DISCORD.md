# 🟢 Momentum trente jours sur le BTC avec garde de baisse — rapport du programme — 2026-11-19

**Verdict au registre : MOMENTUM30_BTC_GARDE INFIRMÉE** (issue attendue : infirmee). Exploration, pas preuve : période déjà vue par MOMENTUM30_BTC, relecture de Jonas en attente.
État du calcul : 9 contrôles sur 9 passés.

## Rendements du 2019-10-09 au 2024-12-31, tous coûts déduits
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
garde 20 %              +585.1 %  +44.4 %    1.02  -55.2 %    27.6   0.55   142
momentum sans garde     +896.9 %  +55.1 %    1.16  -47.4 %    20.3   0.57   142
hold perpétuel          +449.7 %  +38.5 %    0.80  -78.9 %    43.8   1.00     0
témoin expo cste        +258.6 %  +27.6 %    0.80  -53.5 %    25.2   0.55     0
```
- (a) Sharpe garde > hold : 1.019 contre 0.795 → oui
- (b) CAGR garde ≥ hold : +44.4 % contre +38.5 % → oui
- (c) MDD garde moins profond que hold : -55.2 % contre -78.9 % → oui
- (d) MDD garde moins profond que sans garde : -55.2 % contre -47.4 % → NON
- (e) Sharpe garde ≥ sans garde : 1.019 contre 1.163 → NON
- nulls (Sharpe, B = 1000) : p circulaire 0.041, p segments 0.060 → **p retenue 0.060** (non concluant)

Garde : 2 déclenchement(s), 38 jours coupés.

## Par année (sans effet)
```
année        garde   sans g.      hold   expo  basc.
2019       -10.3 %   -10.3 %   -12.0 %   0.36      4
2020      +276.4 %  +276.4 %  +302.7 %   0.69     19
2021        +3.0 %   +49.9 %   +59.6 %   0.45     27
2022       -40.3 %   -40.3 %   -64.2 %   0.34     38
2023      +153.9 %  +153.9 %  +155.9 %   0.67     17
2024       +29.9 %   +29.9 %  +121.1 %   0.64     37
```

## Robustesse (sans effet)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
seuil 15 %              +642.9 %  +46.7 %    1.08  -48.9 %    22.0   0.53   142
seuil 25 %              +685.8 %  +48.3 %    1.07  -48.6 %    22.0   0.56   142
comptant garde         +1097.6 %  +60.7 %    1.27  -46.0 %    20.4   0.55   142
comptant sans garde    +1724.2 %  +74.1 %    1.42  -46.0 %    19.1   0.57   142
hold comptant          +1045.4 %  +59.3 %    1.01  -76.7 %    39.8   1.00     0
frais 12 pb             +529.2 %  +42.1 %    0.98  -56.9 %    28.7   0.55   142
```

## Compteur
- invest 63 (N = 63 au préenregistrement), trading 99

## Fichiers
- `rapports/MOMENTUM30_BTC_GARDE/RAPPORT.md` (joint) ; code `204e238` ; run 8dc5d22facd5
