#!/usr/bin/env python3
"""Vérification B1 (option b) : multiplicateur macro retiré, bump conservé, rétrocompat."""
import sys
sys.path.insert(0, "/root/ARIT2.0/user_data/strategies")

import numpy as np
import pandas as pd
from arit_lib import contracts, params, regimes, cio

ok = True
def check(label, cond):
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {label}")
    if not cond:
        ok = False

def df_macro(adx=30, e50=110, e200=100, close=115, macro="PORTEUR", n=1):
    d = pd.DataFrame({"adx_4h": [adx]*n, "ema50_4h": [e50]*n, "ema200_4h": [e200]*n,
                      "close_4h": [close]*n, contracts.MACRO_REGIME_COL: [macro]*n})
    return d

# --- 1. multiplicateur TREND = x1,0 dans les 3 régimes macro ---
for macro in ("PORTEUR", "NEUTRE", "HOSTILE"):
    out = regimes.classify(df_macro(macro=macro))
    check(f"{macro}: mult long == MULT_FULL", out["multiplicateur"].iloc[0] == params.MULT_FULL)
    check(f"{macro}: mult short == MULT_FULL", out["multiplicateur_short"].iloc[0] == params.MULT_FULL)
    check(f"{macro}: regime == TREND", out["regime"].iloc[0] == "TREND")

# --- 2. TRANSITION reste x0,85 ---
out = regimes.classify(df_macro(adx=22, macro="PORTEUR"))
check("TRANSITION: mult == MULT_REDUCED", out["multiplicateur"].iloc[0] == params.MULT_REDUCED)
check("TRANSITION: regime == TRANSITION", out["regime"].iloc[0] == "TRANSITION")

# --- 3. RANGE/RISK_OFF restent x0 ---
out = regimes.classify(df_macro(adx=15))
check("RANGE: mult == MULT_RISK_OFF", out["multiplicateur"].iloc[0] == params.MULT_RISK_OFF)

# --- 4. bump NEUTRE toujours appliqué par cio ---
def df_cio(macro):
    cols = {c: [0.5] for c in ("s_structure", "s_momentum", "s_sr", "s_patterns", "s_volume")}
    cols.update({c + contracts.SHORT_SUFFIX: [0.5] for c in
                 ("s_structure", "s_momentum", "s_sr", "s_patterns", "s_volume")})
    cols.update({"multiplicateur": [1.0], "multiplicateur_short": [1.0],
                 "seuil": [params.SEUIL_TREND], "regime": ["TREND"],
                 "rr_dispo": [2.0], "rr_dispo_short": [2.0], "new_4h": [True],
                 contracts.TREND_DIR_COL: [0], contracts.MACRO_REGIME_COL: [macro]})
    return pd.DataFrame(cols)

out = cio.conviction(df_cio("NEUTRE"))
check("NEUTRE: seuil bumpé +0,05", abs(out["seuil"].iloc[0] - (params.SEUIL_TREND + params.MACRO_NEUTRE_CONV_BUMP)) < 1e-9)
out = cio.conviction(df_cio("PORTEUR"))
check("PORTEUR: seuil non bumpé", out["seuil"].iloc[0] == params.SEUIL_TREND)

# --- 5. rétrocompat : sans colonne macro, comportement inchangé ---
def df_nomacro():
    return pd.DataFrame({"adx_4h": [30], "ema50_4h": [110], "ema200_4h": [100], "close_4h": [115]})
out = regimes.classify(df_nomacro(), None)
check("rétrocompat: TREND sans colonne macro => mult FULL", out["multiplicateur"].iloc[0] == params.MULT_FULL)
out = regimes.classify(df_nomacro(), {"risk_off": False, "fear_greed": 30, "stale": False})
check("rétrocompat: legacy F&G=30 => mult REDUCED", out["multiplicateur"].iloc[0] == params.MULT_REDUCED)

print("\n" + ("TOUS LES CHECKS PASSENT" if ok else "ÉCHEC — voir ci-dessus"))
sys.exit(0 if ok else 1)
