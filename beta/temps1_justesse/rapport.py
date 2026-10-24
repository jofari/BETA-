"""T1J : le rapport, ecrit par le programme a partir de la synthese de la campagne.

Rien n'y est interprete au-dela du verdict mecanique (prompt du 24/10). La section
« Clarifications avant calcul », figee au preenregistrement, est recopiee telle quelle en tete :
tout ce qui suit le marqueur est regenere a chaque ecriture. Sorties : RAPPORT_JUSTESSE.md, les
tableaux en CSV, et RESUME_DISCORD.md (le message court envoye sur le salon BETA).
"""

from __future__ import annotations

import csv
import logging

from beta.temps1_justesse import campagne as ca
from beta.temps1_justesse import regles as R
from beta.temps1_justesse import verdict as vd

log = logging.getLogger("beta.temps1_justesse.rapport")

NOMS_ACTIFS = {"SPX": "S&P 500", "NDX": "Nasdaq-100", "OR": "or (LBMA PM)", "BTC": "BTC (DS1)",
               "TEMOIN": "témoin actions"}
NOMS_VARIANTES = {"baisse_15": "baisse de référence 15 %", "baisse_25": "baisse de référence 25 %",
                  "sigma_unique": "σ unique"}


# ----------------------------------------------------------------------------- formats

def _n(x, d: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{d}f}".replace(".", ",")


def _pct(x, d: int = 1) -> str:
    return "—" if x is None else f"{100 * x:+.{d}f} %".replace(".", ",")


def _pc(x, d: int = 1) -> str:
    return "—" if x is None else f"{100 * x:.{d}f} %".replace(".", ",")


def _table(entetes: list[str], lignes: list[list[str]]) -> list[str]:
    return (["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
            + ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes])


def _rel(tables: dict, nom: str, actif: str) -> str:
    if nom == R.REFERENCE:
        return "référence"
    x, ref = tables[nom].get(actif), tables[R.REFERENCE].get(actif)
    if not x or not ref or "erreur" in x or "erreur" in ref:
        return "—"
    return {"domine SMA200": "domine SMA200", "domine par SMA200": "dominé par SMA200",
            "aucune domination": "aucune domination"}[vd.relation(x, ref)]


def _compte(x) -> str:
    """Un nombre de rates ou d'episodes : entier, ou moyenne a une decimale pour le temoin."""
    if x is None:
        return "—"
    return str(int(x)) if float(x).is_integer() else _n(x, 1)


def _cellules(m: dict | None) -> list[str]:
    if not m or "erreur" in m:
        return ["non mesurable"] + ["—"] * 7
    return [_n(m["f_entree_mediane"]), _n(m["f_entree_pire"]),
            f"{_compte(m['rates_entree'])} / {_compte(m['n_bears'])}",
            _n(m["fausses_alertes_an"]), _n(m["justesse"]), _n(m["f_sortie_mediane"]),
            _n(m["bascules_an"]), f"{_compte(m['rates_sortie'])} / {_compte(m['n_bulls'])}"]


ENTETES = ["détecteur", "médiane f_entrée", "pire cas", "ratés / bears", "fausses alertes / an",
           "justesse", "médiane f_sortie", "bascules / an", "ratés de sortie / bulls",
           "face à SMA200"]


def _tableau_principal(tables: dict, noms: tuple, actif: str) -> list[str]:
    lignes = []
    for nom in noms:
        if nom not in tables:
            continue
        lignes.append([nom, *_cellules(tables[nom].get(actif)), _rel(tables, nom, actif)])
    return _table(ENTETES, lignes)


def _episodes(tables: dict, noms: tuple, actif: str) -> list[str]:
    ref = tables[noms[0]].get(actif)
    if not ref or "erreur" in ref:
        return ["*Non mesurable.*"]
    entetes = ["pic", "creux", "baisse"] + list(noms)
    lignes = []
    for i, e in enumerate(ref["entrees"]):
        ligne = [e["pic"], e["creux"], _pct(e["baisse"])]
        for nom in noms:
            x = tables[nom][actif]["entrees"][i]
            ligne.append("raté (1)" if x["rate"] else
                         f"{_n(x['f_entree'])} ({x['retard_jours']} j, {x['retard_seances']} s.)")
        lignes.append(ligne)
    return _table(entetes, lignes)


