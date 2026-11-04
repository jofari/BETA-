"""Le rapport d'une experience du moteur, ecrit par le programme (Jonas, 04/11/2026).

Jonas, 24/10 : « je ne veux pas que ce soit toi qui sois deterministe ». Le 04/11 encore, le
rapport de R13 et R14 envoye sur Discord portait des chiffres arrondis a la main, une
decomposition R brut / couts calculee hors de BETA et des interpretations ecrites comme des
resultats. Ce module relit le registre et les runs, et ecrit lui-meme :

- `RAPPORT.md` : le preenregistrement tel qu'il a ete ecrit, les donnees lues, les chiffres de
  chaque variante, la decomposition R brut / couts / R net, les sorties, le sens, les annees,
  la batterie porte par porte (champs du moteur et reserves mot pour mot), le buy-and-hold,
  l'epreuve de causalite, les compteurs, les empreintes, les controles de coherence ;
- `RESUME_DISCORD.md` : le message court du salon BETA, sans tableau Markdown.

Ce qu'il s'interdit : choisir un chiffre, en arrondir un hors des fonctions de format
ci-dessous, rendre ou reformuler un verdict. Le verdict d'une experience est celui de sa ligne
de cloture au registre ; celui d'une variante, celui de son `verdict.json`. Ce que le programme
RECALCULE (decomposition, sorties, sens, annees) vient de `trades.parquet` par les fonctions
du moteur et du dashboard (`beta.stats.descriptif`), et se verifie contre ce que le moteur a
ecrit : tout ecart est ecrit en clair, jamais corrige.

L'avis de Claude, s'il y en a un, est une section a part, marquee comme telle, recopiee d'un
fichier donne en argument : le programme n'y touche pas et ne la resume pas.

    python scripts/rapport_experience.py R13 R14 [--avis avis.md] [--eprouver]
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import pathlib
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from beta import config
from beta.protocole import experiences
from beta.stats import descriptif
from beta.stats.batterie import PORTES

log = logging.getLogger("beta.rapport.experience")

MODULE = "beta/rapport/experience.py"
SCRIPT = "scripts/rapport_experience.py"
SORTIE = config.RACINE / "rapports"
TOLERANCE = 1e-9

ISSUES = {"confirmee": "CONFIRMÉE", "infirmee": "INFIRMÉE", "indecidable": "INDÉCIDABLE"}

# Memes libelles que la fiche du dashboard (`web/fiche.js`, ETIQUETTE_PORTE).
PORTES_LIBELLES = {
    "S1_benjamini_hochberg": "S1 · Benjamini-Hochberg",
    "S2_sharpe_degonfle": "S2 · Sharpe dégonflé",
    "S3_bootstrap": "S3 · bootstrap par blocs",
    "S4_monte_carlo": "S4 · Monte-Carlo",
    "S5_synthetique": "S5 · chemins synthétiques",
    "S6_walk_forward": "S6 · walk-forward purgé",
    "S7_reality_check": "S7 · reality check",
    "S8_buy_and_hold": "S8 · buy-and-hold",
    "S9_diversification": "S9 · diversification",
    "S10_pbo": "S10 · PBO (CSCV)",
}

# Les champs de `batterie.json` montres pour chaque porte, sous leur NOM du moteur : le
# programme les recopie, il ne les traduit pas en phrase. S1 et S3 sont des listes, lues a part.
CHAMPS_PORTES = {
    "S2_sharpe_degonfle": ("sharpe", "sharpe_seuil", "n_essais", "dsr"),
    "S4_monte_carlo": ("permutation.p_perte", "permutation.p_ruine",
                       "permutation.p_drawdown_pire_que_seuil"),
    "S5_synthetique": ("observe", "centile", "seuil", "synthetique_median", "n_chemins"),
    "S6_walk_forward": ("ancre.is_moyen", "ancre.oos_moyen", "ancre.efficacite",
                        "ancre.plis_positifs", "cpcv.part_chemins_perdants"),
    "S7_reality_check": ("p_value", "meilleure", "n_candidates"),
    "S8_buy_and_hold": ("hold.rendement_total_pct", "candidate.rendement_total_pct",
                        "ecart_rendement_pct", "ecart_sharpe"),
    "S9_diversification": ("correlation_max", "avec", "seuil"),
    "S10_pbo": ("pbo", "seuil", "n_configs", "raison"),
}

SORTIES = {"TP": "cible (TP)", "SL": "stop (SL)", "horizon": "horizon"}

# La reserve que `pipeline.executer` ecrit a chaque run, au format fixe.
MOTIF_SIGNAUX = re.compile(r"^(\d+) signaux mesures, (\d+) retenus")


class RapportError(RuntimeError):
    """Experience inconnue, ou rien a rapporter."""


# --- format : les SEULS arrondis du rapport -------------------------------------------------------

def _fini(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def nb(x, d: int = 4, signe: bool = False) -> str:
    """Nombre a la francaise : virgule, vrai signe moins. Absent ou non fini : « — »."""
    v = _fini(x)
    if v is None:
        return "—"
    texte = f"{v:+.{d}f}" if signe else f"{v:.{d}f}"
    return texte.replace("-", "−").replace(".", ",")


def pc(x, d: int = 2, signe: bool = False) -> str:
    """Un pourcentage DEJA en points (35,59 pour 35,59 %)."""
    texte = nb(x, d, signe)
    return texte if texte == "—" else f"{texte} %"


def part(x, d: int = 1) -> str:
    """Une fraction (0,3114) lue en pourcentage (31,1 %)."""
    v = _fini(x)
    return "—" if v is None else pc(100.0 * v, d)


def entier(x) -> str:
    v = _fini(x)
    return "—" if v is None else f"{int(round(v)):,}".replace(",", " ")


def date_fr(iso) -> str:
    """'2026-11-04...' -> '04/11/2026' ; avec l'heure si l'horodatage en porte une."""
    if not iso:
        return "—"
    texte = str(iso)
    jour = f"{texte[8:10]}/{texte[5:7]}/{texte[:4]}"
    heure = texte[11:16] if len(texte) >= 16 and texte[10] in "T " else ""
    return f"{jour} {heure} UTC" if heure and heure != "00:00" else jour


def _valeur(x) -> str:
    """Un champ du moteur tel quel : nombre a 4 decimales, texte, booleen, vide."""
    if isinstance(x, bool):
        return "oui" if x else "non"
    if isinstance(x, (int, float)):
        return nb(x, 4) if isinstance(x, float) else entier(x)
    if x in (None, ""):
        return "—"
    return str(x)


def _table(entetes: list[str], lignes: list[list]) -> list[str]:
    return (["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
            + ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes])


def _bloc_texte(texte) -> list[str]:
    """Un texte du registre, cite tel quel."""
    return [f"> {ligne}" if ligne else ">" for ligne in str(texte or "—").splitlines()]


def _empreinte(objet) -> str:
    brut = json.dumps(objet, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(brut).hexdigest()[:16]


def _commit() -> str:
    try:
        tete = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.RACINE,
                              capture_output=True, text=True, check=False).stdout.strip()
        sale = subprocess.run(["git", "status", "--porcelain", "--", "beta", "scripts"],
                              cwd=config.RACINE, capture_output=True, text=True,
                              check=False).stdout.strip()
    except OSError:
        return "?"
    return f"{tete or '?'}{' + modifications non commitées' if sale else ''}"


# --- lecture : le registre et les runs ------------------------------------------------------------

def _json(chemin: pathlib.Path) -> dict:
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("%s illisible (%s)", chemin, exc)
        return {}


def _parquet(chemin: pathlib.Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(chemin)
    except (OSError, ValueError, ImportError) as exc:
        log.debug("%s illisible (%s)", chemin, exc)
        return pd.DataFrame()


@dataclass
class Variante:
    """Un run d'une experience : ce que le moteur a ecrit, et ce que le journal en dit."""

    run_id: str
    candidate: str
    present: bool
    verdict: dict = field(default_factory=dict)
    batterie: dict = field(default_factory=dict)
    trades: pd.DataFrame = field(default_factory=pd.DataFrame)
    epreuve: dict = field(default_factory=dict)
    journal: list[dict] = field(default_factory=list)


