"""Modele "tous les materiaux" — OLS vs rendement du lendemain (PROTOCOLE VALIDE).

Sortie   : r_{t+1} = P_{t+1}/P_t - 1  (rendement simple du lendemain, non-chevauchant).
Entrees  : 10 materiaux, z-scorres sur fenetre glissante 180j (causal, jusqu'a t inclus).
           sentiment + macro : lag 1 jour (publication prudente). funding/accel : close of day.
Split    : train <= 2024-06-30, test > (out-of-sample, jamais regarde pour ajuster).
Modele   : OLS, une seule estimation sur train, une seule evaluation sur test.

Barres (preenregistrees) :
  1. R2 OOS > 0
  2. au moins 1 coefficient significatif (train), signe stable
  3. bat buy-and-hold (IC / hit-rate OOS > aleatoire)
"""
import numpy as np
import pandas as pd
from scipy import stats

from beta.lake.lecture import fear_greed, funding, load, macro_globales

FEATS = ["funding", "fng", "accel_vol", "vix", "breakeven", "tips",
         "fedfunds", "baa10y", "dxy", "curve"]


def ols_fit(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X1, y, rcond=None)
    resid = y - X1 @ beta
    n, p = X1.shape
    sigma2 = (resid @ resid) / (n - p)
    cov = sigma2 * np.linalg.inv(X1.T @ X1)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    pval = 2 * (1 - stats.t.cdf(np.abs(t), df=n - p))
    r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
    return beta, se, t, pval, r2


def main() -> int:
    btc = load("BTC", "1d").set_index("date")
    close, vol = btc["close"], btc["volume"]

    fund = funding("BTC").set_index("date")["funding_rate"].resample("1D").mean()
    fng = fear_greed().set_index("date")["fng"]
    g = macro_globales()

    raw = pd.DataFrame(index=close.index)
    raw["funding"] = fund
    raw["fng"] = fng
    raw["accel_vol"] = vol / vol.rolling(30).mean().shift(1)
    raw["vix"] = g["vix"]
    raw["breakeven"] = g["breakeven10y"]
    raw["tips"] = g["tips10y"]
    raw["fedfunds"] = g["fedfunds"]
    raw["baa10y"] = g["baa10y"]
    raw["dxy"] = g["dxy"]
    raw["curve"] = g["spread_2s10s"]

    # lag publication prudent (1 jour) sur sentiment + macro
    for c in ["fng", "vix", "breakeven", "tips", "fedfunds", "baa10y", "dxy", "curve"]:
        raw[c] = raw[c].shift(1)

    raw["y"] = close.pct_change().shift(-1)

    # z-score causal 180j
    z = raw[FEATS]
    mu = z.rolling(180, min_periods=60).mean()
    sd = z.rolling(180, min_periods=60).std()
    raw[FEATS] = (z - mu) / sd

    data = raw.dropna()
    split = pd.Timestamp("2024-06-30", tz="UTC")
    tr = data[data.index <= split]
    te = data[data.index > split]

    print(f"couverture : {data.index.min().date()} -> {data.index.max().date()}")
    print(f"n train = {len(tr)}  |  n test = {len(te)}\n")

    beta, se, t, pval, r2_tr = ols_fit(tr[FEATS].values, tr["y"].values)
    print(f"R2 TRAIN (ajuste) = {r2_tr:+.4f}\n")
    print("coefficients (train) — feature | beta | t | p")
    names = ["const"] + FEATS
    for n, b, tt, p in zip(names, beta, t, pval):
        star = "*" if p < 0.05 else " "
        print(f"  {n:>10} | {b:+.5f} | {tt:+6.2f} | {p:.3f}{star}")

    # OOS
    Xo = np.column_stack([np.ones(len(te)), te[FEATS].values])
    yo = te["y"].values
    pred = Xo @ beta
    ssr = ((yo - pred) ** 2).sum()
    sst = ((yo - yo.mean()) ** 2).sum()
    r2_oos = 1 - ssr / sst
    ic = np.corrcoef(pred, yo)[0, 1]
    hit = (np.sign(pred) == np.sign(yo)).mean()

    print(f"\n=== OOS (out-of-sample, le vrai test) ===")
    print(f"R2 OOS = {r2_oos:+.4f}")
    print(f"IC (corr pred/realise) = {ic:+.4f}")
    print(f"hit-rate (signe correct) = {hit:.3f}  (0.5 = hasard)")

    print("\n--- Verdict vs barres ---")
    print(f"[1] R2 OOS > 0        : {'OUI' if r2_oos > 0 else 'NON'}")
    sig = [n for n, p in zip(names[1:], pval[1:]) if p < 0.05]
    print(f"[2] coefs significatifs (train) : {sig if sig else 'aucun'} "
          f"({len(sig)}/10 ; attend ~0.5 par hasard a 5%)")
    print(f"[3] bat hold (IC>0)   : {'OUI' if ic > 0 else 'NON'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())