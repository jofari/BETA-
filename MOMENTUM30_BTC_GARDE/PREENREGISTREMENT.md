# Momentum trente jours sur le BTC avec garde de baisse — préenregistrement

- **Écrit le** : 19/11/2026 (UTC), avant tout calcul de cette stratégie sur les vraies données.
  Demande de Jonas du même jour : « je te lance un backtest de cette théorie, entre-la dans BETA
  en candidate invest ». La théorie, c'est la recommandation de Claude après le diagnostic de la
  veille du 19/11 : une voie en BTC seul, le momentum de MOMENTUM30_BTC, plus une gestion du
  risque choisie d'avance. Hypothèse, règles et seuil : **proposition de Claude**.
- **Statut : exploration, pas recherche** (skill de recherche, entorses nommées) : hypothèse
  écrite par Claude ; nuit entre le gel et le lancement sautée ; littérature balayée en une
  séance ; et surtout **la période de mesure est celle déjà vue par MOMENTUM30_BTC**. Un bon
  résultat ne prouve rien : il peut seulement justifier un paper ou l'ouverture unique du
  hold-out, sur décision de Jonas.
- **Id au registre** : `MOMENTUM30_BTC_GARDE`, famille **invest**, un essai, une seule
  configuration (`n_configurations = 1`). Compteur invest 62 → 63.
- **Code** : `beta/momentum30_btc_garde/moteur.py`, lancé par
  `scripts/mesurer_momentum30_btc_garde.py`. Empreintes de ce texte et du moteur au registre.
- **Hold-out** : 2025-01-01 et après, jamais lu. Train seulement.

## Question

Sur le BTC seul, ajouter au momentum trente jours une garde qui sort après une baisse de 20 %
depuis le plus haut de la période investie réduit-il le drawdown maximal **sans dégrader le
Sharpe**, tout en battant toujours le buy-and-hold ?

## Mécanisme supposé

