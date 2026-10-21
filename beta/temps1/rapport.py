"""Temps 1 — le rapport de l'etape A (temps1/RAPPORT_ETAPE_A.md) et ses CSV.

Il relit la synthese et les runs ecrits par `campagne.lancer_campagne` ; il ne calcule rien
d'autre que des mises en forme. Consigne du prompt : aucune interpretation au-dela du verdict
mecanique — les seules phrases sont des faits (comptes, modes, ecarts).
"""

from __future__ import annotations

import csv
import json
import pathlib

from beta import config
from beta.temps1 import campagne as ca
from beta.temps1 import detecteurs as det

DOSSIER_RAPPORT = config.RACINE / "temps1"
NOMS_CIBLES = {"SPX": "S&P 500", "NDX": "Nasdaq-100"}


def _f(x, n=3) -> str:
    return "—" if x is None else f"{x:.{n}f}".replace(".", ",")


def _pct(x, n=1) -> str:
    return "—" if x is None else f"{100 * x:+.{n}f} %".replace(".", ",")


def _porte(x) -> str:
    return "n/a" if x is None else ("passe" if x else "échoue")


def charger_runs(synthese: dict) -> dict[tuple[str, str], dict]:
    runs = {}
    for rid in synthese["runs"]:
        r = json.loads((ca.DOSSIER / f"{rid}.json").read_text(encoding="utf-8"))
        runs[(r["detecteur"], r["cible"])] = r
    return runs


def lignes_csv(synthese: dict, runs: dict) -> list[dict]:
    """Une ligne par (detecteur x actif x periode), toutes les metriques, portes au labo."""
    portes = {(x["detecteur"], x["cible"]): x for x in synthese["labo"]}
    sortie = []
    for (detecteur, cible), r in runs.items():
        for periode, p in r["periodes"].items():
            m, t, b = (p["metriques"][k] for k in ("strategie", "temoin", "buy_and_hold"))
            fs, cap = p["survie"]["faux_signaux"], p["survie"]["captures"]
            nul = p["nulls"] or {"p": {}}
            retards = [e["retard_j"] for e in p["survie"]["episodes"] if e["retard_j"] is not None]
            g = portes.get((detecteur, cible), {}) if periode == "labo" else {}
            sortie.append({
                "detecteur": detecteur, "actif": cible, "periode": periode,
                "debut": p["periode"]["debut"], "fin": p["periode"]["fin"],
                "run_id": r["run_id"], "ulcer": m["ulcer"], "ulcer_temoin": t["ulcer"],
                "ulcer_sma200": runs[("SMA200", cible)]["periodes"][periode]["metriques"]
                ["strategie"]["ulcer"], "ulcer_buy_and_hold": b["ulcer"],
                "mdd": m["mdd"], "mdd_buy_and_hold": b["mdd"], "cagr": m["cagr"],
                "cagr_buy_and_hold": b["cagr"], "expo_moyenne": m["expo_moyenne"],
                "changements": m["changements_expo"], "protection_agregee": m["protection"],
                "n_episodes_20pct": p["periode"]["n_episodes"],
                "retard_moyen_j": (sum(retards) / len(retards)) if retards else None,
                "faux_signaux_passages": fs["n_passages"], "faux_signaux_n": fs["n_faux"],
                "faux_signaux_non_evaluables": fs["n_non_evaluables"],
                "faux_signaux_cout_cumule": fs["cout_cumule"],
                "capture_haussiere": cap["haussiere"], "capture_baissiere": cap["baissiere"],
                "p_circulaire": nul["p"].get("circulaire", {}).get("ulcer"),
                "p_segments": nul["p"].get("segments", {}).get("ulcer"),
                "p_retenue": nul.get("p_retenue"), "verdict_nulls": p["verdict"],
                "porte1": g.get("porte1"), "porte2": g.get("porte2"), "porte3": g.get("porte3"),
                "vol_365": m["vol"], "sharpe_365_rf0": m["sharpe"],
                "duree_sous_eau_max_j": m["duree_sous_eau_max_j"], "couts": m["couts"],
            })
    return sortie


def lignes_episodes(runs: dict) -> list[dict]:
    sortie = []
    for (detecteur, cible), r in runs.items():
        for periode, p in r["periodes"].items():
            for i, e in enumerate(p["survie"]["episodes"], 1):
                sortie.append({"actif": cible, "periode": periode, "episode": i,
                               "pic": e["date_pic"], "creux": e["date_creux"],
                               "retour": e["date_fin"], "perte_buy_and_hold": e["perte_b"],
                               "detecteur": detecteur, "perte_strategie": e["perte_s"],
                               "protection": e["protection"], "retard_j": e["retard_j"],
                               "part_subie_avant_defensif": e["part_subie"]})
    return sortie