def _sorties(tables: dict, noms: tuple, actif: str) -> list[str]:
    ref = tables[noms[0]].get(actif)
    if not ref or "erreur" in ref or not ref["sorties"]:
        return ["*Aucune sortie mesurable (pas de bull complet dans la période mesurée).*"]
    entetes = ["creux", "pic suivant"] + list(noms)
    lignes = []
    for i, e in enumerate(ref["sorties"]):
        ligne = [e["creux"], e["pic"]]
        for nom in noms:
            x = tables[nom][actif]["sorties"][i]
            ligne.append("raté (1)" if x["rate"] else _n(x["f_sortie"]))
        lignes.append(ligne)
    return _table(entetes, lignes)


# ----------------------------------------------------------------------------- sections

def _section_compteur(s: dict) -> list[str]:
    c = s["compteur"]
    a, b = c["avant_journalisation"], c["apres_journalisation"]
    pre = c.get("preenregistrement") or {}
    md = ["## 1. Compteur d'essais", "",
          f"- **Valeur au gel du préenregistrement (22/10/2026)** : compteur global "
          f"**{c['gel_global_22_10']}**. Elle est rapportée telle quelle, sans être remplacée.",
          f"- **Compteur global** (`experiences.compteur_total`, trading + invest) : "
          f"{pre.get('global_avant')} avant T1J, {a['global']} au lancement (T1J préenregistrée, "
          f"sans mesure), **{b['global']} après la journalisation**.",
          f"- **Compteur invest** (`experiences.compteur(famille=\"invest\")`, celui des tests de "
          f"détecteurs, incrémenté) : {pre.get('invest_avant')} avant T1J, {a['invest']} au "
          f"lancement, **{b['invest']} après la journalisation**.",
          f"- Compteur trading actif : {b['trading']}, inchangé.",
          f"- **Essais du verdict** : "
          f"{c['calcul'].replace(' x ', ' × ').replace('detecteurs', 'détecteurs')}, "
          f"journalisés avant le premier calcul ({c['nouveaux']} nouveaux à ce lancement).",
          f"- **Essais informatifs** (ligne à part, aucun compteur) : bande SMA "
          f"{c['informatifs']['bande']} + variantes σ 21 et σ 126 de C1_V1 "
          f"{c['informatifs']['variantes_c1_v1']} = **{c['informatifs']['total']}**. Les "
          f"variantes du juge sont rapportées, mais ne sont pas des essais.", "",
          "Couples du verdict et leurs identifiants de run (`RUNS.jsonl`) :", ""]
    md += _table(["détecteur", "actif", "run"],
                 [[x["detecteur"], NOMS_ACTIFS[x["actif"]], f"`{x['run_id']}`"]
                  for x in c["couples"]])
    return md


def _section_couverture(s: dict) -> list[str]:
    cov = s["donnees"]["couverture"]
    lignes = []
    for nom in ("SPX", "NDX", "OR", "BTC", "VIX", "USDJPY"):
        x = cov[nom]
        comb = x.get("comblees_seances_us")
        comblees = "—" if not comb else f"{comb['labo_avec_prechauffe']} / {comb['informative']}"
        lignes.append([nom, f"`{x['serie']}`", x["debut"], x["fin"],
                       f"{x['n']:,}".replace(",", " "), str(x["trous_plus_de_5_seances"]),
                       comblees])
    md = ["## 2. Couverture des données", ""]
    md += _table(["série", "série `beta.marches`", "début", "fin", "observations",
                  "trous > 5 séances",
                  "séances US comblées (labo + préchauffe / 2024 → fin)"], lignes)
    md += ["", f"Empreinte des données : `{s['donnees']['empreinte']}`. Les séances US comblées "
           "sont celles où la série n'a pas d'observation du jour : la couche 1 y lit la dernière "
           "valeur connue. Le BTC, le S&P 500, le Nasdaq-100 et l'or sont jugés sur leurs propres "
           "dates, sans comblement.", "",
           "**USD/JPY (clarification E)** : " + s["donnees"]["dexjpus_publication"] + "."]
    return md


