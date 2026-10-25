#!/usr/bin/env python3
"""Télécharge daily klines + funding pour plusieurs symboles futures Binance."""
import json, time, urllib.request, csv, os

OUT = "/root/arit_funding"
os.makedirs(OUT, exist_ok=True)

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

def fetch_funding(sym):
    funding, start = [], 1567000000000
    while True:
        url = (f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}"
               f"&limit=1000&startTime={start}")
        batch = get(url)
        if not batch:
            break
        funding.extend(batch)
        if len(batch) < 1000:
            break
        start = batch[-1]["fundingTime"] + 1
        time.sleep(0.2)
    seen = {f["fundingTime"]: f for f in funding}
    return sorted(seen.values(), key=lambda x: x["fundingTime"])

def fetch_klines(sym):
    kl, start = [], 1500000000000
    while True:
        url = (f"https://fapi.binance.com/fapi/v1/klines?symbol={sym}"
               f"&interval=1d&limit=1500&startTime={start}")
        batch = get(url)
        if not batch:
            break
        kl.extend(batch)
        if len(batch) < 1500:
            break
        start = batch[-1][0] + 1
        time.sleep(0.2)
    seen = {k[0]: k for k in kl}
    return sorted(seen.values(), key=lambda x: x[0])

SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
for sym in SYMS:
    f = fetch_funding(sym)
    with open(f"{OUT}/funding_{sym}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["fundingTime", "fundingRate", "markPrice"])
        for x in f: w.writerow([x["fundingTime"], x["fundingRate"], x["markPrice"]])
    k = fetch_klines(sym)
    with open(f"{OUT}/daily_{sym}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["openTime", "open", "high", "low", "close", "volume"])
        for x in k: w.writerow([x[0], x[1], x[2], x[3], x[4], x[5]])
    print(f"{sym}: funding={len(f)} klines={len(k)} "
          f"({time.strftime('%Y-%m-%d', time.gmtime(k[0][0]/1000))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(k[-1][0]/1000))})")
print("done")