@dataclass
class Experience:
    id: str
    lignes: list[dict]
    preenregistrement: dict
    premier_preenregistrement: dict
    amendements: list[dict]
    cloture: dict | None
    variantes: list[Variante]
    origine_runs: str
    autres_runs: list[str]


def _variante(run_id: str, candidate: str, resultats: pathlib.Path,
              journal: list[dict]) -> Variante:
    dossier = resultats / run_id
    verdict = _json(dossier / "verdict.json")
    return Variante(run_id=run_id, candidate=verdict.get("candidate") or candidate,
                    present=bool(verdict), verdict=verdict,
                    batterie=_json(dossier / "batterie.json"),
                    trades=_parquet(dossier / "trades.parquet"),
                    epreuve=_json(dossier / "epreuve.json"),
                    journal=[e for e in journal if e.get("run_id") == run_id])


def charger(id_exp: str, *, registre: pathlib.Path | None = None,
            journal: pathlib.Path | None = None,
            resultats: pathlib.Path | None = None) -> Experience:
    """Tout ce que le registre et les runs disent d'une experience, sans rien recalculer."""
    from beta.moteur.pipeline import RESULTATS

    resultats = resultats or RESULTATS
    lignes = [x for x in experiences._lignes(registre) if x.get("id") == id_exp]
    if not lignes:
        raise RapportError(f"experience inconnue au registre : {id_exp}")
    preenr = [x for x in lignes if x.get("statut") == "preenregistre"]
    if not preenr:
        raise RapportError(f"{id_exp} : aucune ligne de preenregistrement")
    cloture = next((x for x in reversed(lignes) if x.get("statut") == "clos"), None)

    runs_exp = [e for e in experiences.runs_journalises(journal)
                if e.get("experience") == id_exp]
    if cloture and cloture.get("runs"):
        ids = [str(r) for r in cloture["runs"]]
        lot = [str(c) for c in (cloture.get("lot") or [])]
        noms = dict(zip(ids, lot, strict=False)) if len(lot) == len(ids) else {}
        origine = "cloture"
    else:
        dernier: dict[str, str] = {}
        for e in runs_exp:
            dernier[e.get("candidate") or "?"] = e.get("run_id")
        ids = list(dernier.values())
        noms = {v: k for k, v in dernier.items()}
        origine = "journal"
    variantes = [_variante(r, noms.get(r, "?"), resultats, runs_exp) for r in ids]
    autres = sorted({e.get("run_id") for e in runs_exp} - set(ids))
    return Experience(id=id_exp, lignes=lignes, preenregistrement=preenr[-1],
                      premier_preenregistrement=preenr[0],
                      amendements=[x for x in preenr if x.get("amendement")],
                      cloture=cloture, variantes=variantes, origine_runs=origine,
                      autres_runs=autres)


# --- ce que le programme recalcule, et verifie ----------------------------------------------------

def decomposition(trades: pd.DataFrame) -> dict:
    """R brut, couts et R net moyens par trade, depuis `trades.parquet` (informatif)."""
    if trades.empty or "r" not in trades.columns:
        return {}
    sortie = {"n": len(trades)}
    for colonne in ("r_brut", "cout_r", "frais_r", "spread_r", "funding_r", "r"):
        if colonne in trades.columns:
            sortie[colonne] = float(trades[colonne].dropna().mean())
    return sortie


def signaux_du_moteur(verdict: dict) -> tuple[int | None, int | None]:
    """(signaux mesures, retenus apres chevauchements), lus dans la reserve du moteur."""
    for reserve in verdict.get("reserves") or []:
        trouve = MOTIF_SIGNAUX.match(str(reserve))
        if trouve:
            return int(trouve.group(1)), int(trouve.group(2))
    return None, None


