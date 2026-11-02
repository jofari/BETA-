"""VC6 V2 : rapports ecrits par le programme a partir des resultats (aucun chiffre a la main).

Etape C : VC6_V2/coherence.md, les 4 tests de coherence du moteur, avant tout run.
GO du 02/11/2026 : VC6_V2/rapport_v2.md, le rapport des runs (`ecrire`).
"""

from __future__ import annotations

import subprocess

from beta import config
from beta.vc6.rapport import ENTETE, _ligne_mesures, nb, oui, pc
from beta.vc6_v2 import regles as R

SORTIE_COHERENCE = config.RACINE / "VC6_V2" / "coherence.md"
SORTIE = config.RACINE / "VC6_V2" / "rapport_v2.md"
NOMS = {k: v["nom"] for k, v in R.ESSAIS.items()}
NOM_V1 = R.REFERENCE_V1["nom"]
NULLS = {"positions": "positions (décalage circulaire ; blocs de 63 jours permutés)",
         "mode": "mode (décalage circulaire ; segments mélangés)"}


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


# ================================================================================ rapport des runs

def _table_coherence(a, coh: dict) -> None:
    a("| test | résultat | passe |")
    a("|---|---|---|")
    lignes = {"a": _ligne_a, "b": _ligne_b, "c": _ligne_c, "d": _ligne_d}
    for k in "abcd":
        a(lignes[k](coh[k]))


def _table_nulls(a, runs: dict, suffixe: str = "") -> None:
    a("| essai | null | Ulcer | Ulcer du témoin | p circulaire | p segments | p retenue | "
      "verdict D4 | Ulcer nul médian (circulaire / segments) |")
    a("|---|---|---|---|---|---|---|---|---|")
    for k, run in runs.items():
        n = run["nulls"]
        a(f"| {NOMS[k]}{suffixe} | {NULLS[run['null']]} | {pc(run['mesures']['ulcer'], 2)} | "
          f"{pc(run['temoin']['mesures']['ulcer'], 2)} | {nb(n['p_circulaire'], 3)} | "
          f"{nb(n['p_segments'], 3)} | {nb(n['p_retenue'], 3)} | {n['verdict_d4']} | "
          f"{pc(n['ulcer_nul_median']['circulaire'], 2)} / "
          f"{pc(n['ulcer_nul_median']['segments'], 2)} |")


def _detail(a, cle: str, run: dict, jours: str) -> None:
    """Le detail par essai demande par le prompt du GO."""
    an = run["analyses"]
    m = run["mesures"]
    regime = R.ESSAIS[cle]["regime"]
    a(f"### {NOMS[cle]}{jours}")
    a("")
    a("5 pires drawdowns :")
    a("")
    if regime:
        a("| début | creux | récupération | profondeur | mode au début | exposition au début |")
        a("|---|---|---|---|---|---|")
    else:
        a("| début | creux | récupération | profondeur | exposition au début |")
        a("|---|---|---|---|---|")
    for x in an["pires_drawdowns"]:
        mode = f" {x['mode_au_debut']} |" if regime else ""
        a(f"| {x['debut']} | {x['creux']} | {x['recuperation'] or 'pas encore'} | "
          f"{pc(x['profondeur'])} |{mode} {nb(x['expo_au_debut'], 3)} |")
    a("")
    c = an["contributions"]
    a("Contributions (somme des rendements quotidiens) : " + " ; ".join(
        f"{x.replace('poche:', 'poche ').replace('baissiere:', 'poche baissière ')} "
        f"{pc(v, 1, True)} (pendant le drawdown max : {pc(c['drawdown_max'][x], 1, True)})"
        for x, v in c["total"].items()) + ".")
    a("")
    a("Volatilité réalisée des poches investies (Ei × r, √365) contre la cible de 25 % : "
      + " ; ".join(f"{x} {pc(v['vol'])} sur {v['jours']} j" for x, v in an["vol_realisee"].items())
      + ".")
    a("")
    lv = an["levier"]
    a(f"Jours avec Ei > 1 : {lv['jours']} (financement payé ces jours-là : "
      f"{pc(lv['financement'], 3)} ; gain de la part en levier : "
      f"{pc(lv['gain_part_en_levier'], 3)}). Frais payés : {pc(m['frais'], 2)} ; financement "
      f"payé : {pc(m['financement'], 3)} ; jours contraints par la sécurité de liquidation : "
      f"{m['jours_contraints']}.")
    a("")


