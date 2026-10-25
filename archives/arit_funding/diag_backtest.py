#!/usr/bin/env python3
"""Diagnostic : pourquoi 0 trade ? Distribution des régimes + signaux dans le journal backtest."""
import json, glob
from collections import Counter

files = sorted(glob.glob("/root/ARIT2.0/user_data/logs/decisions/*.jsonl"))
regimes = Counter()
macro_regimes = Counter()
decisions = Counter()
convictions = []
signals = []

for f in files:
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if "regime" in d and "scores" in d:  # entrée d'évaluation
            regimes[d["regime"]] += 1
            macro_regimes[d.get("regime_inputs", {}).get("macro_regime", "?")] += 1
            decisions[d.get("decision", "?")] += 1
            if "conviction" in d:
                convictions.append(d["conviction"])
            if d.get("decision") == "signal":
                signals.append(d.get("raison", "?"))

print("=== distribution régime technique ===")
for k, v in regimes.most_common():
    print(f"  {k:<12} {v}")
print("\n=== distribution régime macro ===")
for k, v in macro_regimes.most_common():
    print(f"  {k:<12} {v}")
print("\n=== décisions ===")
for k, v in decisions.most_common():
    print(f"  {k:<12} {v}")
print("\n=== signaux émis ===")
print(f"  total signaux : {len(signals)}")
for s in Counter(signals).most_common():
    print(f"    {s[0]}: {s[1]}")
if convictions:
    import statistics
    print(f"\nconviction: min={min(convictions):.3f} max={max(convictions):.3f} "
          f"moy={statistics.mean(convictions):.3f}")
