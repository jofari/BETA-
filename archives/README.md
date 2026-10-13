# Archives — gardées pour la traçabilité, plus utilisées

Rangées le 13/10/2026 après l'audit du code (accord de Jonas). Rien ici n'est importé par BETA,
lancé par un timer ou relu par un test. On ne les supprime pas : ils expliquent d'où viennent des
décisions encore en vigueur.

## `recherche_2026-09/` — les voies A et B (25/09)

Scripts de recherche **hors protocole** : ni préenregistrement, ni compteur, ni batterie S1-S9
(chacun le dit dans son en-tête). C'est de cette exploration, et des scripts de
`/root/arit_funding` (hors dépôt), qu'est sortie la décision A2 et la voie C (`DECISIONS.md`).

- `voie_a_allocation.py` — allocation inverse-vol multi-actifs avec bascule de régime :
  **216 combinaisons** essayées sur le train (≤ 2023-12-31), test 2024+.
- `voie_b_trading.py` — suivi de tendance long/short sur les 6 perpétuels : **1 176
  combinaisons** essayées sur le train, test 2024+.

Ces essais ne figurent pas dans le compteur d'essais (93 au 13/10), pas plus que les 5 760
configurations de l'optimisation de la voie C : la question de les y ajouter est ouverte
(`DECISIONS.md`, « En attente de Jonas »). Leurs fenêtres de test couvrent le hold-out
(2025+) : voir la déclaration du 13/10 dans `DECISIONS.md`.

Pour en relancer un (rien ne l'exige) :

    ARIT_HOME=/root/ARIT2.0 PYTHONPATH=/root/BETA- \
        /root/venvs/arit/bin/python archives/recherche_2026-09/voie_a_allocation.py

## `consignes_agents/` — les cahiers des charges donnés à des agents

- `chantier_frais.md`, `chantier_frais2.md` — les missions qui ont ajouté les coûts de détention
  au moteur (mi-septembre). Le premier imposait l'estimateur de spread de Corwin & Schultz,
  remplacé le 13/10 par « 1 tick / prix » (il mesurait la volatilité, pas le spread).
- `strategies/` — les prompts de brainstorming et de critique (trois tours) qui ont précédé les
  voies A, B et C, et le brief de la voie C.

Ce qui reste à sa place, parce que c'est un enregistrement du protocole : `intentions/R7.txt`
(les intentions de R7 déclarées avant génération, relues par `CHANTIERS.md`).