def _ecrire_csv(lignes: list[dict], chemin: pathlib.Path) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lignes[0]))
        w.writeheader()
        w.writerows(lignes)


def _table(entete: list[str], lignes: list[list[str]]) -> str:
    out = ["| " + " | ".join(entete) + " |", "|" + "|".join("---" for _ in entete) + "|"]
    out += ["| " + " | ".join(x) + " |" for x in lignes]
    return "\n".join(out)


def ecrire(synthese: dict, ecarts: list[str]) -> pathlib.Path:
    """Le rapport markdown + `RAPPORT_ETAPE_A.csv` + `RAPPORT_ETAPE_A_episodes.csv`."""
    runs = charger_runs(synthese)
    # Les trous combles ne dependent que de la cible et de la periode : ceux du run SMA200.
    couverture_detail = {
        cible: {serie: {per: runs[("SMA200", cible)]["periodes"][per]["periode"]
                        ["trous_combles"][serie] for per in ("labo", "informative")}
                for serie in runs[("SMA200", cible)]["periodes"]["labo"]["periode"]
                ["trous_combles"]}
        for cible in ca.CIBLES}
    lignes = lignes_csv(synthese, runs)
    DOSSIER_RAPPORT.mkdir(parents=True, exist_ok=True)
    _ecrire_csv(lignes, DOSSIER_RAPPORT / "RAPPORT_ETAPE_A.csv")
    _ecrire_csv(lignes_episodes(runs), DOSSIER_RAPPORT / "RAPPORT_ETAPE_A_episodes.csv")
    par = {(x["detecteur"], x["actif"], x["periode"]): x for x in lignes}
    c = synthese["compteur"]
    don = synthese["donnees"]
    pit = don["pit_dexjpus"]
    un_run = next(iter(runs.values()))["periodes"]
    labo, info = (f"{un_run[x]['periode']['debut']} → {un_run[x]['periode']['fin']}"
                  for x in ("labo", "informative"))
    calcule = synthese["calcule_le"][:16].replace("T", " ")
    md = ["# Temps 1, étape A (laboratoire) — rapport T1A",
          "",
          f"Calculé le {calcule} UTC, code `{synthese['code']}`, "
          f"données `{don['empreinte']}` (dernière séance commune : {don['fin']}). "
          "Préenregistrement : `EXPERIMENTS.jsonl`, id `T1A`. Phase 1 : `temps1/DISCOVERY.md`. "
          "Détail complet : `temps1/RAPPORT_ETAPE_A.csv` (une ligne par détecteur × actif × "
          "période) et `temps1/RAPPORT_ETAPE_A_episodes.csv`.",
          "",
          "## 1. Compteur d'essais",
          "",
          _table(["avant T1A", "après le préenregistrement", "après les 14 couples (journalisés "
                  "avant le premier calcul)"],
                 [[str(c["avant_t1a"]), str(c["apres_preenregistrement"]), str(c["apres"])]]),
          "",
          "## 2. Couverture des données",
          "",
          _table(["série", "source", "début", "fin", "obs.", "trous > 5 séances"],
                 [[n, f"{x['source']} `{x['identifiant']}`"
                   + (f" (valeurs : {x['source_effective'].split(' ')[0]})"
                      if (x.get("source_effective") or x["source"]) != x["source"] else ""),
                   x["debut"] or "—", x["fin"] or "—",
                   str(x["n"]), str(x["trous_plus_de_5_seances"])]
                  for n, x in don["couverture"].items()]),
          "",
          "Séances de l'actif cible comblées par la dernière valeur connue (labo / informative) :",
          "",
          _table(["actif cible", "série", "séances comblées labo", "plus longue suite labo",
                  "séances comblées informative", "plus longue suite informative"],
                 [[NOMS_CIBLES[cible], serie, str(v["labo"]["seances_comblees"]),
                   str(v["labo"]["plus_longue_suite"]),
                   str(v["informative"]["seances_comblees"]),
                   str(v["informative"]["plus_longue_suite"])]
                  for cible, series in couverture_detail.items() for serie, v in series.items()]),
          "",
          f"DEXJPUS, point-in-time : mode **{pit['mode']}** — {pit['datees_alfred']} "
          f"observation(s) datée(s) par ALFRED, {pit['repli_2_jours_ouvres']} au décalage de "
          f"2 jours ouvrés (sur {pit['observations']}).",
          "",
          f"## 3. Tableau principal — période labo ({labo})",
          "",
          _table(["détecteur", "actif", "Ulcer", "Ulcer témoin", "Ulcer SMA200", "p retenue",
                  "porte 1", "porte 2", "porte 3"],
                 [[x["detecteur"], NOMS_CIBLES[x["actif"]], _f(x["ulcer"], 4),
                   _f(x["ulcer_temoin"], 4), _f(x["ulcer_sma200"], 4), _f(x["p_retenue"]),
                   _porte(x["porte1"]), _porte(x["porte2"]), _porte(x["porte3"])]
                  for d_ in det.DETECTEURS for cible in ca.CIBLES
                  for x in [par[(d_, cible, "labo")]]]),
          "",
          "n/a : porte non applicable — porte 3 pour SMA200 elle-même ; aucune porte pour les "
          "fenêtres de la bande (règle 2 : pas de choix de fenêtre).",
          "",
          "## 4. Bande SMA — les cinq fenêtres côte à côte (labo)",
          "",
          _table(["actif", "métrique"] + list(ca.BANDE),
                 [[NOMS_CIBLES[cible], nom] + [fmt(par[(b, cible, "labo")][cle]) for b in ca.BANDE]
                  for cible in ca.CIBLES
                  for nom, cle, fmt in (("Ulcer", "ulcer", lambda v: _f(v, 4)),
                                        ("Ulcer témoin", "ulcer_temoin", lambda v: _f(v, 4)),
                                        ("p retenue", "p_retenue", _f),
                                        ("MDD", "mdd", _pct), ("CAGR", "cagr", _pct),
                                        ("exposition moyenne", "expo_moyenne", _f),
                                        ("changements", "changements", str))]),
          "",
          f"## 5. Période informative ({info}) — déjà vu, ne décide rien",
          "",
          _table(["détecteur", "actif", "Ulcer", "Ulcer témoin", "Ulcer SMA200", "p retenue",
                  "MDD", "CAGR", "expo moy.", "épisodes ≥ 20 %"],
                 [[x["detecteur"], NOMS_CIBLES[x["actif"]], _f(x["ulcer"], 4),
                   _f(x["ulcer_temoin"], 4), _f(x["ulcer_sma200"], 4), _f(x["p_retenue"]),
                   _pct(x["mdd"]), _pct(x["cagr"]), _f(x["expo_moyenne"], 2),
                   str(x["n_episodes_20pct"])]
                  for d_ in det.DETECTEURS for cible in ca.CIBLES
                  for x in [par[(d_, cible, "informative")]]]),
          "",
          "## 6. Verdict mécanique",
          "",
          _verdict(synthese["verdict"]),
          "",
          "## 7. Écarts au prompt",
          "",
          *[f"- {e}" for e in ecarts],
          "",
          "## Annexe — métriques par détecteur × actif × période",
          "",
          _table(["détecteur", "actif", "période", "MDD", "protection", "retard moyen (j)",
                  "faux signaux (coût)", "capture ↑", "capture ↓", "CAGR", "expo", "chgts",
                  "p circ.", "p seg."],
                 [[x["detecteur"], x["actif"], x["periode"], _pct(x["mdd"]),
                   _f(x["protection_agregee"], 2), _f(x["retard_moyen_j"], 0),
                   f"{x['faux_signaux_n']}/{x['faux_signaux_passages']} "
                   f"({_pct(x['faux_signaux_cout_cumule'])})",
                   _f(x["capture_haussiere"], 2), _f(x["capture_baissiere"], 2),
                   _pct(x["cagr"]), _f(x["expo_moyenne"], 2), str(x["changements"]),
                   _f(x["p_circulaire"]), _f(x["p_segments"])]
                  for x in lignes]),
          "",
          "Buy and hold de référence (même période) :",
          "",
          _table(["actif", "période", "Ulcer", "MDD", "CAGR", "épisodes ≥ 20 %"],
                 [[NOMS_CIBLES[cible], periode, _f(x["ulcer_buy_and_hold"], 4),
                   _pct(x["mdd_buy_and_hold"]), _pct(x["cagr_buy_and_hold"]),
                   str(x["n_episodes_20pct"])]
                  for cible in ca.CIBLES for periode in ("labo", "informative")
                  for x in [par[("SMA200", cible, periode)]]]),
          "",
          "Protection par épisode de baisse ≥ 20 % : `temps1/RAPPORT_ETAPE_A_episodes.csv`.",
          ""]
    chemin = DOSSIER_RAPPORT / "RAPPORT_ETAPE_A.md"
    chemin.write_text("\n".join(md), encoding="utf-8")
    return chemin


def _verdict(v: dict) -> str:
    if v["verdict"] == "candidat retenu":
        return (f"**Candidat retenu : {', '.join(v['retenus'])}** (trois portes franchies sur "
                "les deux actifs).")
    if v["verdict"] == "SMA200 retenue":
        return ("**SMA200 retenue** : aucun candidat ne franchit les trois portes sur les deux "
                "actifs ; SMA200 franchit les portes 1 et 2 sur les deux actifs.")
    return ("**Aucun timing démontré** : aucun candidat ne franchit les trois portes sur les deux "
            "actifs, et SMA200 ne franchit pas les portes 1 et 2 sur les deux actifs.")