def ecrire(res: dict) -> str:
    L: list[str] = []
    a = L.append
    runs = res["runs"]
    rob = res["robustesse"]
    per = res["periode"]
    a("# VC6 V2 — rapport des runs")
    a("")
    a(f"- Écrit par le programme (`scripts/vc6_v2.py --go`, commit `{_commit()}`), règles "
      f"`{res['empreinte_regles']}`, préenregistrement `VC6_V2/PREENREGISTREMENT.md`, spec "
      "`VC6_V2/spec_figee.md` (gel vérifié avant de lancer).")
    a("- Points de lecture validés par Jonas le 02/11/2026, tels quels (applications 10, 16, 18 et "
      "24 du préenregistrement).")
    a(f"- Période principale : rendements du {per['debut']} au {per['fin']} ({per['n_jours']} "
      f"jours). Robustesse : BTC seul, Bitstamp, rendements du {rob['debut']} au {rob['fin']} "
      f"({rob['n_jours']} jours).")
    a(f"- Compteurs : invest **{res['compteurs']['invest']}** (59 + 2 essais, journalisés au "
      f"préenregistrement ; rien d'ajouté au GO), global {res['compteurs']['global']}, trading "
      f"{res['compteurs']['trading']}. Sharpe déflaté au N invest = {res['n_essais_invest']}.")
    a("- Prédiction de Jonas : gardée par Jonas, hors du dépôt (`VC6_V2/prediction_jonas.md`) ; ce "
      "rapport n'a donc pas de section « prédiction ».")
    a("- Backtest de diagnostic : il peut éliminer des choix, pas les valider.")
    a("")
    # ---------------------------------------------------------------------------- coherence
    a("## 1. Tests de cohérence du moteur (relancés juste avant les runs)")
    a("")
    _table_coherence(a, res["coherence"])
    a("")
    # ---------------------------------------------------------------------------- mesures
    a("## 2. Mesures (période principale)")
    a("")
    a(ENTETE)
    for k, run in runs.items():
        a(_ligne_mesures(NOMS[k], run["mesures"]))
        a(_ligne_mesures(f"Témoin expo constante ({NOMS[k]})", run["temoin"]["mesures"]))
    a(_ligne_mesures(f"{NOM_V1} (V1)", res["v1"]["mesures"]))
    a(_ligne_mesures("Panier buy and hold 50/25/25", res["references"]["panier"]))
    a(_ligne_mesures("ETF monde (URTH)", res["references"]["etf_monde"]))
    a("")
    tirages = sorted({b for run in list(runs.values()) + list(rob["runs"].values())
                      for b in run["nulls"]["b"].values()})
    a(f"Nulls (B = {' / '.join(f'{b:,}'.replace(',', ' ') for b in tirages)} tirages chacun, "
      "graine 0, métrique = Ulcer, p retenue = la plus haute des deux) :")
    a("")
    _table_nulls(a, runs)
    a("")
    p = res["pbo"]
    a(f"PBO du choix entre les deux essais (S10, 16 blocs, Sharpe), **rapportée sans effet** : "
      f"PBO = {pc(p['pbo'])}"
      f"{'' if p['pbo'] is not None else ' (' + str(p['raison']) + ')'} ; "
      f"{p['n_configs']} configurations distinctes, {p['n_jours']} jours ; sous le seuil de "
      f"20 % : {oui(p['passe'])}.")
    a("")
    # ---------------------------------------------------------------------------- regles
    rg = res["regles"]
    a("## 3. Règles de décision")
    a("")
    t1 = " ; ".join(f"« {NOMS[k]} » : Ulcer {pc(v['ulcer'], 2)} contre témoin "
                    f"{pc(v['ulcer_temoin'], 2)}, p retenue {nb(v['p_retenue'], 3)} → "
                    f"{'utile' if v['utile'] else 'pas utile'}" for k, v in rg["1"].items())
    a(f"1. **Utile = Ulcer < celui de son témoin, avec p retenue < 0,05.** {t1}.")
    ratios = " ; ".join(f"« {NOMS[k]} » {nb(runs[k]['mesures']['ratio_cagr_ulcer'])}"
                        for k in runs)
    r2 = rg["2"]
    retenue = (f"**{NOMS[r2['retenue']]}**" if r2["retenue"] else "**aucune**")
    a(f"2. **Configuration retenue pour la suite.** Essais utiles : "
      f"{', '.join(NOMS[k] for k in r2['utiles']) or 'aucun'}. Ratio rendement annualisé / "
      f"Ulcer : {ratios}. Configuration retenue : {retenue} — {r2['conclusion']}.")
    a("")
    # ---------------------------------------------------------------------------- regle 3
    r3 = rg["3"]
    a("## 4. Règle 3 (rapportée, sans effet sur la décision)")
    a("")
    a("| série | Ulcer | drawdown max | rendement annualisé | contribution de la poche baissière "
      "pendant le drawdown max | contribution totale de la poche baissière |")
    a("|---|---|---|---|---|---|")
    for nom, x in ((NOMS["poche_baissiere_har"], r3["essai"]), (f"{NOM_V1} (V1)", r3["v1"])):
        a(f"| {nom} | {pc(x['ulcer'], 2)} | {pc(x['mdd'])} | {pc(x['cagr'])} | "
          f"{pc(x['baissiere_pendant_mdd'], 1, True)} | {pc(x['baissiere_total'], 1, True)} |")
    a("")
    a("Contribution = somme des rendements quotidiens de la poche baissière, entre le plus haut et "
      "le creux du drawdown max de chaque série (V1, application 30).")
    a("")
    # ---------------------------------------------------------------------------- verdict
    a("## 5. Grille du verdict VC6 (pour info seulement)")
    a("")
    a("| essai | Sharpe > 1 | drawdown max < 25 % | bat le panier à risque égal | bat l'ETF "
      "monde à risque égal |")
    a("|---|---|---|---|---|")
    for k, v in res["verdict_vc6"].items():
        a(f"| {NOMS[k]} | {nb(v['sharpe'])} → {oui(v['sharpe_sup_1'])} | {pc(v['mdd'])} → "
          f"{oui(v['mdd_sup_m25'])} | {pc(v['cagr'])} contre {pc(v['panier_risque_egal_cagr'])} → "
          f"{oui(v['bat_panier'])} | {pc(v['cagr'])} contre {pc(v['etf_risque_egal_cagr'])} → "
          f"{oui(v['bat_etf'])} |")
    a("")
    a("« Bat » = rendement annualisé plus haut que la référence ramenée à la même volatilité "
      "réalisée que l'essai.")
    a("")
    # ---------------------------------------------------------------------------- detail
    a("## 6. Détail par essai (période principale)")
    a("")
    for k, run in runs.items():
        _detail(a, k, run, "")
    # ---------------------------------------------------------------------------- robustesse
    a("## 7. Robustesse : BTC seul depuis 2014 (information, ne décide rien)")
    a("")
    a("σ̂ = écart-type 30 jours des rendements log journaliers de Bitstamp au comptant ; funding "
      "fixe de 0,01 % par règlement de 8 h avant le 10/09/2019, puis funding réel du perpétuel "
      "BTC ; une poche à 100 % ; poche baissière de « V2 – poche baissière sous HAR » = 25 % × "
      "clip(0,25/σ̂ ; 0,2 ; 1) (application 24).")
    a("")
    a(ENTETE)
    for k, run in rob["runs"].items():
        a(_ligne_mesures(f"{NOMS[k]} (BTC seul)", run["mesures"]))
        a(_ligne_mesures(f"Témoin expo constante ({NOMS[k]}, BTC seul)",
                         run["temoin"]["mesures"]))
    a(_ligne_mesures(f"{NOM_V1} (V1, BTC seul)", rob["v1"]["mesures"]))
    a(_ligne_mesures("BTC acheté et conservé (Bitstamp)", rob["references"]["btc"]))
    a(_ligne_mesures("ETF monde (URTH)", rob["references"]["etf_monde"]))
    a("")
    _table_nulls(a, rob["runs"], " (BTC seul)")
    a("")
    a("Utile au critère de la règle 1 (information) : " + " ; ".join(
        f"« {NOMS[k]} » {oui(run['utile'])}" for k, run in rob["runs"].items()) + ".")
    a("")
    for k, run in rob["runs"].items():
        _detail(a, k, run, " (BTC seul)")
    SORTIE.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(SORTIE)
