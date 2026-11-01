"""VC6 V1, etape A : inventaire des sources et copies figees (lecture seule des sources).

Usage : /root/venvs/beta/bin/python inventaire.py <sortie.json>
Lit le lake BETA, beta.marches et DS1 (docker exec psql, lecture seule). N'ecrit QUE dans
data/vc6_v1/sources_figees/ (copies tronquees a la date de fin) et dans <sortie.json>.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import numpy as np
import pandas as pd

RACINE = pathlib.Path("/root/BETA-")
sys.path.insert(0, str(RACINE))

from beta import config  # noqa: E402
from beta.marches import collecte, intraday, sources  # noqa: E402

FIN = pd.Timestamp("2026-10-31", tz="UTC")            # derniere cloture UTC complete
BORNE = FIN + pd.Timedelta(days=1)                     # 2026-11-01 00:00 UTC
FIGEES = config.DATA / "vc6_v1" / "sources_figees"


def sha256(chemin: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def plages(manquants: pd.DatetimeIndex, pas: pd.Timedelta) -> list[dict]:
    """Regroupe des instants manquants consecutifs (au pas donne) en plages."""
    if len(manquants) == 0:
        return []
    m = manquants.sort_values()
    coupe = np.flatnonzero(np.diff(m.asi8) != pas.value) + 1
    sortie = []
    for bloc in np.split(np.arange(len(m)), coupe):
        a, b = m[bloc[0]], m[bloc[-1]]
        sortie.append({"debut": str(a), "fin": str(b), "n": int(len(bloc))})
    return sortie


def trous_7j(dates: pd.DatetimeIndex) -> dict:
    d = pd.DatetimeIndex(dates).normalize()
    attendu = pd.date_range(d.min(), d.max(), freq="D", tz=d.tz)
    manq = attendu.difference(d)
    return {"jours_attendus": int(len(attendu)), "jours_manquants": int(len(manq)),
            "plages_manquantes": plages(manq, pd.Timedelta(days=1))[:20]}


def trous_ouvres(dates: pd.DatetimeIndex) -> dict:
    """Series de jours de bourse : jours lun-ven sans valeur (feries compris), ecarts > 4 j."""
    d = pd.DatetimeIndex(dates).normalize()
    ouvres = pd.bdate_range(d.min(), d.max(), tz=d.tz)
    manq = ouvres.difference(d)
    ecarts = pd.Series(d[1:] - d[:-1], index=d[1:])
    longs = ecarts[ecarts > pd.Timedelta(days=4)]
    return {"jours_lun_ven": int(len(ouvres)), "lun_ven_sans_valeur": int(len(manq)),
            "ecarts_plus_de_4_jours": int(len(longs)),
            "plus_longs_ecarts": [{"apres": str(i - e), "avant": str(i), "jours": int(e.days)}
                                  for i, e in longs.sort_values(ascending=False).head(10).items()],
            "observations_samedi_dimanche": int((d.weekday >= 5).sum())}


def trous_5m(ts: pd.DatetimeIndex) -> dict:
    t = pd.DatetimeIndex(ts)
    pas = pd.Timedelta(minutes=5)
    attendu = int((t.max() - t.min()) / pas) + 1
    dif = pd.Series(t[1:] - t[:-1], index=t[1:])
    trous = dif[dif > pas]
    liste = [{"apres": str(i - e), "avant": str(i), "barres_manquantes": int(e / pas) - 1,
              "heures": round((e - pas).total_seconds() / 3600, 2)}
             for i, e in trous.sort_values(ascending=False).head(15).items()]
    return {"barres": int(len(t)), "barres_attendues": attendu,
            "barres_manquantes": int(attendu - len(t)), "n_trous": int(len(trous)),
            "plus_grands_trous": liste,
            "doublons": int(t.duplicated().sum())}


def lire_lake(slug: str, tf: str) -> tuple[pd.DataFrame, pathlib.Path]:
    chemin = config.chemin_parquet(slug, tf)
    df = pd.read_parquet(chemin)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    return df.sort_values("date").reset_index(drop=True), chemin


def figer(df: pd.DataFrame, nom: str) -> dict:
    FIGEES.mkdir(parents=True, exist_ok=True)
    chemin = FIGEES / f"{nom}.parquet"
    df.to_parquet(chemin, index=False)
    return {"copie": str(chemin.relative_to(RACINE)), "sha256_copie": sha256(chemin),
            "lignes_copie": int(len(df))}


def base(df: pd.DataFrame, col: str = "close") -> dict:
    return {"debut": str(df["date"].min()), "fin": str(df["date"].max()), "n": int(len(df)),
            "valeurs_non_positives": int((df[col] <= 0).sum()) if col in df else None}


def main(sortie: pathlib.Path) -> None:
    inv: dict = {"fin_figee": f"{FIN:%Y-%m-%d}", "borne_exclue_barres": str(BORNE),
                 "fige_le": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
                 "sources": {}}
    S = inv["sources"]

    # --- clotures journalieres crypto (lake : perpetuels Binance USDT-M) -------------------
    for base_ in ("BTC", "ETH", "SOL"):
        slug = f"{base_}_USDT_USDT"
        df, chemin = lire_lake(slug, "1d")
        e = {"origine": f"lake BETA {chemin.relative_to(RACINE)} (perpetuel Binance USDT-M, "
                        "bougie 1d, date = ouverture 00:00 UTC)",
             "sha256_fichier_vivant": sha256(chemin), **base(df), **trous_7j(df["date"]),
             "volume_nul": int((df["volume"] <= 0).sum())}
        f = df[df["date"] < BORNE]
        e.update(figer(f, f"{base_}_perp_1d"))
        S[f"{base_}_perp_1d"] = e

    # --- BTC spot : beta.marches BTC_DS1 (parquet) et DS1 bougies_1d (base) ----------------
    chemin = collecte.chemin(("BTC_DS1")) if hasattr(collecte, "chemin") else \
        config.DATA / "marches" / "BTC_DS1-1d.parquet"
    df = pd.read_parquet(chemin)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    S["BTC_DS1_parquet"] = {"origine": f"beta.marches {pathlib.Path(chemin).relative_to(RACINE)}"
                                       " (DS1 bougies_1d Bitstamp, recopie a 23:10 UTC)",
                            "sha256_fichier_vivant": sha256(pathlib.Path(chemin)), **base(df),
                            **trous_7j(df["date"])}
    parquet_ds1 = df.set_index("date")["close"]
    for src in ("bitstamp", "coinbase"):
        d = sources.ds1_bougies_1d(src).reset_index()
        d["date"] = pd.to_datetime(d["date"]).dt.tz_localize("UTC")
        e = {"origine": f"DS1 table bougies_1d, source {src}, symbole BTCUSD (docker exec psql, "
                        "lecture seule ; jour civil UTC clos)", **base(d), **trous_7j(d["date"]),
             "volume_nul": int((d["volume"] <= 0).sum())}
        if src == "bitstamp":
            commun = parquet_ds1.index.intersection(d.set_index("date").index)
            ecart = (d.set_index("date")["close"].reindex(commun) - parquet_ds1.reindex(commun))
            e["controle_vs_parquet_BTC_DS1"] = {"dates_communes": int(len(commun)),
                                                "ecart_max_abs_close": float(ecart.abs().max())}
        f = d[d["date"] <= FIN]
        e.update(figer(f, f"BTC_{src}_1d"))
        S[f"BTC_{src}_1d"] = e

    # --- bougies 5 min (lake) ---------------------------------------------------------------
    for base_ in ("BTC", "ETH", "SOL"):
        slug = f"{base_}_USDT_USDT"
        df, chemin = lire_lake(slug, "5m")
        e = {"origine": f"lake BETA {chemin.relative_to(RACINE)} (perpetuel Binance USDT-M, "
                        "date = ouverture de la bougie)",
             "sha256_fichier_vivant": sha256(chemin), **base(df), **trous_5m(df["date"]),
             "volume_nul": int((df["volume"] <= 0).sum())}
        f = df[df["date"] < BORNE]
        # controle : la bougie 1d du dernier jour = agregat des 5 min de ce jour
        jour = f[f["date"] >= FIN]
        d1, _ = lire_lake(slug, "1d")
        b = d1[d1["date"] == FIN].iloc[0]
        e["controle_dernier_jour"] = {
            "barres_5m_du_31_10": int(len(jour)),
            "volume_5m": float(jour["volume"].sum()), "volume_1d": float(b["volume"]),
            "close_5m": float(jour["close"].iloc[-1]), "close_1d": float(b["close"]),
            "high_5m": float(jour["high"].max()), "high_1d": float(b["high"]),
            "low_5m": float(jour["low"].min()), "low_1d": float(b["low"])}
        e.update(figer(f, f"{base_}_perp_5m"))
        S[f"{base_}_perp_5m"] = e

    # --- funding ---------------------------------------------------------------------------
    for base_ in ("BTC", "ETH", "SOL"):
        chemin = config.chemin_feather_funding(f"{base_}_USDT_USDT")
        df = pd.read_feather(chemin)
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.sort_values("date").reset_index(drop=True)
        dif = df["date"].diff().dropna().dt.total_seconds() / 3600
        compte = dif.round(3).value_counts().sort_index()
        longs = df.loc[dif[dif > 8].index, "date"]
        e = {"origine": f"{chemin.relative_to(RACINE)} (freqtrade, Binance USDT-M ; date = "
                        "instant de reglement)",
             "sha256_fichier_vivant": sha256(chemin),
             "debut": str(df["date"].min()), "fin": str(df["date"].max()), "n": int(len(df)),
             "intervalles_heures": {str(k): int(v) for k, v in compte.items()},
             "ecarts_plus_de_8h": [{"avant": str(t), "heures": float(dif[i])}
                                   for i, t in longs.items()][:20],
             "heures_de_reglement": {str(k): int(v) for k, v in
                                     df["date"].dt.hour.value_counts().sort_index().items()},
             "taux_nan": int(df["funding_rate"].isna().sum())}
        f = df[df["date"] <= BORNE]
        e.update(figer(f, f"{base_}_funding"))
        S[f"{base_}_funding"] = e

    # --- or ---------------------------------------------------------------------------------
    for nom, lire, origine in (
            ("XAU_LBMA", lambda: pd.read_parquet(config.DATA / "marches" / "XAU_LBMA-1d.parquet"),
             "beta.marches data/marches/XAU_LBMA-1d.parquet (fixing LBMA PM, World Gold Council)"),
            ("XAU_SPOT", lambda: pd.read_parquet(config.DATA / "marches" / "XAU_SPOT-1d.parquet"),
             "beta.marches data/marches/XAU_SPOT-1d.parquet (Dukascopy BID, jour UTC agrege)")):
        df = lire()
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.sort_values("date").reset_index(drop=True)
        chemin = config.DATA / "marches" / f"{nom}-1d.parquet"
        e = {"origine": origine, "sha256_fichier_vivant": sha256(chemin), **base(df),
             **trous_ouvres(df["date"])}
        f = df[df["date"] <= FIN]
        e.update(figer(f, f"{nom}_1d"))
        S[nom] = e
    for slug, nom, origine, ouvre in (
            ("XAUUSD", "XAUUSD_GCF", "lake BETA data/lake/XAUUSD-1d.parquet (yfinance GC=F, "
                                     "future COMEX continu)", True),
            ("XAU_USDT_USDT", "XAU_perp", "lake BETA data/lake/XAU_USDT_USDT-1d.parquet "
                                          "(perpetuel TradFi Binance XAUUSDT)", False),
            ("MSCIWORLD", "URTH", "lake BETA data/lake/MSCIWORLD-1d.parquet (yfinance URTH, "
                                  "iShares MSCI World ETF)", True)):
        df, chemin = lire_lake(slug, "1d")
        e = {"origine": origine, "sha256_fichier_vivant": sha256(chemin), **base(df),
             **(trous_ouvres(df["date"]) if ouvre else trous_7j(df["date"]))}
        if "volume" in df:
            e["volume_nul"] = int((df["volume"] <= 0).sum())
            if nom == "URTH":
                nul = df[df["volume"] <= 0]
                e["volume_nul_derniere_date"] = str(nul["date"].max()) if len(nul) else None
                e["volume_nul_par_annee"] = {str(k): int(v) for k, v in
                                             nul["date"].dt.year.value_counts().sort_index().items()}
                plat = df[(df["open"] == df["high"]) & (df["high"] == df["low"])]
                e["barres_plates_ohlc_egaux"] = int(len(plat))
        f = df[df["date"] <= FIN]
        e.update(figer(f, f"{nom}_1d"))
        S[nom] = e

    sortie.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
