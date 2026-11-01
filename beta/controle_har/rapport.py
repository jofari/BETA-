"""Controle HAR : le rapport et l'addendum de la spec, ecrits par le programme a partir de la
synthese de la campagne. Aucune interpretation au-dela de la regle 5.

Sorties, dans VC6_V1/controle_har/ : RAPPORT_CONTROLE_HAR.md, RAPPORT_CONTROLE_HAR.csv et
RESUME_DISCORD.md. `ajouter_addendum` ajoute l'addendum date « sigma retenu » a spec_figee.md.
"""

from __future__ import annotations

import csv
import logging
import math

from beta.controle_har import campagne as ca
from beta.controle_har import regles as R

log = logging.getLogger("beta.controle_har.rapport")

NOM = {R.HAR: "HAR", R.ECART_TYPE: "écart-type 30 jours"}
TITRE_ADDENDUM = "σ̂ retenu au « Contrôle HAR »"


def _n(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def _p(x) -> str:
    return "—" if x is None else f"{x:.3f}".replace(".", ",")


def _vol(variance) -> str:
    """Variance journaliere moyenne lue en volatilite annualisee : racine(v x 365)."""
    return "—" if variance is None else f"{100 * math.sqrt(variance * 365):.1f} %".replace(".", ",")


def _date(iso: str | None) -> str:
    return "—" if not iso else f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def _table(entetes: list[str], lignes: list[list]) -> list[str]:
    return (["| " + " | ".join(entetes) + " |", "|" + "|".join("---" for _ in entetes) + "|"]
            + ["| " + " | ".join(str(c) for c in ligne) + " |" for ligne in lignes])


def _exclus(a: dict) -> str:
    e = a["jours_exclus"]
    return f"{e['total']} ({e['dans_la_periode_evaluee']} dans la période évaluée)"


def conclusion(actif: str, a: dict) -> str:
    """La ligne sigma retenu d'un actif, mecanique (regle 5)."""
    q = a["qlike"]
    if a["sigma_retenu"] == R.ECART_TYPE:
        return (f"**{actif} : σ̂ = écart-type 30 jours** (QLIKE moyenne du HAR {_n(q['har'])} > "
                f"{_n(q['ecart_type'])} pour l'écart-type 30 jours).")
    return (f"**{actif} : σ̂ = HAR** (QLIKE moyenne du HAR {_n(q['har'])} ≤ {_n(q['ecart_type'])} "
            "pour l'écart-type 30 jours). Repli : écart-type 30 jours avant 730 jours de RV "
            f"(jusqu'à la veille du {_date(a['periodes']['har_des_le'])}) et les jours de "
            "prévision ≤ 0.")


def _section_tableau(s: dict) -> list[str]:
    md = ["## 1. Tableau par actif", "",
          "QLIKE moyenne contre la moyenne des RV 5 min des 5 jours suivants (plus bas = "
          "meilleur), sur les jours où le HAR a ses 730 jours de RV. Les deux prévisions sont "
          "évaluées sur les mêmes jours. Le p de Diebold-Mariano est donné pour information.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        lignes.append([actif, _n(a["qlike"]["har"]), _n(a["qlike"]["ecart_type"]),
                       _p(a["diebold_mariano"]["p"]), a["jours_evalues"], _exclus(a),
                       a["previsions_negatives_remplacees"]["jours_evalues"]])
    md += _table(["actif", "QLIKE HAR", "QLIKE écart-type 30 jours", "p de Diebold-Mariano",
                  "jours évalués", "jours exclus", "prévisions ≤ 0 remplacées"], lignes)
    return md


def _section_sigma(s: dict) -> list[str]:
    md = ["## 2. σ̂ retenu par actif (règle 5)", "",
          "Règle 5 : si le HAR a une QLIKE moyenne plus haute que l'écart-type 30 jours pour un "
          "actif, σ̂ de cet actif = écart-type 30 jours ; sinon σ̂ = HAR. La spec annualise σ̂ en "
          "√365.", ""]
    return md + ["- " + conclusion(actif, a) for actif, a in s["actifs"].items()]


