# BETA — chantiers

> Ce que BETA ne sait pas encore faire, dans l'ordre où ça doit se faire.
> Ouvert le 2026-08-18. Append-only, comme `ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` :
> une ligne fermée est **barrée en place**, avec sa date. Si elle n'est pas barrée, elle est
> ouverte.
>
> Arbitrages de Jonas : `DECISIONS.md` (ce dépôt, depuis le 19/08 ; avant, `ARIT2.0/DECISIONS.md` § F1). Doctrine : `CLAUDE.md`.
>
> **Frontière ARIT / BETA** (posée le 19/08, symétrique de
> `ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` § MISE À JOUR DU 2026-08-19) :
> **ARIT2.0 = la stratégie qui tourne** (AritV1 : ses portes, ses scores, sa gestion, son
> dry-run, son observabilité). **BETA = la recherche d'autres stratégies** (moteur de
> criblage, batterie multi-test, hypothèses d'edge). **Aucun statut ne vit aux deux
> endroits** : le dépôt propriétaire fait foi, l'autre ne porte qu'un pointeur.
> Ce qui a migré ici le 18/08 et n'est plus suivi chez ARIT : **F1 / H7** (le banc) et
> **Q9** (Deflated Sharpe + buy-and-hold → S2 et S8). Ce qui **reste chez ARIT** malgré
> l'apparence : **Q7** (walk-forward pour AritV1 ; S6 est le même outil appliqué aux
> candidates — deux travaux, deux dépôts), **C1-bis** (paramètre d'AritV1, que **R6** se
> contente de mesurer) et **F2 / G2 / G8** (le dry-run, qui ne tourne que chez ARIT).

**État en une phrase au 19/08** : BETA sait chercher un edge et le tuer. Le moteur, la
batterie S1-S9, le pont freqtrade et le pont MCP sont en place ; trois hypothèses sont
passées à la batterie et **aucune n'a survécu** — une infirmée, deux indécidables. Ce qui
manque désormais n'est plus de l'outillage mais **des données** : funding, macro et spot,
sans lesquelles R3, R4 et R5 ne sont pas mesurables.

---

## Fait au 2026-08-18

| # | Chantier | État |
|---|---|---|
| ~~D1~~ | ~~Lake OHLCV : 6 paires, 4 timeframes, catalogue des trous~~ | ✅ **FERMÉ 18/08** — 24 séries, 100 % de couverture, 4,56 M bougies |
| ~~D2~~ | ~~Données de stratégie : trades, évaluations, gestion~~ | ✅ **FERMÉ 18/08** — 79 trades, 3 151 évaluations, 4 084 événements |
| ~~D3~~ | ~~Protocole : préenregistrement + hold-out scellé + compteur~~ | ✅ **FERMÉ 18/08** — verrou matériel, compteur parti de 30 |
| ~~D4~~ | ~~Dashboard + lanceur~~ | ✅ **FERMÉ 18/08** — `BETA.cmd`, port 7474 |

## Fait au 2026-08-19

| # | Chantier | État |
|---|---|---|
| ~~M1~~ | ~~`moteur/contrats.py` — Candidate / Run / Verdict~~ | ✅ **FERMÉ 19/08** — un Run appelle `protocole.exiger()` dans son constructeur |
| ~~M2~~ | ~~`moteur/espace_r.py` — triple barrière vectorisée~~ | ✅ **FERMÉ 19/08** — par blocs, coûts soustraits en R |
| ~~M3~~ | ~~Pont freqtrade~~ | ✅ **FERMÉ 19/08** — export + `--enable-protections --timeframe-detail 5m` imposés |
| ~~M4~~ | ~~Registre de candidates~~ | ✅ **FERMÉ 19/08** — découverte par import, une par fichier |
| ~~S1~~ à ~~S9~~ | ~~La batterie complète~~ | ✅ **FERMÉES 19/08** — voir la section S |
| ~~P1~~ | ~~Bouton Claude Code depuis le dashboard~~ | ✅ **FERMÉ 19/08** — liste blanche, prompt reconstruit côté serveur |
| ~~P2~~ | ~~Serveur MCP stdio~~ | ✅ **FERMÉ 19/08** — 7 outils, JSON-RPC en stdlib, zéro dépendance |
| ~~P3~~ | ~~Garde-fou du backtest MCP~~ | ✅ **FERMÉ 19/08** — refus vérifié par test |
| ~~T1~~ | ~~Repo distant privé~~ | ✅ **FERMÉE 19/08** — `github.com/jofari/BETA-`, `main` poussée |
| ~~F1~~ | ~~Fiche stratégie au dashboard~~ | ✅ **FERMÉ 19/08** — onglet Candidates, verdict avant courbe |

