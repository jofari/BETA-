#!/usr/bin/env bash
# Commit + push quotidien des journaux forward (SUIVI_*.jsonl, PAPER_*.jsonl) : sans lui,
# leur seule copie est sur le VPS. Timer beta-journaux, 01:15 UTC, apres le paper.
# Ne touche QUE les journaux : tout autre changement en cours dans le depot reste hors commit.
# Echec (pull impossible parce que le PC a pousse un journal, push refuse) = unite "failed".
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only -q
git add -- SUIVI_*.jsonl PAPER_*.jsonl
if git diff --cached --quiet; then
    echo "journaux : rien de nouveau"
    exit 0
fi
git commit -q -m "Journaux forward du $(date -u +%F) (automatique, timer beta-journaux)"
git push -q
git log --oneline -1
