#!/usr/bin/env python3
"""Collecteur quotidien d'Open Interest (4 paires) — à planifier en tâche récurrente.

Binance n'expose que ~30 j d'historique OI. Ce script APPEND chaque jour le point OI
courant à un CSV qui s'accumule — dans ~6 mois on a notre propre historique OI propre
et gratuit (la donnée qu'il faudrait payer Coinglass pour avoir).
"""
import json, time, urllib.request, csv, os

OUT = "/root/arit_funding/oi_history"
os.makedirs(OUT, exist_ok=True)
SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

def get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

for sym in SYMS:
    d = get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={sym}")
    ts = d["time"]  # ms
    day = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
    oi_btc = float(d["openInterest"])
    path = f"{OUT}/oi_{sym}.csv"
    exists = os.path.exists(path)
    # ne pas dupliquer la ligne du jour
    dup = False
    if exists:
        with open(path) as fh:
            for line in fh:
                if line.startswith(day):
                    dup = True
    if not dup:
        with open(path, "a", newline="") as fh:
            w = csv.writer(fh)
            if not exists:
                w.writerow(["date", "openInterest"])
            w.writerow([day, oi_btc])
        print(f"{sym}: {day} OI={oi_btc:.2f} BTC (append)")
    else:
        print(f"{sym}: {day} déjà enregistré")
