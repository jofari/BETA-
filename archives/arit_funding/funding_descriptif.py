"""Mesure DESCRIPTIVE du portage (funding) — aucun Run, compteur non engagé.

Répond à la question de R3 : « le funding des perpétuels a-t-il une espérance positive
nette de frais ? » — en chiffres bruts, par paire, sur tout l'historique.

Funding rate connu au DÉBUT de la période (pas de look-ahead). Annualisé sur 3 périodes/jour.
"""
import glob
import pandas as pd

PAIRES = ["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"]
BASE = "/root/ARIT2.0/user_data/data/binance/futures"


def charger(paire: str) -> pd.DataFrame:
    d = pd.read_feather(f"{BASE}/{paire}_USDT_USDT-1h-funding_rate.feather")
    d["date"] = pd.to_datetime(d["date"], utc=True)
    return d.set_index("date")["funding_rate"]


print(f"{'paire':5} {'périodes':>8} {'moyen/an':>9} {'% positifs':>10} "
      f"{'short carry/an':>14} {'long carry/an':>13}")
print("-" * 65)
for p in PAIRES:
    fr = charger(p)
    n = len(fr)
    annuel = fr.mean() * 3 * 365          # 3 périodes de 8h par jour
    pct_pos = (fr > 0).mean() * 100
    short_carry = (fr[fr > 0].mean() if (fr > 0).any() else 0) * 3 * 365
    long_carry = (fr[fr < 0].mean() if (fr < 0).any() else 0) * 3 * 365
    print(f"{p:5} {n:>8} {annuel*100:>8.2f}% {pct_pos:>9.1f}% "
          f"{short_carry*100:>13.2f}% {long_carry*100:>12.2f}%")