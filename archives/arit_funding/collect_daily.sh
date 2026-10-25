#!/bin/bash
# Collecte quotidienne ARIT : Open Interest (4 paires) + données macro.
# Planifiée en cron (no_agent) — construit l'historique OI propre qu'on ne peut pas acheter.
set -e
VENV=/root/venvs/arit/bin/python
$VENV /root/arit_funding/collect_oi.py
$VENV /root/ARIT2.0/scripts/download_macro.py 2>&1 | tail -3
echo "collecte terminée $(date -u +%Y-%m-%dT%H:%M:%SZ)"