---

## M — le moteur (en attente du feu vert de Jonas)

Arbitrage du 18/08 : **hybride** — moteur maison en espace-R pour cribler, freqtrade pour
confirmer les survivantes. Aucun des deux seul ne suffit : le maison ne simule ni frais, ni
slots, ni compounding ; freqtrade ne permet pas 1 000 runs Monte-Carlo.

| # | Chantier | Statut | Effort | Ce que ça débloque |
|---|---|---|---|---|
| ~~M1~~ | ~~`moteur/contrats.py` — les trois contrats gelés~~ | ✅ fermé 19/08 | S | fait : un `Verdict` ne peut être CONFIRMEE ni avec une porte échouée, ni avec une porte **non exécutée** |
| ~~M2~~ | ~~`moteur/espace_r.py` — triple barrière vectorisée~~ | ✅ fermé 19/08 | M | fait : bougie ambiguë ⇒ SL comme chez ARIT ; le coût en R croît quand le stop se resserre |
| ~~M3~~ | ~~Pont freqtrade~~ | ✅ fermé 19/08 | M | fait : refuse une candidate non survivante, sauf `forcer=True` explicite |
| ~~M4~~ | ~~Registre de candidates~~ | ✅ fermé 19/08 | S | fait : une candidate cassée est journalisée en ERROR, elle n'annule pas les autres |

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
| ~~S1~~ | ~~**Benjamini-Hochberg** sur la famille de tests déclarée (FDR 0,10)~~ | ✅ fermé 19/08 | S | `budget de tests et sharpe degonfle.md` · portage de `ARIT2.0/analysis/mesures.py:106` |
| ~~S2~~ | ~~**Sharpe dégonflé (DSR)** — dégonfle le Sharpe par le maximum attendu de N essais, N venant du compteur cumulatif~~ | ✅ fermé 19/08 | S | Bailey & López de Prado (2014) · même note |
| ~~S3~~ | ~~**Bootstrap par blocs stationnaire** (Politis-Romano), ℓ fixé avant, sensibilité publiée sur 3 longueurs~~ | ✅ fermé 19/08 | M | `bootstrap par blocs stationnaire.md` |
| ~~S4~~ | ~~**Monte-Carlo** — permutation de l'ordre des trades + rééchantillonnage, cône d'équity~~ | ✅ fermé 19/08 | M | `monte-carlo (validation).md` |
| ~~S5~~ | ~~**Chemins synthétiques** — GBM et phase randomization, la stratégie rejouée sur ~200 séries~~ | ✅ fermé 19/08 | L | `chemins synthetiques - GBM et phase randomization.md` |
| ~~S6~~ | ~~**Walk-forward avec purge et embargo (CPCV)**~~ | ✅ fermé 19/08 | L | `walk-forward purge et embargo (CPCV).md` |
| ~~S7~~ | ~~**Reality Check de White / SPA de Hansen** — bootstrap sur la statistique du **maximum** d'un univers de N candidates~~ | ✅ fermé 19/08 | L | `budget de tests et sharpe degonfle.md` |
| ~~S8~~ | ~~**Buy-and-hold** comme référence imposée de toute candidate, même période~~ | ✅ fermé 19/08 | S | ex-Q9 d'ARIT · `DECISIONS.md` |
| ~~S9~~ | ~~**Corrélation des courbes d'équity** entre candidates — deux stratégies rentables corrélées à 0,9 n'apportent rien~~ | ✅ fermé 19/08 | M | `DECISIONS.md`, critère de diversification |

**Ordre imposé** : S1, S2 et S8 **avant** la première comparaison de candidates. Sans elles,
le premier gagnant du banc sera un artefact, et on l'aura cru. — *Respecté : les neuf portes
existaient avant la première candidate.*

