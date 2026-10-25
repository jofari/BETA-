# ADDENDUM — Chasse aux données externes (2026-09-05, soir)

> Question de Jonas : quelles données entrantes seraient réellement intéressantes pour ARIT ?
> Test systématique des sources accessibles, avec la vérification clé : **le signal tient-il
> une fois qu'on contrôle le prix (momentum) ?**

---

## Résultat brut (IC = Spearman vs retour futur)

| source | signal | IC brut | **IC partiel (après contrôle momentum)** |
|---|---|---|---|
| futures basis (fut−spot) | niveau / changement | ~0 | — |
| on-chain : adresses uniques | croissance 30j | **+0.31** | **+0.03** |
| on-chain : mempool | croissance 30j | +0.28 | +0.07 |
| on-chain : hashrate / tx / volume | niveau | −0.1 à −0.3 | (non-stationnaire, artéfact) |
| funding rate | niveau / somme | −0.05 à 0 | déjà établi : inerte |

## La conclusion qui compte

**L'on-chain est un leurre de pertinence.** La croissance des adresses actives affiche un
IC brut de +0.31 — le plus fort de toute l'étude — mais elle est **à ~90 % redondante avec le
prix** : les adresses actives montent *quand le prix monte*. Une fois qu'on contrôle le
momentum, il ne reste que +0.03 (rien). Le seul candidat avec un soupçon de signal indépendant
est le **mempool** (congestion réseau, IC partiel +0.07), faible.

**Le basis futures est nul** (IC ≈ 0), contrairement à l'intuition « levier → retournement ».

## Le mur de la donnée gratuite

Ce qui aurait pu être intéressant et que je n'ai **pas pu tester** (payant ou limité à 365 j
sur l'API gratuite) :
- **Open interest / liquidations / ratio long-short** (positioning) — les endpoints
  `/futures/data/*` de Binance sont retirés (404), Coinglass est payant.
- **Order flow / CVD / book depth** — non exposé gratuitement en historique.
- **Offre de stablecoins** (USDT/USDC) — CoinGecko limite à 365 j.
- **ETF flows** — pas de source gratuite fiable en historique.

## Le verdict global de la chasse

> **Le prix contient essentiellement tout le signal exploitable.** Chaque source externe
> testée est soit faible (funding, basis), soit redondante avec le prix (on-chain), soit
> inaccessible (order flow, OI, liquidations). L'edge robuste et généralisable est le
> **momentum de prix (14–60 jours)** — déjà dans les bougies OHLCV d'ARIT.

Implication pour ARIT : **cesser de chercher la donnée externe magique.** Le levier
prioritaire n'est pas d'ajouter une source, c'est d'exploiter le momentum déjà présent,
et de débloquer la porte macro qui bride actuellement le bot (B1).