def controles(exp: Experience) -> list[dict]:
    """Ce que le programme refait et compare a ce que le moteur a ecrit. Jamais corrige."""
    sortie = []

    def ajouter(variante: str, quoi: str, ok: bool | None, detail: str = "") -> None:
        sortie.append({"variante": variante, "controle": quoi, "ok": ok, "detail": detail})

    detail_cloture = (exp.cloture or {}).get("detail") or {}
    for v in exp.variantes:
        nom = v.candidate
        ajouter(nom, "run présent dans data/runs", v.present,
                "" if v.present else f"data/runs/{v.run_id}/verdict.json absent")
        if not v.present:
            continue
        m = v.verdict.get("metriques") or {}
        journal_ok = any(e.get("candidate") == nom and e.get("issue") == v.verdict.get("issue")
                         and e.get("empreinte") == v.verdict.get("empreinte")
                         for e in v.journal)
        ajouter(nom, "run journalisé dans RUNS.jsonl (candidate, empreinte, issue)",
                journal_ok, f"{len(v.journal)} ligne(s)")
        t = v.trades
        if t.empty or "r" not in t.columns:
            ajouter(nom, "trades.parquet lisible", False, "absent ou sans colonne r")
            continue
        r = t["r"].dropna()
        ecart = abs(float(r.mean()) - float(m.get("r_moyen"))) if len(r) and \
            _fini(m.get("r_moyen")) is not None else None
        ajouter(nom, "R moyen recalculé = verdict.json",
                None if ecart is None else ecart <= TOLERANCE,
                "" if ecart is None else f"écart {ecart:.1e}".replace(".", ","))
        ajouter(nom, "nombre de trades recalculé = verdict.json", len(t) == m.get("n"),
                f"{len(t)} contre {m.get('n')}")
        if {"r_brut", "cout_r"} <= set(t.columns):
            ecart = float((t["r"] - (t["r_brut"] - t["cout_r"])).abs().max())
            ajouter(nom, "R net = R brut − coûts, trade par trade", ecart <= TOLERANCE,
                    f"écart maximal {ecart:.1e}".replace(".", ","))
        if {"cout_r", "frais_r", "spread_r", "funding_r"} <= set(t.columns):
            somme = t["frais_r"] + t["spread_r"] + t["funding_r"]
            ecart = float((t["cout_r"] - somme).abs().max())
            ajouter(nom, "coûts = frais + spread + funding, trade par trade",
                    ecart <= TOLERANCE, f"écart maximal {ecart:.1e}".replace(".", ","))
        if nom in detail_cloture:
            d = detail_cloture[nom]
            pareil = (d.get("run") == v.run_id and d.get("issue") == v.verdict.get("issue")
                      and d.get("r_moyen") == m.get("r_moyen")
                      and sorted(d.get("portes_echouees") or [])
                      == sorted(v.verdict.get("portes_echouees") or []))
            ajouter(nom, "ligne de clôture = verdict.json (run, issue, R moyen, portes)",
                    pareil)
    return sortie


def famille(exp: Experience) -> str:
    try:
        return experiences.famille_de(exp.id)
    except experiences.ProtocoleError:
        return exp.preenregistrement.get("famille_compteur") or "trading"


def compteurs(exp: Experience) -> dict:
    famille_exp = famille(exp)
    lots = sorted({v.verdict.get("n_essais_cumules") for v in exp.variantes
                   if v.present and v.verdict.get("n_essais_cumules") is not None})
    try:
        aujourd_hui = experiences.compteur(famille=famille_exp)
    except experiences.ProtocoleError:
        aujourd_hui = None
    return {"famille": famille_exp,
            "au_preenregistrement": exp.premier_preenregistrement.get("n_essais_cumules"),
            "lot": lots, "a_la_cloture": (exp.cloture or {}).get("n_essais_cumules"),
            "aujourd_hui": aujourd_hui}


# --- noms : ce que le registre et les runs appellent les choses -----------------------------------

def noms(exp: Experience) -> tuple[str, dict[str, str]]:
    """(nom de l'experience, libelle de chaque variante), tires des titres des candidates.

    Les titres du lot s'ecrivent « <regle> — <variante> » : si toutes partagent la meme regle,
    elle nomme l'experience et le reste nomme la variante. Sinon : l'identifiant du registre,
    et le titre entier pour chaque variante. Rien n'est invente.
    """
    titres = {v.candidate: (v.verdict.get("titre") or v.candidate) for v in exp.variantes}
    morceaux = {c: t.split(" — ", 1) for c, t in titres.items()}
    tetes = {m[0] for m in morceaux.values() if len(m) == 2}
    if titres and len(tetes) == 1 and all(len(m) == 2 for m in morceaux.values()):
        return tetes.pop(), {c: m[1] for c, m in morceaux.items()}
    return exp.id, titres


def pastille(exps: list[Experience]) -> tuple[str, str]:
    """L'etat du CALCUL, jamais un jugement du resultat."""
    tous = [c for e in exps for c in controles(e)]
    echecs = [c for c in tous if c["ok"] is False]
    passes = sum(1 for c in tous if c["ok"] is True)
    if echecs:
        return "🔴", f"{len(echecs)} contrôle(s) en écart sur {len(tous)} — voir le rapport"
    if any(e.cloture is None or e.cloture.get("verdict") == "indecidable" for e in exps):
        return "🟠", (f"expérience non close ou indécidable ; {passes} contrôles sur "
                      f"{len(tous)} passés")
    return "🟢", f"verdict au registre et {passes} contrôles sur {len(tous)} passés"


# --- le rapport complet ---------------------------------------------------------------------------

def _champ(detail, chemin: str):
    for cle in chemin.split("."):
        if not isinstance(detail, dict):
            return None
        detail = detail.get(cle)
    return detail