def _section_periodes(s: dict) -> list[str]:
    md = ["## 3. Périodes et comptes", "",
          "Les jours exclus ont plus de 10 % des 288 barres 5 min manquantes : ils n'ont pas de "
          "RV. Les barres à volume nul sont des barres présentes, comptées ici sans rien changer. "
          "La période évaluée va de la première origine évaluée à la dernière cible.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        pe, c, e = a["periodes"], a["couverture"], a["jours_exclus"]
        dates = ", ".join(f"{_date(d)} ({n} barres)"
                          for d, n in zip(e["dates"], e["barres_presentes"], strict=True))
        nul = a["barres_volume_nul"]
        lignes.append([
            actif, f"{c['premiere_barre_5m']} → {c['derniere_barre_5m']} ({c['barres_5m']})",
            pe["jours_avec_rv"], _date(pe["har_des_le"]),
            f"{_date(pe['evaluation'][0])} → {_date(pe['evaluation'][1])}",
            _date(pe["derniere_cible"]), dates or "aucun",
            f"{nul['total']} ; {nul['dans_la_periode_evaluee']}",
            f"{a['previsions_negatives_remplacees']['jours_evalues']} ; "
            f"{a['previsions_negatives_remplacees']['tous_jours_har']}"])
    md += _table(["actif", "barres 5 min (UTC)", "jours avec RV", "HAR estimé dès le",
                  "origines évaluées", "dernière cible", "jours exclus",
                  "barres à volume nul (total ; période évaluée)",
                  "prévisions ≤ 0 (jours évalués ; tous les jours du HAR)"], lignes)
    return md


def _section_dm(s: dict) -> list[str]:
    md = ["## 4. Diebold-Mariano (information, ne décide rien)", "",
          "d = QLIKE HAR − QLIKE écart-type 30 jours, jour par jour ; variance de Newey-West "
          "(noyau de Bartlett) ; p bilatérale. Statistique < 0 : le HAR a la perte moyenne la plus "
          "basse.", ""]
    lignes = [[actif, a["diebold_mariano"]["n"], a["diebold_mariano"]["retard"],
               _n(a["diebold_mariano"]["stat"], 2), _p(a["diebold_mariano"]["p"])]
              for actif, a in s["actifs"].items()]
    return md + _table(["actif", "jours", "retard", "statistique", "p"], lignes)


def _section_moyennes(s: dict) -> list[str]:
    md = ["## 5. Niveaux moyens sur les jours évalués (information)", "",
          "Moyenne des variances journalières, lue en volatilité annualisée √(moyenne × 365).",
          ""]
    lignes = [[actif, _vol(a["moyennes_periode_evaluee"]["cible"]),
               _vol(a["moyennes_periode_evaluee"]["har"]),
               _vol(a["moyennes_periode_evaluee"]["ecart_type"])]
              for actif, a in s["actifs"].items()]
    return md + _table(["actif", "cible (RV 5 min, 5 jours suivants)", "prévision HAR",
                        "prévision écart-type 30 jours"], lignes)


def _section_coefficients(s: dict) -> list[str]:
    md = ["## 6. Dernière estimation du HAR (information)", "",
          "MCO avec constante sur les lignes entièrement dans la fenêtre des 730 derniers jours "
          "de RV.", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        d = a["dernier_har"]
        b = d["coefficients"]
        lignes.append([actif, _date(d["jour"]), d["lignes"], f"{b[0]:.3e}".replace(".", ","),
                       _n(b[1], 3), _n(b[2], 3), _n(b[3], 3)])
    return md + _table(["actif", "jour", "lignes", "constante", "RV du jour", "moyenne 5 jours",
                        "moyenne 22 jours"], lignes)


def _section_donnees(s: dict) -> list[str]:
    c = s["compteur"]
    md = ["## 7. Empreintes et données", "",
          f"- **Code** : `{s['code']}`. **Règles** : `{s['regles']}` ; préenregistrement "
          f"`PREENREGISTREMENT.md` `{s['preenregistrement']}` ; registre : `EXPERIMENTS.jsonl`, "
          "test de mesure (diagnostic).",
          f"- **Compteur** (aucun essai) : global {c['avant']['global']} → {c['apres']['global']}, "
          f"invest {c['avant']['invest']} → {c['apres']['invest']}, trading actif "
          f"{c['avant']['trading']} → {c['apres']['trading']}.",
          f"- **Empreinte des valeurs lues** : `{s['donnees']['empreinte']}` ; date de fin figée : "
          f"{_date(s['donnees']['fin'])}.",
          "- **Clôture du jour** : celle de la barre 5 min de 23:55 (amendement du 01/11/2026, "
          "décision de Jonas). Les copies 1d ne servent qu'au contrôle ; jours où leur clôture "
          "diffère : " + " ; ".join(
              f"{actif} : " + (", ".join(_date(d) for d in a["controle_1d"]) or "aucun")
              for actif, a in s["actifs"].items()) + ".", ""]
    lignes = []
    for actif, a in s["actifs"].items():
        cp, cv = s["donnees"]["copies"][actif], a["couverture"]
        sha = s["donnees"]["sha256"]
        lignes.append([actif, f"`{cp['bougies_5m']}`", f"`{sha[f'{actif}_perp_5m']}`",
                       f"`{cp['bougies_1d']}`", f"`{sha[f'{actif}_perp_1d']}`",
                       f"{cv['premiere_cloture_1d']} → {cv['derniere_cloture_1d']} "
                       f"({cv['clotures_1d']})"])
    md += _table(["actif", "bougies 5 min", "SHA-256 vérifié", "clôtures 1d", "SHA-256 vérifié",
                  "clôtures"], lignes)
    return md


def _section_causalite(s: dict) -> list[str]:
    md = ["## 8. Épreuve de causalité", "",
          "Prévisions du HAR (brute et après replis) et de l'écart-type 30 jours recalculées avec "
          "les seules données connues à chaque coupure (" + ", ".join(
              _date(c) for c in R.COUPURES_CAUSALITE) + "), comparées à celles calculées sur tout "
          "l'historique."]
    for actif, a in s["actifs"].items():
        md.append(f"- {actif} : " + ("aucun écart." if not a["causalite"]
                                     else f"ÉCARTS : {a['causalite']}."))
    return md


def _section_ecarts() -> list[str]:
    return ["## 9. Ce que le programme a appliqué sans que le prompt le dise mot pour mot", "",
            "Détail et raisons : applications 1 à 15 de `PREENREGISTREMENT.md`.",
            "- **Données** : perpétuels Binance USDT-M, seules bougies 5 min de BETA et DS1 ; "
            "rendements journaliers tirés de la barre 5 min de 23:55 (amendement du 01/11, "
            "décision de Jonas). Pour le BTC, la série du mode global (Bitstamp ou perpétuel) "
            "reste à trancher en phase 3.",
            "- **HAR** : constante comprise (Corsi 2009) ; fenêtre = RV des 730 derniers jours, "
            "lignes entièrement dedans (704 au plus).",
            "- **Écart-type 30 jours** : écart-type d'échantillon (ddof = 1), au carré.",
            "- **PBO (invariant 13)** : non calculée. Le prompt règle le choix par sa règle 5 et "
            "en fait un test de mesure ; c'est à Jonas de dire s'il en veut une."]


def markdown(s: dict) -> str:
    md = ["# Contrôle HAR (VC6 V1, phase 2)", "",
          f"Calculé le {s['calcule_le']} UTC. Rapport écrit par `scripts/controle_har.py`, sans "
          "interprétation au-delà de la règle 5. Préenregistrement : `PREENREGISTREMENT.md` (même "
          "dossier). Test de mesure : aucun essai ajouté au compteur.", ""]
    for section in (_section_tableau(s), _section_sigma(s), _section_periodes(s), _section_dm(s),
                    _section_moyennes(s), _section_coefficients(s), _section_donnees(s),
                    _section_causalite(s), _section_ecarts()):
        md += section + [""]
    return "\n".join(md)


def csvs(s: dict) -> None:
    with open(ca.SORTIE / "RAPPORT_CONTROLE_HAR.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["actif", "qlike_har", "qlike_ecart_type_30j", "p_diebold_mariano",
                    "stat_diebold_mariano", "retard_diebold_mariano", "jours_evalues",
                    "jours_exclus_total", "jours_exclus_periode_evaluee",
                    "previsions_negatives_remplacees_jours_evalues",
                    "previsions_negatives_tous_jours_har", "sigma_retenu", "har_des_le",
                    "evaluation_debut", "evaluation_fin"])
        for actif, a in s["actifs"].items():
            dm, pe = a["diebold_mariano"], a["periodes"]
            w.writerow([actif, a["qlike"]["har"], a["qlike"]["ecart_type"], dm["p"], dm["stat"],
                        dm["retard"], a["jours_evalues"], a["jours_exclus"]["total"],
                        a["jours_exclus"]["dans_la_periode_evaluee"],
                        a["previsions_negatives_remplacees"]["jours_evalues"],
                        a["previsions_negatives_remplacees"]["tous_jours_har"], a["sigma_retenu"],
                        pe["har_des_le"], pe["evaluation"][0], pe["evaluation"][1]])


def resume(s: dict) -> str:
    """Message court du salon BETA, ecrit par le programme. Pastille verte : la mesure est allee
    au bout (un arret ne produit pas de synthese)."""
    c = s["compteur"]
    md = [f"# 🟢 Contrôle HAR (VC6 V1, phase 2) — rapport du programme — {s['calcule_le'][:10]}",
          ""]
    for actif, a in s["actifs"].items():
        md.append(f"- {conclusion(actif, a)} p de Diebold-Mariano {_p(a['diebold_mariano']['p'])}"
                  f" (information) ; {a['jours_evalues']} jours évalués.")
    md += ["", "Règle 5 : écart-type 30 jours si la QLIKE moyenne du HAR est plus haute ; sinon "
               f"HAR. Test de mesure, aucun essai : global {c['apres']['global']}, invest "
               f"{c['apres']['invest']} (inchangés).", "",
           "Fichiers : `VC6_V1/controle_har/RAPPORT_CONTROLE_HAR.md` (joint) et le CSV. "
           f"Code `{s['code']}`, règles `{s['regles']}`, données `{s['donnees']['empreinte']}`.",
           "", "Message écrit par le programme (`beta/controle_har/rapport.py`), sans "
               "interprétation."]
    return "\n".join(md) + "\n"


def addendum(s: dict) -> str:
    """L'addendum date de spec_figee.md : sigma retenu par actif, depuis la synthese."""
    md = [f"## Addendum du {_date(s['calcule_le'][:10])} — {TITRE_ADDENDUM}", "",
          f"Écrit par le programme (`scripts/controle_har.py --addendum`) à partir de la synthèse "
          f"de la mesure du {s['calcule_le']} UTC : règles `{s['regles']}`, données "
          f"`{s['donnees']['empreinte']}`, code `{s['code']}`. Règle 5 du prompt du « Contrôle "
          "HAR » (`VC6_V1/controle_har/PREENREGISTREMENT.md`). Rapport : "
          "`VC6_V1/controle_har/RAPPORT_CONTROLE_HAR.md`.", ""]
    md += _table(["actif", "QLIKE HAR", "QLIKE écart-type 30 jours", "jours évalués", "σ̂ retenu"],
                 [[actif, _n(a["qlike"]["har"]), _n(a["qlike"]["ecart_type"]), a["jours_evalues"],
                   NOM[a["sigma_retenu"]]] for actif, a in s["actifs"].items()])
    md += ["",
           "- **HAR** : prévision HAR de la variance journalière moyenne des 5 jours suivants, "
           "avec ses replis (écart-type 30 jours avant 730 jours de RV et les jours de prévision "
           "≤ 0).",
           "- **Écart-type 30 jours** : écart-type d'échantillon des 30 derniers rendements log "
           "journaliers, au carré.",
           "- La spec annualise σ̂i en √365."]
    return "\n".join(md) + "\n"


def ajouter_addendum(s: dict) -> bool:
    """Ajoute l'addendum a spec_figee.md s'il n'y est pas deja. Rend True s'il a ete ajoute."""
    texte = ca.SPEC.read_text(encoding="utf-8")
    if TITRE_ADDENDUM in texte:
        log.info("addendum deja present dans %s", ca.SPEC.name)
        return False
    ca.SPEC.write_text(texte.rstrip("\n") + "\n\n" + addendum(s), encoding="utf-8")
    log.info("addendum ajoute a %s", ca.SPEC)
    return True


def ecrire(s: dict) -> None:
    ca.SORTIE.mkdir(parents=True, exist_ok=True)
    (ca.SORTIE / "RAPPORT_CONTROLE_HAR.md").write_text(markdown(s), encoding="utf-8")
    csvs(s)
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.SORTIE / "RAPPORT_CONTROLE_HAR.md")
