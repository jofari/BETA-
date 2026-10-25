"""Memo reception "tous les materiaux" — compare BTC / XAUUSD / SP500.

Meme 8 materiaux agnostiques (macro + propre accel_vol) appliques aux 3 actifs,
meme protocole (train <=2024-06, OOS apres), meme OLS. La question : est-ce que la
macro transmet mieux aux actions/or qu'au BTC ?

Features (8, causales) : vix, breakeven (inflation attendue), tips (taux reel),
fedfunds, baa10y (spread credit), dxy, curve (pente), accel_vol (volume de l'actif).
Macro -> lag 1 jour.
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import load, macro_globales

FEATS = ["vix", "breakeven", "tips", "fedfunds", "baa10y", "dxy", "curve", "accel_vol"]
MACRO = ["vix", "breakeven", "tips", "fedfunds", "baa10y", "dxy", "curve"]


def evaluate(asset, g):
    df = load(asset, "1d").set_index("date")
    close, vol = df["close"], df["volume"]

    raw = pd.DataFrame(index=close.index)
    raw["accel_vol"] = vol / vol.rolling(30).mean().shift(1)
    raw["vix"] = g["vix"]
    raw["breakeven"] = g["breakeven10y"]
    raw["tips"] = g["tips10y"]
    raw["fedfunds"] = g["fedfunds"]
    raw["baa10y"] = g["baa10y"]
    raw["dxy"] = g["dxy"]
    raw["curve"] = g["spread_2s10s"]
    for c in MACRO:
        raw[c] = raw[c].shift(1)
    raw["y"] = close.pct_change().shift(-1)

    mu = raw[FEATS].rolling(180, min_periods=60).mean()
    sd = raw[FEATS].rolling(180, min_periods=60).std()
    raw[FEATS] = (raw[FEATS] - mu) / sd

    data = raw.dropna()
    split = pd.Timestamp("2024-06-30", tz="UTC")
    tr = data[data.index <= split]
    te = data[data.index > split]
    if len(tr) < 30 or len(te) < 30:
        return asset, len(data), len(tr), len(te), np.nan, np.nan, np.nan

    X1 = np.column_stack([np.ones(len(tr)), tr[FEATS].values])
    beta, *_ = np.linalg.lstsq(X1, tr["y"].values, rcond=None)

    Xo = np.column_stack([np.ones(len(te)), te[FEATS].values])
    yo = te["y"].values
    pred = Xo @ beta
    r2 = 1 - ((yo - pred) ** 2).sum() / ((yo - yo.mean()) ** 2).sum()
    ic = np.corrcoef(pred, yo)[0, 1]
    hit = (np.sign(pred) == np.sign(yo)).mean()
    return asset, len(data), len(tr), len(te), r2, ic, hit


def main() -> int:
    g = macro_globales()
    print(f"{'asset':>9} | {'n':>5} | {'train':>6} | {'test':>5} | {'R2 OOS':>8} | {'IC':>7} | {'hit':>6}")
    for a in ["BTC", "XAUUSD", "SP500"]:
        asset, n, ntr, nte, r2, ic, hit = evaluate(a, g)
        print(f"{asset:>9} | {n:>5} | {ntr:>6} | {nte:>5} | {r2:>+8.4f} | {ic:>+7.4f} | {hit:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())