def _porte(v: Variante, porte: str) -> str:
    detail = v.batterie.get(porte)
    if porte == "S1_benjamini_hochberg" and isinstance(detail, list):
        ligne = next((x for x in detail if x.get("nom") == v.candidate), None)
        return "" if not ligne else " ; ".join(
            f"{k} = {_valeur(ligne.get(k))}" for k in ("p_brute", "seuil_BH", "signif_BH",
                                                      "m_declare") if k in ligne)
    if porte == "S3_bootstrap" and isinstance(detail, list):
        return " ; ".join(f"p_value (ell = {_valeur(x.get('ell_demande') or x.get('ell'))}) = "
                          f"{_valeur(x.get('p_value'))}" for x in detail)
    return " ; ".join(f"{c} = {_valeur(_champ(detail, c))}"
                      for c in CHAMPS_PORTES.get(porte, ()) if _champ(detail, c) is not None)


def _issue(v: Variante) -> str:
    if not v.present:
        return "run absent"
    issue = v.verdict.get("issue")
    return ISSUES.get(issue, str(issue or "sans issue"))


def _etat_porte(v: Variante, porte: str) -> str:
    etat = (v.verdict.get("portes") or {}).get(porte, "absente")
    return {True: "ok", False: "**ÉCHEC**", None: "non exécutée"}.get(etat, "absente")


def _section_preenregistrement(exp: Experience) -> list[str]:
    p, p0 = exp.preenregistrement, exp.premier_preenregistrement
    L = ["### Préenregistrement (tel qu'écrit avant la mesure)", ""]
    L.append(f"- Écrit le {date_fr(p0.get('date'))} ; empreinte de la ligne "
             f"`{_empreinte(p)}` ; N au préenregistrement : "
             f"{_valeur(p0.get('n_essais_cumules'))} ; famille du compteur : "
             f"{famille(exp)} ; split autorisé : "
             f"{p.get('split_autorise') or '—'}.")
    mde = "non déclaré" if p.get("mde_attendu") is None else _valeur(p.get("mde_attendu"))
    L.append(f"- Famille déclarée : {_valeur(p.get('famille_taille'))} ; issue attendue : "
             f"{ISSUES.get(p.get('issue_attendue'), p.get('issue_attendue') or '—')} ; MDE "
             f"attendu : {mde}.")
    for cle, libelle in (("decide_par", "Décidé par"), ("derive_de", "Dérivé de")):
        if p.get(cle):
            L.append(f"- {libelle} : « {p[cle]} »")
    for a in exp.amendements:
        L.append(f"- Amendement du {date_fr(a.get('date'))} : « {a.get('amendement')} »")
    L += ["", "**Hypothèse**", ""] + _bloc_texte(p.get("hypothese"))
    L += ["", "**Métrique primaire**", ""] + _bloc_texte(p.get("metrique_primaire"))
    L += ["", "**Règle de décision**", ""]
    regle = p.get("regle_de_decision")
    if isinstance(regle, dict):
        L += [f"- `{k}` : « {x} »" for k, x in regle.items()]
    else:
        L += _bloc_texte(regle)
    if isinstance(p.get("regles"), dict):
        L += ["", "**Règles déclarées** (`regles`)", ""]
        L += [f"- `{k}` : {json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x}"
              for k, x in p["regles"].items()]
    if p.get("deja_connu"):
        L += ["", "**Déjà connu au préenregistrement**", ""] + _bloc_texte(p["deja_connu"])
    return L


def _fin_demandee(verdict: dict) -> str:
    if verdict.get("fin"):
        return str(verdict["fin"])
    return "aucune (bornée au train)" if verdict.get("split") == "train" else "aucune"


def _section_donnees(exp: Experience) -> list[str]:
    L = ["### Données et paramètres de la mesure", ""]
    donnees = (exp.cloture or {}).get("donnees")
    if isinstance(donnees, dict):
        L.append(f"- Série lue (ligne de clôture) : {entier(donnees.get('bougies'))} bougies, "
                 f"du {date_fr(donnees.get('premiere'))} au {date_fr(donnees.get('derniere'))}, "
                 f"empreinte `{donnees.get('sha256', '—')}`.")
    presents = [v for v in exp.variantes if v.present]
    if presents:
        v = presents[0].verdict
        L.append(f"- Paires : {', '.join(v.get('paires') or []) or '—'} ; timeframe "
                 f"{v.get('timeframe') or '—'} ; split {v.get('split') or '—'} ; début "
                 f"demandé {v.get('debut') or 'aucun'} ; fin demandée {_fin_demandee(v)}.")
        L.append(f"- Barrières : take_profit_r = {_valeur(v.get('take_profit_r'))} ; "
                 f"horizon_bougies = {_valeur(v.get('horizon_bougies'))} ; stop_atr (si la "
                 f"candidate ne donne pas de stop) = {_valeur(v.get('stop_atr'))}.")
        L.append(f"- Coûts : frais_pct = {_valeur(v.get('frais_pct'))} ; slippage_pct = "
                 f"{_valeur(v.get('slippage_pct'))} ; cout_aller_retour_pct = "
                 f"{_valeur(v.get('cout_aller_retour_pct'))} ; spread = "
                 f"{_valeur(v.get('spread'))} (modèle {v.get('spread_modele') or '—'}) ; "
                 f"funding = {_valeur(v.get('funding'))}.")
    for v in presents:
        L.append(f"- Paramètres de `{v.candidate}` : "
                 f"{json.dumps(v.verdict.get('parametres') or {}, ensure_ascii=False)}")
    return L


