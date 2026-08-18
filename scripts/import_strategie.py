"""Importe les donnees de STRATEGIE d'ARIT dans le lake, puis en donne le resume.

Ce que ca met a disposition, et qui n'existait nulle part sous une forme requetable :
entrees, sorties, raisons de sortie, raisons de REJET, R moyen, rendement final.

Deux sources complementaires, aucune ne suffisant seule :
- les zips de backtest portent les sorties completes, mais ignorent tout des signaux rejetes ;
- le journal JSONL porte les rejets et la porte qui a bloque, mais aucun evenement de sortie
  finale (ses `gestion` sont des deplacements de stop et des prises partielles).

Usage :
  & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/import_strategie.py
      [--resume]         n'importe rien, relit le lake et affiche le resume
      [--holdout]        inclut le hold-out dans le resume (par defaut EXCLU)
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402

from beta import config  # noqa: E402
from beta.lake import strategie  # noqa: E402
from beta.protocole import holdout  # noqa: E402
from beta.stats import descriptif  # noqa: E402

for flux in (sys.stdout, sys.stderr):
    if hasattr(flux, "reconfigure"):
        flux.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)-22s %(message)s")
log = logging.getLogger("import_strategie")

LARGEUR = 190


def _table(df: pd.DataFrame, colonnes: tuple[str, ...] | None = None) -> str:
    if df.empty:
        return "  (vide)"
    if colonnes:
        df = df[[c for c in colonnes if c in df.columns]]
    with pd.option_context("display.width", LARGEUR, "display.max_columns", None,
                           "display.float_format", lambda v: f"{v:,.4f}"):
        rendu = df.to_string(index=False).splitlines()
    return "\n".join("  " + ligne for ligne in rendu)


def importer() -> dict[str, pd.DataFrame]:
    config.preparer_dossiers()
    tables: dict[str, pd.DataFrame] = {}

    log.info("--- zips de backtest (sorties completes) ---")
    trades = strategie.importer_backtests()

    log.info("--- journal de decisions (rejets, evaluations, stops) ---")
    par_type = strategie.lire_journal()
    tables["evaluations"] = strategie.evaluations_depuis_journal(par_type)
    tables["gestion"] = strategie.gestion_depuis_journal(par_type)

    # Le R n'existe qu'apres cette jointure : le zip ne connait pas le stop structurel
    # d'ARIT, le journal si. Sans elle, toutes les metriques en R seraient fausses.
    tables["trades"] = strategie.attacher_stop_du_journal(
        trades, par_type.get("entry", pd.DataFrame()))

    for nom, df in tables.items():
        if df.empty:
            log.warning("%s : aucune donnee", nom)
            continue
        strategie.ecrire(nom, df)
    return tables


def resumer(train_seulement: bool) -> int:
    try:
        trades = strategie.lire("trades", train_seulement=train_seulement)
        evaluations = strategie.lire("evaluations", train_seulement=train_seulement)
    except strategie.StrategieError as exc:
        print(f"lake de strategie incomplet : {exc}")
        return 1

    portee = ("train seulement (hold-out SCELLE)" if train_seulement
              else "TOUT, hold-out COMPRIS")
    print(f"\n{'=' * 78}\nDONNEES DE STRATEGIE — portee : {portee}")
    print(f"hold-out scelle a partir du {holdout.DEBUT.date()}\n{'=' * 78}")

    global_ = descriptif.resumer(trades)
    print(f"\n-- vue d'ensemble : {global_['n']} trades --")
    print(f"  R moyen         {global_['r_moyen']:+.4f}   (mediane {global_['r_median']:+.4f}"
          f", ecart-type {global_['r_sigma']:.4f})")
    print(f"  MDE             {global_['mde_r']:+.4f} R/trade  <- le plus petit ecart que "
          f"cet echantillon permet de detecter")
    if global_["r_moyen"] == global_["r_moyen"] and global_["mde_r"] == global_["mde_r"]:
        verdict = ("SOUS le seuil de detection : indiscernable de zero"
                   if abs(global_["r_moyen"]) < global_["mde_r"] else "au-dessus du seuil")
        print(f"                  |R moyen| = {abs(global_['r_moyen']):.4f} -> {verdict}")
    print(f"  rendement total {global_['rendement_total_pct']:+.2f} %   "
          f"(moyen {global_['rendement_moyen_pct']:+.3f} % par trade)")
    if "rendement_abs_total" in global_:
        print(f"  resultat absolu {global_['rendement_abs_total']:+.2f}")
    print(f"  win rate        {global_['win_rate']:.1%}   profit factor "
          f"{global_['profit_factor']:.3f}")
    for cle, libelle in (("mfe_r_moyen", "MFE moyen"), ("mae_r_moyen", "MAE moyen"),
                         ("duree_h_mediane", "duree mediane (h)")):
        if cle in global_:
            print(f"  {libelle:15s} {global_[cle]:+.3f}")

    colonnes = ("n", "r_moyen", "mde_r", "r_total", "rendement_total_pct", "win_rate",
                "profit_factor")
    for cles, titre in ((("strategie",), "par strategie"), (("paire",), "par paire"),
                        (("sens",), "par sens")):
        print(f"\n-- {titre} --")
        print(_table(descriptif.par(trades, *cles), tuple(cles) + colonnes))

    print("\n-- raisons de SORTIE (quelle regle ferme reellement les positions) --")
    print(_table(descriptif.raisons_de_sortie(trades),
                 ("raison_sortie",) + colonnes))

    print("\n-- raisons de REJET (la moitie invisible : ce qui n'a PAS ete pris) --")
    print(_table(descriptif.raisons_de_rejet(evaluations)))

    print(f"\n{len(evaluations)} evaluations journalisees.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--resume", action="store_true",
                    help="n'importe rien, relit le lake et affiche le resume")
    ap.add_argument("--holdout", action="store_true",
                    help="inclut le hold-out dans le resume (EXCLU par defaut)")
    args = ap.parse_args()

    if not args.resume:
        try:
            importer()
        except strategie.StrategieError as exc:
            log.error("import impossible : %s", exc)
            return 1
    return resumer(train_seulement=not args.holdout)


if __name__ == "__main__":
    sys.exit(main())
