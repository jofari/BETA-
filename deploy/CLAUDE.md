# CLAUDE.md — `deploy/` : ce qui tourne sur le VPS sans personne

> Famille 2 (utile dans ce dossier) : se charge quand on travaille ici. Texte déplacé de la
> racine le 15/11/2026.


Le même dépôt vit aussi sur un VPS Linux (`/root/BETA-`, venv `/root/venvs/beta`, unités
systemd dans `deploy/`). Le PC et le VPS poussent sur le même `main` : **`git pull --ff-only`
avant de coder**.

- **Timers (UTC)** : `beta-maj` 00:20 (lake) · `beta-suivi` 00:45 (voie C) ·
  `beta-suivi-vc2`…`vc5` 00:50 · `beta-paper` 01:00 (cinq voies) · `beta-journaux` 01:15
  (commit + push des journaux) · `beta-vision` 03:30 (historique public Binance) ·
  `beta-vc4-sessions` (08:02 Londres, 09:32 New York, en semaine) · `beta-paper-direct`
  (chaque minute) · `beta-marches` 23:10 (vrais marchés, quotidien) · `beta-marches-direct`
  (toutes les 5 min, intraday) · `beta-marches-histo` (toutes les heures, rattrapage de l'or
  intraday depuis 2003) · `beta-vc6-paper` 00:40 (paper de plomberie de VC6 V2, non jugé,
  depuis le 03/11/2026 → `PAPER_VC6.jsonl`) · `beta-vc6-rejeu` (lundi 02:00, rejeu du backtest
  → `PAPER_VC6_REJEU.jsonl`).
- **Journaux forward**, à la racine, en ajout seul : `SUIVI_*.jsonl`, `CONSIGNES_VC4.jsonl`,
  `PAPER_*.jsonl` (poussés chaque nuit) ; `DIRECT_PAPER.jsonl` (relevé minute, hors git).
- **Dashboard** `beta-web` en lecture seule sur `127.0.0.1:7474`, ouvert depuis le PC par
  le tunnel `VPS.cmd`. Après un changement de son code : `systemctl restart beta-web`.
- **Alertes** : toute unité `beta-*` en échec — alarme du dry-run comprise (sorties 4 et 5) —
  part sur le salon Discord BETA (drop-in `deploy/notif.conf`).
- Tests sur le VPS : `cd /root/BETA- && /root/venvs/beta/bin/python -m pytest -q`. Les 18 unités
  tournent dans `/root/venvs/beta` depuis la bascule du 16/10/2026 ; `/root/venvs/arit` est le
  venv de freqtrade (téléchargements du lake). Tester dans le venv qui exécute.

## Règles d'exploitation

- **Ne jamais changer de branche dans `/root/BETA-`** : les timers exécutent le code de ce
  dossier, à la minute pour `beta-paper-direct`. Un travail long se fait dans un worktree
  (`git worktree add ../BETA-travail -b <branche> main`), se teste, puis rentre dans `main` en
  avance rapide.
- Une unité qui fait du git a besoin de `Environment=HOME=/root` (sans `User=`, systemd ne donne
  pas de HOME et `/root/.gitconfig` est ignoré : panne de `beta-journaux` le 11/10/2026).
- Toute nouvelle unité reçoit le drop-in `notif.conf` (alerte Discord en cas d'échec).
- Une unité modifiée ici n'est en service qu'après copie dans `/etc/systemd/system/`,
  `systemctl daemon-reload`, puis `enable --now` du timer.