def _section_juge(res: dict) -> list[str]:
    md = ["## 3. Les bears du juge", "",
          f"σ_S&P_ref (S&P 500, labo 1991-2023, annualisée) = **{_pc(res['sigma_sp_ref'], 2)}**. "
          "Un bear marqué « à cheval » n'a qu'une borne dans la période : aucune mesure ne "
          "l'utilise (B)."]
    for actif in ("SPX", "NDX", "OR", "BTC"):
        jr = res["juges"][actif]
        dp = jr["dernier_pivot"]
        md += ["", f"### {NOMS_ACTIFS[actif]}", "",
               f"Juge à partir du {jr['debut_juge']}. Dernier pivot sur tout l'historique : "
               f"{dp['type']} du {dp['date']} ; le cycle qui suit est en cours, exclu."]
        for nom, p in jr["periodes"].items():
            titre = {"labo": "labo 1991-2023", "informative": "2024 → fin (informatif)",
                     "btc": "étape B"}[nom]
            md += ["", f"**{titre}** : θ_baisse de {_pc(p['theta_baisse'][0])} à "
                   f"{_pc(p['theta_baisse'][1])}, θ_hausse de {_pc(p['theta_hausse'][0])} à "
                   f"{_pc(p['theta_hausse'][1])}.", ""]
            if p["bears"]:
                md += _table(["pic", "creux", "baisse", "dans la période"],
                             [[b["pic"], b["creux"], _pct(b["baisse"]),
                               "oui" if b["dans_la_periode"] else "à cheval"] for b in p["bears"]])
            else:
                md += ["*Aucun bear complet.*"]
            if p["bear_en_cours"]:
                md += ["", f"Bear en cours depuis le pic du {p['bear_en_cours']['pic']} "
                       f"({_pct(p['bear_en_cours']['baisse_a_ce_jour'])} à la dernière date), "
                       "exclu."]
    return md


def _section_principal(res: dict) -> list[str]:
    t = res["principal"]
    md = ["## 4. Tableau principal — labo 1991-2023", "",
          "f_entrée : 0 = bascule bear au sommet, 1 = au creux ; un raté compte 1 (A). f_sortie : "
          "0 = bascule bull au creux, 1 = au pic suivant ; un raté compte 1. Toutes les mesures "
          "portent sur la période mesurée du juge (B)."]
    for actif in ("TEMOIN", "OR", "SPX", "NDX"):
        md += ["", f"### {NOMS_ACTIFS[actif]}"
               + (" (moyenne S&P 500 et Nasdaq-100)" if actif == "TEMOIN" else ""), ""]
        md += _tableau_principal(t, R.VERDICT, actif)
        m = t[R.REFERENCE].get(actif) or {}
        if "mesuree" in m:
            md += ["", f"Période mesurée : {m['mesuree'][0]} → {m['mesuree'][1]} "
                   f"({_n(m['annees'], 1)} ans)."]
    return md


def _section_episodes(res: dict) -> list[str]:
    t = res["principal"]
    md = ["## 5. Détecteur × épisode — labo", "",
          "f_entrée de chaque bear du juge, avec le retard en jours civils et en séances "
          "entre le pic et la bascule bear. Puis f_sortie de chaque bull complet."]
    for actif in ("SPX", "NDX", "OR"):
        md += ["", f"### {NOMS_ACTIFS[actif]} — entrées", ""] + _episodes(t, R.VERDICT, actif)
        md += ["", f"### {NOMS_ACTIFS[actif]} — sorties", ""] + _sorties(t, R.VERDICT, actif)
    return md


