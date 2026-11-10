# Momentum trente jours sur le BTC — préenregistrement

- **Écrit le** : 10/11/2026 (UTC), avant tout calcul sur les vraies données. Proposition de
  Claude à la demande de Jonas du même jour (« théorise et teste une stratégie rentable sur
  le BTC et fais-la passer dans BETA »). Relecture de Jonas : en attente (voir
  `RECHERCHE.md`, entorses nommées).
- **Id au registre** : `MOMENTUM30_BTC`, famille **invest** (exposition long-only décidée à la
  clôture, appliquée le lendemain : même famille que TI1, T1A, VC6). Un seul essai, une seule
  configuration (`n_configurations = 1` : rien n'est choisi parmi plusieurs). Compteur invest
  61 → 62.
- **Code** : `beta/momentum30_btc/moteur.py` (fonctions pures), lancé par
  `scripts/mesurer_momentum30_btc.py`. Les empreintes SHA-256 de ce texte et du moteur sont
  écrites au registre ; le script refuse de tourner si l'une a changé.
- **Hold-out** : 2025-01-01 et après, jamais lu. Train seulement.

## Hypothèse

Sur le perpétuel BTC/USDT de Binance en quotidien, une exposition long-only valant 1 quand le
rendement des 30 derniers jours est strictement positif et 0 sinon, décidée à la clôture du
jour t et appliquée au rendement du jour t + 1, bat le buy-and-hold du même perpétuel sur la
même période (rendements du 09/10/2019 au 31/12/2024), tous coûts déduits (frais de bascule,
funding, cash au taux DFF), en Sharpe ET en CAGR, avec un drawdown maximal moins profond, et
son placement dans le temps vaut mieux qu'un placement aléatoire de mêmes périodes
d'exposition (nulls du test invest).

## Applications (comment le code lit les règles, écrites avant tout calcul)

1. **Données** : clôtures quotidiennes du perpétuel BTC du lake (`lecture.load("BTC", "1d")`,
   bougie datée par son ouverture, clôture = 00:00 UTC du lendemain), bornées au train par
   `holdout.borner_train`. Funding 8 h : `lecture.funding("BTC")` (horodaté au règlement).
   Taux sans risque : FRED `DFF` (`lecture.macro_globales()["fedfunds"]`).
2. **Rendement du jour D** : close(D) / close(D − 1) − 1.
3. **Signal à la clôture de t** : m(t) = close(t) / close(t − 30) − 1 (30 bougies quotidiennes).
   **Exposition du jour t + 1** : E = 1 si m(t) > 0, sinon 0. Aucune donnée de t + 1.
4. **Période** : première décision à la clôture du 08/10/2019 (30 jours après la première
   bougie du 08/09/2019) ; rendements du **09/10/2019 au 31/12/2024** (1 910 jours).
   Position de départ : l'exposition de la première décision, sans frais d'entrée (ni pour la
   stratégie, ni pour le hold).
5. **Funding du jour D** : somme des règlements de ]D 00:00 ; D + 1 00:00] UTC (trois par jour).
   Un jour sans règlement = erreur, jamais zéro. Payé par TOUT le long d'un perpétuel :
   coût du jour = E × φ(D) (un funding négatif est reçu). Le hold paie le même φ avec E = 1.
6. **Cash** : (1 − E) × rf(D), rf = DFF du dernier jour ≤ D − 1, / 100 / 365
   (`beta.invest.moteur.rf_quotidien`). Le hold n'a pas de cash.
