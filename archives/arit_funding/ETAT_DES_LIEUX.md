# État des lieux — thèse ARIT (18-19 sept 2026)

## Mesures faites (verdict net)

1. **F&G / VIX / funding : tous lagging.** Corrélation avec le rendement d'hier ~+0,19 à +0,20,
   avec le rendement futur ~0. Ce sont des indicateurs *réactifs*, pas prédictifs.
2. **VIX = indicateur actions, inutile pour BTC** (corr ~0 partout). À réserver aux indices/SPX.
3. **Funding extrêmes (contrarien) : demi-vivant, asymétrique.**
   - crowded shorts → long : +0,39 %/j (t=1,98, marginal, bat le hold)
   - crowded longs → short : mort (t=0,84, indistinguable du hold)
   - mécanisme = **carry + squeeze**, pas « smart money prediction ».
4. **Volume accélération : mort comme directionnel** (plat entre déciles), **vivant comme
   volatilité** (|ret| monte). → input de *sizing*, pas d'entrée.
5. **Combinaison funding ∩ F&G : redondante** (~95 % chevauchement) → n'ajoute rien.
   Sentiment et positionnement = la même brique.

## Leçon de méthode

- Combiner ne paie que si les matériaux sont **indépendants** (orthogonaux).
- « Tous ensemble » proprement = **un** modèle linéaire régularisé + validation OOS,
  pas un shotgun 2^N de seuils.

## Protocole « tous les matériaux » — EN ATTENTE de validation (2 décisions)

1. La liste des 10 matériaux (funding, fng, accel_vol, vix, breakeven10y, tips10y, fedfunds,
   hy_oas, dxy, spread_2s10s) — confirmer/ajuster.
2. Le split train/test (proposé 2024-06, à aligner sur le hold-out scellé de BETA).

## Carte : testable vs forward-only

- **Testable maintenant** : canal inflation/macro (FRED), sweep setups A/B (sur OHLCV),
  volume profile, VSTOXX sur CAC40.
- **Forward-only** (intestable historiquement) : whale exposure, COT crypto, murs de
  liquidité exacts, heat map SL/TP, ML news + transcription live.

## Non négociable (acquis)

- **Suivre, pas anticiper.** Contrarien = anticipation = 0/8 dans BETA.
- Hermes = thèse / recherche, jamais le code ARIT (code = Claude / Jonas).
- Chaque chiffre = avec sa formule + SE + seuil + limite (exigence de Jonas).