def _section_bande(res: dict) -> list[str]:
    t = {**res["informatifs"], R.REFERENCE: res["principal"][R.REFERENCE]}
    noms = ("SMA126", "SMA168", R.REFERENCE, "SMA210", "SMA252")
    md = ["## 6. Bande SMA et variantes de fenêtre de C1_V1 (informatif)", "",
          "### 6.1 Bande SMA : les cinq fenêtres côte à côte", "",
          "Aucun choix de fenêtre : la bande est rapportée, elle ne décide rien."]
    for actif in ("TEMOIN", "OR", "SPX", "NDX"):
        md += ["", f"**{NOMS_ACTIFS[actif]}**", ""] + _tableau_principal(t, noms, actif)
    tv = {**res["informatifs"], "C1_V1": res["principal"]["C1_V1"],
          R.REFERENCE: res["principal"][R.REFERENCE]}
    md += ["", "### 6.2 C1_V1 avec des fenêtres σ de 21 et 126 séances", "",
           "Moyenne et σ changent ensemble pour V ; σ seul pour Y, T et G (précision du 24/10)."]
    for actif in ("TEMOIN", "OR", "SPX", "NDX"):
        md += ["", f"**{NOMS_ACTIFS[actif]}**", ""] + _tableau_principal(
            tv, ("C1_V1_S21", "C1_V1", "C1_V1_S126"), actif)
    return md


def _section_neutres(res: dict) -> list[str]:
    t = res["principal"]
    md = ["## 7. Épisodes neutres de C1_V1 et C1_V2 contre le hasard", "",
          f"Un épisode neutre est juste si |ln(P fin / P veille)| ≤ σ_jour × √n (C). Hasard : "
          f"{R.N_TIRAGES} épisodes par paire détecteur × actif, de mêmes durées, à des dates "
          f"tirées au hasard dans la période mesurée (graine {R.GRAINE}).", ""]
    lignes = []
    for nom in ("C1_V1", "C1_V2"):
        for actif in ("SPX", "NDX", "OR", "BTC"):
            m = t[nom].get(actif) or {}
            if "erreur" in m:
                lignes.append([nom, NOMS_ACTIFS[actif], "non mesurable", "—", "—", "—"])
                continue
            lignes.append([nom, NOMS_ACTIFS[actif], str(m["jours_neutres"]),
                           str(m["episodes_neutres"]), _pc(m["taux_neutres_justes"]),
                           _pc(m.get("taux_neutres_hasard"))])
    md += _table(["détecteur", "actif", "jours neutres", "épisodes neutres",
                  "taux juste (détecteur)", "taux juste (hasard)"], lignes)
    return md


def _section_btc(res: dict) -> list[str]:
    t = res["principal"]
    md = ["## 8. Étape B — BTC", "",
          "Sur tout l'historique jugé du BTC. Ce résultat peut éliminer un candidat, jamais le "
          "valider seul.", ""]
    md += _tableau_principal(t, R.VERDICT, "BTC")
    m = t[R.REFERENCE].get("BTC") or {}
    if "mesuree" in m:
        md += ["", f"Période mesurée : {m['mesuree'][0]} → {m['mesuree'][1]} "
               f"({_n(m['annees'], 1)} ans)."]
    md += ["", "### Entrées", ""] + _episodes(t, R.VERDICT, "BTC")
    md += ["", "### Sorties", ""] + _sorties(t, R.VERDICT, "BTC")
    return md


def _ligne_verdict(v: dict | None, bloque: list[str]) -> str:
    if v is None:
        return "INDÉCIDABLE : " + "; ".join(bloque)
    return (v["statut"].replace("SMA200 retenue comme brique regime",
                                "SMA200 retenue comme brique régime")
            + (f" ; retenus : {', '.join(v['retenus'])}" if v["retenus"] else ""))


def _section_robustesse(res: dict) -> list[str]:
    md = ["## 9. Robustesse du juge (15 %, 25 %, σ unique)", "",
          "Les mêmes détecteurs mesurés avec un autre juge : rapportés, pas comptés (F). Le "
          "résultat est **solide** si le gagnant ET la liste des retenus sont les mêmes sous les "
          "trois variantes (précision du 24/10).", ""]
    lignes = []
    for cle, r in res["robustesse"].items():
        tv = r["tables"]
        cell = []
        for actif in ("TEMOIN", "OR", "BTC"):
            m = {nom: tv[nom].get(actif) or {} for nom in R.VERDICT}
            cell.append(" ; ".join(
                f"{nom} {_n(m[nom].get('f_entree_mediane'))} / "
                f"{_n(m[nom].get('fausses_alertes_an'))}"
                if "erreur" not in m[nom] else f"{nom} non mesurable" for nom in R.VERDICT))
        lignes.append([NOMS_VARIANTES[cle], *cell, _ligne_verdict(r["verdict"],
                                                                   r["indecidable"])])
    md += _table(["variante du juge", "témoin (médiane f_entrée / FA par an)",
                  "or (idem)", "BTC (idem)", "verdict"], lignes)
    md += ["", "**Résultat solide : " + {True: "oui", False: "non", None: "indécidable"}[
        res["solide"]] + "**."]
    return md


