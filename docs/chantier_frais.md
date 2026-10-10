# Mission : intégrer les coûts de détention complets au moteur de criblage BETA

Tu travailles sur le repo BETA- (banc d'essai d'edges). Lis CLAUDE.md en début de
session ; tu es sur le VPS Linux (PAS Windows). Le venv est `/root/venvs/arit/bin/python`.
Lance les tests avec : `cd /root/BETA- && /root/venvs/arit/bin/python -m pytest -q`.
Réponds en français, docstrings/code SANS accents (convention du repo).

## Objectif

Le moteur de criblage (`beta/moteur/espace_r.py`) mesure chaque signal en R/trade, mais
il ne paie aujourd'hui que frais + slippage. Il manque deux coûts de détention réels,
ceux qui coûtent de l'argent quand on TIENT une position :

1. **Le spread bid-ask** (jamais appliqué : entrée/sortie au close, zéro écart).
2. **Le funding rate** des perpétuels (adapté ici comme coût, pas comme signal).

Tu dois les intégrer, proprement paramétrés, sans casser les invariants du projet.

## État actuel (ne pas refaire, compléter)

- `beta/moteur/contrats.py` — `Run` porte `frais_pct=0.05` et `slippage_pct=0.02`,
  exposés par `cout_aller_retour_pct = frais_pct + slippage_pct`.
- `beta/moteur/espace_r.py` — `_bloc()` soustrait ce coût en R via :
  `cout_r = (cout_pct / 100.0) * entree / risque`, puis `r_net = r_brut - cout_r`.
  Le facteur `entree / risque` convertit un coût en % du prix en unités de R.
- `beta/moteur/pipeline.py` — `_joindre_funding()` joint déjà la colonne `funding_rate`
  au dataframe (merge_asof backward, sans look-ahead). Les paires indices n'ont PAS cette
  colonne (`_est_indice` court-circuite). Le df passé à `espace_r.evaluer` porte donc déjà
  `funding_rate` quand la paire est un perpétuel, sinon la colonne est absente.
- Le buy-and-hold de référence (`beta/stats/reference.py`) paie déjà `cout_aller_retour_pct`
  une fois. Ne le réécris pas, mais note dans ton résumé s'il devrait aussi payer funding
  et spread (je trancherai séparément).

## Chantier 1 — Spread bid-ask (estimateur, pas de donnée externe)

Il n'existe aucune série historique brute de spread bid-ask Binance en accès libre.
Le spread doit être **estimé depuis les OHLCV déjà dans le lake** (invariant n°2 : aucune
nouvelle source de données, on ne télécharge rien).

Implémente l'estimateur de **Corwin & Schultz (2012)** du spread effectif (high-low spread
estimator), qui donne un spread **relatif au prix**, par bougie, en fenêtre glissante
(propose ~21 jours ; rends la fenêtre un paramètre nommé explicite). C'est une série de
spreads **par paire et variant dans le temps**, exactement ce qui est demandé, calculée de
manière reproductible.

Convention de coût : le spread effectif complet (ask−bid) est payé une fois par
aller-retour — demi-spread à l'entrée, demi-spread à la sortie. Convertis en R avec le
même facteur `entree / risque` que les frais. Gère proprement le warm-up de la fenêtre
glissante (valeurs NaN en début de série) : documente le choix (ex. écarter le signal ou
retomber sur la moyenne des spreads connus).

## Chantier 2 — Funding rate (coût de détention)

Pour les trades issus d'une paire dont le df porte la colonne `funding_rate` (perpétuels
uniquement) : cumule `funding_rate × sens` sur les bougies où la position est ouverte (de
l'entrée à la sortie incluse), puis convertis le total en R via `× entree / risque`.

Signe : un funding positif coûte aux longs (sens = +1) et récompense les shorts
(sens = −1). Hypothèse de notionnel **1x** : collatéral plein, pas de levier — d'où le même
facteur `entree / risque` que pour les frais (une position dont le risque est « risque »
en prix et le notionnel « entree » en prix).

Cas à gérer : colonne absente (indice) => coût funding nul, aucune erreur. `funding_rate`
NaN (trous de jointure) => traite comme 0 plutôt que de faire sauter le trade.

## Chantier 3 — Paramétrage et versionnage des coûts

Dans `Run` (`beta/moteur/contrats.py`) :

- Ajoute `spread: bool = True` et `funding: bool = True` (activés par défaut : c'est le but
  de la mission — les nouveaux runs paient les vrais coûts).
- **Corrige un bug latent** : `Run.id` (propriété) ne tient compte NI de `frais_pct`, NI de
  `slippage_pct`, NI de `spread`/`funding`. Deux runs identiques sauf sur les coûts seraient
  confondus. Ajoute tous les paramètres de coût à la graine de `Run.id` ET à `Run.resume()`.

Ne touche pas au protocole ni au compteur d'essais, ne réexécute aucun run passé.

## Tests à ajouter

Dans `tests/test_moteur.py` (ou le fichier idoine), au minimum :

1. Le spread réduit `r` par rapport à un run sans spread.
2. Un funding positif réduit le R d'un long et augmente le R d'un short.
3. Une paire sans colonne `funding_rate` (indice) ne casse pas l'évaluation.
4. Deux `Run` à coûts différents produisent des `.id` différents.

Vérifie que TOUTE la suite reste verte (baseline actuelle : verte).

## Livrable

Ne commit pas, ne push pas (je décide du versionnage avec le projet). À la fin, résume en
français, de façon concise :

1. Fichiers modifiés et ce qui y a changé.
2. Valeurs de paramètres par défaut retenues (spread on/off, funding on/off, fenêtre de
   l'estimateur).
3. Tests ajoutés + résultat de `pytest`.
4. Points d'attention : impact du changement sur les runs déjà mesurés (R1-R11 gardent
   leurs métriques historiques, mais ne sont plus comparables à un run mesuré après ce
   changement — S7/S9), et la question buy-and-hold.
5. Toute décision que tu as dû prendre seul (ex. traitement du warm-up du spread) et que je
   dois valider.