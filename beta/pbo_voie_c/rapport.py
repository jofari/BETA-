"""PBOC : le rapport, ecrit par le programme. Aucune interpretation au-dela du verdict."""

from __future__ import annotations

import logging

from beta.pbo_voie_c import campagne as ca
from beta.pbo_voie_c import regles as R

log = logging.getLogger("beta.pbo_voie_c.rapport")

VERDICT = {"candidate": "la voie C reste candidate",
           "surajustee": "la voie C est marquée « surajustée »"}


def _pc(x) -> str:
    return "—" if x is None else f"{100 * x:.1f} %".replace(".", ",")


def _n(x, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}f}".replace(".", ",")


def _q(r: dict, pc: bool = False, d: int = 3) -> str:
    f = _pc if pc else (lambda v: _n(v, d))
    q = r["quantiles"]
    return (f"min {f(q['0'])} · 5 % {f(q['0.05'])} · 25 % {f(q['0.25'])} · médiane "
            f"{f(q['0.5'])} · 75 % {f(q['0.75'])} · 95 % {f(q['0.95'])} · max {f(q['1'])}")


def _distribution(d: dict) -> list[str]:
    deciles = " · ".join(f"{10 * k}-{10 * (k + 1)} % : {n}" for k, n in enumerate(d["deciles_w"]))
    return [f"- PBO : **{_pc(d['pbo'])}** ({d['n_combinaisons']} combinaisons, "
            f"{d['n_configs']} configurations)",
            f"- Rang OOS relatif w de n* : {_q(d['w'], pc=True)}",
            f"- Combinaisons par décile de w : {deciles}",
            f"- Logit λ : moyenne {_n(d['lambda']['moyenne'], 3)}, {_q(d['lambda'])}",
            f"- Sharpe IS de n* : médiane {_n(d['sharpe_is_etoile']['quantiles']['0.5'])} ; "
            f"Sharpe OOS de n* : médiane {_n(d['sharpe_oos_etoile']['quantiles']['0.5'])}",
            f"- Configurations distinctes choisies comme n* : {d['n_etoiles_distinctes']}"]


def _nom(c: dict) -> str:
    return (f"{c['cible']:.0%} {c['estimateur']} {int(c['fenetre'])} j "
            f"L[{c['lmin']:g} ; {c['lmax']:g}] pas {int(c['pas'])} bande {c['bande']:.0%}")


def markdown(s: dict) -> str:
    p, n = s["positif"], s["negatif"]
    sp, si = p["avantage"][f"{R.SR_POSITIF:g}"], p["avantage"][f"{R.SR_INFORMATIF:g}"]
    md = [f"# PBO de la grille de la voie C (PBOC) — rapport du programme — "
          f"{s['calcule_le'][:10]}", "",
          "## Empreintes",
          f"- Code : `{s['code']}` · règles : `{s['regles']}` · préenregistrement "
          f"(`pbo_voie_c/PREENREGISTREMENT.md`) : `{s['preenregistrement']}`",
          f"- Données de la voie C : `{s['voie_c']['donnees']}`" if s["voie_c"] else
          "- Données de la voie C : non lues (arrêt aux contrôles)",
          f"- Calcul du {s['debut_calcul']} au {s['calcule_le']}", "",
          "## Contrôle positif (décide)",
          f"Grille N(0, 1) de {R.N_JOURS} × {R.N_CONTROLE}, graine {p['graine']}, avantage de "
          f"Sharpe {R.SR_POSITIF:g} (√252) ajouté chaque jour à la colonne 0. Réussi si PBO ≤ "
          f"{_pc(R.SEUIL_POSITIF)}.",
          *_distribution(sp),
          f"- Part des combinaisons où n* est la colonne 0 : {_pc(sp['part_etoile_colonne_0'])} ; "
          f"Sharpe réalisé de la colonne 0 : {_n(sp['sharpe_realise_colonne_0'])}",
          f"- **Contrôle positif : {'réussi' if p['reussi'] else 'RATÉ'}**", "",
          f"### Informatif (ne décide rien) : avantage de Sharpe {R.SR_INFORMATIF:g}, même grille",
          *_distribution(si),
          f"- Part des combinaisons où n* est la colonne 0 : {_pc(si['part_etoile_colonne_0'])} ; "
          f"Sharpe réalisé de la colonne 0 : {_n(si['sharpe_realise_colonne_0'])}", "",
          "## Contrôle négatif (décide)",
          f"{n['pbo']['n']} graines neuves ({n['graines'][0]} à {n['graines'][1]}), même taille, "
          f"sans avantage. Réussi si la moyenne des PBO est dans [{_pc(R.BORNES_NEGATIF[0])} ; "
          f"{_pc(R.BORNES_NEGATIF[1])}].",
          f"- Moyenne : **{_pc(n['moyenne'])}** (erreur-type {_pc(n['erreur_type'])})",
          f"- PBO par graine : {_q(n['pbo'], pc=True)}",
          f"- **Contrôle négatif : {'réussi' if n['reussi'] else 'RATÉ'}**", "",
          "### Rapporté (ne décide rien) : graine 0 seule, sans avantage",
          *_distribution(n["graine_0"]), ""]
    if s["voie_c"] is None:
        md += ["## Voie C", f"**Arrêt : {s['arret']}.** Aucune donnée de la voie C n'a été lue, "
               "aucun verdict.", ""]
    else:
        v = s["voie_c"]
        d = v["dedoublonnage"]
        md += ["## Voie C",
               f"- Fenêtre d'évaluation : {v['fenetre']['debut']} → {v['fenetre']['fin']}, "
               f"{v['fenetre']['n_jours']} jours, {R.S} blocs de {R.JOURS_PAR_BLOC}",
               f"- Configurations : **{d['n_grille']} avant**, {d['n_groupes']} groupes (option b, "
               f"cible {R.CIBLE_GARDEE:.0%} gardée), {d['n_doublons_exacts']} doublon(s) exact(s) "
               f"retiré(s), **{d['n_apres']} après**",
               *(f"  - doublon : {_nom(x['config'])} = {_nom(x['identique_a'])}"
                 for x in d["doublons"]),
               *_distribution(v["pbo"]),
               "- Configurations le plus souvent choisies comme n* :",
               *(f"  - {_nom(e['config'])} : {_pc(e['part'])} des combinaisons"
                 for e in v["etoiles_frequentes"]), "",
               "## Verdict mécanique",
               f"PBO = {_pc(v['pbo']['pbo'])}, seuil {_pc(R.SEUIL_VOIE_C)} : "
               f"**{VERDICT[s['verdict']]}**.", ""]
    c = s["compteur"]
    md += ["## Compteur",
           f"Diagnostic, aucun essai : global {c['avant']['global']} → {c['apres']['global']}, "
           f"invest {c['avant']['invest']} → {c['apres']['invest']}, trading "
           f"{c['avant']['trading']} → {c['apres']['trading']}.", "",
           "Rapport écrit par le programme (`beta/pbo_voie_c/rapport.py`), sans interprétation."]
    return "\n".join(md) + "\n"


