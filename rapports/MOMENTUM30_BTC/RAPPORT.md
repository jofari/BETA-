# Momentum trente jours sur le BTC (exposition long-only) — rapport du programme — 2026-11-10

**Verdict au registre : MOMENTUM30_BTC CONFIRMÉE.** Issue attendue : infirmee ; conforme : non.
État du calcul : 5 contrôles sur 5 passés (pastille = état du calcul, pas jugement du résultat). Code `76f8ec1`, run `4b650c8870ab`.

## Préenregistrement (mot pour mot, registre)
- Id `MOMENTUM30_BTC`, famille invest, préenregistrée le 2026-11-10 (N invest = 62), issue attendue : infirmee.
- Hypothèse : Sur le perpetuel BTC/USDT Binance en quotidien, une exposition long-only valant 1 quand close(t)/close(t-30)-1 > 0 et 0 sinon, decidee a la cloture du jour t et appliquee au rendement du jour t+1, bat le buy-and-hold du meme perpetuel sur les rendements du 09/10/2019 au 31/12/2024, tous couts deduits (6 pb par bascule, funding paye par tout le long, cash au DFF), en Sharpe ET en CAGR, avec un drawdown maximal moins profond, et son placement dans le temps bat les deux nulls du test invest (p retenue < 0,05).
- Métrique primaire : Sharpe quotidien net de rf x racine(365), CAGR base 365 et MDD de la strategie contre ceux du hold du perpetuel BTC (meme periode, meme funding) ; p retenue des nulls sur le Sharpe (beta.invest.nulls, B = 1000, graine 0)
- Règle de décision : confirmée = Sharpe_strategie > Sharpe_hold ET CAGR_strategie >= CAGR_hold ET MDD_strategie moins profond que MDD_hold, ET p retenue des deux nulls (decalage circulaire, melange des segments ; Sharpe ; B = 1000 ; p = la plus grande) < 0,05 ; indécidable = les trois conditions vraies ET 0,05 <= p retenue < 0,20, ou p incalculable ; infirmée = une des trois conditions fausse, ou p retenue >= 0,20.
- Décidé par : Claude, 2026-11-10, a la demande de Jonas (« theorise et teste une strategie rentable sur le BTC ») ; hypothese et regles = proposition de Claude, relecture de Jonas en attente ; nuit entre gel et lancement sautee a sa demande
- Déjà connu : ARIT 05/09/2026 (research/pertinence_donnees_2026-09-05) : long-only quotidien, signe du rendement sur L jours, 5 pb par bascule, SANS funding, 2019-09 -> 2026-09 (hold-out de BETA inclus) : Sharpe BTC L14 1,01 / L30 1,00 / L60 0,88 contre 0,55 pour le hold ; train < 2023 1,03, 2023+ 0,98. L = 30 fixe AVANT ce test par l'idee I16 (11/09). BETA invest : TI1 momentum BTC 126 j seul = hasard ; T1J/T1F MOM126 et SMA200 sur BTC non solides ; VC3/VC5 confirmees avec momentum 126 j parmi 5 votes en allocation. BETA trading : 9 hypotheses contrariennes infirmees, aucune continuation mesuree. Litterature verifiee le 10/11 : Moskowitz-Ooi-Pedersen 2012 (pour), Liu-Tsyvinski 2021 (pour), Grobys-Sapkota 2019 (contre). Regarde avant le gel sans rendement calcule : couverture des series, dates, moyenne du funding du train (0,0134 %/8 h). Aucun chiffre de la strategie, du hold ni du temoin calcule avant le gel.
- Empreintes gelées : spec `0f0e05c1e4c3f53b`, code `7ef4d7985b440c5a` (vérifiées avant la mesure).

## Données lues
- BTC perpétuel 1d : 1942 bougies du 2019-09-08 au 2024-12-31 ; rendements du 2019-10-09 au 2024-12-31 (1911 jours) ; 7855 règlements de funding.
- Empreintes : clôtures `157135862b7937f2`, funding journalier `bf900c0af03e8697`, DFF `287e941600d99919`.

## Résultat (tous coûts déduits : 6 pb par bascule, funding, cash au DFF)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
stratégie L30           +896.9 %  +55.1 %    1.16  -47.4 %    20.3   0.57   142
hold perpétuel          +449.7 %  +38.5 %    0.80  -78.9 %    43.8   1.00     0
témoin expo cste        +269.1 %  +28.3 %    0.80  -54.9 %    26.1   0.57     0
```
Rendement et CAGR en %, Sharpe quotidien net de rf × √365, MDD en %, Ulcer en %, expo = exposition moyenne, basc. = nombre de bascules.
Coûts de la stratégie sur la période : frais +8.5 %, funding +60.7 % (hold : funding +73.6 %). Sharpe déflaté au compteur invest (62) : stratégie 0.621, hold 0.298 (informatif).

## Règle de décision, condition par condition
- (a) Sharpe stratégie > hold : 1.163 contre 0.795 → oui
- (b) CAGR stratégie ≥ hold : +55.1 % contre +38.5 % → oui
- (c) MDD moins profond : -47.4 % contre -78.9 % → oui
- nulls (Sharpe, B = 1000) : p circulaire 0.009 (médiane nulle 0.51, q95 1.02), p segments 0.027 (médiane nulle 0.58, q95 1.08) → **p retenue 0.027** (reel)

**→ CONFIRMÉE** (`moteur.verdict`).

## Par année civile (sans effet)
```
année     stratégie      hold   expo  basc.  jours
2019        -10.3 %   -12.0 %   0.36      4     84
2020       +276.4 %  +302.7 %   0.69     19    366
2021        +49.9 %   +59.6 %   0.55     27    365
2022        -40.3 %   -64.2 %   0.34     38    365
2023       +153.9 %  +155.9 %   0.67     17    365
2024        +29.9 %  +121.1 %   0.64     37    366
```

## Sous-périodes (sans effet)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
strat 2019-10-09        +202.2 %  +40.8 %    0.96  -47.4 %    21.5   0.52    88
hold  2019-10-09         +18.4 %   +5.4 %    0.44  -78.9 %    40.1   1.00     0
strat 2023-01-01        +229.9 %  +81.5 %    1.55  -36.4 %    12.6   0.65    54
hold  2023-01-01        +364.2 % +115.2 %    1.71  -29.4 %    11.6   1.00     0
```

