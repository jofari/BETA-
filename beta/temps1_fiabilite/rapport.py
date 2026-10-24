"""T1F : le rapport, ecrit par le programme a partir de la synthese de la campagne.

Aucune interpretation au-dela du verdict mecanique (prompt du 24/10). Sorties :
temps1_fiabilite/RAPPORT_FIABILITE.md, RAPPORT_FIABILITE_tests.csv,
RAPPORT_FIABILITE_episodes.csv et RESUME_DISCORD.md.
"""

from __future__ import annotations

import csv
import logging

from beta.temps1_fiabilite import campagne as ca
from beta.temps1_fiabilite import regles as R

log = logging.getLogger("beta.temps1_fiabilite.rapport")

NOMS = {"SPX": "S&P 500", "NDX": "Nasdaq-100", "TEMOIN": "témoin actions", "OR": "or (LBMA PM)",
        "BTC": "BTC (DS1)"}
LECTURE = {"reel": "réel", "non concluant": "non concluant",
           "hasard": "indistinguable du hasard"}
VERDICT = {"fiable": "fiable", "du a l'agitation": "dû à l'agitation",
           "non concluant": "non concluant"}
ORDRE = ("SPX", "NDX", "TEMOIN", "OR", "BTC")


def _n(x, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def _p(x) -> str:
    return "—" if x is None else f"{x:.3f}".replace(".", ",")


def _dist(q: dict) -> str:
    return f"{_n(q['mediane'])} [{_n(q['q05'])} ; {_n(q['q95'])}]"


def _table(entetes: list[str], lignes: list[list[str]]) -> list[str]:
    return (["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
            + ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes])


ENTETES = ["détecteur", "actif", "f_entrée observée", "f_entrée aléatoire, médiane [5 % ; 95 %]",
           "p_latence", "justesse observée", "justesse aléatoire, médiane [5 % ; 95 %]",
           "p_justesse", "lecture D4 (latence / justesse)",
           "fausses alertes / an : observées, aléatoires (médiane)"]


def _tableau_test(t: dict) -> list[str]:
    lignes = []
    for nom in R.DETECTEURS:
        for actif in ORDRE:
            r = t[nom][actif]
            lignes.append([nom, NOMS[actif], _n(r["f_entree_observee"]),
                           _dist(r["f_entree_aleatoire"]), _p(r["p_latence"]),
                           _n(r["justesse_observee"]), _dist(r["justesse_aleatoire"]),
                           _p(r["p_justesse"]),
                           f"{LECTURE[r['lecture_latence']]} / {LECTURE[r['lecture_justesse']]}",
                           f"{_n(r['fausses_alertes_observees'])} ; "
                           f"{_n(r['fausses_alertes_aleatoires']['mediane'])}"])
    return _table(ENTETES, lignes)


def _cas(e: dict) -> str:
    if e["cas"] == "en bear avant le pic":
        return f"bear depuis {e['seances_avant']} s."
    if e["cas"] == "bascule le jour du pic":
        return "bascule au pic"
    return "non"


def _section_test2(s: dict) -> list[str]:
    t2 = s["test_2"]
    md = ["## 4. Test 2 — diagnostic des f = 0 (rapporté, ne décide rien)", "",
          "État du détecteur au jour du pic de chaque bear du juge, en trois cas (« bear depuis "
          "n s. » : en bear depuis n ≥ 1 séance avant le pic ; « bascule au pic » : bascule bear "
          "le jour même ; « non » : pas en bear au pic). La f_entrée diagnostic ignore les "
          f"épisodes bear commencés plus de {R.FENETRE_DIAGNOSTIC} séances avant le pic (raté = "
          "1, comme A). Cette variante n'est pas une règle."]
    for actif in R.ACTIFS:
        ref = t2[R.DETECTEURS[0]][actif]["episodes"]
        lignes = []
        for i, e in enumerate(ref):
            ligne = [e["pic"], e["creux"]]
            for nom in R.DETECTEURS:
                x = t2[nom][actif]["episodes"][i]
                ligne.append(f"{_cas(x)} · f {_n(x['f_entree'])} · diag {_n(x['f_diagnostic'])}")
            lignes.append(ligne)
        md += ["", f"### {NOMS[actif]}", ""]
        md += _table(["pic", "creux", *R.DETECTEURS], lignes)
    md += ["", "### Synthèse", ""]
    lignes = []
    for nom in R.DETECTEURS:
        for actif in R.ACTIFS:
            r = t2[nom][actif]["resume"]
            parts = r["parts_f0"]
            lignes.append([nom, NOMS[actif], str(r["n_bears"]), str(r["n_f0"]),
                           *("—" if parts[c] is None else f"{100 * parts[c]:.0f} %".replace(
                               ".", ",") for c in ("en bear avant le pic",
                                                   "bascule le jour du pic",
                                                   "pas en bear au pic")),
                           _n(r["f_entree_mediane"]), _n(r["f_diagnostic_mediane"]),
                           str(r["rates_diagnostic"])])
    md += _table(["détecteur", "actif", "bears", "f = 0", "f = 0 : bear avant le pic",
                  "f = 0 : bascule au pic", "f = 0 : pas en bear", "médiane f_entrée",
                  "médiane f diagnostic", "ratés diagnostic"], lignes)
    return md


ECARTS = [
    "**Permutation (test 1)** : le mélange brut de l'ordre des épisodes ne conserve pas les "
    "bascules, car deux épisodes voisins de même état fusionnent. Jonas a tranché "
    "(clarification 1) : la suite des états est gardée et les durées sont mélangées entre "
    "épisodes du même état.",
    "**Plage** : la permutation et le décalage portent sur la période mesurée de T1J "
    "(clarification 2). Hors de cette plage, le signal reste l'observé.",
    "**Témoin** : il est calculé tirage par tirage, avec la moyenne S&P 500 / Nasdaq-100 du même "
    "tirage (clarification 3).",
    "**Décalage (test 1 bis)** : en séances de l'actif, tiré uniformément dans [90, N − 90] "
    "(clarification 4).",
    "**Compteur** : une marque `diagnostic=True`, ignorée par le compteur, a été ajoutée au "
    "protocole pour concilier « aucun essai » et « journalisé dans `EXPERIMENTS.jsonl` ». Aucun "
    "run n'est journalisé.",
    "**Test 2** : « déjà en bear le jour du pic » est rapporté en trois cas, sans en retenir un "
    "seul.",
    "**Données** : celles de T1J, chaque série étant coupée à sa date de fin dans T1J. "
    "L'empreinte est vérifiée, comme les bears et les mesures observées de chaque couple.",
    "**Graine 0** : appliquée par couple détecteur × actif et par test. p n'a pas de correction "
    "+1 : c'est la part brute des 1 000 tirages, comme écrit. Les quantiles sont linéaires "
    "(numpy).",
    "**Fausses alertes** : calculées pour chaque tirage comme demandé, et rapportées dans une "
    "colonne en plus.",
]


def markdown(s: dict) -> str:
    c = s["compteur"]
    md = ["# Temps 1 — fiabilité du test de justesse (T1F)", "",
          f"Calculé le {s['calcule_le']} UTC. Rapport écrit par `scripts/temps1_fiabilite.py`, "
          "sans interprétation au-delà du verdict mécanique. Le verdict de T1J n'est pas modifié.",
          "", "## 1. Empreintes", "",
          f"- **Code** : `{s['code']}`. Modules de T1J réutilisés, vérifiés identiques au commit "
          f"`{s['modules_t1j']['commit']}` : {', '.join(R.MODULES_JUSTESSE)}.",
          f"- **Données** : `{s['donnees']}`, celles de T1J. Règles de T1J : `{s['regles_t1j']}`.",
          f"- **Préenregistrement** : `temps1_fiabilite/PREENREGISTREMENT.md` "
          f"`{s['preenregistrement']}` ; règles `{s['regles']}` ; registre : `EXPERIMENTS.jsonl`, "
          f"id `{R.ID_EXP}`, diagnostic.",
          f"- **Compteur** (aucun essai) : global {c['avant']['global']} → {c['apres']['global']}, "
          f"invest {c['avant']['invest']} → {c['apres']['invest']}, trading actif "
          f"{c['avant']['trading']} → {c['apres']['trading']}.",
          f"- **Tirages** : {R.N_TIRAGES} par couple et par test, graine {R.GRAINE}. Périodes "
          "mesurées (celles de T1J) : "
          + " ; ".join(f"{NOMS[a]} {p['debut']} → {p['fin']} ({p['seances']} séances)"
                       for a, p in s["plages"].items()) + ".", "",
          "## 2. Test 1 — permutation des durées par état (verdict de fiabilité)", "",
          "p_latence = part des tirages dont la médiane de f_entrée est ≤ celle du détecteur "
          "observé ; p_justesse = part des tirages dont la justesse est ≥ celle du détecteur "
          "observé. Lecture D4 : p < 0,05 réel ; 0,05 ≤ p < 0,20 non concluant ; p ≥ 0,20 "
          "indistinguable du hasard.", ""]
    md += _tableau_test(s["tests"]["test_1"])
    md += ["", "## 3. Test 1 bis — décalage circulaire (robustesse, rapporté)", ""]
    md += _tableau_test(s["tests"]["test_1_bis"])
    md += [""] + _section_test2(s)
    md += ["", "## 5. Verdict de fiabilité mécanique", "",
           "Fiable : p_latence < 0,05 au test 1 sur le témoin actions ET sur l'or. Dû à "
           "l'agitation : l'un des deux ≥ 0,20. Sinon non concluant. BTC rapporté : il ne "
           "valide rien seul.", ""]
    md += _table(["candidat", "p_latence témoin", "p_latence or", "verdict",
                  "BTC : p_latence (lecture D4)"],
                 [[x, _p(v["p_temoin"]), _p(v["p_or"]), f"**{VERDICT[v['verdict']]}**",
                   f"{_p(v['btc']['p_latence'])} ({LECTURE[v['btc']['lecture']]})"]
                  for x, v in s["verdict"].items()])
    md += ["", "## 6. Écarts au prompt", ""] + [f"- {e}" for e in ECARTS]
    return "\n".join(md) + "\n"


def csvs(s: dict) -> None:
    lignes = []
    for test, t in s["tests"].items():
        for nom in R.DETECTEURS:
            for actif in ORDRE:
                r = t[nom][actif]
                lignes.append([test, nom, actif, r["f_entree_observee"],
                               r["f_entree_aleatoire"]["mediane"], r["f_entree_aleatoire"]["q05"],
                               r["f_entree_aleatoire"]["q95"], r["p_latence"],
                               r["lecture_latence"], r["justesse_observee"],
                               r["justesse_aleatoire"]["mediane"], r["justesse_aleatoire"]["q05"],
                               r["justesse_aleatoire"]["q95"], r["p_justesse"],
                               r["lecture_justesse"], r["fausses_alertes_observees"],
                               r["fausses_alertes_aleatoires"]["mediane"]])
    with (ca.SORTIE / "RAPPORT_FIABILITE_tests.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["test", "detecteur", "actif", "f_entree_observee", "f_aleatoire_mediane",
                    "f_aleatoire_q05", "f_aleatoire_q95", "p_latence", "lecture_latence",
                    "justesse_observee", "justesse_aleatoire_mediane", "justesse_aleatoire_q05",
                    "justesse_aleatoire_q95", "p_justesse", "lecture_justesse",
                    "fausses_alertes_observees", "fausses_alertes_aleatoires_mediane"])
        w.writerows(lignes)
    with (ca.SORTIE / "RAPPORT_FIABILITE_episodes.csv").open("w", encoding="utf-8",
                                                             newline="") as f:
        w = csv.writer(f)
        w.writerow(["detecteur", "actif", "pic", "creux", "cas", "seances_avant", "f_entree",
                    "f_diagnostic", "rate_diagnostic"])
        for nom in R.DETECTEURS:
            for actif in R.ACTIFS:
                for e in s["test_2"][nom][actif]["episodes"]:
                    w.writerow([nom, actif, e["pic"], e["creux"], e["cas"], e["seances_avant"],
                                e["f_entree"], e["f_diagnostic"], e["rate_diagnostic"]])


