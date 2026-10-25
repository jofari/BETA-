"""Macro -> indices/or a horizon hebdo/mensuel (5/10/21 jours ouvres). Train/OOS.

Question : la macro transmet-elle aux indices a un horizon plus long, la ou le test
quotidien (h=1) donnait un R2 OOS nul/negatif ?

- features macro (z-score glissant 180j, lag 1j) : vix, breakeven (inflation), tips (taux
  reel), fedfunds, baa10y (credit), dxy, curve (pente 2s10s).
- actifs : SP500, NASDAQ, CAC40, MSCIWORLD, XAUUSD + BTC (témoin, doit rester mort).
- horizons : h = 5, 10, 21 jours (forward simple, chevauchant pour h>1 -> caveat).
- train <= 2023-12-31, test >= 2024-01-01. OLS, R2 OOS + IC + R2 train (overfit).
"""
import numpy as np
import pandas as pd

from beta.lake.lecture import load, macro_globales

ASSETS = ["SP500", "NASDAQ", "CAC40", "MSCIWORLD", "XAUUSD", "BTC"]
MACRO_COLS = ["vix", "breakeven10y", "tips10y", "fedfunds", "baa10y", "dxy", "spread_2s10s"]
FEATS = ["vix", "breakeven", "tips", "fedfunds", "baa10y", "dxy", "curve"]
H = [5, 10, 21]


def zscore(s, w=180, mp=60):
    mu = s.rolling(w, min_periods=mp).mean()
    sd = s.rolling(w, min_periods=mp).std()
    return (s - mu) / sd


def ols(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return beta


def r2_oos(tr, te, feats, ycol):
    beta = ols(tr[FEATS].values, tr[ycol].values)
    Xo = np.column_stack([np.ones(len(te)), te[FEATS].values])
    yo = te[ycol].values
    pred = Xo @ beta
    ssr = ((yo - pred) ** 2).sum()
    sst = ((yo - yo.mean()) ** 2).sum()
    return 1 - ssr / sst, np.corrcoef(pred, yo)[0, 1]


def r2_train(tr, feats, ycol):
    beta = ols(tr[FEATS].values, tr[ycol].values)
    X = np.column_stack([np.ones(len(tr)), tr[FEATS].values])
    y = tr[ycol].values
    pred = X @ beta
    return 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def main() -> int:
    g = macro_globales()
    feats = pd.DataFrame(index=g.index)
    for col, name in zip(MACRO_COLS, FEATS):
        feats[name] = zscore(g[col].astype(float)).shift(1)

    split = pd.Timestamp("2024-01-01", tz="UTC")

    print("R2 OOS (macro -> rendement forward), par actif x horizon :")
    print(f"{'actif':>10}" + "".join(f"{('h='+str(h)):>11}" for h in H))
    for asset in ASSETS:
        c = load(asset, "1d").set_index("date")["close"]
        row = []
        for h in H:
            rf = (c.shift(-h) / c - 1)
            d = pd.DataFrame({"rf": rf}).join(feats, how="inner").dropna()
            tr = d[d.index <= split]
            te = d[d.index > split]
            if len(tr) < 80 or len(te) < 40:
                row.append(float("nan"))
                continue
            r2o, _ic = r2_oos(tr, te, FEATS, "rf")
            row.append(r2o)
        print(f"{asset:>10}" + "".join(f"{v:>+11.3f}" for v in row))

    # Zoom sur or + SP500, h=21 : R2 train vs OOS + IC
    print("\nZoom (h=21) : R2 train vs R2 OOS vs IC (pour voir l'overfit)")
    print(f"{'actif':>10} {'R2 train':>10} {'R2 OOS':>10} {'IC OOS':>10}")
    for asset in ["XAUUSD", "SP500", "BTC"]:
        c = load(asset, "1d").set_index("date")["close"]
        rf = (c.shift(-21) / c - 1)
        d = pd.DataFrame({"rf": rf}).join(feats, how="inner").dropna()
        tr = d[d.index <= split]
        te = d[d.index > split]
        r2t = r2_train(tr, FEATS, "rf")
        r2o, ic = r2_oos(tr, te, FEATS, "rf")
        print(f"{asset:>10} {r2t:>+10.3f} {r2o:>+10.3f} {ic:>+10.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())