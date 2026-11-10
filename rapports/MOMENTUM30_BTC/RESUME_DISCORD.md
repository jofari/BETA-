# 🟢 Momentum trente jours sur le BTC (exposition long-only) — rapport du programme — 2026-11-10

**Verdict au registre : MOMENTUM30_BTC CONFIRMÉE** (issue attendue : infirmee). Proposition de Claude du 10/11, relecture de Jonas en attente → exploration, pas preuve.
État du calcul : 5 contrôles sur 5 passés.

## Stratégie contre hold du perpétuel BTC, rendements du 2019-10-09 au 2024-12-31, tous coûts déduits
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
stratégie L30           +896.9 %  +55.1 %    1.16  -47.4 %    20.3   0.57   142
hold perpétuel          +449.7 %  +38.5 %    0.80  -78.9 %    43.8   1.00     0
témoin expo cste        +269.1 %  +28.3 %    0.80  -54.9 %    26.1   0.57     0
```
- (a) Sharpe stratégie > hold : 1.163 contre 0.795 → oui
- (b) CAGR stratégie ≥ hold : +55.1 % contre +38.5 % → oui
- (c) MDD moins profond : -47.4 % contre -78.9 % → oui
- nulls (Sharpe, B = 1000) : p circulaire 0.009 (médiane nulle 0.51, q95 1.02), p segments 0.027 (médiane nulle 0.58, q95 1.08) → **p retenue 0.027** (reel)

## Par année (sans effet)
```
année     stratégie      hold   expo  basc.  jours
2019        -10.3 %   -12.0 %   0.36      4     84
2020       +276.4 %  +302.7 %   0.69     19    366
2021        +49.9 %   +59.6 %   0.55     27    365
2022        -40.3 %   -64.2 %   0.34     38    365
2023       +153.9 %  +155.9 %   0.67     17    365
2024        +29.9 %  +121.1 %   0.64     37    366
```

## Robustesse (sans effet)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
fenêtre 14 j            +667.1 %  +47.6 %    1.05  -52.1 %    25.2   0.56   230
fenêtre 60 j (dès 11/2019)  +511.5 %  +42.1 %    0.94  -60.4 %    30.1   0.58    89
comptant (φ = 0)       +1724.2 %  +74.1 %    1.42  -46.0 %    19.1   0.57   142
hold comptant          +1045.4 %  +59.3 %    1.01  -76.7 %    39.8   1.00     0
frais 12 pb             +815.5 %  +52.6 %    1.13  -48.6 %    20.9   0.57   142
```

## Compteur
- invest 62 (N = 62 au préenregistrement), trading 99

## Fichiers
- `rapports/MOMENTUM30_BTC/RAPPORT.md` (joint) ; code `76f8ec1` ; run 4b650c8870ab

## Avis de Claude — ce n'est PAS le programme

Le verdict et tous les chiffres ci-dessus sortent de `scripts/mesurer_momentum30_btc.py`. Ce qui suit est une lecture, pas un résultat.

- **Statut : exploration, pas recherche.** L'hypothèse, le mécanisme et la règle de décision ont été écrits par Claude le 10/11 à la demande de Jonas, et la nuit entre le gel et le lancement a été sautée. Tant que Jonas n'a pas relu le préenregistrement (`MOMENTUM30_BTC/PREENREGISTREMENT.md`), ce CONFIRMÉE n'est pas une preuve : c'est une question qui mérite d'être posée proprement.
- **Snooping partiel assumé.** La fenêtre de 30 jours vient d'ARIT (05/09), mesurée sur les mêmes clôtures BTC 2019-2024 (et sur le hold-out 2025+). Le lookback n'a pas été choisi ici, mais il a été choisi sur ces données-là. Le Sharpe déflaté au compteur invest (62 essais) vaut 0,62 pour la stratégie, sous le seuil de 0,95 que la batterie de trading exigerait (informatif : la règle invest ne le demande pas).
- **D'où vient l'écart.** Par année, la stratégie fait MOINS bien que le hold 4 années sur 6 (2020, 2021, 2023, 2024 : retard du signal). Elle gagne tout en 2022 (−40 % contre −64 %) et sur 2019. Sur 2023-2024, le hold est devant en Sharpe (1,71 contre 1,55) et en CAGR. L'edge mesuré est « éviter le grand bear », pas « battre le hold chaque année ». C'est cohérent avec le mécanisme écrit avant (le signal paie par son retard), et c'est fragile : un seul épisode porte la condition (b).
- **Les nulls passent de justesse** (p retenue 0,027 ; le mélange des segments est à 0,027, le décalage circulaire à 0,009). Avec 142 bascules sur 1 910 jours, les deux nulls ont une distribution large (q95 ≈ 1,0-1,1 de Sharpe) : le placement des périodes d'exposition est meilleur que le hasard, mais pas de beaucoup.
- **Le funding pèse** : 61 points de rendement sur la période pour la stratégie, 74 pour le hold. Au comptant (φ = 0), les deux montent et l'écart se garde (robustesse).
- **2024 est l'année de l'ETF** : +30 % contre +121 % pour le hold. Si l'institutionnalisation rend le marché plus efficient, c'est là qu'on le verra. Le hold-out 2025+ reste scellé ; c'est lui qui tranchera, une seule fois, sur décision de Jonas.
- **Ce que je ferais ensuite (à décider par Jonas)** : (1) relire le préenregistrement et le qualifier (recherche ou exploration) ; (2) ne rien régler ; (3) si gardé : paper BTC sur le perpétuel (décision 00:00 UTC, même règle) pour roder l'exécution, et ouverture unique du hold-out 2025+ plus tard, jamais après un réglage.