7. **Frais** : 6 pb × |E(D) − E(D − 1)| (0,05 % taker + 0,01 % de slippage par côté, la moitié de
   l'aller-retour 0,12 % du moteur de BETA). Spread d'un tick (≈ 0,01 pb sur BTC) : ignoré.
8. **Rendement net** : R_S(D) = E R_B − 6 pb |ΔE| − E φ + (1 − E) rf (`moteur.rendement_net`).
9. **Métriques** : `beta.invest.metriques.standard` — rendement total, CAGR (base 365 jours),
   volatilité, Sharpe (quotidien, net de rf, × √365), Sharpe déflaté au compteur invest après
   cet essai (62, informatif), drawdown maximal (MDD, négatif), durée sous l'eau, Calmar, Ulcer,
   exposition moyenne, nombre de bascules. Les mêmes pour le hold et pour le témoin.
10. **Témoin exposition constante** (informatif) : E = exposition moyenne de la stratégie,
    constante, sans frais, même funding et même cash (`moteur.temoin_constant`).
11. **Nulls** (D du test invest, `beta.invest.nulls`) : la série tirée est E(D) sur les
    1 910 jours. (a) décalage circulaire, τ uniforme dans [90 ; N − 90] ; (b) mélange des
    segments (mêmes durées d'exposition et de retrait, ordre tiré au hasard, jamais deux segments
    égaux côte à côte). Chaque tirage recalcule le rendement net avec les mêmes coûts (frais
    sur les bascules de la série tirée, aucun frais le premier jour, funding et cash aux vraies
    dates). B = 1 000 par null, graine 0, flux `nulls.flux(0, "MOMENTUM30_BTC", <null>)`.
    Métrique : Sharpe. p = (1 + #{Sharpe_nul ≥ Sharpe_obs}) / (1 + B). **p retenue = la plus
    grande des deux.**
12. **Empreintes** : SHA-256 des clôtures, des règlements de funding et du DFF lus, écrites
    dans la clôture de l'expérience.

## Règle de décision (le programme l'applique, `moteur.verdict`)

Trois conditions, stratégie contre hold, sur la même période et aux mêmes coûts :
- (a) Sharpe_stratégie > Sharpe_hold ;
- (b) CAGR_stratégie ≥ CAGR_hold ;
- (c) MDD_stratégie moins profond que MDD_hold (MDD_s > MDD_h, les deux négatifs).

- **CONFIRMÉE** : (a), (b), (c) vraies ET p retenue < 0,05.
- **INDÉCIDABLE** : (a), (b), (c) vraies ET 0,05 ≤ p retenue < 0,20 (non concluant), ou p
  incalculable.
- **INFIRMÉE** : une des trois conditions fausse, ou p retenue ≥ 0,20 (hasard : les périodes
  d'exposition placées au hasard font aussi bien).

Rien d'autre ne pèse sur le verdict. Le témoin, le Sharpe déflaté, les variantes de robustesse
et les tableaux par année sont rapportés **sans effet**.

## Robustesse (rapportée, sans effet sur le verdict ; aucune n'est « choisie »)

- fenêtres 14 et 60 jours (les bords du plateau d'ARIT) : mêmes coûts, mêmes métriques, sans
  nulls ; la fenêtre 14 j est lue sur la période principale, la fenêtre 60 j sur une période
  qui commence à son propre warm-up (rendements du 07/11/2019 au 31/12/2024) ;
- comptant (φ = 0 pour la stratégie ET le hold) : ce que vaudrait l'idée sur BTC au comptant ;
- frais doublés (12 pb par côté) ;
- par année civile : rendement de la stratégie et du hold, exposition moyenne, bascules ;
- deux sous-périodes : 09/10/2019 → 31/12/2022 et 01/01/2023 → 31/12/2024 (la coupure
  d'ARIT), Sharpe et CAGR de chacun.

## Issue attendue

**Infirmée.** Prior : 14 hypothèses de trading passées au banc, aucune confirmée ; le funding
(~15 %/an pour un long sur le train) n'était pas dans les chiffres d'ARIT ; la condition
(b) CAGR ≥ hold n'est documentée nulle part (ARIT ne rapporte que le Sharpe) ; les nulls sont
exigeants (TI1 : momentum 126 j = hasard).

## Déjà connu au moment du gel

- ARIT, `research/pertinence_donnees_2026-09-05/RAPPORT.md` (05/09/2026) : long-only
  quotidien, signe du rendement sur L jours, frais 5 pb par bascule, **sans funding**, sur
  2019-09 → 2026-09 (**donc hold-out de BETA inclus** : snooping partiel assumé) : Sharpe BTC
  L7 0,44 / L14 1,01 / **L30 1,00** / L60 0,88 / L90 0,48 contre 0,55 pour le hold ; train
  < 2023 : 1,03 ; 2023+ : 0,98. La fenêtre de 30 jours est fixée AVANT ce test par I16 (notée
  le 11/09/2026 : « à préenregistrer avec UN lookback choisi d'avance (30 j, sommet du
  plateau) »), pas choisie ici.
- BETA, famille invest : TI1 (20/10) — le vote « momentum BTC 126 j » seul, comme exposition
  d'un panier des 6 paires, est **hasard** aux nulls ; T1J/T1F (24/10) — MOM126 et SMA200 sur
  le BTC ne datent pas les bears de façon solide ; VC3/VC5 (07-10/10) confirmées avec un
  momentum 126 j parmi 5 votes, sur un panier, en allocation. Aucune de ces mesures ne porte
  sur 30 jours ni sur le BTC seul en long-only quotidien.
- BETA, famille trading : R2, R4, R7, R8, R9, R10, R11, R13, R14 (contrariennes) toutes
  infirmées ; aucune candidate de continuation n'a été mesurée.
- Littérature vérifiée le 10/11 : Moskowitz-Ooi-Pedersen 2012 (pour), Liu-Tsyvinski 2021
  (pour, quotidien et hebdomadaire sur BTC), Grobys-Sapkota 2019 (contre).
- Regardé avant ce gel, sans aucun rendement calculé : couverture et dates des séries (1 942
  bougies 1d, 0 trou ; 7 855 règlements de funding ; DFF sans trou sur 2019-10 → 2024-12) et
  la moyenne du funding sur le train (0,0134 % par 8 h). Aucun chiffre de la stratégie, du
  hold ni du témoin n'a été calculé avant l'écriture de ce fichier.

## Suite si confirmée

Aucun passage au réel. Décision de Jonas : paper sur le perpétuel BTC (même règle, décision à
la clôture 00:00 UTC) et/ou ouverture unique du hold-out 2025+ sans aucun réglage entre-temps.
Un résultat obtenu sans la relecture de Jonas reste « exploration » (skill de recherche).
