"""PBOR : la campagne, de bout en bout.

Ordre : gel verifie (registre, regles, texte du preenregistrement, code commite, regles egales a
celles de la porte S10) -> les 3 lots de septembre (chaque verdict.json controle, trades.parquet
a l'empreinte figee, PBO de S10) -> les 6 variantes de la voie C du 22/09
(`voie_c_voltarget.preparer` coupe au 05/09/2026, puis `variantes_selection`, le chemin meme de
`main()`) -> rapport ecrit par le programme. Aucun run n'est journalise, aucun verdict n'est
touche : PBOR est un diagnostic, le compteur ne bouge pas.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from beta import config
from beta.pbo_passe import regles as R
from beta.protocole import experiences
from beta.stats import batterie, pbo

log = logging.getLogger("beta.pbo_passe.campagne")

DOSSIER = config.DATA / "pbo_passe"
RUNS = config.DATA / "runs"
SORTIE = config.RACINE / "pbo_passe"
TEXTE = SORTIE / "PREENREGISTREMENT.md"
# Ce qui doit etre commite, tel quel, avant le premier calcul.
CODE = ("beta/pbo_passe", "beta/stats/pbo.py", "beta/stats/cscv.py", "beta/stats/batterie.py",
        "beta/strategies/voie_c_voltarget.py", "pbo_passe/PREENREGISTREMENT.md",
        "scripts/pbo_passe.py")


class PBOError(RuntimeError):
    """Une condition du preenregistrement n'est pas remplie : arret, aucun chiffre."""


# ----------------------------------------------------------------------------- verifications

def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(config.RACINE), *args], capture_output=True,
                          timeout=30)


def _code() -> str | None:
    r = _git("rev-parse", "--short", "HEAD")
    return r.stdout.decode().strip() or None if r.returncode == 0 else None


def empreinte_texte() -> str:
    return hashlib.sha256(TEXTE.read_bytes()).hexdigest()[:16]


def _sha(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


def verifier_gel() -> dict:
    if (R.SEUIL, R.S, R.PPA) != (batterie.SEUIL_PBO, pbo.S, pbo.PPA):
        raise PBOError("les regles de PBOR ne sont plus celles de la porte S10")
    experiences.exiger(R.ID_EXP)
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise PBOError(f"{R.ID_EXP} n'est pas journalisee (scripts/preenregistrer_pbor.py)")
    pre = lignes[-1]
    if pre.get("diagnostic") is not True:
        raise PBOError(f"{R.ID_EXP} n'est pas marquee diagnostic")
    if pre.get("empreinte") != R.empreinte():
        raise PBOError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                       f"{R.empreinte()}")
    if pre.get("empreinte_preenregistrement") != empreinte_texte():
        raise PBOError("pbo_passe/PREENREGISTREMENT.md change depuis le gel")
    sale = _git("status", "--porcelain", "--", *CODE)
    if sale.returncode != 0 or sale.stdout.strip():
        raise PBOError("code ou preenregistrement non commite :\n" + sale.stdout.decode())
    return pre


# ----------------------------------------------------------------------------- les lots

def charger_lot(lot: dict, runs: pathlib.Path | None = None,
                empreintes: dict[str, str] | None = None) -> tuple[dict, list[dict]]:
    """Les trades de chaque candidate du lot, tels qu'enregistres, apres controle du run."""
    runs = RUNS if runs is None else runs
    empreintes = R.EMPREINTES_TRADES if empreintes is None else empreintes
    trades, fiches = {}, []
    for nom, run_id in lot["runs"].items():
        dossier = runs / run_id
        verdict = json.loads((dossier / "verdict.json").read_text(encoding="utf-8"))
        detail = json.loads((dossier / "batterie.json").read_text(encoding="utf-8"))
        s7 = detail.get("S7_reality_check") or {}
        if (verdict.get("candidate") != nom
                or not str(verdict.get("lance_le", "")).startswith(lot["lance_le"])
                or verdict.get("n_essais_cumules") != lot["n_essais_cumules"]
                or s7.get("n_candidates") != len(lot["runs"])):
            raise PBOError(f"le run {run_id} n'est pas celui de '{nom}' dans le lot "
                           f"du {lot['lance_le']} (N = {lot['n_essais_cumules']})")
        chemin = dossier / "trades.parquet"
        if _sha(chemin) != empreintes.get(run_id):
            raise PBOError(f"trades du run {run_id} changes depuis le gel")
        trades[nom] = pd.read_parquet(chemin)
        fiches.append({"candidate": nom, "run": run_id, "issue": verdict.get("issue"),
                       "n_trades": int(len(trades[nom])),
                       "meilleure_s7": s7.get("meilleure")})
    return trades, fiches


