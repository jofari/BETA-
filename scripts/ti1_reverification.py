"""TI1 — reverification de la campagne du 20/10 et detail par sous-periode (demande du 20/10 soir).

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/ti1_reverification.py SORTIE.md

1. Recalcule les 24 mesures de la campagne (`invest.campagne.evaluer`, pure : rien n'est ecrit,
   rien n'est compte) sur les memes donnees (empreinte verifiee d'abord) et les compare, champ
   par champ, aux resultats stockes dans `data/test_invest/`.
2. Detaille chaque configuration par annee civile, a partir des series stockees : rendement de la
   strategie, du panier, de BTC et du temoin, pire baisse dans l'annee, exposition moyenne, part
   du temps en defensif. Descriptif seulement : aucune p-value, aucun nouveau test, compteur
   inchange.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from beta.invest import campagne as ca  # noqa: E402
from beta.invest import donnees as dn  # noqa: E402
from beta.invest import moteur  # noqa: E402

log = logging.getLogger("beta.ti1_reverification")
TOLERANCE = 1e-9


def _ecarts(a, b, chemin="") -> list[tuple[str, float | str]]:
    """Les feuilles qui different (numeriques au-dela de TOLERANCE, ou de nature)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k in ("dsr", "n_essais", "compteur", "calcule_le", "code", "statut", "run_id"):
                continue                      # dependent du compteur ou de l'horloge
            out += _ecarts(a.get(k), b.get(k), f"{chemin}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(chemin, f"longueurs {len(a)} / {len(b)}")]
        out = []
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += _ecarts(x, y, f"{chemin}[{i}]")
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return [] if abs(float(a) - float(b)) <= TOLERANCE else [(chemin, abs(a - b))]
    return [] if a == b else [(chemin, f"{a!r} / {b!r}")]


def reverifier(d: dn.Donnees) -> list[dict]:
    lignes = []
    for cfg in ca.campagne_ti1():
        rid = ca.run_id(cfg, d.empreinte)
        stocke = json.loads((ca.DOSSIER / f"{rid}.json").read_text(encoding="utf-8"))
        neuf = ca.evaluer(cfg, d)
        diff = _ecarts(stocke, neuf)
        lignes.append({"run_id": rid, "periode": cfg.periode, "libelle": ca.libelle(cfg),
                       "ecarts": len(diff), "exemples": diff[:3],
                       "verdict": stocke["verdict"]})
        log.info("%s %-10s %-28s %d ecart(s)", rid, cfg.periode, ca.libelle(cfg), len(diff))
    return lignes


def _pire_baisse(v: np.ndarray) -> float:
    return float((v / np.maximum.accumulate(v) - 1.0).min()) if len(v) else math.nan


def par_annee(res: dict, closes_btc: pd.Series) -> list[dict]:
    """Une ligne par annee civile de la periode, depuis les series stockees du run."""
    s = res["series"]
    dates = pd.DatetimeIndex(pd.to_datetime(s["dates"]))
    v_s, v_b, v_btc = (np.asarray(s[k], dtype=float) for k in ("v_s", "v_b", "v_btc"))
    e = np.asarray(s["e"], dtype=float)                    # e[i] joue sur le jour i + 1
    e_moy = float(np.mean(e))
    r_b = v_b[1:] / v_b[:-1] - 1.0
    v_t = np.concatenate([[1.0], np.cumprod(1.0 + moteur.temoin_constant(
        e, r_b, res["config"]["kappa_pb"])["r"])])
    defensif = res["config"]["mapping"]["e_def"]
    sortie = []
    for annee in sorted(set(dates[1:].year)):
        jours = np.flatnonzero(dates.year == annee)
        jours = jours[jours >= 1]
        i0, i1 = jours[0] - 1, jours[-1]                   # V a la veille du 1er jour -> fin
        e_an = e[jours - 1]
        sortie.append({
            "annee": int(annee), "debut": f"{dates[jours[0]]:%Y-%m-%d}",
            "fin": f"{dates[i1]:%Y-%m-%d}", "jours": int(len(jours)),
            "strategie": v_s[i1] / v_s[i0] - 1.0, "panier": v_b[i1] / v_b[i0] - 1.0,
            "btc": v_btc[i1] / v_btc[i0] - 1.0, "temoin": v_t[i1] / v_t[i0] - 1.0,
            "pire_baisse_strategie": _pire_baisse(v_s[i0:i1 + 1]),
            "pire_baisse_panier": _pire_baisse(v_b[i0:i1 + 1]),
            "expo_moyenne": float(np.mean(e_an)), "expo_moyenne_periode": e_moy,
            "part_defensif": float(np.mean(np.isclose(e_an, defensif))),
        })
    return sortie


def _p(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else \
        f"{100 * x:+.1f} %".replace(".", ",")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    sortie = pathlib.Path(sys.argv[1])
    synthese = json.loads((ca.DOSSIER / f"campagne_{ca.ID_EXP}.json").read_text(encoding="utf-8"))
    fin = pd.Timestamp(ca.FIN, tz="UTC")
    p0 = min(pd.Timestamp(x, tz="UTC") for x, _ in ca.PERIODES.values()) - pd.Timedelta(days=1)
    d = dn.charger(fin, p0, pit="publication")
    if d.empreinte != synthese["donnees"]["empreinte"]:
        raise SystemExit(f"donnees changees ({d.empreinte} != {synthese['donnees']['empreinte']}) "
                         ": reverification impossible a l'identique, rien n'est recalcule")
    verif = reverifier(d)
    lignes_csv, md = [], []
    for periode in ca.PERIODES:
        for cfg in ca.campagne_ti1():
            if cfg.periode != periode:
                continue
            rid = ca.run_id(cfg, d.empreinte)
            res = json.loads((ca.DOSSIER / f"{rid}.json").read_text(encoding="utf-8"))
            for x in par_annee(res, d.closes["BTC"]):
                lignes_csv.append({"periode": periode, "config": ca.libelle(cfg), "run_id": rid,
                                   "verdict": res["verdict"], **x})
    csv_chemin = sortie.with_suffix(".csv")
    with csv_chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes_csv[0]))
        w.writeheader()
        w.writerows(lignes_csv)
    n_ecarts = sum(x["ecarts"] for x in verif)
    md += [f"# TI1 — revérification et détail par année ({len(verif)} mesures)", "",
           f"Données `{d.empreinte}` (identiques à celles du 20/10), fin {ca.FIN}. Recalcul pur, "
           "rien n'est écrit ni compté (compteur inchangé).", "",
           f"**Écarts au recalcul : {n_ecarts}** (sur toutes les métriques, épisodes, "
           "distributions nulles et p-values ; seuls le DSR et le compteur, qui dépendent du N "
           "courant, sont exclus).", ""]
    for periode in ca.PERIODES:
        md += [f"## Période {periode}", "",
               "| configuration | année | stratégie | panier | BTC | témoin | pire baisse strat. "
               "| pire baisse panier | expo moy. | part défensif |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for x in lignes_csv:
            if x["periode"] != periode or "·" not in x["config"] or "sans " in x["config"]:
                continue
            expo = f"{x['expo_moyenne']:.2f}".replace(".", ",")
            md.append(f"| {x['config']} | {x['annee']} | {_p(x['strategie'])} | "
                      f"{_p(x['panier'])} | {_p(x['btc'])} | {_p(x['temoin'])} | "
                      f"{_p(x['pire_baisse_strategie'])} | {_p(x['pire_baisse_panier'])} | "
                      f"{expo} | {100 * x['part_defensif']:.0f} % |")
        md.append("")
    sortie.write_text("\n".join(md), encoding="utf-8")
    print(f"{n_ecarts} ecart(s) ; {sortie} ; {csv_chemin}")
    return 0 if n_ecarts == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
