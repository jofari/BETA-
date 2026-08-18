# BETA — chantiers

> Ce que BETA ne sait pas encore faire, dans l'ordre où ça doit se faire.
> Ouvert le 2026-08-18. Append-only, comme `ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` :
> une ligne fermée est **barrée en place**, avec sa date. Si elle n'est pas barrée, elle est
> ouverte.
>
> Arbitrages de Jonas : `ARIT2.0/DECISIONS.md` § F1. Doctrine : `CLAUDE.md`.

**État en une phrase** : BETA sait dire ce que le marché a fait et ce qu'une stratégie en a
fait. Il ne sait **pas encore chercher un edge**, ni comparer plusieurs candidates sans
fabriquer de faux gagnants. C'est tout l'objet des sections R et M.

---

## Fait au 2026-08-18

| # | Chantier | État |
|---|---|---|
| ~~D1~~ | ~~Lake OHLCV : 6 paires, 4 timeframes, catalogue des trous~~ | ✅ **FERMÉ 18/08** — 24 séries, 100 % de couverture, 4,56 M bougies |
| ~~D2~~ | ~~Données de stratégie : trades, évaluations, gestion~~ | ✅ **FERMÉ 18/08** — 79 trades, 3 151 évaluations, 4 084 événements |
| ~~D3~~ | ~~Protocole : préenregistrement + hold-out scellé + compteur~~ | ✅ **FERMÉ 18/08** — verrou matériel, compteur parti de 30 |
| ~~D4~~ | ~~Dashboard + lanceur~~ | ✅ **FERMÉ 18/08** — `BETA.cmd`, port 7474 |

---

## M — le moteur (en attente du feu vert de Jonas)

Arbitrage du 18/08 : **hybride** — moteur maison en espace-R pour cribler, freqtrade pour
confirmer les survivantes. Aucun des deux seul ne suffit : le maison ne simule ni frais, ni
slots, ni compounding ; freqtrade ne permet pas 1 000 runs Monte-Carlo.

| # | Chantier | Statut | Effort | Ce que ça débloque |
|---|---|---|---|---|
| **M1** | `moteur/contrats.py` — les trois contrats gelés : `Candidate` (fonction pure `signaux(df)`), `Run` (exige un id de préenregistrement), `Verdict` | 🔴 ouvert | S | tout le reste ; à écrire **avant** toute implémentation |
| **M2** | `moteur/espace_r.py` — triple barrière vectorisée, portage de `ARIT2.0/analysis/dataset.py:_issue` et `replay_entries.py` | 🔴 ouvert | M | le criblage de centaines de candidates |
| **M3** | Pont freqtrade — export d'une candidate survivante en stratégie freqtrade, run avec `--enable-protections` et `--timeframe-detail 5m` | 🔴 ouvert | M | le seul verdict **portefeuille** (frais, slots, compounding) |
| **M4** | Registre de candidates — une par fichier, isolée, aucune ne touchant au moteur | 🔴 ouvert | S | l'ajout d'une candidate sans risque de régression sur les autres |

⚠️ **M2 ne produit jamais un verdict portefeuille.** Un chiffre issu du criblage se lit en
R par trade, jamais en rendement de portefeuille. La confusion des deux est l'erreur qui
rend un banc d'essai dangereux.

---

## S — la batterie multi-test (ce qui distingue BETA d'un backtester de plus)

> **Un banc d'essai est une machine à multiplier les tests. Il produira d'autant plus de
> faux gagnants qu'il est efficace.** Ces outils ne sont donc pas des compléments — ce sont
> les fonctionnalités principales. Ils ne peuvent que rendre un résultat **pire**, jamais
> meilleur : leur seul usage honnête est de **tuer** un candidat, pas de le sacrer.

Spécification déjà écrite, dans le second cerveau de Jonas — ces chantiers l'implémentent,
ils ne la redécouvrent pas.

| # | Chantier | Statut | Effort | Source de la spec |
|---|---|---|---|---|
| ~~S0~~ | ~~MDE affiché à côté de chaque métrique~~ | ✅ fermé 18/08 | S | `stats/descriptif.py` — déjà appliqué |
| **S1** | **Benjamini-Hochberg** sur la famille de tests déclarée (FDR 0,10) | 🔴 ouvert | S | `budget de tests et sharpe degonfle.md` · portage de `ARIT2.0/analysis/mesures.py:106` |
| **S2** | **Sharpe dégonflé (DSR)** — dégonfle le Sharpe par le maximum attendu de N essais, N venant du compteur cumulatif | 🔴 ouvert | S | Bailey & López de Prado (2014) · même note |
| **S3** | **Bootstrap par blocs stationnaire** (Politis-Romano), ℓ fixé avant, sensibilité publiée sur 3 longueurs | 🔴 ouvert | M | `bootstrap par blocs stationnaire.md` |
| **S4** | **Monte-Carlo** — permutation de l'ordre des trades + rééchantillonnage, cône d'équity | 🔴 ouvert | M | `monte-carlo (validation).md` |
| **S5** | **Chemins synthétiques** — GBM et phase randomization, la stratégie rejouée sur ~200 séries | 🔴 ouvert | L | `chemins synthetiques - GBM et phase randomization.md` |
| **S6** | **Walk-forward avec purge et embargo (CPCV)** | 🔴 ouvert | L | `walk-forward purge et embargo (CPCV).md` |
| **S7** | **Reality Check de White / SPA de Hansen** — bootstrap sur la statistique du **maximum** d'un univers de N candidates | 🔴 ouvert | L | `budget de tests et sharpe degonfle.md` |
| **S8** | **Buy-and-hold** comme référence imposée de toute candidate, même période | 🔴 ouvert | S | décision Q9 · `ARIT2.0/DECISIONS.md` § F1 |
| **S9** | **Corrélation des courbes d'équity** entre candidates — deux stratégies rentables corrélées à 0,9 n'apportent rien | 🔴 ouvert | M | `ARIT2.0/DECISIONS.md` § F1, critère de diversification |