def resume(s: dict) -> str:
    """Message court du salon BETA. Pastille mecanique : verte si candidate, orange si
    surajustee ou arret aux controles."""
    p, n = s["positif"], s["negatif"]
    pastille = "🟢" if s["verdict"] == "candidate" else "🟠"
    md = [f"# {pastille} PBO de la voie C (PBOC) — rapport du programme — {s['calcule_le'][:10]}",
          "",
          f"- **Contrôle positif** (Sharpe {R.SR_POSITIF:g}, graine 0) : PBO {_pc(p['pbo'])} → "
          f"{'réussi' if p['reussi'] else 'RATÉ'} (seuil ≤ {_pc(R.SEUIL_POSITIF)}). Informatif, "
          f"Sharpe {R.SR_INFORMATIF:g} : {_pc(p['avantage'][f'{R.SR_INFORMATIF:g}']['pbo'])}",
          f"- **Contrôle négatif** (graines {n['graines'][0]}-{n['graines'][1]}) : moyenne "
          f"{_pc(n['moyenne'])} → {'réussi' if n['reussi'] else 'RATÉ'} (bornes "
          f"{_pc(R.BORNES_NEGATIF[0])}-{_pc(R.BORNES_NEGATIF[1])}). Graine 0 seule : "
          f"{_pc(n['graine_0']['pbo'])}"]
    if s["voie_c"] is None:
        md.append(f"- **Arrêt** : {s['arret']}. Aucune donnée de la voie C lue.")
    else:
        v = s["voie_c"]
        md += [f"- **Voie C** : {v['dedoublonnage']['n_grille']} → "
               f"{v['dedoublonnage']['n_apres']} configurations, PBO **{_pc(v['pbo']['pbo'])}** → "
               f"**{VERDICT[s['verdict']]}** (seuil {_pc(R.SEUIL_VOIE_C)})"]
    c = s["compteur"]
    md += ["", f"Diagnostic, aucun essai : global {c['apres']['global']}, invest "
           f"{c['apres']['invest']} (inchangés). Code `{s['code']}`, préenregistrement "
           f"`{s['preenregistrement']}`.", "",
           "Message écrit par le programme (`beta/pbo_voie_c/rapport.py`), sans interprétation."]
    return "\n".join(md) + "\n"


def ecrire(s: dict) -> None:
    ca.SORTIE.mkdir(parents=True, exist_ok=True)
    (ca.SORTIE / "RAPPORT_PBO.md").write_text(markdown(s), encoding="utf-8")
    (ca.SORTIE / "RESUME_DISCORD.md").write_text(resume(s), encoding="utf-8")
    log.info("rapport ecrit : %s", ca.SORTIE / "RAPPORT_PBO.md")
