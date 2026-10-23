"""Fiches detaillees des voies d'allocation (voie C, VC2-VC5) pour l'onglet Candidates.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/fiches_voies.py

REJOUE les backtests DEJA MESURES, a l'identique (memes configs, meme fenetre 2021-06-12 ->
2026-09-05, rien n'est charge apres) et ecrit `data/voies/fiches.json` pour l'affichage. Ce
n'est PAS une mesure : rien n'est journalise dans EXPERIMENTS/RUNS, le compteur d'essais ne
bouge pas, aucune porte n'est jugee. Le script s'arrete si un Sharpe rejoue s'ecarte de celui
qui a ete mesure (la fiche montrerait alors autre chose que le verdict).

`data/` est jetable : relancer ce script suffit a refaire les fiches. La fenetre etant figee,
il n'a pas besoin de timer ; le forward (depuis le gel) est relu en direct par le serveur.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import math
import pathlib
import sys

import numpy as np
import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.rapport import voies  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402
from beta.strategies import voie_c4 as c4  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.fiches_voies")

PAS_COURBE = 3                      # un point tous les 3 jours : ~640 points sur 5 ans
TOLERANCE_SHARPE = 0.006          # les Sharpe mesures sont arrondis au centieme

# Sharpe mesures (DECISIONS.md, scripts/mesurer_vc*.py ; voie C : voie_c_suivi, frais 5 pb).
SHARPE_MESURE = {"VOIE_C": 1.11, "VC2": 0.72, "VC3": 0.80, "VC4": 0.76, "VC5": 0.75}


def _charger_suivi_voie_c():
    spec = importlib.util.spec_from_file_location("voie_c_suivi",
                                                  RACINE / "scripts" / "voie_c_suivi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _perf(r: pd.Series) -> dict:
    p = vc.performance(r)
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in p.items()}


def _equite(r: pd.Series) -> pd.Series:
    return (1.0 + r).cumprod()


def _dd(r: pd.Series) -> pd.Series:
    e = _equite(r)
    return e / e.cummax() - 1.0


def _par_annee(series: dict[str, pd.Series]) -> list[dict]:
    lignes = []
    for annee in sorted(set(series["strat"].index.year)):
        ligne = {"annee": int(annee)}
        for nom, r in series.items():
            tranche = r[r.index.year == annee]
            ligne[nom] = float(_equite(tranche).iloc[-1] - 1.0)
            ligne[f"mdd_{nom}"] = float(_dd(tranche).min())
        ligne["jours"] = int((series["strat"].index.year == annee).sum())
        lignes.append(ligne)
    return lignes


def _fiche(nom: str, r: pd.Series, refs: dict[str, pd.Series], extra: dict) -> dict:
    r = r.astype(float)
    jours = r.index
    series = {"strat": r} | {k: v.reindex(jours).fillna(0.0) for k, v in refs.items()}
    masques = {"pleine": np.ones(len(jours), bool),
               "train": np.asarray(jours <= c2.FIN_TRAIN),
               "oos": np.asarray(jours > c2.FIN_TRAIN)}
    periodes = {p: {k: _perf(s[m]) for k, s in series.items()} for p, m in masques.items()}
    for p, m in masques.items():
        if extra.get("turnover") is not None:
            periodes[p]["strat"]["turnover"] = float(extra["turnover"][m].mean() * vc.JOURS_AN)
        if extra.get("frais") is not None:
            periodes[p]["strat"]["frais"] = float(extra["frais"][m].mean() * vc.JOURS_AN)

    equites = {k: _equite(s) for k, s in series.items()}
    dds = {k: _dd(s) for k, s in series.items()}
    brut = extra.get("brut")
    idx = list(range(0, len(jours), PAS_COURBE))
    if idx[-1] != len(jours) - 1:
        idx.append(len(jours) - 1)
    courbe = []
    for i in idx:
        point = {"date": jours[i].strftime("%Y-%m-%d")}
        for k in series:
            point[k] = round(100.0 * float(equites[k].iloc[i]), 3)
            point[f"dd_{k}"] = round(100.0 * float(dds[k].iloc[i]), 3)
        point["brut"] = None if brut is None else round(float(brut[i]), 4)
        courbe.append(point)

    creux = dds["strat"].idxmin()
    sommet = equites["strat"][:creux].idxmax()
    log_r = np.log1p(r)
    par_an = log_r.groupby(jours.year).sum()
    meilleure = int(par_an.idxmax())
    part = float(par_an.max() / log_r.sum()) if log_r.sum() > 0 else None

    etats = extra.get("etats")
    return {
        "id": nom,
        "debut": jours[0].strftime("%Y-%m-%d"), "fin": jours[-1].strftime("%Y-%m-%d"),
        "jours": len(jours), "fin_train": c2.FIN_TRAIN.strftime("%Y-%m-%d"),
        "periodes": periodes,
        "annees": _par_annee(series),
        "pire_baisse": {"valeur": float(dds["strat"].min()),
                        "sommet": sommet.strftime("%Y-%m-%d"),
                        "creux": creux.strftime("%Y-%m-%d")},
        "meilleure_annee": {"annee": meilleure, "part_du_gain": part},
        "etats": None if etats is None else {k: float(v) for k, v in
                                             etats.value_counts(normalize=True).items()},
        "brut_moyen": None if brut is None else float(np.nanmean(brut)),
        "courbe": courbe,
    }


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s  %(message)s")
    d = c2.donnees(fin=c2.FIN_BACKTEST)
    assert d["closes"].index.max() <= c2.FIN_BACKTEST
    rend = d["closes"].pct_change()
    croissance = (1.0 + rend.fillna(0.0)).cumprod().mean(axis=1)
    refs = {"btc": rend["BTC"].fillna(0.0),
            "panier": croissance.pct_change().fillna(croissance.iloc[0] - 1.0)}

    fiches = {}
    for nom in ("VC2", "VC3", "VC5"):
        res = c2.calculer(d, c2.config(nom))
        jours = res["jours"]
        fiches[nom] = _fiche(nom, pd.Series(res["r_net"], index=jours), refs, {
            "turnover": np.asarray(res["turnover"]), "frais": np.asarray(res["frais"]),
            "brut": np.abs(np.asarray(res["positions"])).sum(axis=1), "etats": res["etat"]})

    cinq = c4.donnees_5m(debut=d["closes"].index[0], fin=c2.FIN_BACKTEST + c4.UN_JOUR)
    res4 = c4.calculer(d, cinq, c2.config("VC4"))
    fiches["VC4"] = _fiche("VC4", res4["r_net_jour"], refs, {"etats": res4["etat"]})

    suivi = _charger_suivi_voie_c()
    rc = suivi.calculer()
    garde = np.asarray(rc["jours"] <= c2.FIN_BACKTEST)
    fiches["VOIE_C"] = _fiche("VOIE_C", pd.Series(rc["r_net"][garde], index=rc["jours"][garde]),
                              refs, {"brut": np.abs(rc["tenu"][garde]).sum(axis=1)})

    for nom, f in fiches.items():
        rejoue = f["periodes"]["pleine"]["strat"]["sharpe"]
        if abs(rejoue - SHARPE_MESURE[nom]) > TOLERANCE_SHARPE:
            log.error("%s : Sharpe rejoue %.3f != mesure %.2f — fiches NON ecrites",
                      nom, rejoue, SHARPE_MESURE[nom])
            return 1
        print(f"{nom:7s} Sharpe {rejoue:.3f} (mesure {SHARPE_MESURE[nom]:.2f}) | maxDD "
              f"{f['pire_baisse']['valeur']:.1%} | {f['debut']} -> {f['fin']}")

    voies.FICHIER.parent.mkdir(parents=True, exist_ok=True)
    voies.FICHIER.write_text(json.dumps({"genere_le": pd.Timestamp.now(tz="UTC").isoformat(
        timespec="seconds"), "voies": fiches}, ensure_ascii=False), encoding="utf-8")
    print(f"ecrit : {voies.FICHIER} ({voies.FICHIER.stat().st_size / 1e3:.0f} ko)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