**Ordre imposé** : S1, S2 et S8 **avant** la première comparaison de candidates. Sans elles,
le premier gagnant du banc sera un artefact, et on l'aura cru.

---

## R — la recherche d'edge (l'objet même du projet)

Objectif de F1, mot pour mot : « tester **d'autres stratégies** que AritV1, pour trouver
celle qui a le meilleur rendement **et diversifier les formes d'investissement** ».

### R0 — le protocole de recherche, avant les candidates

Une boucle, toujours la même, et **jamais dans un autre ordre** :

```
hypothèse falsifiable
  → préenregistrement (protocole/experiences.py : hypothèse, métrique, règle de décision, MDE attendu)
  → candidate isolée (moteur/contrats.py)
  → criblage espace-R (M2)  →  batterie S1-S9
  → verdict : confirmée / infirmée / INDÉCIDABLE
  → si elle survit : confirmation freqtrade (M3), puis hold-out — une seule fois
```

L'issue **indécidable** est légitime et sera la plus fréquente. Le premier test d'A5 côté
ARIT l'a montré : 7 signaux marginaux pour un MDE de +1,53 R.

### R1-R6 — les hypothèses déjà identifiées

| # | Hypothèse | Statut | Origine | Effort |
|---|---|---|---|---|
| **R1** | **Le trailing stop détruit les shorts.** Signal short brut +0,0637 R, stratégie complète −0,4683 R sur la même période ; MFE moyen +0,438 R côté short contre +1,215 R côté long | 🔴 à préenregistrer | mesure du 18/08 — **seul écart du lot à dépasser son MDE**, mais sous-groupe trouvé après coup ⇒ **à préenregistrer avant de mesurer** | S |
| **R2** | **Mean-reversion** — l'opposé structurel d'AritV1, qui est un suiveur de tendance | 🔴 à préenregistrer | `ARIT2.0/DECISIONS.md` § F1 | M |
| **R3** | **Portage / funding** — 86 % du profit de MacroFlip venait de là | 🔴 à préenregistrer | § F1 | M |
| **R4** | **Macro seule**, sans couche technique | 🔴 à préenregistrer | § F1 | M |
| **R5** | **Spot vs perpétuel** — D1 côté ARIT a été abandonné parce qu'il mesurait l'alternance bull/bear, pas un edge. À reposer proprement, avec le hold-out | 🔴 à préenregistrer | § F1 · `BUILD_NOTES` 17/08 | M |
| **R6** | **`news_window`** bloque 91,75 % de tout ce qui est rejeté (756 signaux sur 824). Porte la plus active du système : que vaut ce qu'elle bloque ? | 🔴 à préenregistrer | mesure du 18/08 · lien direct avec **C1-bis** | S |

⚠️ **R1 et R6 se mesurent sur les données déjà présentes**, sans écrire une seule candidate.
Ce sont donc les deux moins chers, et les deux premiers à préenregistrer.

---

## P — le pont MCP (double sens)

| # | Chantier | Statut | Effort |
|---|---|---|---|
| **P1** | Sens 1 — bouton du dashboard qui lance `claude "prompt"` avec le contexte du run, sur le modèle de `ALPHA/alpha/actions.py:160` | 🟠 reporté | S |
| **P2** | Sens 2 — serveur MCP stdio : `beta_data_catalog`, `beta_load_ohlcv`, `beta_register_edge`, `beta_submit_strategy`, `beta_run_backtest`, `beta_results`, `beta_publish` | 🟠 reporté | M |
| **P3** | Garde-fou : `beta_run_backtest` **refuse** un run sans préenregistrement, comme le fait déjà `protocole.exiger()` | 🟠 reporté | S |

⚠️ **Reporté par Jonas le 18/08** : « je veux juste des data pour le moment, pas de nouvelles
stratégies automatiques derrière ». Le pipeline **YouTube → stratégie générée** (`P4`) est
reporté, pas annulé — une vidéo est une source d'**hypothèses**, jamais d'edge.

---

## Dettes connues

| # | Dette | Statut | Conséquence si on l'oublie |
|---|---|---|---|
| **T1** | **Repo distant privé non créé** — `gh` n'est pas installé sur la machine | 🔴 ouverte | tout le travail vit sur un seul disque |
| **T2** | **venv partagé avec ARIT** (`C:\Users\jofar\venvs\arit`) | 🔴 ouverte | une mise à jour pour ARIT casse BETA, ou l'inverse |
| **T3** | **Bornes de fin hétérogènes** — LINK/XRP vont au 18/08, les 4 paires d'ARIT s'arrêtent au 04/08 | 🔴 ouverte | un run multi-paires s'arrête à la borne commune sans le dire ; visible dans le dashboard, à ne pas oublier au moment de conclure |
| **T4** | **`ts_utc` du journal d'ARIT ment** sur les événements `gestion` (heure d'exécution du backtest, pas de la bougie). Contourné côté BETA par `signal_id` | 🔴 ouverte | à corriger **à la source**, côté ARIT, sinon chaque nouveau consommateur retombera dedans |