def _section_deja_vu(res: dict) -> list[str]:
    t = res["deja_vu"]
    md = ["## 10. Tableau informatif 2024 → fin — **déjà vu, ne décide rien**", ""]
    for actif in ("TEMOIN", "OR", "SPX", "NDX"):
        md += ["", f"**{NOMS_ACTIFS[actif]}**", ""] + _tableau_principal(t, R.VERDICT, actif)
        erreurs = {nom: t[nom][actif]["erreur"] for nom in R.VERDICT
                   if actif in t[nom] and "erreur" in t[nom][actif]}
        if erreurs:
            md += ["", "Non mesurable : " + next(iter(erreurs.values())) + "."]
    return md


def _section_verdict(res: dict) -> list[str]:
    v = res["verdict"]
    md = ["## 11. Verdict mécanique", ""]
    if v is None:
        return md + [f"**INDÉCIDABLE** : {'; '.join(res['indecidable'])}. Aucun verdict n'est "
                     "rendu (règle 2 du prompt)."]
    lignes = []
    for x in R.CANDIDATS:
        a = v["etape_a"][x]
        lignes.append([x,
                       "oui" if a["TEMOIN"]["domine_par_sma200"] else "non",
                       f"{a['TEMOIN']['plus_faible']} / {a['TEMOIN']['episodes']}",
                       "oui" if a["OR"]["domine_par_sma200"] else "non",
                       f"{a['OR']['plus_faible']} / {a['OR']['episodes']}",
                       "retenu" if a["retenu"] else "non retenu",
                       ("éliminé" if v["etape_b"][x]["elimine"] else "passe")
                       if x in v["etape_b"] else "—"])
    md += _table(["candidat", "dominé par SMA200 (témoin)",
                  "épisodes où f_entrée < SMA200 (témoin)", "dominé par SMA200 (or)",
                  "épisodes où f_entrée < SMA200 (or)", "étape A", "étape B (BTC)"], lignes)
    g = v["gagnant"]
    if g["moyennes"]:
        md += ["", "Classement D (moyennes témoin / or) :", ""]
        md += _table(["candidat", "médiane f_entrée moyenne", "fausses alertes / an moyennes",
                      "pire cas moyen"],
                     [[x, _n(m["f_entree_mediane"]), _n(m["fausses_alertes_an"]),
                       _n(m["f_entree_pire"])] for x, m in g["moyennes"].items()])
    md += ["", f"**Verdict : {_ligne_verdict(v, [])}.**", "",
           "**Résultat solide (variantes du juge) : " + {True: "oui", False: "non",
                                                       None: "indécidable"}[res["solide"]] + "**."]
    return md


