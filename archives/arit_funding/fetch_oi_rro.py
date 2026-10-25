#!/usr/bin/env python3
"""Fetch KCRORO (RORO, FRED) + Open Interest historique Binance."""
import json, time, urllib.request, csv

OUT = "/root/arit_funding"

def get(url, retries=4):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))

# --- OI historique Binance (période 1d, pagination) ---
def get_oi_page(start=None, end=None):
    url = "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1d&limit=500"
    if start:
        url += f"&startTime={start}"
    if end:
        url += f"&endTime={end}"
    return json.loads(get(url))

oi = []
# d'abord remonter le plus loin possible en arrière
start = None
while True:
    page = get_oi_page(start=start)
    if not page:
        break
    oi.extend(page)
    if len(page) < 500:
        break
    start = page[-1]["timestamp"] + 1
    time.sleep(0.2)

# dédupliquer par timestamp
seen = {}
for x in oi:
    seen[x["timestamp"]] = x
oi = sorted(seen.values(), key=lambda x: x["timestamp"])

with open(f"{OUT}/oi_btc.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["timestamp", "sumOpenInterest", "sumOpenInterestValue"])
    for x in oi:
        w.writerow([x["timestamp"], x["sumOpenInterest"], x["sumOpenInterestValue"]])

if oi:
    t0 = time.strftime("%Y-%m-%d", time.gmtime(oi[0]["timestamp"]/1000))
    t1 = time.strftime("%Y-%m-%d", time.gmtime(oi[-1]["timestamp"]/1000))
    print(f"OI BTC: {len(oi)} points ({t0} -> {t1})")
else:
    print("OI: AUCUN point récupéré")
