# CLAUDE.md — `beta/stats/` : les portes, et les outils qui ne sont pas des portes

> Famille 2 (utile dans ce dossier) : se charge quand on travaille ici. Écrit le 15/11/2026.

## Deux sortes de modules, à ne jamais mélanger

**Les dix portes** rendent l'issue d'une candidate (`batterie.evaluer`, `batterie.issue`).

| Porte | Module | Ce qu'elle demande | Seuil (`batterie.py`) |
|---|---|---|---|
| S0 | `descriptif` | le plus petit effet détectable, avant toute p-value | réserve, pas un seuil |
| S1 | `multitest.benjamini_hochberg` | reste-t-il quelque chose sur la famille déclarée ? | FDR 10 % |
| S2 | `multitest.sharpe_degonfle` | le Sharpe survit-il aux N essais du compteur ? | DSR ≥ 0,95 |
| S3 | `bootstrap` | l'écart survit-il à la dépendance temporelle, sur 3 longueurs de bloc ? | p ≤ 0,05 partout |
| S4 | `montecarlo` | la séquence observée était-elle chanceuse ? | P(perte) ≤ 10 % |
| S5 | `synthetique` | gagne-t-elle plus que sur un marché sans structure ? | 95ᵉ centile |
| S6 | `walkforward` | l'edge tient-il par sous-période ? (test de stabilité, pas une validation croisée) | efficacité ≥ 0,5, couples perdants ≤ 35 % |
| S7 | `multitest.reality_check` | la meilleure du lot bat-elle zéro ? | p ≤ 0,05 |
| S8 | `reference` | bat-elle le hold, mêmes coûts, en rendement ET en Sharpe ? | écarts > 0 |
| S9 | `diversification` | est-elle autre chose qu'une copie ? | corrélation < 0,70 |
| S10 | `pbo`, `cscv` | choisir la meilleure du lot, est-ce du surapprentissage ? | PBO < 20 % |

**Les outils informatifs** (15/11/2026) donnent des chiffres à lire à côté. Aucun seuil, aucun
verdict, rien dans `batterie.issue`.

| Module | Ce qu'il donne |
|---|---|
| `sharpe` | erreur-type du Sharpe, PSR, longueur minimale (MinTRL), durée minimale de backtest après N essais (MinBTL), annualisation corrigée de l'autocorrélation (Lo), écart de deux Sharpe (Memmel, bootstrap apparié) |
| `risque` | Sortino, Omega, VaR et CVaR, VaR de Cornish-Fisher, table des drawdowns, Ulcer, CDaR, drawdown rejoué par blocs, alpha et bêta contre une référence (Newey-West), comparaison à volatilité égale |
| `robustesse` | concentration des gains, stress des coûts et multiple qui annule le R moyen, R par année, R sans une paire |
| `selection` | SPA de Hansen (trois p-values), p-values ajustées de Romano-Wolf |
| `fiche` | assemble le tout pour un run enregistré ; `scripts/fiche_robustesse.py <run_id>` |

## Règles du dossier

1. **Un seuil de porte ne change que par décision de Jonas**, consignée dans `DECISIONS.md`. Un
   défaut de CALCUL se corrige (avec un test qui le montre, et la date dans le commentaire) ; une
   RÈGLE ne se corrige pas, elle se propose. Huit propositions attendent (`DECISIONS.md`,
   « Portes 2 à 9 »).
2. **Un outil informatif ne devient jamais une porte en silence.** Pas de `passe`, pas de seuil,
   pas d'adjectif dans sa sortie. S'il doit devenir une porte, c'est une décision.
3. **Tout module ici ne connaît que des séries** (R par trade, P&L journalier, courbe) : jamais
   une stratégie, jamais le lake. C'est ce qui permet de juger un backtest freqtrade, un rejeu du
   moteur ou une série venue d'ailleurs.
4. **Un paramètre de méthode est fixé AVANT de voir le résultat** et vit en constante de module
   (longueurs de bloc, nombre de tirages, nombre de plis). On ne le règle pas run par run.
5. **Une porte non exécutée vaut `None`, jamais `True`.** Un outil sans ses données rend
   `{"raison": ...}`, jamais un zéro de remplissage.
6. **La courbe du moteur est à risque fixe, non composée** : elle peut passer sous zéro. Tout
   P&L journalier se calcule par différence (`diff`) ou en somme des R clôturés
   (`pbo.rendements_lot`), jamais par `pct_change` — défaut corrigé trois fois (S8 le 15/10, S9 le
   05/11, comparaison le 15/11).
7. **Chaque formule a un test contre une valeur faite à la main ou une propriété connue**
   (calibration sous H0, cas limite), pas contre sa propre sortie. `tests/test_stats.py`,
   `test_audit_portes_0511.py`, `test_outils_stats.py`, `test_pbo.py`, `test_cscv.py`.
8. Après une mesure, les chiffres et le verdict sortent du programme
   (`scripts/rapport_experience.py`), pas de Claude.

## Ce qui a été relu et quand

- 13/10 : coûts du moteur (spread d'un tick, frais des deux côtés).
- 15/10 : S6 (in-sample négatif), S8 (Sharpe par différence).
- 05/11 : S4, S5, S6, S7, S9, MDE (rapport `/root/rapports/2026-11-05_audit-portes-batterie.md`
  sur le VPS). S3 vérifiée bien calibrée, non modifiée.
- 15/11 : prix de sortie du moteur, comparaison à AritV1 ; ajout des outils informatifs.
