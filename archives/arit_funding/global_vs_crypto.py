"""Descriptif (gratuit) : les indicateurs GLOBAUX prédisent-ils la direction du BTC ?

Question ouverte depuis le 10/09 : le régime global (taux, crédit, actions, FX, commodités)
se transmet-il au crypto ? IC de Spearman de chaque indicateur (niveau + variation 30j) vs
retour futur du BTC (7j et 30j), sur l'historique commun.
"""
import csv, glob, time
import numpy as np
import pandas as pd
from scipy import stats

BTC = "/root/arit_funding/daily_BTCUSDT.csv"
G = "/root/ARIT2.0/user_data/data/macro/global/"

# --- BTC close quotidien ---
btc = {}
with open(BTC) as fh:
    for r in csv.DictReader(fh):
        d = time.strftime("%Y-%m-%d", time.gmtime(int(r["openTime"]) / 1000))
        btc[d] = float(r["close"])
btc = pd.Series(btc).sort_index(); btc.index = pd.to_datetime(btc.index)

# --- une série FRED ---
def fred(fichier):
    df = pd.read_csv(G + fichier, parse_dates=["observation_date"], index_col="observation_date")
    s = df.iloc[:, 0].replace(".", np.nan).astype(float)
    return s[s.index >= "2019-01-01"]

series = {
    "VIX (peur)": fred("vix.csv"),
    "TIPS 10y (taux réel)": fred("tips10y.csv"),
    "breakeven 10y (inflation)": fred("breakeven10y.csv"),
    "spread HY (crédit)": fred("hy_oas.csv"),
    "spread IG (crédit)": fred("ig_oas.csv"),
    "DXY (dollar)": fred("dxy.csv"),
    "2s10s (courbe)": fred("spread_2s10s.csv"),
}

def ic(a, b):
    a, b = a.align(b, join="inner")
    m = a.notna() & b.notna()
    a, b = a[m], b[m]
    return stats.spearmanr(a, b)[0] if len(a) > 30 else np.nan

print(f"{'indicateur':28} {'IC niveau→fwd7':>15} {'IC Δ30j→fwd7':>15} {'IC niveau→fwd30':>16}")
print("-" * 76)
for nom, s in series.items():
    fwd7 = btc.shift(-7) / btc - 1
    fwd30 = btc.shift(-30) / btc - 1
    d30 = s.pct_change(30)
    print(f"{nom:28} {ic(s, fwd7):>15.3f} {ic(d30, fwd7):>15.3f} {ic(s, fwd30):>16.3f}")