def _section_resultats(exp: Experience, libelles: dict[str, str]) -> list[str]:
    L = ["### Résultats par variante (moteur, `verdict.json`)", ""]
    lignes = []
    for v in exp.variantes:
        m = v.verdict.get("metriques") or {}
        mesures, retenus = signaux_du_moteur(v.verdict)
        lignes.append([libelles.get(v.candidate, v.candidate), f"`{v.run_id}`",
                       _issue(v), entier(mesures),
                       entier(m.get("n")), nb(m.get("r_moyen"), 4, True),
                       nb(m.get("r_median"), 4, True), nb(m.get("r_sigma")),
                       nb(m.get("mde_r")), part(m.get("win_rate")),
                       nb(m.get("profit_factor")), nb(m.get("mfe_r_moyen"), 4, True),
                       nb(m.get("mae_r_moyen"), 4, True), nb(m.get("duree_h_mediane"), 2)])
    L += _table(["Variante", "Run", "Issue", "Signaux mesurés", "Trades retenus", "R moyen",
                 "R médian", "σ(R)", "MDE", "Taux de gain", "Profit factor", "MFE moyen",
                 "MAE moyen", "Durée médiane (h)"], lignes)
    L += ["", "« Signaux mesurés » vient de la réserve écrite par le moteur à chaque run ; "
          "« Trades retenus » = après élimination des chevauchements (`metriques.n`)."]
    return L


def _section_decomposition(exp: Experience, libelles: dict[str, str]) -> list[str]:
    L = ["### R brut, coûts, R net (recalculés par le programme depuis `trades.parquet`)", "",
         "Moyennes par trade, en R. Informatif : la métrique primaire est le R net, et "
         "aucune règle de décision ne porte sur le R brut.", ""]
    lignes = []
    for v in exp.variantes:
        d = decomposition(v.trades)
        lignes.append([libelles.get(v.candidate, v.candidate), entier(d.get("n")),
                       nb(d.get("r_brut"), 4, True), nb(d.get("cout_r")),
                       nb(d.get("frais_r")), nb(d.get("spread_r")),
                       nb(d.get("funding_r"), 4, True), nb(d.get("r"), 4, True)])
    L += _table(["Variante", "Trades", "R brut", "Coûts (total)", "dont frais",
                 "dont spread", "dont funding", "R net"], lignes)
    return L


def _ventilation(titre: str, exp: Experience, libelles: dict, cle: str, entete: str,
                 etiquettes: dict | None = None) -> list[str]:
    L = [f"### {titre}", ""]
    lignes = []
    for v in exp.variantes:
        t = v.trades
        if t.empty or cle not in t.columns:
            continue
        table = descriptif.par(t, cle).sort_values(cle)
        for x in table.to_dict("records"):
            groupe = x[cle]
            lignes.append([libelles.get(v.candidate, v.candidate),
                           (etiquettes or {}).get(groupe, groupe), entier(x.get("n")),
                           part(x["n"] / len(t)), nb(x.get("r_moyen"), 4, True),
                           nb(x.get("r_total"), 2, True), part(x.get("win_rate"))])
    if not lignes:
        return L + ["Aucun trade."]
    return L + _table(["Variante", entete, "Trades", "Part", "R moyen", "R total",
                       "Taux de gain"], lignes)


def _section_portes(exp: Experience, libelles: dict[str, str]) -> list[str]:
    presents = [v for v in exp.variantes if v.present]
    L = ["### Batterie, porte par porte (`verdict.json` et `batterie.json`)", ""]
    if not presents:
        return L + ["Aucun run lisible."]
    entetes = ["Porte"] + [libelles.get(v.candidate, v.candidate) for v in presents]
    lignes = [[PORTES_LIBELLES.get(p, p)] + [_etat_porte(v, p) for v in presents]
              for p in PORTES]
    lignes.append(["Portes échouées"] + [f"{len(v.verdict.get('portes_echouees') or [])} sur "
                                         f"{len(PORTES)}" for v in presents])
    L += _table(entetes, lignes)
    for v in presents:
        L += ["", f"**{libelles.get(v.candidate, v.candidate)}** (`{v.candidate}`, run "
              f"`{v.run_id}`) — champs du moteur :", ""]
        for p in PORTES:
            texte = _porte(v, p)
            if texte:
                L.append(f"- {PORTES_LIBELLES.get(p, p)} : {texte}")
        L += ["", "Réserves du moteur, mot pour mot :", ""]
        L += [f"- {r}" for r in v.verdict.get("reserves") or []] or ["- aucune"]
    return L


def _section_hold(exp: Experience, libelles: dict[str, str]) -> list[str]:
    L = ["### Buy-and-hold du même actif sur la même période (S8)", "",
         "« Candidate » = la courbe du moteur (capital 100 000, 1 % du capital risqué par "
         "trade, non composée) ; elle peut passer sous zéro.", ""]
    lignes = []
    for v in exp.variantes:
        s8 = v.batterie.get("S8_buy_and_hold") or {}
        h, c = s8.get("hold") or {}, s8.get("candidate") or {}
        if not s8:
            continue
        lignes.append([libelles.get(v.candidate, v.candidate),
                       f"{date_fr(h.get('debut'))} → {date_fr(h.get('fin'))}",
                       pc(h.get("rendement_total_pct"), 2, True), nb(h.get("sharpe_annuel"), 2),
                       pc(h.get("drawdown_max_pct"), 2, True),
                       pc(c.get("rendement_total_pct"), 2, True), nb(c.get("sharpe_annuel"), 2),
                       pc(c.get("drawdown_max_pct"), 2, True),
                       {True: "oui", False: "non"}.get(s8.get("passe"), "—")])
    if not lignes:
        return L + ["S8 absente des runs lisibles."]
    return L + _table(["Variante", "Période du hold", "Hold : rendement", "Hold : Sharpe",
                       "Hold : drawdown max", "Candidate : rendement", "Candidate : Sharpe",
                       "Candidate : drawdown max", "S8 franchie"], lignes)


