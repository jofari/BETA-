"""VC6 V2 : rapports ecrits par le programme a partir des resultats (aucun chiffre a la main).

Etape C : VC6_V2/coherence.md, les 4 tests de coherence du moteur, avant tout run.
"""

from __future__ import annotations

import subprocess

from beta import config
from beta.vc6.rapport import nb, oui, pc
from beta.vc6_v2 import regles as R

SORTIE_COHERENCE = config.RACINE / "VC6_V2" / "coherence.md"


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.RACINE,
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def _ligne_a(x: dict) -> str:
    if "raison" in x:
        nom = R.ESSAIS["poche_baissiere_har"]["nom"]
        return f"| a. « {nom} », E_BTC forcé à 1 | {x['raison']} | non |"
    return (f"| a. « {R.ESSAIS['poche_baissiere_har']['nom']} », E_BTC forcé à 1, contre la "
            f"« {R.REFERENCE_V1['nom']} » de la V1 | valeur finale {nb(x['valeur_finale_v2'], 6)} "
            f"contre {nb(x['valeur_finale_v1'], 6)} ; Ulcer {pc(x['ulcer_v2'], 4)} contre "
            f"{pc(x['ulcer_v1'], 4)} ; rendements des {x['jours']} jours identiques au bit près "
            f"au moteur de la V1 : {oui(x['rendements_identiques_moteur_v1'])}, à la mesure de la "
            f"V1 : {oui(x['rendements_identiques_mesure_v1'])} (écart maximal "
            f"{x['ecart_max']:.1e}) | "
            f"{oui(x['passe'])} |")


def _ligne_b(x: dict) -> str:
    return (f"| b. « {R.ESSAIS['har_sans_regime']['nom']} », Ei forcé à 1, sans frais, contre le "
            f"panier 50/25/25 rééquilibré chaque jour calculé à part | valeur finale "
            f"{nb(x['moteur'], 6)} contre {nb(x['independant'], 6)} ; écart "
            f"{pc(x['ecart_relatif'], 4)} (seuil 0,1 %) ; Ei = 1 tous les jours : "
            f"{oui(x['expositions_toutes_a_1'])} | {oui(x['passe'])} |")


def _ligne_c(x: dict) -> str:
    garde = ", ".join(f"{a} {n}" for a, n in x["jours_sans_rv_sigma_garde"].items())
    statut = {"passe": "les deux s'améliorent",
              "echec": "aucun ne s'améliore : alignement suspect",
              "un seul": "un seul s'améliore : cas non prévu"}[x["statut"]]
    return (f"| c. Anticipation, « {R.ESSAIS['har_sans_regime']['nom']} » : σ̂ remplacé par la "
            f"volatilité réalisée du jour t + 1 | Sharpe {nb(x['sharpe_normal'])} → "
            f"{nb(x['sharpe_anticipe'])} ; Ulcer {pc(x['ulcer_normal'], 2)} → "
            f"{pc(x['ulcer_anticipe'], 2)} ; {statut} ; jours sans RV, σ̂ gardé : {garde} | "
            f"{oui(x['passe'])} |")


def _ligne_d(x: dict) -> str:
    h, b = x["har_sans_regime"], x["poche_baissiere_har"]
    return (f"| d. Null, décalage circulaire de 0 jour, contre le résultat observé | "
            f"« {R.ESSAIS['har_sans_regime']['nom']} » (null des positions) : rendements "
            f"identiques au bit près {oui(h['circulaire_0_rendements_identiques'])}, Ulcer "
            f"identique {oui(h['circulaire_0_ulcer_identique'])} ; ordre identité des "
            f"{h['blocs']} blocs de 63 jours : {oui(h['blocs_identite_rendements_identiques'])} ; "
            f"« {R.ESSAIS['poche_baissiere_har']['nom']} » (null du mode) : série du mode "
            f"inchangée {oui(b['mode_identique'])}, rendements identiques au bit près "
            f"{oui(b['circulaire_0_rendements_identiques'])}, Ulcer identique "
            f"{oui(b['circulaire_0_ulcer_identique'])} | {oui(x['passe'])} |")


def ecrire_coherence(res: dict, compteurs: dict, empreinte: str) -> str:
    L: list[str] = []
    a = L.append
    j = res["jours"]
    a("# VC6 V2 — tests de cohérence du moteur (avant tout run)")
    a("")
    a(f"- Écrit par le programme (`scripts/vc6_v2.py --coherence`, commit `{_commit()}`), règles "
      f"`{empreinte}`, préenregistrement `VC6_V2/PREENREGISTREMENT.md` (gel vérifié avant de "
      "lancer).")
    a(f"- Période principale : rendements du {j['debut']} au {j['fin']} ({j['n']} jours).")
    a(f"- Compteurs : invest **{compteurs['invest']}** (59 + 2 essais), global "
      f"{compteurs['global']}, trading {compteurs['trading']}.")
    a("- Aucun run d'essai : ni témoin, ni null tiré au hasard, ni règle de décision. Les runs "
      "attendent le GO de Jonas.")
    issue = ("les 4 tests passent" if res["passe"]
             else f"ARRÊT au test {res.get('arret', '?')}")
    a(f"- **Résultat : {issue}.**")
    a("")
    a("| test | résultat | passe |")
    a("|---|---|---|")
    lignes = {"a": _ligne_a, "b": _ligne_b, "c": _ligne_c, "d": _ligne_d}
    for k in "abcd":
        if k in res:
            a(lignes[k](res[k]))
        else:
            a(f"| {k}. | non lancé (arrêt au test {res.get('arret', '?')}) | — |")
    a("")
    a("- Test a : référence = le moteur de la V1 sur les mêmes entrées et les rendements que la V1 "
      "a mesurés le 02/11 (`data/vc6_temps2/resultats.pkl`, vérifiés par le correctif du 02/11).")
    a("- Test b : calcul à part = `VC6_V1/temps2/verif_independante.py`, le script du test b de la "
      "V1, qui n'importe rien de BETA.")
    a("- Test c : il calcule le Sharpe et l'Ulcer observés de « V2 – HAR sans régime », sans "
      "témoin ni nulls ; ces deux chiffres sont donc connus avant le GO (c'est pourquoi la V2 est "
      "préenregistrée avant les tests).")
    a("- Test d : il ne rend que des égalités, pas les chiffres des essais.")
    a("")
    SORTIE_COHERENCE.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(SORTIE_COHERENCE)