def resume(s: dict) -> str:
    """Message court du salon BETA. Pastille mecanique : verte si tout est fiable, orange si un
    candidat est du a l'agitation, jaune sinon."""
    vs = [v["verdict"] for v in s["verdict"].values()]
    pastille = ("🟢" if all(v == "fiable" for v in vs)
                else "🟠" if any(v == "du a l'agitation" for v in vs) else "🟡")
    md = [f"# {pastille} Fiabilité du test de justesse T1F — rapport du programme — "
          f"{s['calcule_le'][:10]}", ""]
    for x, v in s["verdict"].items():
        md.append(f"- **{x} : {VERDICT[v['verdict']]}** (p_latence témoin {_p(v['p_temoin'])}, "
                  f"or {_p(v['p_or'])} ; BTC {_p(v['btc']['p_latence'])})")
    c = s["compteur"]
    md += ["", f"Diagnostic, aucun essai : global {c['apres']['global']}, invest "
           f"{c['apres']['invest']} (inchangés). Verdict de T1J non modifié.", "",
           "Fichiers : `temps1_fiabilite/RAPPORT_FIABILITE.md` (joint) et 2 CSV. Code "
           f"`{s['code']}`, données `{s['donnees']}`.", "",
           "Message écrit par le programme (`beta/temps1_fiabilite/rapport.py`), sans "
           "interprétation."]
    return "\n".join(md) + "\n"


def ecrire(s: dict) -> None:
    ca.SORTIE.mkdir(parents=True, exist_ok=True)
    (ca.SORTIE / "RAPPORT_FIABILITE.md").write_text(markdown(s), encoding="utf-8")
    csvs(s)
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.SORTIE / "RAPPORT_FIABILITE.md")