def _ligne_epreuve(rapport: dict, quand: str) -> str:
    if not rapport:
        return "—"
    series = rapport.get("series") or {}
    if not series and rapport.get("mesures"):
        temoin = str(rapport["mesures"].get("temoin") or "?").split(",")[0]
        series = {temoin: rapport["mesures"]}
    morceaux = [f"{nom} : {entier(m.get('n_bougies'))} bougies du "
                f"{date_fr(m.get('premiere'))} au {date_fr(m.get('derniere'))}, "
                f"{entier(m.get('n_signaux'))} signaux ({entier(m.get('n_long'))} longs, "
                f"{entier(m.get('n_short'))} courts), causalité {m.get('causalite', '—')}, "
                f"déterminisme {m.get('determinisme', '—')}" for nom, m in series.items()]
    etat = "OK" if rapport.get("ok") else "REFUSÉE"
    refus = "".join(f" ; refus : {r}" for r in rapport.get("refus") or [])
    return f"{etat} ({quand}) — " + " | ".join(morceaux) + refus


def _section_epreuve(exp: Experience, libelles: dict, relancees: dict) -> list[str]:
    L = ["### Épreuve de causalité sur la série mesurée", ""]
    for v in exp.variantes:
        libelle = libelles.get(v.candidate, v.candidate)
        if v.epreuve:
            ligne = _ligne_epreuve(v.epreuve, "enregistrée par le moteur avec le run")
            L.append(f"- {libelle} : {ligne}")
        else:
            L.append(f"- {libelle} : non enregistrée avec le run (le moteur l'enregistre "
                     "depuis le 04/11/2026).")
        if v.candidate in relancees:
            r = relancees[v.candidate]
            ligne = _ligne_epreuve(r.get("rapport") or {},
                                   "code de la candidate : " + r.get("code", "?"))
            L.append(f"  - Relancée par le programme le {date_fr(r.get('le'))} "
                     f"(`beta.atelier.epreuve`, même série et même période que le run) : "
                     f"{ligne}")
    return L


def _section_compteurs(exp: Experience) -> list[str]:
    c = compteurs(exp)
    lot = ", ".join(_valeur(x) for x in c["lot"]) or "—"
    return ["### Compteur d'essais", "",
            f"- Famille : {c['famille']}.",
            f"- N au préenregistrement : {_valeur(c['au_preenregistrement'])} ; N figé pour "
            f"juger le lot (S2) : {lot} ; compteur inscrit à la clôture : "
            f"{_valeur(c['a_la_cloture'])} ; compteur aujourd'hui : "
            f"{_valeur(c['aujourd_hui'])}."]


def _section_tracabilite(exp: Experience) -> list[str]:
    L = ["### Traçabilité", ""]
    lignes = []
    for v in exp.variantes:
        journal = ", ".join(date_fr(e.get("date")) for e in v.journal) or "absent"
        lignes.append([f"`{v.run_id}`", f"`{v.candidate}`",
                       f"`{v.verdict.get('empreinte', '—')}`",
                       date_fr(v.verdict.get("lance_le")), journal])
    L += _table(["Run", "Candidate", "Empreinte du code", "Lancé le", "RUNS.jsonl"], lignes)
    origine = {"cloture": "la ligne de clôture du registre",
               "journal": "le dernier run de chaque candidate dans RUNS.jsonl (aucune liste "
                          "de runs à la clôture)"}[exp.origine_runs]
    L += ["", f"Runs retenus : ceux de {origine}."]
    if exp.autres_runs:
        L.append(f"Autres runs journalisés sous {exp.id}, non retenus : "
                 + ", ".join(f"`{r}`" for r in exp.autres_runs) + ".")
    return L


def _section_controles(exp: Experience, libelles: dict) -> list[str]:
    L = ["### Contrôles de cohérence (refaits par le programme)", ""]
    lignes = [[libelles.get(c["variante"], c["variante"]), c["controle"],
               {True: "ok", False: "**ÉCART**", None: "non vérifiable"}[c["ok"]], c["detail"]]
              for c in controles(exp)]
    return L + _table(["Variante", "Contrôle", "Résultat", "Détail"], lignes)


def _section_experience(exp: Experience, relancees: dict) -> list[str]:
    nom, libelles = noms(exp)
    cl = exp.cloture
    L = [f"## {nom} (registre : {exp.id})", "", "### Verdict du programme", ""]
    if cl:
        L.append(f"**{ISSUES.get(cl.get('verdict'), cl.get('verdict'))}** — ligne de clôture "
                 f"du registre, datée du {date_fr(cl.get('date'))} ; conforme à l'issue "
                 f"attendue : {_valeur(cl.get('conforme_a_l_issue_attendue'))}.")
    else:
        L.append("**Pas de clôture au registre** : aucun verdict d'expérience à rapporter.")
    issues = [f"{libelles.get(v.candidate, v.candidate)} : {_issue(v)}"
              for v in exp.variantes]
    L += ["", "Issues des variantes (moteur) : " + " ; ".join(issues) + "."]
    if cl and cl.get("resultat"):
        L += ["", "Texte de la clôture, tel qu'au registre :", ""] + _bloc_texte(cl["resultat"])
    L += [""] + _section_preenregistrement(exp)
    L += [""] + _section_donnees(exp)
    L += [""] + _section_resultats(exp, libelles)
    L += [""] + _section_decomposition(exp, libelles)
    L += [""] + _ventilation("Sorties, par raison (`trades.parquet`)", exp, libelles,
                             "raison_sortie", "Sortie", SORTIES)
    L += [""] + _ventilation("Par sens (`trades.parquet`)", exp, libelles, "sens", "Sens",
                             {"long": "long", "short": "court"})
    L += [""] + _ventilation("Par année de sortie (`trades.parquet`)", exp, libelles,
                             "annee", "Année")
    L += [""] + _section_portes(exp, libelles)
    L += [""] + _section_hold(exp, libelles)
    L += [""] + _section_epreuve(exp, libelles, relancees)
    L += [""] + _section_compteurs(exp)
    L += [""] + _section_tracabilite(exp)
    L += [""] + _section_controles(exp, libelles)
    return L


