"""La fiche de robustesse d'un run deja enregistre — INFORMATIVE, ni porte ni verdict.

    /root/venvs/arit/bin/python scripts/fiche_robustesse.py <run_id> [<run_id> ...]
    /root/venvs/arit/bin/python scripts/fiche_robustesse.py --lot <run_id> <run_id> ...

Relit `data/runs/<run_id>/` (trades, equity, courbe du hold de S8) et ecrit a cote
`robustesse.json` et `robustesse.md`. Rien n'est rejoue : aucun signal nouveau, aucune donnee
de marche relue, aucun essai consomme, `verdict.json` intact. Les chiffres sortent du
programme (`beta/stats/fiche.py`) ; les recopier tels quels.

`--lot` ajoute, pour les runs donnes pris ENSEMBLE, le SPA de Hansen et les p-values
ajustees de Romano-Wolf (`beta/stats/selection.py`), sur le P&L journalier de S7, et les
ecrit dans `data/lots/lot_<empreinte>.json`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from beta.moteur.pipeline import RESULTATS  # noqa: E402
from beta.stats import fiche, multitest, selection  # noqa: E402


def _propre(objet):
    """JSON strict : NaN et infinis deviennent null (un fichier que tout lecteur relit)."""
    if isinstance(objet, dict):
        return {str(k): _propre(v) for k, v in objet.items()}
    if isinstance(objet, (list, tuple)):
        return [_propre(v) for v in objet]
    if isinstance(objet, float) and not math.isfinite(objet):
        return None
    if hasattr(objet, "item"):
        return _propre(objet.item())
    return objet


def _charger(run_id: str) -> tuple[dict, pd.DataFrame, pd.DataFrame, dict | None]:
    dossier = RESULTATS / run_id
    if not (dossier / "trades.parquet").exists():
        raise SystemExit(f"run inconnu ou sans trades : {dossier}")
    verdict = json.loads((dossier / "verdict.json").read_text(encoding="utf-8"))
    trades = pd.read_parquet(dossier / "trades.parquet")
    equity = (pd.read_parquet(dossier / "equity.parquet")
              if (dossier / "equity.parquet").exists() else pd.DataFrame())
    hold = None
    if (dossier / "batterie.json").exists():
        batterie = json.loads((dossier / "batterie.json").read_text(encoding="utf-8"))
        hold = (batterie.get("S8_buy_and_hold") or {}).get("hold", {}).get("courbe")
    return verdict, trades, equity, hold


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)-7s %(name)s %(message)s")
    parseur = argparse.ArgumentParser(prog="fiche_robustesse")
    parseur.add_argument("runs", nargs="+", help="identifiants de run (dossiers de data/runs)")
    parseur.add_argument("--lot", action="store_true",
                         help="ajouter SPA de Hansen et Romano-Wolf sur les runs pris ensemble")
    arguments = parseur.parse_args(argv)

    trades_lot: dict[str, pd.DataFrame] = {}
    for run_id in arguments.runs:
        verdict, trades, equity, hold = _charger(run_id)
        resultat = fiche.construire(trades, equity, hold,
                                    n_essais=verdict.get("n_essais_cumules"),
                                    graine=0)
        titre = (f"{verdict.get('candidate', '?')} (expérience {verdict.get('experience', '?')}, "
                 f"run {run_id}, issue de la batterie : {verdict.get('issue', '?')})")
        dossier = RESULTATS / run_id
        (dossier / "robustesse.json").write_text(
            json.dumps(_propre(resultat), ensure_ascii=False, indent=1), encoding="utf-8")
        texte = fiche.markdown(resultat, titre)
        (dossier / "robustesse.md").write_text(texte, encoding="utf-8")
        print(texte)
        print(f"-> {dossier / 'robustesse.md'}\n")
        trades_lot[f"{verdict.get('candidate', run_id)}@{run_id}"] = trades

    if arguments.lot and len(trades_lot) > 1:
        univers = multitest.univers_journalier(trades_lot)
        lot = {"avertissement": fiche.AVERTISSEMENT, "runs": sorted(arguments.runs),
               "reality_check_s7": multitest.reality_check(univers),
               "spa_hansen": selection.spa_hansen(univers),
               "romano_wolf": selection.romano_wolf(univers)}
        empreinte = hashlib.sha256(" ".join(sorted(arguments.runs)).encode()).hexdigest()[:12]
        chemin = RESULTATS.parent / "lots" / f"lot_{empreinte}.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(json.dumps(_propre(lot), ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(json.dumps(_propre(lot), ensure_ascii=False, indent=1))
        print(f"-> {chemin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
