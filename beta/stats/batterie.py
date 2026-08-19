"""La batterie complete : S1 a S9 appliquees a une candidate, et le verdict qui en sort.

Ordre d'execution volontaire, du moins cher au plus cher, mais surtout du plus decisif au
plus fin :

    S0  MDE          — ai-je seulement de quoi voir un edge ? (avant toute p-value)
    S8  hold         — est-ce que je bats la reference imposee ?
    S3  bootstrap    — l'ecart survit-il a la dependance temporelle ?
    S2  DSR          — survit-il au nombre d'essais deja consommes ?
    S4  Monte-Carlo  — la sequence observee etait-elle chanceuse ?
    S6  walk-forward — l'edge tient-il hors echantillon, purge et embargo poses ?
    S5  synthetique  — gagne-t-il PLUS que sur un marche sans structure ?
    S9  correlation  — apporte-t-il autre chose que ce qu'on a deja ?
    S1  BH           — et une fois la famille de tests declaree, en reste-t-il ?

**Aucune de ces portes ne peut ameliorer un resultat.** Elles ne savent que le degrader.
C'est la propriete qui les rend utiles : une candidate qui les franchit toutes n'est pas
prouvee, elle est seulement *pas encore tuee*. D'ou l'issue par defaut INDECIDABLE.

Le module ne connait ni candidate ni marche : il recoit des trades, une courbe d'equity et
des resultats de rejeu. C'est ce qui lui permet de juger indifferemment un backtest
freqtrade importe, un rejeu du moteur BETA, ou une strategie venue d'ailleurs.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.stats import (bootstrap, descriptif, diversification, montecarlo, multitest,
                        reference, synthetique, walkforward)

log = logging.getLogger("beta.stats.batterie")

# Seuils des portes. Ecrits ici, une seule fois : un seuil choisi apres avoir vu le
# resultat ne teste plus rien. Les modifier est une decision a consigner dans DECISIONS.md.
SEUIL_P = 0.05
SEUIL_DSR = 0.95
SEUIL_P_PERTE = 0.10
SEUIL_EFFICACITE_WF = 0.50
SEUIL_CHEMINS_PERDANTS = 0.35
CENTILE_SYNTHETIQUE = 95.0
N_MIN_TRADES = 30

PORTES = ("S1_benjamini_hochberg", "S2_sharpe_degonfle", "S3_bootstrap",
          "S4_monte_carlo", "S5_synthetique", "S6_walk_forward",
          "S7_reality_check", "S8_buy_and_hold", "S9_diversification")


def evaluer(trades: pd.DataFrame, *, equity: pd.DataFrame | None = None,
            series_marche: dict[str, pd.DataFrame] | None = None,
            n_essais: int = 30, cout_aller_retour_pct: float = 0.0,
            resultats_synthetiques: list[float] | None = None,
            equities_voisines: dict[str, pd.DataFrame] | None = None,
            nom: str = "candidate", famille: pd.DataFrame | None = None,
            univers_candidates: dict[str, np.ndarray] | None = None,
            graine: int = 0) -> dict:
    """Passe une candidate a la batterie. Rend metriques, portes et reserves.

    Tout argument absent desactive sa porte plutot que de la faire passer : une porte non
    executee vaut `None`, jamais `True`. La difference entre « verifie » et « pas verifie »
    est precisement ce qu'un rapport de backtest ordinaire perd.
    """
    metriques = descriptif.resumer(trades)
    portes: dict[str, bool | None] = dict.fromkeys(PORTES)
    reserves: list[str] = []
    detail: dict = {}

    r = (trades["r"].dropna().to_numpy() if "r" in trades.columns
         else np.empty(0, dtype=float))

    # --- S0 : le MDE avant toute p-value ---------------------------------------------
    mde = metriques.get("mde_r", float("nan"))
    r_moyen = metriques.get("r_moyen", float("nan"))
    if len(r) < N_MIN_TRADES:
        reserves.append(f"{len(r)} trades : sous {N_MIN_TRADES}, aucune porte n'est "
                        "informative — le resultat est indecidable par construction")
    if np.isfinite(mde) and np.isfinite(r_moyen) and abs(r_moyen) < mde:
        reserves.append(f"effet observe ({r_moyen:+.4f} R) sous le MDE ({mde:.4f} R) : "
                        "l'echantillon ne permet pas de le distinguer de zero")

    if len(r) >= 3:
        # --- S3 : bootstrap par blocs stationnaire, sensibilite publiee ----------------
        sensibilite = bootstrap.sensibilite(r, graine=graine)
        detail["S3_bootstrap"] = sensibilite
        portes["S3_bootstrap"] = bootstrap.stable(sensibilite, SEUIL_P)
        if not portes["S3_bootstrap"]:
            pires = [f"l={s['ell_demande']}: p={s['p_value']:.3f}" for s in sensibilite]
            reserves.append("bootstrap instable ou non significatif — " + ", ".join(pires))

        # --- S2 : Sharpe degonfle par le nombre d'essais cumules ----------------------
        dsr = multitest.sharpe_degonfle(r, n_essais)
        detail["S2_sharpe_degonfle"] = dsr
        portes["S2_sharpe_degonfle"] = bool(np.isfinite(dsr["dsr"])
                                            and dsr["dsr"] >= SEUIL_DSR)
        if np.isfinite(dsr["sharpe"]) and np.isfinite(dsr["sharpe_seuil"]):
            reserves.append(f"Sharpe {dsr['sharpe']:.3f} contre {dsr['sharpe_seuil']:.3f} "
                            f"attendu du maximum de {n_essais} essais")

        # --- S4 : Monte-Carlo, cone d'equity ------------------------------------------
        mc = montecarlo.resume(r, graine=graine)
        detail["S4_monte_carlo"] = mc
        p_perte = mc["remise"].get("p_perte", float("nan"))
        portes["S4_monte_carlo"] = bool(np.isfinite(p_perte) and p_perte <= SEUIL_P_PERTE)
        centile_dd = mc["permutation"].get("centile_drawdown_reel", float("nan"))
        if np.isfinite(centile_dd) and centile_dd <= 10:
            reserves.append(f"drawdown observe au {centile_dd:.0f}e centile des sequences "
                            "simulees : la chronologie reelle a ete chanceuse")

    # --- S6 : walk-forward purge et embargo ------------------------------------------
    if len(trades) >= N_MIN_TRADES and "ts_entree" in trades.columns:
        wf = walkforward.marche_en_avant(trades)
        cp = walkforward.cpcv(trades)
        detail["S6_walk_forward"] = {"ancre": wf, "cpcv": cp}
        efficacite = wf.get("efficacite", float("nan"))
        perdants = cp.get("part_chemins_perdants", float("nan"))
        portes["S6_walk_forward"] = bool(
            np.isfinite(efficacite) and efficacite >= SEUIL_EFFICACITE_WF
            and np.isfinite(perdants) and perdants <= SEUIL_CHEMINS_PERDANTS)
        if np.isfinite(perdants):
            reserves.append(f"{perdants:.0%} des chemins CPCV finissent en perte")

    # --- S8 : buy-and-hold, reference imposee ----------------------------------------
    if equity is not None and series_marche:
        ref = reference.hold(series_marche, cout_aller_retour_pct)
        moi = reference.strategie_journaliere(equity)
        comparaison = reference.comparer(moi, ref)
        detail["S8_buy_and_hold"] = {"hold": ref, "candidate": moi, **comparaison}
        portes["S8_buy_and_hold"] = comparaison["passe"]
        if not comparaison["passe"]:
            reserves.append(f"ne bat pas le hold : ecart de rendement "
                            f"{comparaison['ecart_rendement_pct']:+.1f} pts, "
                            f"ecart de Sharpe {comparaison['ecart_sharpe']:+.2f}")

    # --- S5 : chemins synthetiques ----------------------------------------------------
    if resultats_synthetiques:
        obs = float(np.nansum(r)) if len(r) else float("nan")
        comp = synthetique.comparer(obs, resultats_synthetiques, CENTILE_SYNTHETIQUE)
        detail["S5_synthetique"] = comp
        portes["S5_synthetique"] = comp["passe"]
        if not comp["passe"]:
            reserves.append(f"resultat au {comp['centile']:.0f}e centile des marches "
                            "synthetiques : indiscernable d'une serie sans structure")

    # --- S9 : diversification ---------------------------------------------------------
    if equities_voisines is not None and equity is not None:
        toutes = {**equities_voisines, nom: equity}
        div = diversification.porte(nom, toutes)
        detail["S9_diversification"] = div
        portes["S9_diversification"] = div["passe"]
        if div.get("reserve"):
            reserves.append(div["reserve"])
        elif not div["passe"]:
            reserves.append(f"correlee a {div['correlation_max']:.2f} avec {div['avec']} : "
                            "n'apporte pas de diversification")

    # --- S7 : reality check sur l'univers de candidates -------------------------------
    if univers_candidates and len(univers_candidates) > 1:
        rc = multitest.reality_check(univers_candidates, graine=graine)
        detail["S7_reality_check"] = rc
        portes["S7_reality_check"] = bool(np.isfinite(rc["p_value"])
                                          and rc["p_value"] <= SEUIL_P
                                          and rc.get("meilleure") == nom)

    # --- S1 : Benjamini-Hochberg sur la famille declaree ------------------------------
    if famille is not None and not famille.empty:
        table = multitest.benjamini_hochberg(famille)
        detail["S1_benjamini_hochberg"] = table.to_dict("records")
        ligne = table[table.get("nom", pd.Series(dtype=object)) == nom]
        portes["S1_benjamini_hochberg"] = (bool(ligne["signif_BH"].iloc[0])
                                           if len(ligne) else None)

    metriques.update({"n_essais_cumules": n_essais})
    return {"metriques": metriques, "portes": portes, "reserves": tuple(reserves),
            "detail": detail}


def issue(portes: dict, n_trades: int = 0) -> str:
    """Traduit l'etat des portes en issue. INDECIDABLE tant qu'il reste un trou.

    Trois cas, et un seul est une decouverte :
    - une porte executee a echoue          => infirmee
    - une porte n'a pas ete executee       => indecidable (on ne sait pas, on ne suppose pas)
    - toutes executees et franchies        => confirmee
    """
    from beta.moteur.contrats import CONFIRMEE, INDECIDABLE, INFIRMEE

    if n_trades < N_MIN_TRADES:
        return INDECIDABLE
    executees = {nom: passe for nom, passe in portes.items() if passe is not None}
    if not executees:
        return INDECIDABLE
    if any(not passe for passe in executees.values()):
        return INFIRMEE
    return CONFIRMEE if len(executees) == len(PORTES) else INDECIDABLE
