"""PBOC : la campagne, de bout en bout.

Ordre : gel verifie (registre, regles, texte du preenregistrement, code commite) -> controle
positif (graine 0) -> controle negatif (graines 1001 a 1100) -> si un controle rate : arret,
aucune donnee de la voie C lue -> grille de la voie C (le code de `voie_c_optim.evaluer`
lui-meme, rendements nets captes a la sortie de `derouler_bande`) -> dedoublonnage -> PBO ->
verdict mecanique -> rapport ecrit par le programme.
Aucun run n'est journalise : PBOC est un diagnostic, le compteur ne bouge pas.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import logging
import math
import subprocess
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from beta import config
from beta.pbo_voie_c import regles as R
from beta.protocole import experiences
from beta.stats import cscv

log = logging.getLogger("beta.pbo_voie_c.campagne")

DOSSIER = config.DATA / "pbo_voie_c"
SORTIE = config.RACINE / "pbo_voie_c"
TEXTE = SORTIE / "PREENREGISTREMENT.md"
# Ce qui doit etre commite, tel quel, avant le premier calcul.
CODE = ("beta/pbo_voie_c", "beta/stats/cscv.py", "beta/strategies/voie_c_optim.py",
        "beta/strategies/voie_c_voltarget.py", "pbo_voie_c/PREENREGISTREMENT.md",
        "scripts/pbo_voie_c.py")
PARAMETRES = ("cible", "estimateur", "fenetre", "lmax", "lmin", "pas", "bande")
QUANTILES = (0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0)


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


def verifier_gel() -> dict:
    experiences.exiger(R.ID_EXP)
    lignes = [x for x in experiences._lignes() if x.get("id") == R.ID_EXP
              and x.get("statut") == "preenregistre"]
    if not lignes:
        raise PBOError(f"{R.ID_EXP} n'est pas journalisee (scripts/preenregistrer_pboc.py)")
    pre = lignes[-1]
    if pre.get("diagnostic") is not True:
        raise PBOError(f"{R.ID_EXP} n'est pas marquee diagnostic")
    if pre.get("empreinte") != R.empreinte():
        raise PBOError(f"regles changees depuis le gel : {pre.get('empreinte')} -> "
                       f"{R.empreinte()}")
    if pre.get("empreinte_preenregistrement") != empreinte_texte():
        raise PBOError("pbo_voie_c/PREENREGISTREMENT.md change depuis le gel")
    sale = _git("status", "--porcelain", "--", *CODE)
    if sale.returncode != 0 or sale.stdout.strip():
        raise PBOError("code ou preenregistrement non commite :\n" + sale.stdout.decode())
    return pre


# ----------------------------------------------------------------------------- controles

def grille_hasard(graine: int) -> np.ndarray:
    return np.random.default_rng(graine).standard_normal((R.N_JOURS, R.N_CONTROLE))


def _resume(valeurs) -> dict:
    x = np.asarray(valeurs, dtype=float)
    return {"n": int(len(x)), "moyenne": float(x.mean()),
            "ecart_type": float(x.std(ddof=1)) if len(x) > 1 else None,
            "quantiles": {f"{q:g}": float(np.quantile(x, q)) for q in QUANTILES}}


def distribution(r: cscv.Resultat) -> dict:
    """Rangs hors echantillon de n*, tels quels : w, logits, deciles de w, n* distincts."""
    deciles = np.histogram(r.w, bins=np.linspace(0.0, 1.0, 11))[0]
    return {"pbo": r.pbo, "n_combinaisons": r.n_combinaisons, "n_configs": r.n_configs,
            "w": _resume(r.w), "lambda": _resume(r.lambdas),
            "deciles_w": [int(x) for x in deciles],
            "rang_oos": _resume(r.rangs),
            "sharpe_is_etoile": _resume(r.sharpe_is), "sharpe_oos_etoile": _resume(r.sharpe_oos),
            "n_etoiles_distinctes": int(len(np.unique(r.etoiles)))}


def avec_avantage(m: np.ndarray, sr: float) -> np.ndarray:
    mp = m.copy()
    mp[:, 0] += sr / math.sqrt(R.PPA)
    return mp


def controle_positif() -> dict:
    m = grille_hasard(R.GRAINE_POSITIF)
    sorties = {}
    for sr in (R.SR_POSITIF, R.SR_INFORMATIF):
        mp = avec_avantage(m, sr)
        r = cscv.pbo(mp, R.S, R.PPA)
        c = mp[:, 0]
        sorties[f"{sr:g}"] = {**distribution(r),
                              "part_etoile_colonne_0": float((r.etoiles == 0).mean()),
                              "sharpe_realise_colonne_0": float(c.mean() / c.std(ddof=1)
                                                                * math.sqrt(R.PPA))}
        log.info("controle positif, avantage %g : PBO %.4f", sr, r.pbo)
    pbo = sorties[f"{R.SR_POSITIF:g}"]["pbo"]
    return {"graine": R.GRAINE_POSITIF, "avantage": sorties, "pbo": pbo,
            "reussi": bool(pbo <= R.SEUIL_POSITIF)}


def controle_negatif() -> dict:
    debut, fin = R.GRAINES_NEGATIF
    pbos = {}
    for g in range(debut, fin + 1):
        pbos[g] = cscv.pbo(grille_hasard(g), R.S, R.PPA).pbo
        if (g - debut + 1) % 10 == 0:
            log.info("controle negatif : %d graines sur %d", g - debut + 1, fin - debut + 1)
    seule = distribution(cscv.pbo(grille_hasard(R.GRAINE_NEGATIF_RAPPORTEE), R.S, R.PPA))
    moyenne = float(np.mean(list(pbos.values())))
    bas, haut = R.BORNES_NEGATIF
    return {"graines": [debut, fin], "pbo_par_graine": {str(k): v for k, v in pbos.items()},
            "pbo": _resume(list(pbos.values())), "moyenne": moyenne,
            "erreur_type": float(np.std(list(pbos.values()), ddof=1) / math.sqrt(len(pbos))),
            "graine_0": seule, "reussi": bool(bas <= moyenne <= haut)}


# ----------------------------------------------------------------------------- voie C

def grille_voie_c() -> tuple[pd.DatetimeIndex, list[dict], np.ndarray]:
    """Rendements nets quotidiens des 5 760 configurations, par le code de la grille lui-meme.

    `voie_c_optim.evaluer` appelle `derouler_bande` une fois par configuration, dans l'ordre de
    `itertools.product` ; on remplace la fonction par une enveloppe qui garde sa sortie. Rien
    du moteur ni de la grille n'est recopie, et les statistiques qu'evaluer calcule sont jetees.
    """
    from beta.strategies import voie_c_optim as vo

    capte = []
    original = vo.derouler_bande

    def enveloppe(*args, **kwargs):
        r_net, r_brut = original(*args, **kwargs)
        capte.append(np.array(r_net, copy=True))
        return r_net, r_brut

    vo.derouler_bande = enveloppe
    try:
        grille, ctx = vo.evaluer()
    finally:
        vo.derouler_bande = original
    params = grille[list(PARAMETRES)].to_dict("records")
    del grille
    attendu = list(itertools.product(vo.CIBLES, vo.ESTIMATEURS, vo.FENETRES, vo.LEVIERS_MAX,
                                     vo.LEVIERS_MIN, vo.PAS, vo.BANDES))
    if len(capte) != len(attendu) or len(params) != len(attendu) or any(
            tuple(p[k] for k in PARAMETRES) != a for p, a in zip(params, attendu, strict=True)):
        raise PBOError("les rendements captes ne suivent pas l'ordre de la grille")
    closes, _, _ = vo.donnees()
    dates = closes.index[closes.index >= ctx["debut"]]
    if len(dates) != len(capte[0]) or dates[-1] != ctx["fin"]:
        raise PBOError("calendrier de la grille et rendements de longueurs differentes")
    return dates, params, np.column_stack(capte)


def fenetre_evaluation(dates: pd.DatetimeIndex) -> np.ndarray:
    debut, fin = (pd.Timestamp(x, tz="UTC") for x in (R.DEBUT, R.FIN))
    if dates[0] != pd.Timestamp(R.DEBUT_MOTEUR, tz="UTC"):
        raise PBOError(f"moteur parti le {dates[0]:%Y-%m-%d}, pas le {R.DEBUT_MOTEUR}")
    garde = np.asarray((dates >= debut) & (dates <= fin))
    if int(garde.sum()) != R.N_JOURS or int((~garde).sum()) != 8 or not garde[8:].all():
        raise PBOError(f"fenetre d'evaluation de {int(garde.sum())} jours, pas {R.N_JOURS}")
    return garde


def dedoublonner(params: list[dict], m: np.ndarray) -> dict:
    """Option b puis doublons exacts. `m` est deja coupee a la fenetre d'evaluation."""
    if len(params) != R.N_GRILLE:
        raise PBOError(f"{len(params)} configurations dans la grille, pas {R.N_GRILLE}")
    structure = [k for k in PARAMETRES if k != "cible"]
    groupes = {}
    for i, p in enumerate(params):
        groupes.setdefault(tuple(p[k] for k in structure), []).append(i)
    if len(groupes) != R.N_GROUPES or {len(v) for v in groupes.values()} != {6}:
        raise PBOError("groupes de l'option b : la grille n'a pas 960 groupes de 6 cibles")
    representants = []
    for membres in groupes.values():
        gardes = [i for i in membres if math.isclose(params[i]["cible"], R.CIBLE_GARDEE)]
        if len(gardes) != 1:
            raise PBOError(f"cible {R.CIBLE_GARDEE} absente ou repetee dans un groupe")
        representants.append(gardes[0])
    representants.sort()
    vus, gardes, doublons = {}, [], []
    for i in representants:
        cle = hashlib.sha256(np.ascontiguousarray(m[:, i]).tobytes()).hexdigest()
        if cle in vus:
            doublons.append({"config": params[i], "identique_a": params[vus[cle]]})
        else:
            vus[cle] = i
            gardes.append(i)
    return {"n_grille": len(params), "n_groupes": len(groupes),
            "n_representants": len(representants), "n_doublons_exacts": len(doublons),
            "n_apres": len(gardes), "gardes": gardes, "doublons": doublons}


