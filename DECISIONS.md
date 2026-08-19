# DECISIONS.md — BETA : décisions OUVERTES de Jonas

> **But** : un arbitrage de Jonas ne doit jamais vivre uniquement dans une conversation.
> Ce fichier ne contient QUE ce qui attend encore quelque chose — une réponse de Jonas, ou du
> code à écrire. Il se lit en entier en début de session, avant tout code.
>
> **Même règle de tenue qu'ARIT** (`ARIT2.0/DECISIONS.md`, règle du 17/08) : une décision
> appliquée, fermée ou abandonnée **disparaît d'ici dans la même session**, après avoir déposé
> ce qu'elle laisse de durable à sa destination pérenne (travail restant → `CHANTIERS.md`,
> piège ou mesure → les notes du dépôt). La trace des fermées est dans `git log -p -- DECISIONS.md`.
>
> **Frontière avec ARIT** (19/08) : les décisions qui portent sur **AritV1 en production**
> (levier, vétos macro, calendrier, dry-run, VPS, ablations de scores) restent dans
> `ARIT2.0/DECISIONS.md`. Celles qui portent sur **le banc et la recherche d'autres
> stratégies** sont ici. Aucune ne vit aux deux endroits.
>
> **L'état d'avancement n'est pas ici** : il est dans `CHANTIERS.md`, qui fait foi.

---

## F1 — ouverture du banc d'essai : ACTÉ le 2026-08-18

**L'idée (Jonas, 12/08)** : un banc permettant de tester **d'autres stratégies que AritV1**,
pour (1) trouver celle qui a le meilleur rendement et (2) **diversifier les formes
d'investissement**. Motif : l'entrée d'AritV1 n'a aucun edge directionnel mesurable — 78
signaux en 5 ans, p = 0,38 / 0,30 contre le modèle nul.

| Point | Décision du 18/08 |
|---|---|
| **Ouverture** | F1 est **ouvert**. Nom du projet : **BETA**. |
| **Prérequis B2/B5/B6** | levés — **B6 fermé le 18/08** (`ARIT2.0/research/EXPERIMENTS.jsonl`, verrou matériel). Plus aucun verrou méthodologique devant le banc. |
| **Périmètre immédiat** | **les données, et rien d'autre**. « Je veux juste des data pour le moment, pas de nouvelles stratégies automatiques derrière, nous pourrons les réanalyser. » ⇒ le pipeline YouTube → stratégie générée est **reporté**, pas annulé. |
| **Dépendances** | BETA **peut utiliser les pip sécurisés** (pandas/numpy/scipy/pyarrow/duckdb). L'invariant zéro-pip d'ALPHA ne s'applique pas ; le front reste sans CDN. |
| **Univers** | **6 paires** : BTC, ETH, SOL, BNB (habituelles) **+ LINK et XRP**. Critère d'ajout : **l'ancienneté du contrat perpétuel**, pas la popularité — le goulot est le nombre de signaux, donc c'est l'historique qui commande. |
| **Téléchargement** | les 4 habituelles sont **déjà sur disque** — ne lancer que les 2 nouvelles. Les téléchargements peuvent être **simultanés** dans BETA (repère : 27 min pour 4 paires en séquentiel). |
| **Emplacement** | **nouveau dossier hors ARIT2.0, repo git séparé et PRIVÉ.** |
| **Patte graphique** | celle d'ALPHA (`ALPHA/web/style.css`), thème sombre, tokens CSS. |
| **MCP** | double sens : dashboard → Claude Code (comme `ALPHA/alpha/actions.py:160`) **et** Claude Code → BETA (serveur MCP stdio exposant le catalogue, les runs, le registre d'expériences). Reporté avec le pipeline YouTube. |

### Le moteur — tranché le 18/08 : **hybride**

**Moteur maison en espace-R pour cribler** (des centaines de candidates, avec la batterie
statistique complète), **freqtrade pour confirmer** les 2-3 survivantes en conditions
réalistes. Pourquoi aucun des deux seul ne suffisait :

| | Moteur maison (espace-R, vectorisé) | freqtrade |
|---|---|---|
| Monte-Carlo / bootstrap (1 000 runs) | faisable | **irréalisable** avec `--timeframe-detail 5m` |
| Proximité avec ARIT | il faut re-porter la géométrie SL/TP | **native** — même produit, mêmes protections |
| Frais, slots, sizing, compounding | **non simulés** (limite déjà assumée par `replay_entries.py`) | simulés |
| Code à écrire | portage de `ARIT2.0/analysis/dataset.py:_issue` | quasi nul |

⚠️ Conséquence à ne pas perdre de vue : la phase de criblage **ne mesure ni les frais, ni les
slots, ni le compounding**. Un chiffre issu du criblage n'est donc **jamais** un verdict
portefeuille ; seule la phase freqtrade en produit un.

### Les trois risques, redits parce qu'ils ne disparaissent pas

1. **P-hacking industrialisé** — un banc est une machine à multiplier les tests, et il en
   produira d'autant plus de faux gagnants qu'il est efficace. B6 est fermé, mais le
   **compteur d'essais cumulatif** (parti de 30) et le **hold-out scellé** doivent être dans
   BETA dès le premier lot, pas ajoutés après. ⚠️ Ordre imposé : **S1 (Benjamini-Hochberg),
   S2 (Sharpe dégonflé) et S8 (buy-and-hold) avant la première comparaison de candidates.**
2. **Interdit n° 5 d'ARIT** — comparer des stratégies ≠ optimiser des seuils. Le banc ne doit
   jamais devenir un contournement de l'interdiction d'hyperopter G1-G7 et les poids.
   **BETA ne modifie jamais `ARIT2.0`** : il le lit.
3. **Référence imposée** — **buy-and-hold** de la même période pour toute candidate (ex-Q9
   d'ARIT, devenu S8) : ce qui ne bat pas le hold mesure le marché, pas un edge.

**Ce qui reste à faire n'est pas listé ici** : blocs M (moteur), S (multi-test), R (recherche
d'edge), P (MCP) dans `CHANTIERS.md`. Les deux hypothèses les moins chères, **R1** (le
trailing stop détruit les shorts) et **R6** (`news_window`), se mesurent sur les données déjà
présentes, sans écrire une seule candidate : ce sont les deux premières à préenregistrer.

---

## En attente de Jonas

| # | Objet | État | Depuis |
|---|---|---|---|
| **M** | Feu vert pour écrire le moteur (M1-M4) | **à trancher** — le périmètre du 18/08 était « les données, et rien d'autre » | 18/08 |
| **P** | Pont MCP double sens + pipeline YouTube | **reporté** par Jonas | 18/08 |