ECARTS = [
    "**BTC** : base DS1, table `bougies_1d`, source Bitstamp (clôture du jour civil UTC). DS1 "
    "n'avait aucune bougie : elle a été installée le 24/10 (décision 1 de Jonas).",
    "**VIX** : `VIXCLS` (FRED), comme demandé. Sa clôture de 16:15 ET est prise le jour même : "
    "c'est la lecture « publiée au plus tard en t » à la date près.",
    "**USD/JPY** : ALFRED est indisponible. On applique le vrai calendrier de parution du H.10 "
    "(clarification E) au lieu du décalage de 2 jours ouvrés du prompt, sur toute la période. "
    "Ce calendrier hebdomadaire n'a pas pu être vérifié avant 2026.",
    "**Compteur** : le prompt dit 117 au gel ; le compteur global valait 131 au lancement et "
    "l'invest 38. Les deux sont rapportés, sans remplacement (Jonas 24/10).",
    "**Essais** : 16 au verdict (SMA200 et BTC compris) et 18 informatifs, au lieu du « 1 par "
    "couple détecteur × actif jugé du verdict principal » du prompt (Jonas 24/10).",
    "**Période mesurée** : avec B, toutes les mesures (latences, fausses alertes, bascules, "
    "justesse, épisodes neutres) portent sur [premier pivot du juge dans la période, dernier "
    "pivot dans la période[. Les années des taux « par an » sont celles de cette période mesurée. "
    "La découverte (§ 3) parlait encore des jours civils de toute la période : c'est la "
    "conséquence de B et de l'exclusion du dernier cycle.",
    "**Fausses alertes** : un épisode bear du détecteur compte s'il commence dans la période "
    "mesurée. Il est faux s'il ne recoupe aucun bear du juge, à cheval ou en cours compris.",
    "**f_sortie** : un raté de sortie compte 1, comme A (précision du 24/10).",
    "**Variante σ unique** : le test des épisodes neutres y utilise le même σ unique, puisque "
    "σ_jour est défini par σ_actif. Cela ne touche pas le verdict.",
    "**Tableau 2024 → fin** : les 4 détecteurs du verdict seulement, sans la bande ni les "
    "variantes, pour ne pas multiplier les mesures non comptées.",
]


# ----------------------------------------------------------------------------- ecriture

def markdown(s: dict) -> str:
    res = s["resultats"]
    corps = [f"# Résultats — calculés le {s['calcule_le']} UTC", "",
             f"Code `{s['code']}`, règles `{s['regles']}`, clarifications `{s['clarifications']}`, "
             f"données `{s['donnees']['empreinte']}`. Préenregistrement : `EXPERIMENTS.jsonl`, id "
             f"`{R.ID_EXP}`. Rapport écrit par `scripts/temps1_justesse.py`, sans interprétation "
             "au-delà du verdict mécanique.", ""]
    corps += _section_compteur(s) + [""] + _section_couverture(s) + [""]
    caus = s["causalite"]
    corps += ["**Épreuve de causalité** : signaux recalculés avec les seules données connues à "
              f"{len(caus['coupures'])} dates de coupure, puis comparés aux signaux calculés sur "
              "tout l'historique. "
              + ("Aucun écart." if not caus["echecs"] else
                 f"**ÉCHEC** ({len(caus['echecs'])} écarts) : aucun chiffre n'est calculé."), ""]
    if res is None:
        return "\n".join(corps)
    for section in (_section_juge, _section_principal, _section_episodes, _section_bande,
                    _section_neutres, _section_btc, _section_robustesse, _section_deja_vu,
                    _section_verdict):
        corps += section(res) + [""]
    corps += ["## 12. Écarts au prompt et leurs raisons", ""] + [f"- {e}" for e in ECARTS]
    return "\n".join(corps) + "\n"


def _csv(chemin, entetes: list[str], lignes: list[list]) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(entetes)
        w.writerows(lignes)


COLONNES = ["f_entree_mediane", "f_entree_pire", "rates_entree", "n_bears", "fausses_alertes_an",
            "justesse", "r_bear", "r_bull", "f_sortie_mediane", "f_sortie_pire", "rates_sortie",
            "n_bulls", "bascules_an", "taux_neutres_justes", "taux_neutres_hasard"]


def _lignes_tables(bloc: str, tables: dict) -> list[list]:
    sortie = []
    for nom, par_actif in tables.items():
        for actif, m in par_actif.items():
            if "erreur" in m:
                sortie.append([bloc, nom, actif, m["erreur"]] + [""] * len(COLONNES))
            else:
                sortie.append([bloc, nom, actif, ""] + [m.get(k) for k in COLONNES])
    return sortie


