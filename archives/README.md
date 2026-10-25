# Archives — gardées pour la traçabilité, plus utilisées

Rangées le 13/10/2026 après l'audit du code (accord de Jonas). Rien ici n'est importé par BETA,
lancé par un timer ou relu par un test. On ne les supprime pas : ils expliquent d'où viennent des
décisions encore en vigueur. Seule exception : les deux scripts des voies A et B, supprimés le
25/10/2026 à la demande de Jonas (ci-dessous).

## `recherche_2026-09/` — les voies A et B (25/09)

**Supprimés le 25/10/2026** (Jonas, « ménage des runs ») : les deux scripts ne sont plus dans
l'arbre de travail. Ils restent dans l'historique git ; le dernier commit qui les contient est
`92b53cb`.

Scripts de recherche **hors protocole** : ni préenregistrement, ni compteur, ni batterie S1-S9
(chacun le dit dans son en-tête). C'est de cette exploration, et des scripts de
`/root/arit_funding` (archivés le 25/10 dans `arit_funding/`, ci-dessous), qu'est sortie la
décision A2 et la voie C (`DECISIONS.md`).

- `voie_a_allocation.py` — allocation inverse-vol multi-actifs avec bascule de régime :
  **216 combinaisons** essayées sur le train (≤ 2023-12-31), test 2024+.
- `voie_b_trading.py` — suivi de tendance long/short sur les 6 perpétuels : **1 176
  combinaisons** essayées sur le train, test 2024+.

Ces essais ne figurent pas dans le compteur d'essais (93 au 13/10), pas plus que les 5 760
configurations de l'optimisation de la voie C : la question de les y ajouter est ouverte
(`DECISIONS.md`, « En attente de Jonas »). Leurs fenêtres de test couvrent le hold-out
(2025+) : voir la déclaration du 13/10 dans `DECISIONS.md`.

Pour en retrouver un (rien ne l'exige) :

    git show 92b53cb:archives/recherche_2026-09/voie_a_allocation.py > voie_a_allocation.py
    git show 92b53cb:archives/recherche_2026-09/voie_b_trading.py > voie_b_trading.py

## `arit_funding/` — la recherche de septembre hors dépôt (05/09 → 24/09)

Copie, faite le 25/10/2026 à la demande de Jonas (« ménage des runs »), de ce que contenait
`/root/arit_funding` sur le VPS. Ce dossier a été supprimé ensuite. Ce sont les études et backtests
de septembre pilotés par Hermès, hors protocole : ni préenregistrement, ni compteur.

- 37 scripts `.py`, parmi lesquels les briques de la voie C (22-24/09) : `inverse_vol.py`,
  `btc_seul_voltarget.py`, `balayage_briques.py`, `verif_carry.py`, `mesure_levier.py`.
- `collect_daily.sh` : la copie du script de la tâche Hermès `arit-collecte-quotidienne`, mise
  en pause le 25/10.
- `RAPPORT.md`, `ADDENDUM_donnees.md`, `ETAT_DES_LIEUX.md` et `b1_line.jsonl`.
- Les 19 CSV de données publiques (Binance, blockchain.info, FRED) et `oi_history/` : l'open
  interest relevé chaque jour par Hermès, du 08/09 au 25/10.
- `requirements.txt` : le `pip freeze` du `.venv` du dossier (Python 3.11, créé par uv).

19 des 38 scripts (`.py` et `.sh`) citent en dur le chemin `/root/arit_funding/`, qui n'existe
plus : ils ne tournent pas tels quels. 15 importent `beta`. `RAPPORT.md`, `ADDENDUM_donnees.md`,
`b1_line.jsonl` et 9 scripts existent aussi, identiques, dans ARIT2.0
(`research/pertinence_donnees_2026-09-05/`).

## `consignes_agents/` — les cahiers des charges donnés à des agents

- `chantier_frais.md`, `chantier_frais2.md` — les missions qui ont ajouté les coûts de détention
  au moteur (mi-septembre). Le premier imposait l'estimateur de spread de Corwin & Schultz,
  remplacé le 13/10 par « 1 tick / prix » (il mesurait la volatilité, pas le spread).
- `strategies/` — les prompts de brainstorming et de critique (trois tours) qui ont précédé les
  voies A, B et C, et le brief de la voie C.

Ce qui reste à sa place, parce que c'est un enregistrement du protocole : `intentions/R7.txt`
(les intentions de R7 déclarées avant génération, relues par `CHANTIERS.md`).
