"""R1 — le trailing stop detruit-il les shorts ?

Test APPARIE : chaque trade reellement pris par AritV1 est rejoue avec une sortie en triple
barriere fixe (stop initial du journal, cible +1,5 R, horizon 96 h — les parametres
d'ARIT, pas des nouveaux), et l'on compare son R a celui qu'il a reellement obtenu avec le
trailing. Meme signal, meme entree, meme stop : la seule chose qui change est la regle de
sortie, donc l'ecart lui est imputable.

L'appariement n'est pas un detail de confort. Sur 21 shorts en train, un test non apparie
n'aurait aucune chance de voir quoi que ce soit ; sur des paires, la variance de l'ECART est
tres inferieure a celle des deux series, ce qui est la seule facon de rendre l'echantillon
exploitable. Il ne le rend pas grand pour autant : le MDE reste la premiere ligne du
rapport.

Le hold-out ne participe pas : `strategie.lire(train_seulement=True)`. Les 7 shorts de
hold-out existent, on ne les regarde pas.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.lake import lecture, strategie
from beta.moteur import espace_r
from beta.protocole import experiences
from beta.stats import bootstrap, descriptif

log = logging.getLogger("beta.recherche.r1")

ID_EXPERIENCE = "R1"
TIMEFRAME = "1h"
TP1_R = 1.5              # PDR 03.3 cote ARIT : la cible du systeme, donc l'unite du test
HORIZON_BOUGIES = 96     # 96 h, l'horizon de ARIT2.0/analysis/dataset.py
N_MIN = 10


def _rejouer_paire(paire: str, trades_paire: pd.DataFrame) -> pd.DataFrame:
    """Rejoue en barriere fixe les trades d'une paire. Index = index des trades d'origine."""
    debut = (trades_paire["ts_entree"].min() - pd.Timedelta(hours=1)).isoformat()
    fin = (trades_paire["ts_entree"].max() + pd.Timedelta(hours=HORIZON_BOUGIES + 2)
           ).isoformat()
    df = lecture.load(paire, TIMEFRAME, debut=debut, fin=fin)
    if df.empty:
        return pd.DataFrame()

    dates = pd.to_datetime(df["date"], utc=True)
    sens = np.zeros(len(df), dtype=int)
    stop_distance = np.full(len(df), np.nan)
    prix_entree = df["close"].to_numpy(dtype=float).copy()
    origine: dict[int, int] = {}

    for idx, trade in trades_paire.iterrows():
        # `searchsorted` place l'entree sur la bougie qui la CONTIENT : les trades d'ARIT
        # sont pris en 1h mais horodates a la minute d'execution.
        position = int(dates.searchsorted(trade["ts_entree"], side="right")) - 1
        if position < 0 or position >= len(df) - 1:
            continue
        risque = abs(float(trade["prix_entree"]) - float(trade["sl_initial"]))
        if not np.isfinite(risque) or risque <= 0:
            continue
        if sens[position]:                      # deux trades sur la meme bougie : on garde
            continue                            # le premier, sans quoi ils s'ecraseraient
        sens[position] = 1 if trade["sens"] == "long" else -1
        stop_distance[position] = risque
        prix_entree[position] = float(trade["prix_entree"])
        origine[position] = idx

    signaux = pd.DataFrame({"sens": sens, "stop_distance": stop_distance,
                            "prix_entree": prix_entree})
    rejoues = espace_r.evaluer(df, signaux, take_profit_r=TP1_R,
                               horizon_bougies=HORIZON_BOUGIES, paire=paire)
    if rejoues.empty:
        return rejoues
    rejoues["trade_origine"] = rejoues["index_entree"].map(origine)
    return rejoues.dropna(subset=["trade_origine"])


def apparier() -> pd.DataFrame:
    """Une ligne par trade rejoue : R reel (trailing) contre R en barriere fixe."""
    trades = strategie.lire("trades", train_seulement=True)
    if trades.empty:
        return pd.DataFrame()
    morceaux = []
    for paire, groupe in trades.groupby("paire"):
        try:
            rejoues = _rejouer_paire(paire, groupe)
        except lecture.DataError as exc:
            log.error("%s non rejouable : %s", paire, exc)
            continue
        if rejoues.empty:
            continue
        rejoues = rejoues.set_index("trade_origine")
        morceaux.append(pd.DataFrame({
            "paire": paire,
            "sens": groupe.loc[rejoues.index, "sens"],
            "ts_entree": groupe.loc[rejoues.index, "ts_entree"],
            "r_trailing": groupe.loc[rejoues.index, "r"].astype(float),
            "r_barriere": rejoues["r"].astype(float),
            "raison_trailing": groupe.loc[rejoues.index, "raison_sortie"],
            "raison_barriere": rejoues["raison_sortie"],
        }))
    if not morceaux:
        return pd.DataFrame()
    paires = pd.concat(morceaux, ignore_index=True)
    paires["ecart"] = paires["r_barriere"] - paires["r_trailing"]
    return paires


def mesurer(clore: bool = True) -> dict:
    """La mesure complete de R1. Refuse de tourner sans preenregistrement."""
    preenregistrement = experiences.exiger(ID_EXPERIENCE)
    apparies = apparier()
    if apparies.empty:
        return {"id": ID_EXPERIENCE, "verdict": "indecidable",
                "resultat": "aucun trade rejouable"}

    resultats = {}
    for sens in ("short", "long"):
        groupe = apparies[apparies["sens"] == sens]
        ecart = groupe["ecart"].dropna().to_numpy()
        sigma = float(np.std(ecart, ddof=1)) if len(ecart) > 1 else float("nan")
        test = (bootstrap.intervalle(ecart, n_repetitions=2000)
                if len(ecart) >= 3 else {"p_value": float("nan"),
                                         "ic_bas": float("nan"),
                                         "ic_haut": float("nan")})
        resultats[sens] = {
            "n": len(ecart),
            "r_trailing_moyen": float(groupe["r_trailing"].mean()) if len(groupe) else float("nan"),
            "r_barriere_moyen": float(groupe["r_barriere"].mean()) if len(groupe) else float("nan"),
            "ecart_moyen": float(np.mean(ecart)) if len(ecart) else float("nan"),
            "ecart_sigma": sigma,
            # MDE de l'ECART apparie : c'est lui qui commande, pas celui des deux series.
            "mde_r": descriptif.mde(len(ecart), sigma),
            "p_value": test["p_value"], "ic_bas": test["ic_bas"], "ic_haut": test["ic_haut"],
        }

    court = resultats["short"]
    verdict, motif = _conclure(court)
    resultat = {
        "id": ID_EXPERIENCE, "verdict": verdict, "motif": motif,
        "metrique_primaire": preenregistrement["metrique_primaire"],
        "n_total_apparies": len(apparies), "par_sens": resultats,
        "p_brute": court["p_value"], "mde_attendu": preenregistrement.get("mde_attendu"),
    }
    if clore:
        experiences.clore(ID_EXPERIENCE, verdict, motif, **{
            "n": court["n"], "ecart_moyen": court["ecart_moyen"],
            "mde_r": court["mde_r"], "p_value": court["p_value"]})
    return resultat


def _conclure(court: dict) -> tuple[str, str]:
    """La regle de decision, ecrite au preenregistrement, appliquee telle quelle."""
    n, ecart, mde, p = court["n"], court["ecart_moyen"], court["mde_r"], court["p_value"]
    if n < N_MIN:
        return "indecidable", f"{n} shorts apparies : trop peu pour decider quoi que ce soit"
    if not np.isfinite(ecart) or not np.isfinite(mde):
        return "indecidable", "ecart ou MDE non calculable"
    if abs(ecart) < mde:
        return "indecidable", (f"ecart {ecart:+.4f} R sous le MDE {mde:.4f} R "
                               f"(n = {n}) : indistinguable de zero")
    if ecart > 0 and np.isfinite(p) and p <= 0.05:
        return "confirmee", (f"la barriere fixe rend {ecart:+.4f} R de plus par short "
                             f"(n = {n}, p = {p:.4f}, MDE = {mde:.4f})")
    if ecart <= 0:
        return "infirmee", (f"la barriere fixe fait PIRE que le trailing ({ecart:+.4f} R, "
                            f"n = {n})")
    return "indecidable", (f"ecart {ecart:+.4f} R au-dessus du MDE mais p = {p:.4f} > 0,05 "
                           f"(n = {n})")
