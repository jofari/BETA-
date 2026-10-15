"""Relance ciblee des runs enregistres apres les correctifs du 15/10 (S6 et ruine).

    /root/venvs/arit/bin/python scripts/reevaluer_s6_ruine.py            # montre seulement
    /root/venvs/arit/bin/python scripts/reevaluer_s6_ruine.py --ecrire   # reecrit data/runs/

Demande par Jonas le 2026-10-15. Deux gestes, sur les trades DEJA enregistres, sans relancer
le moteur ni la batterie entiere (S1, S5, S7, S9 dependent du lot et des chemins
synthetiques : les rejouer ne reproduirait pas le verdict d'origine) :

1. S4 : le Monte-Carlo est rejoue avec la graine du Run (0) sur `trades.parquet`. Si et
   seulement si le rejeu reproduit EXACTEMENT les valeurs stockees, `p_ruine` est ajoutee a
   `batterie.json`. Sinon le run est laisse tel quel et signale.
2. S6 : la porte est rejugee par `batterie.porte_s6` sur le walk-forward stocke (un IS <= 0
   la fait echouer), puis l'issue par `batterie.issue`.

Aucun compteur ne bouge : ni RUNS.jsonl, ni EXPERIMENTS.jsonl. Si une issue change, le script
le dit et ne l'ecrit pas : changer l'issue d'une experience deja mesuree est une decision.
Idempotent.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from beta.moteur.pipeline import RESULTATS  # noqa: E402
from beta.stats import batterie, montecarlo  # noqa: E402

log = logging.getLogger("beta.reevaluer_s6_ruine")

GRAINE_RUN = 0                    # `contrats.Run.graine` par defaut, la seule utilisee
CLES_CONTROLE = ("p_perte", "p_drawdown_pire_que_seuil", "drawdown_max_reel_pct",
                 "centile_drawdown_reel", "equity_finale_reelle")


def rejouer_mc(r: np.ndarray, mode: str, graine: int = GRAINE_RUN,
               n_tirages: int = montecarlo.N_TIRAGES, capital: float = 100_000.0,
               risque_pct: float = 1.0, bloc: int = 250) -> dict:
    """`montecarlo.simuler` sans la matrice entiere : memes tirages, par blocs de lignes.

    Sur 10 744 trades, la matrice 10 000 x n pese pres d'1 Go et le pic depasse 3 Go, de
    quoi faire tomber le VPS. Le generateur est consomme dans le meme ordre (une
    permutation par ligne ; des entiers ligne apres ligne), donc les tirages sont les
    memes — ce que `_reproduit` verifie contre les valeurs stockees, run par run. Ne rend
    que ce qui sert au controle et `p_ruine` (pas le cone).
    """
    x = np.asarray(r, dtype=float)
    x = x[np.isfinite(x)]
    n = len(x)
    rng = np.random.default_rng(graine)
    finaux, dd, minimums = [], [], []
    for debut in range(0, n_tirages, bloc):
        k = min(bloc, n_tirages - debut)
        if mode == "permutation":
            matrice = np.array([rng.permutation(x) for _ in range(k)])
        else:
            matrice = x[rng.integers(0, n, size=(k, n))]
        courbes = montecarlo._courbes(matrice, capital, risque_pct)
        finaux.append(courbes[:, -1])
        dd.append(montecarlo._drawdown_max_pct(courbes))
        minimums.append(courbes.min(axis=1))
    finaux, dd, minimums = (np.concatenate(v) for v in (finaux, dd, minimums))
    reel = montecarlo._courbes(x[None, :], capital, risque_pct)[0]
    dd_reel = float(montecarlo._drawdown_max_pct(reel[None, :])[0])
    return {"n": n, "equity_finale_reelle": float(reel[-1]),
            "equity_finale": {f"p{p}": float(np.percentile(finaux, p))
                              for p in montecarlo.PERCENTILES_CONE},
            "drawdown_max_reel_pct": dd_reel,
            "p_perte": float((finaux < capital).mean()),
            "p_drawdown_pire_que_seuil": float((dd <= -montecarlo.SEUIL_DD_PCT).mean()),
            "centile_drawdown_reel": float((dd <= dd_reel).mean() * 100.0),
            "p_ruine": float((minimums <= 0.0).mean())}


def _reproduit(stocke: dict, rejoue: dict) -> bool:
    for mode in ("permutation", "remise"):
        a, b = stocke.get(mode, {}), rejoue.get(mode, {})
        if a.get("n") != b.get("n"):
            return False
        for cle in CLES_CONTROLE:
            if not np.isclose(a.get(cle, np.nan), b.get(cle, np.nan), rtol=0, atol=1e-9):
                return False
        for p, v in (a.get("equity_finale") or {}).items():
            if not np.isclose(v, b["equity_finale"].get(p, np.nan), rtol=0, atol=1e-6):
                return False
    return True


def reevaluer(dossier: pathlib.Path, ecrire: bool) -> str:
    verdict = json.loads((dossier / "verdict.json").read_text(encoding="utf-8"))
    detail = json.loads((dossier / "batterie.json").read_text(encoding="utf-8"))
    trades = pd.read_parquet(dossier / "trades.parquet")
    notes = []

    mc = detail.get("S4_monte_carlo")
    if mc and "p_ruine" not in mc.get("remise", {}):
        r = trades["r"].dropna().to_numpy()
        rejoue = {mode: rejouer_mc(r, mode) for mode in ("permutation", "remise")}
        if _reproduit(mc, rejoue):
            for mode in ("permutation", "remise"):
                mc[mode]["p_ruine"] = rejoue[mode]["p_ruine"]
            notes.append(f"P(ruine) {rejoue['remise']['p_ruine']:.1%}")
        else:
            notes.append("S4 NON REPRODUIT : p_ruine non ajoutee")

    wf = detail.get("S6_walk_forward")
    nouvelle_issue = verdict["issue"]
    if wf:
        avant = verdict["portes"].get("S6_walk_forward")
        apres, reserve = batterie.porte_s6(wf.get("ancre", {}), wf.get("cpcv", {}))
        portes = dict(verdict["portes"], S6_walk_forward=apres)
        nouvelle_issue = batterie.issue(portes, len(trades))
        if nouvelle_issue != verdict["issue"]:
            notes.append(f"ISSUE CHANGERAIT {verdict['issue']} -> {nouvelle_issue} : "
                         "non ecrit, a trancher")
            ecrire = False
        else:
            verdict["portes"] = portes
            verdict["portes_echouees"] = [n for n, p in portes.items() if p is False]
            if reserve and reserve not in verdict["reserves"]:
                verdict["reserves"].append(reserve)
            notes.append(f"S6 {avant} -> {apres}")

    if ecrire:
        (dossier / "verdict.json").write_text(
            json.dumps(verdict, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        (dossier / "batterie.json").write_text(
            json.dumps(detail, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return f"{dossier.name}  {verdict['issue']:<11}  " + " · ".join(notes or ["rien"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ecrire", action="store_true", help="reecrire data/runs/")
    args = parser.parse_args()
    for dossier in sorted(p for p in RESULTATS.iterdir() if (p / "verdict.json").exists()):
        if not (dossier / "batterie.json").exists() or not (dossier / "trades.parquet").exists():
            log.info("%s  incomplet, ignore", dossier.name)
            continue
        log.info("%s", reevaluer(dossier, args.ecrire))
    return 0


if __name__ == "__main__":
    sys.exit(main())