## Robustesse (sans effet, aucune variante n'est choisie)
```
                       rendement     CAGR  Sharpe      MDD   Ulcer   expo basc.
fenêtre 14 j            +667.1 %  +47.6 %    1.05  -52.1 %    25.2   0.56   230
fenêtre 60 j (dès 11/2019)  +511.5 %  +42.1 %    0.94  -60.4 %    30.1   0.58    89
comptant (φ = 0)       +1724.2 %  +74.1 %    1.42  -46.0 %    19.1   0.57   142
hold comptant          +1045.4 %  +59.3 %    1.01  -76.7 %    39.8   1.00     0
frais 12 pb             +815.5 %  +52.6 %    1.13  -48.6 %    20.9   0.57   142
```

## Contrôles de cohérence
- ✅ hold sans cout = ratio des clotures — 10.4536303109 contre 10.4536303109
- ✅ decalage circulaire de 0 jour = observe — 1.1632895964 = 1.1632895964
- ✅ causalite : exposition(prefixe) = prefixe(exposition), 3 coupures — coupures 400, 1000, N-1
- ✅ aucun NaN dans E, R_B, phi, rf
- ✅ 3 reglements de funding par jour — 0 jour(s) hors norme

## Compteur d'essais
- MOMENTUM30_BTC (invest) : N = 62 au préenregistrement ; aujourd'hui : invest 62, trading 99.

## Fichiers
- `MOMENTUM30_BTC/RECHERCHE.md` (question, littérature, mécanisme, données, prédiction), `MOMENTUM30_BTC/PREENREGISTREMENT.md` (gelé), `beta/momentum30_btc/moteur.py`, `scripts/mesurer_momentum30_btc.py`, `data/momentum30_btc/resultats.json`.
## Avis de Claude — ce n'est PAS le programme

Le verdict et tous les chiffres ci-dessus sortent de `scripts/mesurer_momentum30_btc.py`. Ce qui suit est une lecture, pas un résultat.

- **Statut : exploration, pas recherche.** L'hypothèse, le mécanisme et la règle de décision ont été écrits par Claude le 10/11 à la demande de Jonas, et la nuit entre le gel et le lancement a été sautée. Tant que Jonas n'a pas relu le préenregistrement (`MOMENTUM30_BTC/PREENREGISTREMENT.md`), ce CONFIRMÉE n'est pas une preuve : c'est une question qui mérite d'être posée proprement.
- **Snooping partiel assumé.** La fenêtre de 30 jours vient d'ARIT (05/09), mesurée sur les mêmes clôtures BTC 2019-2024 (et sur le hold-out 2025+). Le lookback n'a pas été choisi ici, mais il a été choisi sur ces données-là. Le Sharpe déflaté au compteur invest (62 essais) vaut 0,62 pour la stratégie, sous le seuil de 0,95 que la batterie de trading exigerait (informatif : la règle invest ne le demande pas).
- **D'où vient l'écart.** Par année, la stratégie fait MOINS bien que le hold 4 années sur 6 (2020, 2021, 2023, 2024 : retard du signal). Elle gagne tout en 2022 (−40 % contre −64 %) et sur 2019. Sur 2023-2024, le hold est devant en Sharpe (1,71 contre 1,55) et en CAGR. L'edge mesuré est « éviter le grand bear », pas « battre le hold chaque année ». C'est cohérent avec le mécanisme écrit avant (le signal paie par son retard), et c'est fragile : un seul épisode porte la condition (b).
- **Les nulls passent de justesse** (p retenue 0,027 ; le mélange des segments est à 0,027, le décalage circulaire à 0,009). Avec 142 bascules sur 1 910 jours, les deux nulls ont une distribution large (q95 ≈ 1,0-1,1 de Sharpe) : le placement des périodes d'exposition est meilleur que le hasard, mais pas de beaucoup.
- **Le funding pèse** : 61 points de rendement sur la période pour la stratégie, 74 pour le hold. Au comptant (φ = 0), les deux montent et l'écart se garde (robustesse).
- **2024 est l'année de l'ETF** : +30 % contre +121 % pour le hold. Si l'institutionnalisation rend le marché plus efficient, c'est là qu'on le verra. Le hold-out 2025+ reste scellé ; c'est lui qui tranchera, une seule fois, sur décision de Jonas.
- **Ce que je ferais ensuite (à décider par Jonas)** : (1) relire le préenregistrement et le qualifier (recherche ou exploration) ; (2) ne rien régler ; (3) si gardé : paper BTC sur le perpétuel (décision 00:00 UTC, même règle) pour roder l'exécution, et ouverture unique du hold-out 2025+ plus tard, jamais après un réglage.
