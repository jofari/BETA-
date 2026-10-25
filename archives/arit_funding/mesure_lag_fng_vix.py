"""Mesure du lead/lag de F&G et VIX vs rendements BTC.

Question : les indicateurs de sentiment "reagissent en retard" (ils suivent le prix)
ou "dictent le regime" (ils precedent/coincident) ? La reponse conditionne leur usage
comme FILTRE de regime (l'idee du filtre directionnel intraday).

Methode : cross-correlation entre l'indicateur au jour t et le rendement forward du BTC
a l'horizon h (h>0 = l'indicateur corrrele avec les rendements FUTURS = il precede).
Plus la persistance (autocorrelation), pour juger si c'est un bon label de regime "sticky".
"""
from __future__ import annotations

import pandas as pd

from beta.lake.lecture import fear_greed, load, macro_globales

BTCTF = "1d"


def render(btc_ret_1d: pd.Series) -> pd.DataFrame:
    fng = fear_greed().set_index("date")["fng"]
    glob = macro_globales()
    vix = glob["vix"] if "vix" in glob else pd.Series(dtype=float)

    idx = btc_ret_1d.index
    fng = fng.reindex(idx).ffill()
    vix = vix.reindex(idx).ffill()

    # cross-correlation : corr(indicateur(t), rendement(t+h))
    lags = range(-7, 8)
    rows = []
    for h in lags:
        rows.append({
            "lag_j": h,
            "fng_vs_r": fng.corr(btc_ret_1d.shift(-h)),
            "vix_vs_r": vix.corr(btc_ret_1d.shift(-h)),
        })
    x = pd.DataFrame(rows).set_index("lag_j")

    pers = pd.DataFrame({
        "autocorr_1j": [fng.autocorr(1), vix.autocorr(1)],
        "autocorr_5j": [fng.autocorr(5), vix.autocorr(5)],
        "autocorr_21j": [fng.autocorr(21), vix.autocorr(21)],
    }, index=["fng", "vix"])

    return x, pers


def main() -> int:
    btc = load("BTC", BTCTF).set_index("date")["close"]
    r = btc.pct_change().dropna()

    x, pers = render(r)

    print("Cross-correlation indicateur(t) vs rendement BTC(t+h) — h>0 = l'indicateur PRECEDE le prix\n")
    print(x.round(3).to_string())

    print("\nLecture des signes : F&G positif = greed haussier (attend corr >0 si predictif).")
    print("VIX positif = peur (attend corr <0 si predictif).\n")

    print("Persistance (autocorrelation) — 'sticky' = bon label de regime\n")
    print(pers.round(3).to_string())

    # Synthese : ratio d'energie avant vs apres
    lead = x.loc[[r2 for r2 in [-7, -5, -3, -1]], "fng_vs_r"].abs().mean()
    lag = x.loc[[s for s in [1, 3, 5, 7]], "fng_vs_r"].abs().mean()
    print(f"\nF&G : energie a gauche (reactif) {lead:.3f} vs a droite (predictif) {lag:.3f}")
    lead = x.loc[[r2 for r2 in [-7, -5, -3, -1]], "vix_vs_r"].abs().mean()
    lag = x.loc[[s for s in [1, 3, 5, 7]], "vix_vs_r"].abs().mean()
    print(f"VIX : energie a gauche (reactif) {lead:.3f} vs a droite (predictif) {lag:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())