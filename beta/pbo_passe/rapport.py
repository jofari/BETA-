"""PBOR : le rapport, ecrit par le programme. Aucune interpretation au-dela de la lecture S10."""

from __future__ import annotations

import logging

from beta.pbo_passe import campagne as ca
from beta.pbo_passe import regles as R

log = logging.getLogger("beta.pbo_passe.rapport")

LECTURE = {"franchie": "PBO < 20 % : la porte S10 aurait été franchie",
           "echouee": "PBO ≥ 20 % : la porte S10 aurait échoué",
           "non executee": "PBO incalculable : la porte S10 n'aurait pas été exécutée"}


def _pc(x) -> str:
    return "—" if x is None else f"{100 * x:.1f} %".replace(".", ",")


def _pbo(res: dict) -> list[str]:
    retires = res["n_jours_avant"] - res["n_jours"]
    lignes = [f"- Période : {res['debut'] or '—'} → {res['fin'] or '—'}, {res['n_jours']} jours "
              f"({retires} plus ancien(s) retiré(s) pour {res['s']} blocs égaux"
              + (f", {res['jours_par_bloc']} jours par bloc)" if res.get("jours_par_bloc")
                 else ")"),
              f"- Configurations : {res['n_configs_avant']} → {res['n_configs']} après "
              "retrait des doublons exacts"
              + (" (" + ", ".join(f"{d['nom']} = {d['identique_a']}" for d in res["doublons"])
                 + ")" if res["doublons"] else "")]
    if res["pbo"] is None:
        return lignes + [f"- PBO : **incalculable** — {res['raison']}"]
    w = res["w"]
    etoiles = sorted(res["etoiles"].items(), key=lambda x: (-x[1], x[0]))
    return lignes + [
        f"- PBO : **{_pc(res['pbo'])}** ({res['n_combinaisons']} combinaisons)",
        f"- Rang OOS relatif w de n* : 5 % {_pc(w['0.05'])} · 25 % {_pc(w['0.25'])} · "
        f"médiane {_pc(w['0.5'])} · 75 % {_pc(w['0.75'])} · 95 % {_pc(w['0.95'])}",
        "- Choisie comme n* (meilleure en apprentissage) : "
        + " · ".join(f"{nom} {_pc(part)}" for nom, part in etoiles)]


def texte(s: dict) -> str:
    jour = s["calcule_le"][:10]
    lignes = [f"# PBO du passé (PBOR) — rapport du programme — {jour}", "",
              "## Empreintes",
              f"- Code : `{s['code']}` · règles : `{s['regles']}` · préenregistrement "
              f"(`pbo_passe/PREENREGISTREMENT.md`) : `{s['preenregistrement']}`",
              f"- Calcul du {s['debut_calcul']} au {s['calcule_le']}", "",
              "Diagnostic, rapport seul : aucun verdict déjà rendu n'est modifié. Méthode de la "
              f"porte S10 (`beta/stats/pbo.py`) : CSCV, {R.S} blocs contigus, Sharpe, seuil "
              f"PBO < {_pc(R.SEUIL)}.", ""]
    for cle, x in s["lots"].items():
        lignes += [f"## {cle} — {x['titre']}", "",
                   "| Candidate | Run | Verdict rendu (inchangé) | Trades | Meilleure selon S7 |",
                   "|---|---|---|---|---|"]
        lignes += [f"| {c['candidate']} | `{c['run']}` | {c['issue']} | {c['n_trades']} | "
                   f"{c['meilleure_s7']} |" for c in x["candidates"]]
        lignes += ["", "Rendement quotidien : somme des R des trades clôturés ce jour-là.",
                   *_pbo(x["pbo"]), f"- Matrice des rendements : `{x['donnees']}`",
                   f"- **{LECTURE[x['lecture_s10']]}**", ""]
    vc = s["voie_c"]
    lignes += ["## Voie C — les 6 variantes du 22/09", "",
               "`voie_c_voltarget.py` (`preparer` coupé au "
               f"{R.FIN_VC}, puis `variantes_selection`) : r_net quotidien, 5 bps, funding. "
               f"Les 6 variantes existent toutes à partir du {vc['depart']}.",
               *_pbo(vc["pbo"]), f"- Matrice des rendements : `{vc['donnees']}`",
               f"- Variante retenue par la règle du 22/09 (meilleur Sharpe net du train, "
               f"jusqu'au {R.FIN_TRAIN_VC}) : {vc['retenue_train']}",
               f"- **{LECTURE[vc['lecture_s10']]}**", ""]
    c = s["compteur"]
    lignes += ["## Compteurs",
               f"- Avant : global {c['avant']['global']}, trading {c['avant']['trading']}, "
               f"invest {c['avant']['invest']} · après : global {c['apres']['global']}, trading "
               f"{c['apres']['trading']}, invest {c['apres']['invest']} (diagnostic)", ""]
    return "\n".join(lignes)


def resume(s: dict) -> str:
    def un(nom: str, x: dict) -> str:
        res = x["pbo"]
        chiffre = "incalculable" if res["pbo"] is None else _pc(res["pbo"])
        return (f"- {nom} ({res['n_configs']} config.) : PBO {chiffre} → "
                f"{LECTURE[x['lecture_s10']].split(' : ')[1]}")

    lignes = ["**PBOR — PBO du passé (diagnostic, rapport seul)**",
              f"Code `{s['code']}`, préenregistrement `{s['preenregistrement']}`. "
              "Aucun verdict modifié, compteur inchangé.", ""]
    lignes += [un(f"{cle} {x['titre']}", x) for cle, x in s["lots"].items()]
    lignes += [un("Voie C, variantes du 22/09", s["voie_c"]), "",
               "Rapport complet en pièce jointe (pbo_passe/RAPPORT_PBO.md)."]
    return "\n".join(lignes)


def ecrire(s: dict) -> None:
    ca.SORTIE.mkdir(parents=True, exist_ok=True)
    (ca.SORTIE / "RAPPORT_PBO.md").write_text(texte(s), encoding="utf-8")
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.SORTIE / "RAPPORT_PBO.md")