def _avec_annee(exp: Experience) -> Experience:
    for v in exp.variantes:
        if not v.trades.empty and "ts_sortie" in v.trades.columns:
            v.trades = v.trades.assign(
                annee=pd.to_datetime(v.trades["ts_sortie"], utc=True).dt.year)
    return exp


def markdown(exps: list[Experience], *, commande: str, avis: str | None = None,
             relancees: dict | None = None, maintenant: datetime | None = None) -> str:
    maintenant = maintenant or datetime.now(UTC)
    rond, etat = pastille(exps)
    titres = " · ".join(noms(e)[0] for e in exps)
    L = [f"# {titres} — rapport du programme", "",
         f"- Écrit par le programme (`{commande}`, module `{MODULE}`, commit `{_commit()}`), "
         f"le {maintenant.strftime('%d/%m/%Y %H:%M')} UTC.",
         "- Sources : `EXPERIMENTS.jsonl` (préenregistrement, mesures, clôture), "
         "`RUNS.jsonl`, `data/runs/<run>/` (`verdict.json`, `batterie.json`, "
         "`trades.parquet`, `epreuve.json`).",
         "- Aucun chiffre tapé à la main. Arrondis faits par le programme : R à 4 décimales "
         "ici (2 dans le résumé Discord), pourcentages à 2 décimales, taux à 1 décimale ; "
         "valeurs exactes dans les fichiers cités.",
         f"- État du calcul : {rond} {etat}. La pastille dit l'état du calcul, pas un "
         "jugement du résultat."]
    for exp in exps:
        L += [""] + _section_experience(_avec_annee(exp), relancees or {})
    if avis:
        L += ["", "## Avis de Claude — ce n'est PAS le programme", "",
              "Section écrite par Claude et recopiée telle quelle depuis un fichier fourni à "
              "la main. Ni ses chiffres ni ses conclusions ne sortent du programme.", "",
              avis.strip()]
    L += ["", f"Rapport écrit par le programme (`{MODULE}`), sans interprétation."]
    return "\n".join(L) + "\n"


# --- le resume Discord ----------------------------------------------------------------------------

def _bloc_variantes(exp: Experience, libelles: dict) -> list[str]:
    largeur = max([len(libelles.get(v.candidate, v.candidate)) for v in exp.variantes] + [8])
    entete = (f"{'variante':<{largeur}}  {'issue':<11} {'n':>5}  {'R net':>6}  {'R brut':>6}  "
              f"{'coûts':>5}  {'MDE':>5}  échouées")
    lignes = ["```", entete]
    for v in exp.variantes:
        m = v.verdict.get("metriques") or {}
        d = decomposition(v.trades)
        issue = _issue(v).lower()
        echouees = f"{len(v.verdict.get('portes_echouees') or [])}/{len(PORTES)}" \
            if v.present else "—"
        lignes.append(f"{libelles.get(v.candidate, v.candidate):<{largeur}}  {issue:<11} "
                      f"{entier(m.get('n')):>5}  {nb(m.get('r_moyen'), 2, True):>6}  "
                      f"{nb(d.get('r_brut'), 2, True):>6}  {nb(d.get('cout_r'), 2):>5}  "
                      f"{nb(m.get('mde_r'), 2):>5}  {echouees}")
    return lignes + ["```"]