Vérifié par test plutôt que par relecture : la batterie **ne sacre pas** le meilleur d'un lot
de vingt séries de bruit pur (S7, p > 0,05), et **voit** une vraie gagnante glissée dedans.
C'est le seul contrôle qui dise quelque chose sur une batterie de garde-fous.

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
| ~~R1~~ | **Le trailing stop détruit les shorts.** | 🟡 **mesurée 19/08 — INDÉCIDABLE** | mesure du 18/08 — **seul écart du lot à dépasser son MDE**, mais sous-groupe trouvé après coup ⇒ **à préenregistrer avant de mesurer** | S |
| ~~R2~~ | **Mean-reversion** (z-score 48 bougies, seuil 2) | 🔴 **mesurée 19/08 — INFIRMÉE** | `DECISIONS.md` | M |
| **R3** | **Portage / funding** — 86 % du profit de MacroFlip venait de là | ⛔ préenregistrée, **bloquée par D5** | § F1 | M |
| **R4** | **Macro seule**, sans couche technique | ⛔ préenregistrée, **bloquée par D6** | § F1 | M |
| **R5** | **Spot vs perpétuel** — à reposer proprement, avec le hold-out | ⛔ préenregistrée, **bloquée par D7** | § F1 · `BUILD_NOTES` 17/08 | M |
| ~~R6~~ | **`news_window`** — que vaut ce qu'elle bloque ? | 🟡 **mesurée 19/08 — hypothèse NON MESURABLE** | mesure du 18/08 · lien direct avec **C1-bis** | S |

⚠️ **R1 et R6 se mesurent sur les données déjà présentes**, sans écrire une seule candidate.
Ce sont donc les deux moins chers, et les deux premiers à préenregistrer.
— *Fait le 19/08. Les six hypothèses sont préenregistrées, compteur cumulé à **36 essais**.*

### Ce que les mesures du 19/08 ont donné

**R1 — indécidable, et c'est la bonne réponse.** Test apparié sur les 21 shorts du train :
même entrée, même stop, seule la sortie change. La barrière fixe rend **+0,5272 R de plus
par short** (p = 0,0175, IC bootstrap [+0,049 ; +1,006]), mais le **MDE vaut 0,7463 R**.
L'écart est sous le seuil de détection de l'échantillon : la p-value passe, la puissance
non. Il ne survit pas non plus à Benjamini-Hochberg sur la famille de 8 (seuil 0,0125).
Côté long, rien : +0,1282 R pour un MDE de 0,7552, p = 0,27.
*Validation croisée du portage au passage* : −0,4683 R côté trailing, exactement le chiffre
publié le 18/08, et +0,0589 R en barrière fixe contre +0,0637 annoncé.

**R6 — l'hypothèse n'était pas mesurable, et il a fallu la mesurer pour le savoir.**
Les « 756 signaux bloqués » sont **756 lignes de journal**, soit **63 signaux distincts**
(dette T4 : ~13 `gate_check` par signal). Pire : **53 de ces 63 sont aussi acceptés
ailleurs**. `news_window` ne sépare pas une population de signaux d'une autre — elle
retarde un signal, puis le laisse passer quand la fenêtre de news retombe. Les deux groupes
de l'hypothèse n'existent pas ; il reste 10 signaux exploitables.
⇒ **Le chiffre « 91,75 % de tout ce qui est rejeté » décrit des lignes de journal, pas des
signaux.** À corriger partout où il est cité.

**R2 — infirmée, nettement.** 790 trades sur BTC/ETH en 4h, R moyen **−0,2326** pour un MDE
de 0,1450, win rate 27 %. Les neuf portes échouent. Le retour à la moyenne nu, sans filtre
de régime, n'a pas d'edge sur cet univers — ce qui ne dit rien d'une mean-reversion filtrée,
qui serait une autre candidate avec son propre préenregistrement.

---

## P — le pont MCP (double sens)

| # | Chantier | Statut | Effort |
|---|---|---|---|
| ~~P1~~ | ~~Bouton du dashboard qui lance `claude "prompt"` avec le contexte du run~~ | ✅ fermé 19/08 | S |
| ~~P2~~ | ~~Serveur MCP stdio, 7 outils~~ | ✅ fermé 19/08 | M |
| ~~P3~~ | ~~`beta_run_backtest` refuse un run sans préenregistrement~~ | ✅ fermé 19/08 | S |

⚠️ **Rouvert par Jonas le 19/08** (« tous les chantiers M, S, R et P »). Le pipeline
**YouTube → stratégie générée** (`P4`) reste reporté, lui : une vidéo est une source
d'**hypothèses**, jamais d'edge.

Lancement du serveur MCP :
`& C:/Users/jofar/venvs/arit/Scripts/python.exe -m beta.mcp.serveur`

---

## Dettes connues

