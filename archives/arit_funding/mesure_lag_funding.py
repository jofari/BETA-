"""Structure temporelle du funding rate BTC : lead ou lag vs rendements ?

DESCRIPTION, pas un test d'edge. Meme question que pour F&G/VIX (reactif/predictif),
mais sur le funding — proxy crypto-natif du positionnement "smart vs dumb money".
Si une structure prometteuse emerge, on la PRE-ENREGISTRE dans BETA avant tout test d'edge.
"""
import pandas as pd

from beta.lake.lecture import funding, load


def main() -> int:
    btc = load("BTC", "1d").set_index("date")["close"]
    r = btc.pct_change().dropna()

    f = funding("BTC").set_index("date")["funding_rate"]
    fd = f.resample("1D").mean().dropna()          # 8h -> quotidien (moyenne)
    fd = fd.reindex(r.index).ffill()

    print("corr( funding quotidien (t) , rendement BTC (t+h) )")
    print("  h>0 : le funding PRECEDE le prix. Fund+ = longs crowded.")
    print()
    for h in range(-7, 8):
        print(f"  lag {h:+d}: {fd.corr(r.shift(-h)):+.4f}")

    print("\npersistance funding quotidien : autocorr 1j / 5j / 21j = "
          f"{fd.autocorr(1):.3f} / {fd.autocorr(5):.3f} / {fd.autocorr(21):.3f}")

    # couverture
    print(f"\ncouverture : funding {fd.index.min().date()} -> {fd.index.max().date()} "
          f"({len(fd)} jours), rendements {r.index.min().date()} -> {r.index.max().date()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())