def csvs(s: dict) -> None:
    res = s["resultats"]
    if res is None:
        return
    lignes = (_lignes_tables("labo+btc", res["principal"])
              + _lignes_tables("informatif_labo", res["informatifs"])
              + _lignes_tables("deja_vu_2024", res["deja_vu"]))
    for cle, r in res["robustesse"].items():
        lignes += _lignes_tables(f"juge_{cle}", r["tables"])
    _csv(ca.SORTIE / "RAPPORT_JUSTESSE.csv", ["bloc", "detecteur", "actif", "erreur", *COLONNES],
         lignes)
    ep = []
    for bloc, tables in (("labo+btc", res["principal"]), ("informatif_labo", res["informatifs"]),
                         ("deja_vu_2024", res["deja_vu"])):
        for nom, par_actif in tables.items():
            for actif, m in par_actif.items():
                if actif == "TEMOIN" or "erreur" in m:
                    continue
                for e in m["entrees"]:
                    ep.append([bloc, nom, actif, "entree", e["pic"], e["creux"], e["baisse"],
                               e["f_entree"], e["rate"], e["bascule"], e["retard_jours"],
                               e["retard_seances"]])
                for e in m["sorties"]:
                    ep.append([bloc, nom, actif, "sortie", e["pic"], e["creux"], None,
                               e["f_sortie"], e["rate"], e["bascule"], None, None])
    _csv(ca.SORTIE / "RAPPORT_JUSTESSE_episodes.csv",
         ["bloc", "detecteur", "actif", "sens", "pic", "creux", "baisse", "f", "rate", "bascule",
          "retard_jours", "retard_seances"], ep)
    juge = []
    for actif, jr in res["juges"].items():
        for nom, p in jr["periodes"].items():
            for b in p["bears"]:
                juge.append([actif, nom, b["pic"], b["creux"], b["baisse"], b["dans_la_periode"]])
    _csv(ca.SORTIE / "RAPPORT_JUSTESSE_juge.csv",
         ["actif", "periode", "pic", "creux", "baisse", "dans_la_periode"], juge)


def resume(s: dict) -> str:
    """Le message court du salon BETA : verdict mecanique et compteurs, rien d'autre."""
    res = s["resultats"]
    c = s["compteur"]
    a, b = c["avant_journalisation"], c["apres_journalisation"]
    # Pastille mecanique : etat du calcul et solidite, jamais un jugement sur le resultat.
    if res is None:
        pastille, ligne = "🔴", "Arrêt : épreuve de causalité échouée, aucun chiffre"
    elif res["verdict"] is None:
        pastille, ligne = "🟠", "INDÉCIDABLE : " + "; ".join(res["indecidable"])
    else:
        pastille = "🟢" if res["solide"] else "🟡"
        ligne = "Verdict mécanique : " + _ligne_verdict(res["verdict"], [])
    md = [f"# {pastille} Test de justesse T1J — rapport du programme — {s['calcule_le'][:10]}",
          "", f"**{ligne}.**"]
    if res is not None and res["verdict"] is not None:
        md += [f"**Résultat solide (variantes du juge) : "
               f"{ {True: 'oui', False: 'non', None: 'indécidable'}[res['solide']] }.**"]
    md += ["", "## Compteurs",
           f"- Global (`compteur_total`) : gel {c['gel_global_22_10']} · {a['global']} → "
           f"**{b['global']}**",
           f"- Invest (`compteur(famille=\"invest\")`) : {a['invest']} → **{b['invest']}**",
           f"- Essais du verdict : 16 · informatifs : {c['informatifs']['total']} (non comptés)",
           "", "## Fichiers",
           "- `temps1_justesse/RAPPORT_JUSTESSE.md` (joint) et ses 3 CSV",
           f"- Code `{s['code']}`, règles `{s['regles']}`, données `{s['donnees']['empreinte']}`",
           "", "Message écrit par le programme (`beta/temps1_justesse/rapport.py`), sans "
           "interprétation."]
    return "\n".join(md) + "\n"


def ecrire(s: dict) -> None:
    tete = ca.clarifications()
    marqueur = ca.RAPPORT.read_text(encoding="utf-8").split(ca.MARQUEUR, 1)[1].split("\n", 1)[0]
    texte = tete + ca.MARQUEUR + marqueur + "\n\n" + markdown(s)
    ca.RAPPORT.write_text(texte, encoding="utf-8")
    csvs(s)
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.RAPPORT)