| # | Dette | Statut | Conséquence si on l'oublie |
|---|---|---|---|
| ~~T1~~ | ~~Repo distant privé non créé~~ | ✅ fermée 19/08 — `github.com/jofari/BETA-`, rebasé sur le commit initial et poussé | — |
| **T2** | **venv partagé avec ARIT** (`C:\Users\jofar\venvs\arit`) | 🔴 ouverte | une mise à jour pour ARIT casse BETA, ou l'inverse |
| **T3** | **Bornes de fin hétérogènes** — LINK/XRP vont au 18/08, les 4 paires d'ARIT s'arrêtent au 04/08 | 🔴 ouverte | un run multi-paires s'arrête à la borne commune sans le dire ; visible dans le dashboard, à ne pas oublier au moment de conclure |
| **T4** | **`ts_utc` du journal d'ARIT ment** sur les événements `gestion` (heure d'exécution du backtest, pas de la bougie). Contourné côté BETA par `signal_id`. ⚠️ **La correction appartient à ARIT** : inscrite là-bas le 19/08 sous **T4-ARIT** (`ARIT2.0/research/pistes_2026-07-31/CHANTIERS.md` § MISE À JOUR DU 2026-08-19) — cause exacte : `ev_gestion()` ne pose pas de `ts_utc`, `write()` retombe sur `_now_iso()` | 🔴 ouverte (contournée ici, **non corrigée** à la source) | à corriger **à la source**, côté ARIT, sinon chaque nouveau consommateur retombera dedans |
| **T5** | **Le pont freqtrade n'a pas ses données** — `--datadir` pointe sur `data/raw`, où seuls LINK et XRP sont en feather ; BTC/ETH/SOL/BNB ne vivent qu'en parquet dans le lake | 🔴 ouverte | la confirmation portefeuille (M3) ne peut tourner que sur 2 paires sur 6. Faire lire `ARIT2.0/user_data/data/` à freqtrade lui ferait écrire dans le dossier d'ARIT — **interdit par l'invariant n° 1** — donc à résoudre par un export feather depuis le lake |
| **T6** | **Chemins synthétiques rejoués sur une seule paire** (la première du run) | 🟠 ouverte, assumée | le coût est linéaire en nombre de paires ; la réserve est écrite dans chaque verdict, elle n'est donc pas silencieuse |
| **T7** | **L'équity à risque fixe non composé peut passer sous zéro** — R2 finit à −83 750 sur 100 000 | 🟠 ouverte, assumée | mathématiquement cohérent, physiquement impossible. Le choix rend deux candidates comparables entre elles ; le compounding se mesure côté freqtrade (M3), une seule fois |


---

## D5-D7 — les données qui manquent, et qui bloquent trois hypothèses

Ouverts le 19/08. Ce ne sont plus des chantiers d'outillage : le banc d'essai fonctionne,
ce sont ses **entrées** qui manquent. Trois hypothèses préenregistrées sont à l'arrêt
faute de séries, et aucune ne peut être mesurée en attendant.

| # | Chantier | Débloque | Effort | Comment |
|---|---|---|---|---|
| **D5** | **Taux de financement** des perpétuels, 6 paires, même profondeur d'historique que l'OHLCV | **R3** (portage / funding) | M | `ccxt.fetch_funding_rate_history`, à verser au lake comme une table de plus, avec son catalogue de trous |
| **D6** | **Séries macro** (DXY, taux, fear & greed) au pas journalier | **R4** (macro seule) | M | ARIT les calcule déjà dans ses évaluations (`regime_inputs.*`) : commencer par les **extraire du journal** plutôt que les retélécharger |
| **D7** | **Séries spot** des mêmes 6 paires | **R5** (spot vs perpétuel) | S | `freqtrade download-data --trading-mode spot`, le chemin existe déjà dans `lake/telechargement.py` |

⚠️ **D6 avant D5.** Les features macro sont déjà sur le disque, dans le journal d'ARIT :
c'est le seul des trois qui ne demande aucun appel réseau. À faire en premier pour cette
seule raison.

## Ce qui reste, après le 19/08

1. **D5-D7** — sans quoi R3, R4 et R5 restent à l'arrêt.
2. **T5** — sans quoi le verdict portefeuille ne couvre que 2 paires sur 6.
3. **De nouvelles candidates.** Le moteur en accepte autant qu'on veut ; il n'en existe
   qu'une. Chacune demande son préenregistrement, et chacune **augmente le compteur
   d'essais** — donc durcit le seuil de toutes les autres. C'est voulu.