def resume(exps: list[Experience], *, chemin_rapport: str, avis: bool = False,
           relancees: dict | None = None, maintenant: datetime | None = None) -> str:
    maintenant = maintenant or datetime.now(UTC)
    rond, etat = pastille(exps)
    titres = " · ".join(noms(e)[0] for e in exps)
    verdicts = " · ".join(
        f"{e.id} {ISSUES.get((e.cloture or {}).get('verdict'), 'NON CLOSE')}" for e in exps)
    L = [f"# {rond} {titres} — rapport du programme — {maintenant.date().isoformat()}", "",
         f"**Verdicts au registre : {verdicts}.**",
         f"État du calcul : {etat} (pastille = état du calcul, pas jugement du résultat)."]
    for exp in exps:
        nom, libelles = noms(_avec_annee(exp))
        p0, cl = exp.premier_preenregistrement, exp.cloture or {}
        L += ["", f"## {nom} — {exp.id} — {ISSUES.get(cl.get('verdict'), 'NON CLOSE')}",
              f"- Préenregistrée le {date_fr(p0.get('date'))} (N = "
              f"{_valeur(p0.get('n_essais_cumules'))}) ; close le {date_fr(cl.get('date'))} ; "
              f"conforme à l'issue attendue : {_valeur(cl.get('conforme_a_l_issue_attendue'))}"]
        donnees = cl.get("donnees")
        presents = [v for v in exp.variantes if v.present]
        if presents:
            v0 = presents[0].verdict
            serie = f"{', '.join(v0.get('paires') or [])} {v0.get('timeframe') or ''}".strip()
            if isinstance(donnees, dict):
                serie += (f", du {date_fr(donnees.get('premiere'))[:10]} au "
                          f"{date_fr(donnees.get('derniere'))[:10]}, "
                          f"{entier(donnees.get('bougies'))} bougies (empreinte "
                          f"{donnees.get('sha256', '—')})")
            L.append(f"- Série : {serie}")
        L += _bloc_variantes(exp, libelles)
        L.append("R net, R brut et coûts : moyennes par trade, en R (R brut et coûts "
                 "recalculés depuis les trades ; la règle ne porte que sur le R net).")
        holds = {pc((v.batterie.get("S8_buy_and_hold") or {}).get("hold", {})
                    .get("rendement_total_pct"), 2, True) for v in presents}
        franchie = sum(1 for v in presents
                       if (v.batterie.get("S8_buy_and_hold") or {}).get("passe") is True)
        L.append(f"- Buy-and-hold du même actif sur la même période (S8) : "
                 f"{' / '.join(sorted(holds)) or '—'} ; S8 franchie par {franchie} variante(s) "
                 f"sur {len(presents)}")
        avec = [v for v in exp.variantes if v.epreuve]
        relance = [c for c in (relancees or {}) if c in {v.candidate for v in exp.variantes}]
        if avec:
            ok = sum(1 for v in avec if v.epreuve.get("ok"))
            L.append(f"- Épreuve de causalité sur la série mesurée (moteur) : OK pour {ok} "
                     f"variante(s) sur {len(exp.variantes)}")
        elif relance:
            ok = [c for c in relance if (relancees[c].get("rapport") or {}).get("ok")]
            signaux = sorted({entier(((relancees[c].get("rapport") or {}).get("mesures") or {})
                                     .get("n_signaux")) for c in relance})
            meme = all(relancees[c].get("code") == "même empreinte que le run" for c in relance)
            code = (" (même code que les runs)" if meme
                    else " (code DIFFÉRENT des runs : voir le rapport)")
            L.append(f"- Épreuve de causalité sur la série mesurée : non enregistrée avec les "
                     f"runs ; relancée par le programme : OK pour {len(ok)} variante(s) sur "
                     f"{len(relance)}, {' / '.join(signaux)} signaux{code}")
        else:
            L.append("- Épreuve de causalité sur la série mesurée : non enregistrée avec les "
                     "runs (le moteur l'enregistre depuis le 04/11/2026)")
    c = [compteurs(e) for e in exps]
    L += ["", "## Compteur d'essais"]
    for e, x in zip(exps, c, strict=True):
        L.append(f"- {e.id} ({x['famille']}) : N = {_valeur(x['au_preenregistrement'])} au "
                 f"préenregistrement, lot jugé à N = "
                 f"{', '.join(_valeur(n) for n in x['lot']) or '—'}")
    familles = {x["famille"]: x["aujourd_hui"] for x in c}
    L.append("- Aujourd'hui : " + " ; ".join(f"{f} {_valeur(n)}" for f, n in familles.items()))
    runs = ", ".join(v.run_id for e in exps for v in e.variantes)
    L += ["", "## Fichiers", f"- `{chemin_rapport}` (joint) : préenregistrement mot pour mot, "
          "batterie porte par porte, sorties, sens, années, contrôles de cohérence",
          f"- Code `{_commit()}` ; runs {runs}"]
    if avis:
        L.append("- Le rapport joint contient une section « Avis de Claude », séparée et "
                 "marquée : elle ne vient pas du programme.")
    L += ["", f"Message écrit par le programme (`{MODULE}`), sans interprétation."]
    return "\n".join(L) + "\n"


# --- l'epreuve relancee, a la demande -------------------------------------------------------------

def relancer_epreuves(exps: list[Experience]) -> dict:
    """L'epreuve de l'atelier relancee sur la serie et la periode de chaque run.

    Pour les runs mesures avant que le moteur n'enregistre l'epreuve (04/11/2026). Tourne en
    sous-processus, comme dans l'atelier. Le code eprouve est celui d'AUJOURD'HUI : le rapport
    dit s'il a la meme empreinte que le run.
    """
    from beta.atelier import epreuve
    from beta.moteur import registre

    sortie = {}
    for exp in exps:
        for v in exp.variantes:
            if not v.present or v.epreuve:
                continue
            paires = v.verdict.get("paires") or []
            if len(paires) != 1:
                log.warning("%s : %d paires, epreuve relancee sur la premiere seulement",
                            v.candidate, len(paires))
            if not paires:
                continue
            try:
                code = ("même empreinte que le run"
                        if registre.charger(v.candidate).empreinte == v.verdict.get("empreinte")
                        else "DIFFÉRENT du run")
            except Exception:                              # noqa: BLE001 - dit tel quel
                code = "introuvable"
            rapport = epreuve.lancer(v.candidate, timeframe=v.verdict.get("timeframe") or "",
                                     actif=paires[0], debut=v.verdict.get("debut") or "",
                                     fin=v.verdict.get("fin") or "")
            sortie[v.candidate] = {"le": datetime.now(UTC).isoformat(), "run": v.run_id,
                                   "actif": paires[0], "code": code, "rapport": rapport}
    return sortie


# --- ecriture -------------------------------------------------------------------------------------

def ecrire(ids: list[str], *, sortie: pathlib.Path | None = None, avis: pathlib.Path | None = None,
           eprouver: bool = False, commande: str | None = None) -> dict:
    """Ecrit RAPPORT.md et RESUME_DISCORD.md (et EPREUVES.json si `eprouver`). Rend les chemins."""
    exps = [charger(i) for i in ids]
    sortie = sortie or SORTIE / "-".join(ids)
    sortie.mkdir(parents=True, exist_ok=True)
    texte_avis = avis.read_text(encoding="utf-8") if avis else None
    relancees = relancer_epreuves(exps) if eprouver else {}
    if relancees:
        (sortie / "EPREUVES.json").write_text(
            json.dumps(relancees, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8")
    commande = commande or f"{SCRIPT} {' '.join(ids)}"
    maintenant = datetime.now(UTC)
    rapport = sortie / "RAPPORT.md"
    rapport.write_text(markdown(exps, commande=commande, avis=texte_avis, relancees=relancees,
                                maintenant=maintenant), encoding="utf-8")
    try:
        relatif = rapport.relative_to(config.RACINE).as_posix()
    except ValueError:
        relatif = str(rapport)
    resume_md = sortie / "RESUME_DISCORD.md"
    resume_md.write_text(resume(exps, chemin_rapport=relatif, avis=bool(texte_avis),
                                relancees=relancees, maintenant=maintenant), encoding="utf-8")
    log.info("rapport ecrit : %s", rapport)
    return {"rapport": rapport, "resume": resume_md,
            "epreuves": sortie / "EPREUVES.json" if relancees else None,
            "pastille": pastille(exps)}
