"""Mesure R3 — le portage (funding) a-t-il une espérance positive nette de frais ?

Cash-and-carry delta-neutre (short perp + long spot approxime par le perp, base ~ 0) :
  carry net/an = mean(funding) * 3 * 365  -  couts amortis
  hold/an      = rendement annualise du buy-and-hold (close du perp, proxy spot)

Regle R3 :  confirmee si net > 0 ET bat le hold ET p <= 0,05
            infirmee  si net <= 0
"""
import glob
import numpy as np
import pandas as pd

PAIRES = ["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"]
BASE = "/root/ARIT2.0/user_data/data/binance/futures"

FRAIS_ALLER_RETOUR_PCT = 0.07       # spot 0,05 + perp 0,02, une fois par jambe


def charger(paire, tf, suffixe):
    d = pd.read_feather(f"{BASE}/{paire}_USDT_USDT-{tf}-{suffixe}.feather")
    d["date"] = pd.to_datetime(d["date"], utc=True)
    return d.set_index("date")


print(f"{'paire':5} {'carry net/an':>13} {'hold/an':>9} {'net > 0':>8} "
      f"{'bat hold':>9} {'p(carry>0)':>11}")
print("-" * 60)
for p in PAIRES:
    fr = charger(p, "1h", "funding_rate")["funding_rate"]
    # annualise : 3 periodes de 8h / jour
    carry_brut = fr.mean() * 3 * 365

    # couts amortis sur la duree de la serie (annees)
    jours = (fr.index[-1] - fr.index[0]).days
    annees = max(jours / 365, 0.1)
    amorti = (FRAIS_ALLER_RETOUR_PCT / 100) / annees
    carry_net = carry_brut - amorti

    # hold : close du perp 1d
    ohlcv = charger(p, "1d", "futures")["close"]
    hold = (ohlcv.iloc[-1] / ohlcv.iloc[0]) ** (365 / max((ohlcv.index[-1] - ohlcv.index[0]).days, 1)) - 1

    # t-test : carry significativement > 0 ?
    se = fr.std() / np.sqrt(len(fr))
    from scipy import stats
    t = fr.mean() / se
    pval = stats.t.sf(t, df=len(fr) - 1)

    print(f"{p:5} {carry_net*100:>12.2f}% {hold*100:>8.1f}% "
          f"{'OUI' if carry_net > 0 else 'non':>8} "
          f"{'OUI' if carry_net > hold else 'non':>9} {pval:<.2e}")