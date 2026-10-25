#!/usr/bin/env python3
"""Récupère l'historique complet du funding rate BTCUSDT (Binance futures) + klines journalières."""
import json, time, urllib.request, csv, os

OUT = "/root/arit_funding"
os.makedirs(OUT, exist_ok=True)

def get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

# ---- funding history (paginated FORWARD from inception, 8h records since 2019) ----
# NB: no-startTime query returns only the latest 500; paginate with startTime instead.
funding = []
start = 1567000000000  # juste avant l'inception du perp BTCUSDT (~2019-09-10)
while True:
    url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=1000&startTime={start}"
    batch = get(url)
    if not batch:
        break
    funding.extend(batch)
    if len(batch) < 1000:
        break
    start = batch[-1]["fundingTime"] + 1
    time.sleep(0.2)

# dedupe by fundingTime
seen = {}
for f in funding:
    seen[f["fundingTime"]] = f
funding = sorted(seen.values(), key=lambda x: x["fundingTime"])
print(f"funding records: {len(funding)}")
if funding:
    print(f"  first: {time.strftime('%Y-%m-%d', time.gmtime(funding[0]['fundingTime']/1000))}")
    print(f"  last : {time.strftime('%Y-%m-%d', time.gmtime(funding[-1]['fundingTime']/1000))}")

with open(f"{OUT}/funding.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["fundingTime", "fundingRate", "markPrice"])
    for f in funding:
        w.writerow([f["fundingTime"], f["fundingRate"], f["markPrice"]])

# ---- daily klines (paginated FORWARD from inception) ----
klines = []
start = 1500000000000  # ~2017, avant les premiers perp
while True:
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=1500&startTime={start}"
    batch = get(url)
    if not batch:
        break
    klines.extend(batch)
    if len(batch) < 1500:
        break
    start = batch[-1][0] + 1
    time.sleep(0.2)

seen = {}
for k in klines:
    seen[k[0]] = k
klines = sorted(seen.values(), key=lambda x: x[0])
print(f"daily klines: {len(klines)}")
if klines:
    print(f"  first: {time.strftime('%Y-%m-%d', time.gmtime(klines[0][0]/1000))}")
    print(f"  last : {time.strftime('%Y-%m-%d', time.gmtime(klines[-1][0]/1000))}")

with open(f"{OUT}/daily.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["openTime", "open", "high", "low", "close", "volume"])
    for k in klines:
        w.writerow([k[0], k[1], k[2], k[3], k[4], k[5]])

print("done")
