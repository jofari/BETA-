"""Temps 1 - complement ETH et SOL : le rapport, ecrit par le programme a partir de la synthese
de la campagne. Les noms du Temps 1 s'ecrivent en entier (Jonas, 01/11/2026).

Aucune interpretation au-dela de la conclusion mecanique (regle 7 du preenregistrement). Sorties,
dans VC6_V1/temps1_complement_eth_sol/ : RAPPORT_COMPLEMENT.md, RAPPORT_COMPLEMENT.csv,
RAPPORT_COMPLEMENT_episodes.csv et RESUME_DISCORD.md.
"""

from __future__ import annotations

import csv
import logging

from beta.temps1_complement import campagne as ca
from beta.temps1_complement import regles as R

log = logging.getLogger("beta.temps1_complement.rapport")

LECTURE = {"reel": "réel", "non concluant": "non concluant",
           "hasard": "indistinguable du hasard"}
JUSTESSE, FIABILITE = "« Temps 1 – justesse »", "« Temps 1 – fiabilité »"


def _n(x, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def _p(x) -> str:
    return "—" if x is None else f"{x:.3f}".replace(".", ",")


def _pct(x) -> str:
    return "—" if x is None else f"{100 * x:.1f} %".replace(".", ",").replace("-", "−")


def _dist(q: dict) -> str:
    return f"{_n(q['mediane'])} [{_n(q['q05'])} ; {_n(q['q95'])}]"


def _table(entetes: list[str], lignes: list[list[str]]) -> list[str]:
    return (["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
            + ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes])


def conclusion(actif: str, a: dict) -> str:
    """La ligne de conclusion d'un actif, mecanique."""
    if a["statut"] == ca.INDECIDABLE:
        return (f"**Conclusion {actif} : indécidable** ({a['raison']}). Aucun verdict pour cet "
                "actif : arrêt, la suite revient à Jonas.")
    p = a["test_1"]["p_justesse"]
    seuil = _n(R.SEUIL_P_JUSTESSE)
    if a["statut"] == ca.RETENU:
        return (f"**Conclusion {actif} : retenu** (p_justesse {_p(p)} < {seuil}) : la poche "
                f"{actif} suit sa propre SMA 200.")
    return (f"**Conclusion {actif} : non retenu** (p_justesse {_p(p)} ≥ {seuil}) : {actif} "
            "suivra le régime de la SMA 200 du BTC.")


def _phases(a: dict) -> str:
    j = a.get("juge")
    if j is None:
        return "—"
    dans = [b for b in j["bears"] if b["dans_m"]]
    texte = (f"{len(dans)} bear(s) complet(s) dans la période mesurée"
             + ("" if not dans else " : " + " ; ".join(
                 f"{b['pic']} → {b['creux']} ({_pct(b['baisse'])})" for b in dans)))
    if j["bear_en_cours"]:
        e = j["bear_en_cours"]
        texte += (f". Bear en cours depuis le {e['pic']} ({_pct(e['baisse_a_ce_jour'])} au "
                  f"{R.FIN}), exclu")
    return texte + f". Rien n'est jugé avant le {j['debut_juge']}"


def _periode(a: dict) -> str:
    c = a["couverture"]
    texte = f"données {c['debut']} → {c['fin']}"
    if a.get("juge"):
        texte = f"juge depuis le {a['juge']['debut_juge']} ; " + texte
    if a.get("observe"):
        o = a["observe"]
        texte = (f"période mesurée {o['mesuree'][0]} → {o['mesuree'][1]} ({_n(o['annees'], 1)} "
                 f"ans) ; ") + texte
    return texte


def _fiabilite(a: dict) -> str:
    t1, t1b = a["test_1"], a["test_1_bis"]
    return (f"p_latence {_p(t1['p_latence'])} (test 1, {LECTURE[t1['lecture_latence']]}) ; "
            f"test 1 bis : p_justesse {_p(t1b['p_justesse'])} "
            f"({LECTURE[t1b['lecture_justesse']]}), p_latence {_p(t1b['p_latence'])} "
            f"({LECTURE[t1b['lecture_latence']]})")


def _section_resultat(s: dict) -> list[str]:
    md = ["## 1. Résultat par actif", "",
          f"Retenu si p_justesse du test 1 < {_n(R.SEUIL_P_JUSTESSE)} (règle 7 du "
          "préenregistrement) ; sinon, l'actif suivra le régime de la SMA 200 du BTC. "
          "p_latence et le test 1 bis sont rapportés : ils ne décident rien."]
    for actif, a in s["actifs"].items():
        md += ["", f"### {actif}", ""]
        if a["statut"] == ca.INDECIDABLE:
            md += _table(["p_justesse", "fiabilité", "phases baissières couvertes", "période"],
                         [["—", "—", _phases(a), _periode(a)]])
        else:
            t1 = a["test_1"]
            md += _table(["p_justesse", "fiabilité", "phases baissières couvertes", "période"],
                         [[f"{_p(t1['p_justesse'])} (test 1, "
                           f"{LECTURE[t1['lecture_justesse']]})", _fiabilite(a), _phases(a),
                           _periode(a)]])
        md += ["", conclusion(actif, a)]
    return md


def _section_donnees(s: dict) -> list[str]:
    c = s["compteur"]
    md = ["## 2. Empreintes et données", "",
          f"- **Code** : `{s['code']}`. Modules du {JUSTESSE} (commit "
          f"`{s['modules']['t1j']}`) et du {FIABILITE} (commit `{s['modules']['t1f']}`) "
          "réutilisés, vérifiés identiques octet pour octet.",
          f"- **Règles** : `{s['regles']}` ; préenregistrement `PREENREGISTREMENT.md` "
          f"`{s['preenregistrement']}` ; règles du {JUSTESSE} `{s['regles_t1j']}`, du "
          f"{FIABILITE} `{s['regles_t1f']}` ; registre : `EXPERIMENTS.jsonl`, diagnostic.",
          f"- **σ_S&P_ref** (juge du {JUSTESSE}) : {_pct(s['sigma_sp_ref'])} "
          f"({s['sigma_sp_ref']!r}), recalculé sur la copie figée du {JUSTESSE} et égal à la "
          "valeur de sa mesure.",
          f"- **Compteur** (aucun essai) : global {c['avant']['global']} → {c['apres']['global']}, "
          f"invest {c['avant']['invest']} → {c['apres']['invest']}, trading actif "
          f"{c['avant']['trading']} → {c['apres']['trading']}.",
          f"- **Tirages** : {s['tirages_par_test']} par actif et par test, graine {s['graine']}.",
          f"- **Empreinte des clôtures lues** : `{s['donnees']['empreinte']}` ; date de fin "
          f"figée : {s['donnees']['fin']}.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        cp, cv = s["donnees"]["copies"][actif], a["couverture"]
        lignes.append([actif, cp["serie"], f"`{cp['copie']}`", f"`{cp['sha256']}`", cv["debut"],
                       cv["fin"], cv["n"], cv["jours_manquants"]])
    md += _table(["actif", "série", "copie figée", "SHA-256 vérifié", "début", "fin", "clôtures",
                  "jours manquants"], lignes)
    return md


def _section_juge(s: dict) -> list[str]:
    md = ["## 3. Les bears du juge", "",
          f"Juge principal du {JUSTESSE} : baisse de référence 20 %, σ de l'actif sur les 2 "
          "années civiles avant chaque trimestre (× √252), σ_S&P_ref constante. Il démarre au "
          "premier trimestre précédé de 2 ans de données. Un bear n'est mesuré que si ses deux "
          "bornes sont dans la période mesurée [premier pivot, dernier pivot[."]
    for actif, a in s["actifs"].items():
        j = a.get("juge")
        md += ["", f"### {actif}", ""]
        if j is None:
            md.append("*Juge non calculé (épreuve de causalité ratée).*")
            continue
        md.append(f"Juge à partir du {j['debut_juge']} ; θ_baisse de {_pct(j['theta_baisse'][0])} "
                  f"à {_pct(j['theta_baisse'][1])}, θ_hausse de {_pct(j['theta_hausse'][0])} à "
                  f"{_pct(j['theta_hausse'][1])}.")
        if j["dernier_pivot"]:
            md.append(f"Dernier pivot : {j['dernier_pivot']['type']} du "
                      f"{j['dernier_pivot']['date']} ; le cycle qui suit est en cours, exclu.")
        md.append("")
        if j["bears"]:
            md += _table(["pic", "creux", "baisse", "dans la période mesurée"],
                         [[b["pic"], b["creux"], _pct(b["baisse"]),
                           "oui" if b["dans_m"] else "non"] for b in j["bears"]])
        else:
            md.append("*Aucun bear complet.*")
        if j["bear_en_cours"]:
            e = j["bear_en_cours"]
            md += ["", f"Bear en cours depuis le pic du {e['pic']} "
                       f"({_pct(e['baisse_a_ce_jour'])} à la dernière date), exclu."]
    return md


def _section_mesures(s: dict) -> list[str]:
    md = [f"## 4. Mesures observées de la SMA 200 (fonctions du {JUSTESSE})", "",
          "f_entrée : 0 = bascule bear au pic, 1 = au creux ; un raté compte 1. f_sortie : 0 = "
          "bascule bull au creux, 1 = au pic suivant ; un raté compte 1.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        o = a.get("observe")
        if o is None:
            lignes.append([actif] + ["—"] * 8)
            continue
        lignes.append([actif, _n(o["f_entree_mediane"]), _n(o["f_entree_pire"]),
                       f"{o['rates_entree']} / {o['n_bears']}", _n(o["fausses_alertes_an"]),
                       _n(o["justesse"]), _n(o["f_sortie_mediane"]), _n(o["bascules_an"]),
                       f"{o['rates_sortie']} / {o['n_bulls']}"])
    md += _table(["actif", "médiane f_entrée", "pire cas", "ratés / bears", "fausses alertes / an",
                  "justesse", "médiane f_sortie", "bascules / an", "ratés de sortie / bulls"],
                 lignes)
    for actif, a in s["actifs"].items():
        o = a.get("observe")
        if o is None:
            continue
        md += ["", f"### {actif} — entrées", ""]
        md += _table(["pic", "creux", "baisse", "f_entrée", "bascule bear", "retard"],
                     [[e["pic"], e["creux"], _pct(e["baisse"]),
                       "raté (1)" if e["rate"] else _n(e["f_entree"]), e["bascule"] or "—",
                       "—" if e["rate"] else f"{e['retard_jours']} j"] for e in o["entrees"]])
        md += ["", f"### {actif} — sorties", ""]
        if o["sorties"]:
            md += _table(["creux", "pic suivant", "f_sortie", "bascule bull"],
                         [[e["creux"], e["pic"], "raté (1)" if e["rate"] else _n(e["f_sortie"]),
                           e["bascule"] or "—"] for e in o["sorties"]])
        else:
            md.append("*Aucun bull complet dans la période mesurée.*")
    return md


def _section_tests(s: dict) -> list[str]:
    md = [f"## 5. Tests contre le hasard de même agitation (fonctions du {FIABILITE})", "",
          "Test 1 (décide) : la suite des états est gardée, les durées sont permutées entre "
          "épisodes du même état. Test 1 bis (rapporté) : décalage circulaire dans [90, N − 90]. "
          "p_latence = part des tirages de médiane f_entrée ≤ observée ; p_justesse = part des "
          "tirages de justesse ≥ observée. Lecture D4 : p < 0,05 réel ; 0,05 ≤ p < 0,20 non "
          "concluant ; p ≥ 0,20 indistinguable du hasard.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        if a["statut"] == ca.INDECIDABLE:
            continue
        for cle, nom in (("test_1", "1"), ("test_1_bis", "1 bis")):
            r = a[cle]
            lignes.append([actif, nom, _n(r["f_entree_observee"]), _dist(r["f_entree_aleatoire"]),
                           _p(r["p_latence"]), _n(r["justesse_observee"]),
                           _dist(r["justesse_aleatoire"]), _p(r["p_justesse"]),
                           f"{LECTURE[r['lecture_latence']]} / {LECTURE[r['lecture_justesse']]}",
                           f"{_n(r['fausses_alertes_observees'])} ; "
                           f"{_n(r['fausses_alertes_aleatoires']['mediane'])}"])
    md += _table(["actif", "test", "f_entrée observée", "f_entrée aléatoire, médiane [5 % ; 95 %]",
                  "p_latence", "justesse observée", "justesse aléatoire, médiane [5 % ; 95 %]",
                  "p_justesse", "lecture D4 (latence / justesse)",
                  "fausses alertes / an : observées, aléatoires (médiane)"], lignes)
    plages = [f"{a} {v['plage']['debut']} → {v['plage']['fin']} ({v['plage']['seances']} séances)"
              for a, v in s["actifs"].items() if v.get("plage")]
    if plages:
        md += ["", "Plages des tirages (périodes mesurées) : " + " ; ".join(plages) + "."]
    return md


def _cas(e: dict) -> str:
    if e["cas"] == "en bear avant le pic":
        return f"bear depuis {e['seances_avant']} s."
    if e["cas"] == "bascule le jour du pic":
        return "bascule au pic"
    return "non"


def _section_test2(s: dict) -> list[str]:
    md = ["## 6. Test 2 — diagnostic des f = 0 (rapporté, ne décide rien)", "",
          "État de la SMA 200 au jour du pic de chaque bear du juge. La f_entrée diagnostic ignore "
          "les épisodes bear commencés plus de 21 séances avant le pic (raté = 1). Cette variante "
          "n'est pas une règle.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        if a["statut"] == ca.INDECIDABLE:
            continue
        for e in a["test_2"]["episodes"]:
            lignes.append([actif, e["pic"], e["creux"], _cas(e), _n(e["f_entree"]),
                           _n(e["f_diagnostic"])])
    md += _table(["actif", "pic", "creux", "en bear au pic", "f_entrée", "f diagnostic"], lignes)
    return md


def _section_causalite(s: dict) -> list[str]:
    md = ["## 7. Épreuve de causalité", "",
          "SMA 200 recalculée avec les seules clôtures connues à chaque date de coupure du "
          f"{JUSTESSE} postérieure au début de l'actif, comparée au signal calculé sur tout "
          "l'historique."]
    for actif, a in s["actifs"].items():
        md.append(f"- {actif} : " + ("aucun écart." if not a.get("causalite")
                                     else f"ÉCARTS aux coupures {a['causalite']}."))
    return md


def _section_ecarts() -> list[str]:
    return ["## 8. Écarts au prompt et leurs raisons", "",
            "- **Données** : ETH et SOL n'ont, dans BETA et DS1, qu'une clôture journalière : "
            "celle du perpétuel Binance USDT-M (inventaire de l'étape A). « Début disponible » = "
            f"la cotation du perpétuel. Le BTC du {JUSTESSE} était jugé au comptant "
            "(Bitstamp).",
            "- **Fiabilité** : p_latence et sa lecture D4, par actif. Le verdict de fiabilité du "
            f"{FIABILITE} (témoin actions ET or) ne se transpose pas à un actif seul "
            "(application 8).",
            "- **Variantes du juge** (15 %, 25 %, σ unique) : non calculées (application 13).",
            f"- **Annualisation** : celle des règles figées du {JUSTESSE} (√252), y compris pour "
            f"des actifs cotés 7 j / 7, comme le BTC du {JUSTESSE}."]


def markdown(s: dict) -> str:
    md = ["# Temps 1 – complément ETH et SOL", "",
          f"Calculé le {s['calcule_le']} UTC. Rapport écrit par `scripts/temps1_complement.py`, "
          f"sans interprétation au-delà de la conclusion mécanique. Les verdicts du {JUSTESSE} "
          f"et du {FIABILITE} ne sont pas modifiés. Préenregistrement : `PREENREGISTREMENT.md` "
          "(même dossier).", ""]
    for section in (_section_resultat(s), _section_donnees(s), _section_juge(s),
                    _section_mesures(s), _section_tests(s), _section_test2(s),
                    _section_causalite(s), _section_ecarts()):
        md += section + [""]
    return "\n".join(md)


def csvs(s: dict) -> None:
    with open(ca.SORTIE / "RAPPORT_COMPLEMENT.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["actif", "statut", "p_justesse_test1", "lecture_justesse_test1",
                    "p_latence_test1", "lecture_latence_test1", "p_justesse_test1bis",
                    "p_latence_test1bis", "justesse_observee", "f_entree_mediane_observee",
                    "bears_complets_mesures", "debut_juge", "mesuree_debut", "mesuree_fin",
                    "annees", "donnees_debut", "donnees_fin", "raison"])
        for actif, a in s["actifs"].items():
            t1, t1b, o = a.get("test_1") or {}, a.get("test_1_bis") or {}, a.get("observe") or {}
            w.writerow([actif, a["statut"], t1.get("p_justesse"), t1.get("lecture_justesse"),
                        t1.get("p_latence"), t1.get("lecture_latence"), t1b.get("p_justesse"),
                        t1b.get("p_latence"), o.get("justesse"), o.get("f_entree_mediane"),
                        o.get("n_bears"), (a.get("juge") or {}).get("debut_juge"),
                        (o.get("mesuree") or [None, None])[0],
                        (o.get("mesuree") or [None, None])[1], o.get("annees"),
                        a["couverture"]["debut"], a["couverture"]["fin"], a.get("raison")])
    with open(ca.SORTIE / "RAPPORT_COMPLEMENT_episodes.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["actif", "type", "debut", "fin", "baisse", "dans_periode_mesuree", "f",
                    "rate", "bascule", "retard_jours"])
        for actif, a in s["actifs"].items():
            o = a.get("observe") or {}
            mesures = {(e["pic"], e["creux"]): e for e in o.get("entrees", [])}
            for b in (a.get("juge") or {}).get("bears", []):
                e = mesures.get((b["pic"], b["creux"]), {})
                w.writerow([actif, "bear", b["pic"], b["creux"], b["baisse"], b["dans_m"],
                            e.get("f_entree"), e.get("rate"), e.get("bascule"),
                            e.get("retard_jours")])
            for e in o.get("sorties", []):
                w.writerow([actif, "bull", e["creux"], e["pic"], None, True, e["f_sortie"],
                            e["rate"], e["bascule"], None])


def resume(s: dict) -> str:
    """Message court du salon BETA. Pastille mecanique : verte si tous les actifs sont retenus,
    orange si un actif est indecidable, jaune sinon."""
    statuts = [a["statut"] for a in s["actifs"].values()]
    pastille = ("🟢" if all(x == ca.RETENU for x in statuts)
                else "🟠" if ca.INDECIDABLE in statuts else "🟡")
    c = s["compteur"]
    md = [f"# {pastille} Temps 1 – complément ETH et SOL — rapport du programme — "
          f"{s['calcule_le'][:10]}", ""]
    md += ["- " + conclusion(actif, a) for actif, a in s["actifs"].items()]
    md += ["", f"Règle : retenu si p_justesse (test 1) < {_n(R.SEUIL_P_JUSTESSE)} ; sinon la SMA "
               f"200 du BTC. Diagnostic, aucun essai : global {c['apres']['global']}, invest "
               f"{c['apres']['invest']} (inchangés).", "",
           "Fichiers : `VC6_V1/temps1_complement_eth_sol/RAPPORT_COMPLEMENT.md` (joint) et 2 CSV. "
           f"Code `{s['code']}`, règles `{s['regles']}`, données "
           f"`{s['donnees']['empreinte']}`.", "",
           "Message écrit par le programme (`beta/temps1_complement/rapport.py`), sans "
           "interprétation."]
    return "\n".join(md) + "\n"


def ecrire(s: dict) -> None:
    ca.SORTIE.mkdir(parents=True, exist_ok=True)
    (ca.SORTIE / "RAPPORT_COMPLEMENT.md").write_text(markdown(s), encoding="utf-8")
    csvs(s)
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.SORTIE / "RAPPORT_COMPLEMENT.md")
