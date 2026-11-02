"""VC6 V1, avant la phase 3 : inventaire des données qu'elle utilise (lecture seule).

Usage : /root/venvs/beta/bin/python VC6_V1/phase3_inventaire.py <sortie.json>

Relit les copies figées de data/vc6_v1/sources_figees/ (funding BTC, ETH, SOL ; or ; ETF monde),
vérifie leur SHA-256 contre VC6_V1/sources_figees.json, et donne début, fin et trous sur toute la
série et sur la période principale (01/06/2021 -> 31/10/2026). Cherche aussi une série de marge
de maintenance dans le lake BETA, data/ et le schéma de la base DS1. N'écrit que <sortie.json>.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import subprocess
import sys

import pandas as pd

RACINE = pathlib.Path("/root/BETA-")
FIGEES = RACINE / "data/vc6_v1/sources_figees"
DEBUT_PRINCIPAL = pd.Timestamp("2021-06-01", tz="UTC")
FIN = pd.Timestamp("2026-10-31", tz="UTC")
MOTIF_MARGE = re.compile(r"(marg|maint|bracket|lever)", re.I)

FUNDING = {"BTC": "BTC_funding", "ETH": "ETH_funding", "SOL": "SOL_funding"}
QUOTIDIENNES = {
    "or_LBMA": "XAU_LBMA_1d",
    "or_SPOT": "XAU_SPOT_1d",
    "or_GCF": "XAUUSD_GCF_1d",
    "or_perp": "XAU_perp_1d",
    "ETF_monde_URTH": "URTH_1d",
}


def sha256(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def controle_hash(nom: str, attendus: dict) -> dict:
    chemin = FIGEES / f"{nom}.parquet"
    reel = sha256(chemin)
    attendu = next(
        (v.get("sha256_copie") for v in attendus.values()
         if v.get("copie") == f"data/vc6_v1/sources_figees/{nom}.parquet"),
        None,
    )
    return {"sha256": reel, "conforme_au_gel": reel == attendu}


def funding(nom: str) -> dict:
    d = pd.read_parquet(FIGEES / f"{nom}.parquet").sort_values("date")
    t = d["date"]

    def trous(tt: pd.Series) -> dict:
        ecarts = tt.diff().dropna()
        jours = pd.date_range(tt.iloc[0].normalize(), FIN, freq="D", tz="UTC")
        jours_sans = jours.difference(tt.dt.normalize().unique())
        return {
            "reglements": int(len(tt)),
            "ecarts_sup_8h": int((ecarts > pd.Timedelta(hours=8)).sum()),
            "ecart_max_h": float(ecarts.max() / pd.Timedelta(hours=1)),
            "ecarts_inf_8h": int((ecarts < pd.Timedelta(hours=8)).sum()),
            "jours_sans_reglement": int(len(jours_sans)),
        }

    principal = t[(t >= DEBUT_PRINCIPAL)]
    return {
        "debut": str(t.iloc[0]),
        "fin": str(t.iloc[-1]),
        "valeurs_manquantes": int(d["funding_rate"].isna().sum()),
        "toute_la_serie": trous(t),
        "periode_principale": trous(principal),
    }


def quotidienne(nom: str) -> dict:
    d = pd.read_parquet(FIGEES / f"{nom}.parquet").sort_values("date")
    dates = d["date"].dt.normalize()

    def trous(dd: pd.Series, debut: pd.Timestamp) -> dict:
        ouvres = pd.bdate_range(debut, FIN, tz="UTC")
        ouvres = ouvres[ouvres <= dd.iloc[-1]]
        manquants = ouvres.difference(dd.unique())
        ecarts = dd.drop_duplicates().diff().dropna()
        return {
            "lignes": int(len(dd)),
            "jours_lun_ven_sans_valeur": int(len(manquants)),
            "ecarts_sup_4_jours": int((ecarts > pd.Timedelta(days=4)).sum()),
            "ecart_max_jours": int(ecarts.max() / pd.Timedelta(days=1)),
            "valeurs_week_end": int((dd.dt.dayofweek >= 5).sum()),
        }

    principal = dates[dates >= DEBUT_PRINCIPAL]
    sortie = {
        "debut": str(d["date"].iloc[0]),
        "fin": str(d["date"].iloc[-1]),
        "clotures_manquantes_ou_non_positives": int((d["close"].isna() | (d["close"] <= 0)).sum()),
        "toute_la_serie": trous(dates, dates.iloc[0]),
        "periode_principale": (
            trous(principal, max(DEBUT_PRINCIPAL, dates.iloc[0])) if len(principal)
            else "aucune ligne"
        ),
        "couvre_periode_principale": bool(dates.iloc[0] <= DEBUT_PRINCIPAL),
    }
    if "volume" in d:
        p = d[d["date"] >= DEBUT_PRINCIPAL]
        sortie["volume_nul_periode_principale"] = int((p["volume"] == 0).sum())
    return sortie


def marge() -> dict:
    fichiers = sorted(
        str(p.relative_to(RACINE))
        for p in (RACINE / "data").rglob("*")
        if p.is_file() and MOTIF_MARGE.search(p.name)
    )
    requete = (
        "select distinct table_schema||'.'||table_name||'.'||column_name "
        "from information_schema.columns "
        "where table_schema not in ('pg_catalog','information_schema') "
        "and (column_name ~* '(marg|maint|bracket|lever)' "
        "or table_name ~* '(marg|maint|bracket|lever)')"
    )
    r = subprocess.run(
        ["docker", "exec", "ds1-db", "psql", "-U", "ds1", "-d", "ds1", "-Atc", requete],
        capture_output=True, text=True,
    )
    colonnes_ds1 = [x for x in r.stdout.splitlines() if x.strip()]
    return {
        "fichiers_data_BETA": fichiers,
        "colonnes_DS1": colonnes_ds1,
        "requete_DS1_ok": r.returncode == 0,
        "presente": bool(fichiers or colonnes_ds1),
    }


def main(sortie: str) -> None:
    attendus = json.loads((RACINE / "VC6_V1/sources_figees.json").read_text())["sources"]
    res: dict = {"funding": {}, "quotidiennes": {}}
    for actif, nom in FUNDING.items():
        res["funding"][actif] = {"copie": nom, **controle_hash(nom, attendus), **funding(nom)}
    for cle, nom in QUOTIDIENNES.items():
        res["quotidiennes"][cle] = {"copie": nom, **controle_hash(nom, attendus), **quotidienne(nom)}
    res["marge_de_maintenance"] = marge()
    manquantes = []
    if not res["marge_de_maintenance"]["presente"]:
        manquantes.append("marge de maintenance")
    for k, v in {**res["funding"], **res["quotidiennes"]}.items():
        if not v["conforme_au_gel"]:
            manquantes.append(f"{k} (copie différente du gel)")
    res["donnees_manquantes"] = manquantes
    res["phase3_possible"] = not manquantes
    pathlib.Path(sortie).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