def empreinte_matrice(dates: pd.DatetimeIndex, m: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update("|".join(f"{d:%Y-%m-%d}" for d in dates).encode())
    h.update(np.ascontiguousarray(m).tobytes())
    return h.hexdigest()[:16]


def voie_c() -> dict:
    dates, params, m = grille_voie_c()
    garde = fenetre_evaluation(dates)
    dates, m = dates[garde], m[garde]
    d = dedoublonner(params, m)
    mk = m[:, d["gardes"]]
    r = cscv.pbo(mk, R.S, R.PPA)
    etoiles, nb = np.unique(r.etoiles, return_counts=True)
    ordre = np.argsort(-nb, kind="stable")[:10]
    return {"donnees": empreinte_matrice(dates, mk),
            "fenetre": {"debut": f"{dates[0]:%Y-%m-%d}", "fin": f"{dates[-1]:%Y-%m-%d}",
                        "n_jours": int(len(dates))},
            "dedoublonnage": {k: v for k, v in d.items() if k != "gardes"},
            "pbo": distribution(r),
            "etoiles_frequentes": [{"config": params[d["gardes"][int(etoiles[k])]],
                                    "part": float(nb[k] / r.n_combinaisons)} for k in ordre]}


# ----------------------------------------------------------------------------- campagne

def verdict(pbo: float) -> str:
    return "candidate" if pbo < R.SEUIL_VOIE_C else "surajustee"


def _compteurs() -> dict:
    return {"global": experiences.compteur_total(),
            "invest": experiences.compteur(famille="invest"),
            "trading": experiences.compteur(famille="trading")}


def lancer() -> dict:
    from beta.pbo_voie_c import rapport

    pre = verifier_gel()
    avant = _compteurs()
    s = {"experience": R.ID_EXP, "code": _code(), "regles": R.empreinte(),
         "preenregistrement": empreinte_texte(),
         "debut_calcul": datetime.now(UTC).isoformat(timespec="seconds")}
    s["positif"] = controle_positif()
    s["negatif"] = controle_negatif()
    rates = [k for k in ("positif", "negatif") if not s[k]["reussi"]]
    if rates:
        s["arret"] = f"controle(s) rate(s) : {', '.join(rates)} ; voie C non calculee"
        s["voie_c"] = None
        s["verdict"] = None
        log.warning(s["arret"])
    else:
        s["voie_c"] = voie_c()
        s["verdict"] = verdict(s["voie_c"]["pbo"]["pbo"])
    s["calcule_le"] = datetime.now(UTC).isoformat(timespec="seconds")
    s["compteur"] = {"avant": avant, "apres": _compteurs(), "diagnostic": pre.get("diagnostic")}
    DOSSIER.mkdir(parents=True, exist_ok=True)
    sortie = DOSSIER / f"campagne_{R.ID_EXP}_{s['code']}.json"
    sortie.write_text(json.dumps(s, ensure_ascii=False, default=float), encoding="utf-8")
    rapport.ecrire(s)
    issue = s["arret"] if rates else (f"PBO {s['voie_c']['pbo']['pbo']:.4f} : voie C "
                                      f"{s['verdict']}")
    cle = hashlib.sha256(sortie.read_bytes()).hexdigest()[:12]
    experiences.marquer_mesuree(R.ID_EXP, cle, f"diagnostic — {issue}")
    return s