Le diagnostic du 19/11 montre que les voies C perdent quand une règle **garde une exposition
figée** pendant une chute que les signaux lents (momentum 126 j, macro à J+2) ne voient pas encore.
Le momentum trente jours sort plus tôt, mais pas avant que la baisse ait effacé le gain de
trente jours : une chute brutale au milieu d'une tendance haussière (le momentum reste positif)
est subie en entier. La garde réagit au prix lui-même. Kaminski et Lo (2014) : une garde de
baisse ne peut ajouter du rendement que si les rendements ont de l'inertie après une perte ; sur
une marche au hasard elle ne fait que baisser le rendement attendu. Han, Zhou et Zhu (2014) :
un stop de 10 % réduit fortement les krachs du momentum sur les actions américaines (1926-2011),
avant frais. **Qui prend l'autre côté** : les acheteurs de creux et les teneurs de marché qui
absorbent les ventes forcées ; si les baisses de 20 % sont en moyenne rachetées vite, la garde
coûte (elle vend bas et ne rachète qu'au signal neuf).

## Hypothèse

Sur le perpétuel BTC/USDT de Binance en quotidien, l'exposition du momentum trente jours de
MOMENTUM30_BTC, coupée par une garde de baisse de 20 % (règle ci-dessous), bat le buy-and-hold
du même perpétuel (rendements du 09/10/2019 au 31/12/2024, tous coûts déduits) en Sharpe, en
CAGR et en drawdown maximal, a un drawdown maximal **moins profond** que le même momentum sans
garde, un Sharpe **au moins égal** au sien, et son placement dans le temps bat les deux nulls du
test invest.

## Applications (écrites avant tout calcul)

1. **Données, période, rendements, funding, cash, frais, rendement net, métriques, nulls,
   empreintes** : identiques à MOMENTUM30_BTC (applications 1, 2, 4 à 12 de
   `MOMENTUM30_BTC/PREENREGISTREMENT.md`), par les mêmes fonctions
   (`beta.momentum30_btc.moteur`). Rendements du **09/10/2019 au 31/12/2024** (1 910 jours),
   frais 6 pb × |ΔE|, funding réel payé par tout le long, cash au DFF. Nulls : décalage
   circulaire et mélange des segments sur la série d'exposition, B = 1 000, graine 0, flux
   `nulls.flux(0, "MOMENTUM30_BTC_GARDE", <null>)`, métrique Sharpe, p retenue = la plus grande.
2. **Signal de base à la clôture de t** : s(t) = 1 si close(t) / close(t − 30) − 1 > 0, sinon 0.
3. **Garde** : un épisode est une suite de clôtures où s = 1 ; il commence à la clôture où s
   passe de 0 à 1 (ou à la première décision si s = 1 dès le départ). Plus haut de l'épisode =
   maximum des clôtures depuis la clôture d'entrée incluse. Si close(t) / plus haut − 1 ≤ −20 %,
   la garde se déclenche et reste déclenchée jusqu'à la fin de l'épisode (s repasse à 0).
   **Exposition du jour t + 1** : 1 si s(t) = 1 et garde non déclenchée, sinon 0. On ne rentre
   qu'au signal neuf suivant.
4. **Seuil de 20 %**, fixé sans calcul : le budget de perte des voies C est de −25 % ; 20 %
   laisse une marge de cinq points pour l'écart d'une journée (la garde se lit à la clôture).
   Aucun autre seuil n'est essayé avant la mesure.
5. **Momentum sans garde** (référence des conditions d et e) : `beta.momentum30_btc.moteur`
   recalculé par le programme sur les mêmes données, mêmes coûts.

## Règle de décision (le programme l'applique, `moteur.verdict`)

- (a) Sharpe_garde > Sharpe_hold ; (b) CAGR_garde ≥ CAGR_hold ; (c) MDD_garde moins profond
  que MDD_hold ;
- (d) MDD_garde moins profond que MDD du momentum sans garde ;
- (e) Sharpe_garde ≥ Sharpe du momentum sans garde.

- **CONFIRMÉE** : (a) à (e) vraies ET p retenue < 0,05.
- **INDÉCIDABLE** : (a) à (e) vraies ET 0,05 ≤ p retenue < 0,20, ou p incalculable.
- **INFIRMÉE** : une condition fausse, ou p retenue ≥ 0,20.

Rien d'autre ne pèse sur le verdict.

## Rapporté sans effet (aucune variante n'est choisie)

Témoin exposition constante ; nombre de déclenchements de la garde et jours coupés ; seuils
15 % et 25 % ; comptant (φ = 0) ; frais doublés (12 pb) ; par année civile ; sous-périodes
09/10/2019 → 31/12/2022 et 01/01/2023 → 31/12/2024 ; Sharpe déflaté au compteur invest.

## Issue attendue

**Infirmée**, par la condition (e) le plus probablement : la garde se lit à la clôture (elle
vend après l'écart), elle attend un signal neuf pour rentrer (elle rate des reprises), et le
momentum trente jours sort déjà assez vite ; Kaminski et Lo montrent qu'une garde coûte du
rendement quand il n'y a pas d'inertie après les pertes.

## Déjà connu au moment du gel

- **MOMENTUM30_BTC, mesurée le 10/11 sur exactement cette période** : CONFIRMÉE, Sharpe 1,16 /
  CAGR +55 % / MDD −47 % contre hold 0,80 / +38 % / −79 % ; p retenue 0,027. Ses tableaux par
  année et par sous-période ont été lus. Les drawdowns de la stratégie, épisode par épisode,
  n'ont **pas** été calculés ; le seuil de 20 % n'en vient pas.
- Diagnostic de la veille des voies C (19/11/2026, `rapports/DIAGNOSTIC_VEILLE_2026-11-19`).
- Claude connaît l'histoire générale du BTC sur la période (krach de mars 2020, chute de mai
  2021, marché baissier de 2022) : connaissance générale, pas un calcul ; elle est nommée ici.
- Littérature vérifiée le 19/11 : Kaminski et Lo, *When do stop-loss rules stop losses?*,
  Journal of Financial Markets 18 (2014) 234-254 (contre, sauf inertie) ; Han, Zhou et Zhu,
  *Taming momentum crashes: a simple stop-loss strategy* (document de travail, 2014 ; pour,
  avant frais, actions américaines).
- Aucun chiffre de cette stratégie, de ses déclenchements ni de ses variantes n'a été calculé
  avant l'écriture de ce fichier.

## Suite si confirmée

Aucun passage au réel. Décision de Jonas : relecture (sinon le résultat reste exploration),
puis paper BTC et/ou ouverture unique du hold-out 2025+, sans aucun réglage entre-temps.
