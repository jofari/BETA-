# RAPPORT — Pertinence des données & momentum (étude 2026-09-05, v2 consolidée)

> Étude hors-ligne sur **4 actifs** (BTC/ETH/SOL/BNB), daily + funding rate, données Binance
> publiques, 2019-09 → 2026-09. Recherche exploratoire, PAS un verdict de prod. Aucun code ARIT modifié.
> Sharpe = arithmétique standard (`moyenne des retours / écart-type × √365`), frais taker 0.05 %/côté.

---

## RÉSUMÉ EN UNE PHRASE

**Le momentum de prix (14–60 jours) est un edge robuste, généralisable aux 4 actifs et validé
hors échantillon. Le funding et la macro sont faibles ou conditionnels. La donnée la plus
pertinente pour ARIT est déjà dans ses bougies OHLCV.**

---

## 1. Momentum : l'edge principal, robuste et généralisable

**Sharpe long-only (full sample) par lookback et par actif :**

| actif | L7 | L14 | L30 | L60 | L90 | B&H |
|---|---|---|---|---|---|---|
| BTC | 0.44 | 1.01 | 1.00 | 0.88 | 0.48 | 0.55 |
| ETH | 0.84 | 0.92 | 1.07 | 0.71 | 0.36 | 0.62 |
| SOL | 0.90 | 0.97 | 1.26 | 0.84 | 0.74 | 0.69 |
| BNB | 0.54 | 0.84 | 0.94 | 0.85 | 0.75 | 0.83 |

Trois faits :
1. **Le momentum bat le buy & hold sur chaque actif** (Sharpe ~1.0 vs 0.55–0.83).
2. **La courbe est lisse, pas un pic unique** : le pic est entre 14 et 60 jours. « 30 jours »
   n'est pas un gagnant chanceux de balayage — c'est le sommet d'un plateau régulier.
3. **Ça tient hors échantillon** (train < 2023 → holdout ≥ 2023) :

| actif | Sharpe train | Sharpe holdout |
|---|---|---|
| BTC | 1.03 | 0.98 |
| ETH | 1.30 | 0.83 |
| SOL | 1.69 | 0.89 |
| BNB | 1.14 | 0.78 |

La décroissance train→holdout est normale (pas d'effondrement vers zéro) : l'effet n'est pas
un surajustement, il est simplement plus fort sur la période haussière pré-2023.

---

## 2. Funding : faible, et pas généralisable

**IC (Spearman) funding → retour futur ≈ 0** (de −0.06 à +0.001). Seul effet réel : le
squeeze des shorts aux extrêmes négatifs, et il ne se voit nettement **que sur BTC**.

**Grille funding × momentum → retour 7j** (quintile de funding relatif × signe du momentum) :

| actif | fund bas × mom− | fund haut × mom+ | meilleure cellule |
|---|---|---|---|
| BTC | +1.88 % | +1.97 % | fund haut × mom+ |
| ETH | +1.10 % | +3.11 % | fund haut × mom+ |
| SOL | +0.51 % | +6.07 % | fund bas × mom+ |
| BNB | +0.86 % | +3.68 % | fund haut × mom+ |

Ce qui ressort : **le momentum domine partout** (mom+ > mom− dans presque toutes les cases).
Le funding n'ajoute qu'un effet de second ordre, incohérent d'un actif à l'autre. Le
« squeeze des shorts » (fund bas × mom−) est net sur BTC (+1.88 %) mais s'estompe sur les
autres. **Le funding n'est pas un edge ; au mieux un modulateur de positionnement sur BTC.**

---

## 3. La leçon de méthode (à retenir)

Mon analyse IC suggérait « filtre de volatilité » (momentum plus prédictif en vol basse,
IC +0.17 vs +0.06). Le **backtest l'a infirmé** : ajouter le filtre vol fait chuter le Sharpe
de 1.22 → 0.55 (définition géométrique). Pourquoi : l'IC mesure le *rang* (fiabilité), pas la
*taille* des gains. Les grosses tendances se font en haute volatilité ; les couper coupe le P&L.

→ **Un IC élevé n'est pas un P&L. On ne recommande jamais un filtre sans l'avoir backtesté.**

---

## 4. Ce que ça change pour ARIT

1. **L'edge est dans le prix, pas dans la macro.** Le momentum 14–60j bat tout le reste.
   ARIT l'a déjà (EMA/RSI), mais dilué dans 5 scores et bridé par la porte macro.
2. **Le momentum-30j mérite d'être testé comme filtre de direction** sur le substrat 4h —
   c'est le préenregistrement `E1` (pendant technique du Test 1 de docs/01).
3. **Le funding ne doit pas devenir un score.** Son effet est faible et non généralisable ;
   au mieux un débloqueur long sur BTC seul, et encore, à confirmer.
4. **Le "86 % du profit de MacroFlip venait du funding" (DECISIONS.md) est à revérifier** :
   rien dans ces mesures ne justifie un tel poids au funding.

---

## 5. Prochain pas

Préenregistrement **E1** (`research/EXPERIMENTS.jsonl`) : tester si le momentum-30j discrimine
l'espérance des signaux sur le substrat ARIT (4h, 4 paires). À valider par Jonas puis à lancer
sur sa machine Windows (freqtrade).