def empreinte_matrice(m: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update("|".join(f"{d:%Y-%m-%d}" for d in m.index).encode())
    h.update("|".join(map(str, m.columns)).encode())
    h.update(np.ascontiguousarray(m.to_numpy(dtype=float)).tobytes())
    return h.hexdigest()[:16]


def lecture(res: dict) -> str:
    if res["passe"] is None:
        return "non executee"
    return "franchie" if res["passe"] else "echouee"


def lot(cle: str, runs: pathlib.Path | None = None,
        empreintes: dict[str, str] | None = None) -> dict:
    trades, fiches = charger_lot(R.LOTS[cle], runs, empreintes)
    m = pbo.rendements_lot(trades)
    res = pbo.calculer(m, R.SEUIL, R.S, R.PPA)
    return {"titre": R.LOTS[cle]["titre"], "candidates": fiches,
            "donnees": empreinte_matrice(m), "pbo": res, "lecture_s10": lecture(res)}


# ----------------------------------------------------------------------------- voie C

def voie_c() -> dict:
    """Les 6 variantes du 22/09 par le code de `voie_c_voltarget`, coupe au 05/09/2026."""
    from beta.strategies import voie_c_voltarget as vc

    ctx = vc.preparer(fin=R.FIN_VC)
    if ctx["fenetre"][-1] != pd.Timestamp(R.FIN_VC, tz="UTC"):
        raise PBOError(f"la fenetre finit le {ctx['fenetre'][-1]:%Y-%m-%d}, pas le {R.FIN_VC}")
    sorties = vc.variantes_selection(ctx)
    if tuple(sorties) != R.VARIANTES_VC:
        raise PBOError(f"variantes inattendues : {list(sorties)}")
    m = pd.DataFrame({nom: s["r_net"] for nom, s in sorties.items()})
    res = pbo.calculer(m, R.SEUIL, R.S, R.PPA)
    # La regle de main() : meilleur Sharpe net du train, premier en cas d'egalite.
    train = m.index <= pd.Timestamp(R.FIN_TRAIN_VC, tz="UTC")
    sharpe = {nom: vc.performance(m.loc[train, nom])["sharpe"] for nom in m.columns}
    return {"depart": f"{ctx['depart']:%Y-%m-%d}", "donnees": empreinte_matrice(m),
            "pbo": res, "lecture_s10": lecture(res),
            "retenue_train": max(sharpe, key=sharpe.get)}


# ----------------------------------------------------------------------------- campagne

def _compteurs() -> dict:
    return {"global": experiences.compteur_total(),
            "invest": experiences.compteur(famille="invest"),
            "trading": experiences.compteur(famille="trading")}


def _resume_pbo(res: dict) -> str:
    return "incalculable" if res["pbo"] is None else f"PBO {res['pbo']:.4f}"


def lancer() -> dict:
    from beta.pbo_passe import rapport

    pre = verifier_gel()
    avant = _compteurs()
    s = {"experience": R.ID_EXP, "code": _code(), "regles": R.empreinte(),
         "preenregistrement": empreinte_texte(),
         "debut_calcul": datetime.now(UTC).isoformat(timespec="seconds"), "lots": {}}
    for cle in R.LOTS:
        s["lots"][cle] = lot(cle)
        log.info("%s : %s, S10 %s", cle, _resume_pbo(s["lots"][cle]["pbo"]),
                 s["lots"][cle]["lecture_s10"])
    s["voie_c"] = voie_c()
    log.info("voie C : %s, S10 %s", _resume_pbo(s["voie_c"]["pbo"]), s["voie_c"]["lecture_s10"])
    s["calcule_le"] = datetime.now(UTC).isoformat(timespec="seconds")
    s["compteur"] = {"avant": avant, "apres": _compteurs(), "diagnostic": pre.get("diagnostic")}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie = DOSSIER / f"campagne_{R.ID_EXP}_{s['code']}.json"
    sortie.write_text(json.dumps(s, ensure_ascii=False, default=float), encoding="utf-8")
    rapport.ecrire(s)
    issue = " ; ".join([f"{cle} {_resume_pbo(x['pbo'])} (S10 {x['lecture_s10']})"
                        for cle, x in s["lots"].items()]
                       + [f"voie C {_resume_pbo(s['voie_c']['pbo'])} "
                          f"(S10 {s['voie_c']['lecture_s10']})"])
    cle = hashlib.sha256(sortie.read_bytes()).hexdigest()[:12]
    experiences.marquer_mesuree(R.ID_EXP, cle, f"diagnostic — {issue}")
    return s
