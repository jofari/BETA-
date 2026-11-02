"""VC6 V1, Temps 2 : le rapport, ecrit par le programme a partir des resultats (aucun chiffre a la
main). Sortie : VC6_V1/rapport_temps2.md."""

from __future__ import annotations

import math
import subprocess

from beta import config
from beta.vc6 import regles as R

SORTIE = config.RACINE / "VC6_V1" / "rapport_temps2.md"
NOMS = {k: v["nom"] for k, v in R.VARIANTES.items()}


def pc(x, d=1, signe=False) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    s = f"{x * 100:+.{d}f}" if signe else f"{x * 100:.{d}f}"
    return s.replace(".", ",").replace("-", "−") + " %"


def nb(x, d=2) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def oui(b) -> str:
    return "—" if b is None else ("oui" if b else "non")


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=config.RACINE,
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return "?"


def _ligne_mesures(nom: str, m: dict) -> str:
    return (f"| {nom} | {pc(m['ulcer'], 2)} | {pc(m['mdd'])} | {pc(m['cagr'])} | "
            f"{nb(m['sharpe'])} | {nb(m['ratio_cagr_ulcer'])} | {nb(m.get('dsr'), 3)} | "
            f"{nb(m['expo_moyenne'], 3)} | {nb(m['changements_par_an'], 1)} | "
            f"{pc(m['financement'], 2) if m['financement'] is not None else '—'} | "
            f"{pc(m['frais'], 2)} | "
            f"{m['jours_contraints'] if m['jours_contraints'] is not None else '—'} |")


ENTETE = ("| série | Ulcer | drawdown max | rendement annualisé | Sharpe √365 | rendement / Ulcer "
          "| Sharpe déflaté | exposition moyenne | changements / an | financement payé "
          "| frais payés | jours contraints |\n|---|---|---|---|---|---|---|---|---|---|---|---|")


def _sol_replis(res: dict) -> dict:
    """Jours de decision de la periode principale ou le sigma de SOL est le repli du HAR."""
    from beta.controle_har import campagne as hc
    from beta.vc6 import donnees as dn
    b = dn.barres_5m("SOL")
    p = hc.previsions(b)
    jours = res["jours"][:-1]
    av = p["avant_730"].reindex(jours.tz_localize(None) if jours.tz else jours)
    debut = p.index[p["jours_rv"] >= 730][0]
    return {"premiere": f"{b.index.min():%Y-%m-%d %H:%M} UTC", "har_des_le": f"{debut:%Y-%m-%d}",
            "jours_repli": int(av.sum()), "jours": int(len(jours))}


def ecrire(res: dict) -> str:
    L: list[str] = []
    a = L.append
    runs = res["runs"]
    coh = res["coherence"]
    a("# VC6 V1 — rapport du « Temps 2 »")
    a("")
    a(f"- Écrit par le programme (`scripts/vc6_temps2.py`, commit `{_commit()}`), règles "
      f"`{res['empreinte_regles']}`, préenregistrement `VC6_V1/temps2/PREENREGISTREMENT.md`.")
    a(f"- Période principale : rendements du {res['periode']['debut']} au "
      f"{res['periode']['fin']} ({res['periode']['n_jours']} jours).")
    a(f"- Compteurs : invest **{res['compteurs']['invest']}** (54 + 5 essais), global "
      f"{res['compteurs']['global']}, trading {res['compteurs']['trading']}. Sharpe déflaté au N "
      f"invest = {res['n_essais_invest']}.")
    a("- Backtest de diagnostic : il peut éliminer des choix, pas les valider.")
    a("")
    a("## 1. Tests de cohérence du moteur (avant tout run)")
    a("")
    ab = coh["a_b"]
    a("| test | moteur | calcul à part | écart | passe |")
    a("|---|---|---|---|---|")
    a(f"| a1. BTC seul, SMA 200, exposition 1, bascule immédiate, sans frais | "
      f"{nb(ab['a1']['moteur'], 6)} | {nb(ab['a1']['independant'], 6)} | "
      f"{pc(ab['a1']['ecart_relatif'], 4)} | {oui(ab['a1']['passe'])} |")
    a(f"| a2. BTC seul, exposition 1, rampe 5 jours, poche baissière 25 % BTC, sans frais | "
      f"{nb(ab['a2']['moteur'], 6)} | {nb(ab['a2']['independant'], 6)} | "
      f"{pc(ab['a2']['ecart_relatif'], 4)} | {oui(ab['a2']['passe'])} |")
    a(f"| b. Panier 50/25/25 rééquilibré chaque jour, sans régime ni frais | "
      f"{nb(ab['b']['moteur'], 6)} | {nb(ab['b']['independant'], 6)} | "
      f"{pc(ab['b']['ecart_relatif'], 4)} | {oui(ab['b']['passe'])} |")
    for nom, c in coh["c"].items():
        a(f"| c. Anticipation ({nom}) : valeur finale normale → anticipée ; Ulcer | "
          f"{nb(c['valeur_normale'], 3)} → {nb(c['valeur_anticipee'], 3)} | Ulcer "
          f"{pc(c['ulcer_normal'], 2)} → {pc(c['ulcer_anticipe'], 2)} | amélioration attendue | "
          f"{oui(c['passe'])} |")
    d = coh["d"]
    a(f"| d. Aller-retour de 100 % du capital (rendements nuls) | frais "
      f"{nb(d['frais_total'], 6)}, valeur {nb(d['valeur_finale'], 6)} | "
      f"{nb(d['attendu'], 6)} ; {nb(d['valeur_attendue'], 6)} | 0 | {oui(d['passe'])} |")
    e = coh["e"]
    a(f"| e. Funding, semaine du {e['semaine'][0]} au {e['semaine'][1]} (tirée parmi "
      f"{e['semaines_candidates']} semaines à Ei = 2, graine 0) | {e['moteur']:.12e} | "
      f"{e['a_la_main']:.12e} | {e['ecart']:.1e} | {oui(e['passe'])} |")
    a("")
    a("Le calcul à part des tests a et b est `VC6_V1/temps2/verif_independante.py`. Il "
      "n'importe rien de BETA. Le test e refait la somme à la main sur les règlements bruts de "
      "chaque jour.")
    a("")
    # --------------------------------------------------------------------------------- mesures
    a("## 2. Mesures")
    a("")
    a(ENTETE)
    for k in ("fixe", "vol", "annexe40", "or", "mixte"):
        a(_ligne_mesures(NOMS[k], runs[k]["mesures"]))
        a(_ligne_mesures(f"Témoin expo constante ({NOMS[k]})", runs[k]["temoin"]["mesures"]))
    a(_ligne_mesures("Panier buy and hold 50/25/25", res["references"]["panier"]))
    a(_ligne_mesures("ETF monde (URTH)", res["references"]["etf_monde"]))
    a("")
    a("Nulls D4 (B = 1 000 tirages chacun, signal = série du mode, métrique = Ulcer) :")
    a("")
    a("| essai | Ulcer | Ulcer du témoin | p circulaire | p segments | p retenue | verdict D4 "
      "| Ulcer nul médian (circulaire / segments) |")
    a("|---|---|---|---|---|---|---|---|")
    for k in ("fixe", "vol", "annexe40", "or", "mixte"):
        n = runs[k]["nulls"]
        a(f"| {NOMS[k]} | {pc(runs[k]['mesures']['ulcer'], 2)} | "
          f"{pc(runs[k]['temoin']['mesures']['ulcer'], 2)} | {nb(n['p_circulaire'], 3)} | "
          f"{nb(n['p_segments'], 3)} | {nb(n['p_retenue'], 3)} | {n['verdict_d4']} | "
          f"{pc(n['ulcer_nul_median']['circulaire'], 2)} / "
          f"{pc(n['ulcer_nul_median']['segments'], 2)} |")
    a("")
    a("PBO (S10, 16 blocs, Sharpe), **rapportée sans effet** (addendum du 02/11) :")
    a("")
    for nom, p in res["pbo"].items():
        a(f"- {nom.replace('_', ' ')} : PBO = {pc(p['pbo'])}"
          f"{'' if p['pbo'] is not None else ' (' + str(p['raison']) + ')'} ; "
          f"{p['n_configs']} configurations distinctes, {p['n_jours']} jours ; sous le seuil de "
          f"20 % : {oui(p['passe'])}.")
    a("")
    # --------------------------------------------------------------------------------- regles
    rg = res["regles"]
    a("## 3. Règles de décision")
    a("")
    r1 = rg["1"]
    txt = " ; ".join(f"{NOMS[k]} : Ulcer {pc(v['ulcer'], 2)} contre témoin "
                     f"{pc(v['ulcer_temoin'], 2)}, p {nb(v['p_retenue'], 3)} → "
                     f"{'utile' if v['utile'] else 'pas utile'}"
                     for k, v in r1.items() if k != "annexe40")
    a(f"1. **Utile = Ulcer < témoin avec p < 0,05.** {txt}. (Test annexe, non éligible : "
      f"{'utile' if r1['annexe40']['utile'] else 'pas utile'} au même critère, rapporté "
      "seulement.)")
    rf, rv = runs["fixe"]["mesures"]["ratio_cagr_ulcer"], runs["vol"]["mesures"]["ratio_cagr_ulcer"]
    a(f"2. **« Variante expo vol » retenue si utile et ratio > celui de « Variante expo fixe ».** "
      f"Ratio rendement / Ulcer : expo vol {nb(rv)}, expo fixe {nb(rf)} ; expo vol utile : "
      f"{oui(r1['vol']['utile'])} → retenue : {oui(rg['2']['regle2_vol_retenue'])}. Meilleure "
      f"désignée : **{NOMS[rg['2']['meilleure']]}** ({rg['2']['note']}).")
    base = runs[rg["2"]["meilleure"]]["mesures"]
    t3 = " ; ".join(f"{NOMS[k]} : Ulcer {pc(runs[k]['mesures']['ulcer'], 2)} contre "
                    f"{pc(base['ulcer'], 2)} ({'plus bas' if rg['3'][k]['ulcer_plus_bas'] else 'pas plus bas'}), "
                    f"rendement annualisé {pc(runs[k]['mesures']['cagr'])} contre seuil "
                    f"{pc(base['cagr'] - 0.02)} → {'remplace' if rg['3'][k]['remplace'] else 'ne remplace pas'}"
                    for k in ("or", "mixte"))
    a(f"3. **Poche or ou mixte si Ulcer plus bas et rendement ≥ meilleure à poche BTC − 2 "
      f"points.** {t3}. Conclusion : **{rg['3']['conclusion']}**.")
    a(f"4. **Aucune variante de sizing utile → exposition constante × HAR.** Aucune utile : "
      f"{oui(rg['4']['aucune_utile'])}"
      f"{' → conclusion : exposition constante × HAR' if rg['4']['aucune_utile'] else ''}.")
    a("")
    # --------------------------------------------------------------------------------- verdict
    a("## 4. Grille du verdict VC6 (pour info seulement)")
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
      "réalisée (application 25).")
    a("")
    # --------------------------------------------------------------------------------- levier
    a("## 5. Levier")
    a("")
    a("| essai | exposition moyenne | jours avec Ei > 1 | rendement de ces jours | drawdown de ces "
      "jours | financement payé ces jours | gain de la part en levier |")
    a("|---|---|---|---|---|---|---|")
    for k, v in res["levier"].items():
        a(f"| {NOMS[k]} | {nb(v['expo_moyenne'], 3)} | {v['jours']} | {pc(v['rendement'], 2)} | "
          f"{pc(v['drawdown'], 2)} | {pc(v['financement'], 3)} | "
          f"{pc(v['gain_part_en_levier'], 3)} |")
    a("")
    # --------------------------------------------------------------------------------- SMA
    a("## 6. SMA 200 : retard de sortie et aller-retours")
    a("")
    a("Grands bears (baisse du BTC ≥ 30 % depuis son plus haut, période principale) :")
    a("")
    a("| plus haut | creux | retour au plus haut | baisse du BTC | bascule en baissier | délai "
      "(jours) | baisse du BTC avant la bascule | perte des variantes avant la bascule |")
    a("|---|---|---|---|---|---|---|---|")
    for b in res["grands_bears"]:
        pv = " ; ".join(f"{NOMS[k]} {pc(x)}" for k, x in b["perte_variantes"].items())
        a(f"| {b['pic']} | {b['creux']} | {b['fin'] or 'pas encore'} | {pc(b['baisse_btc'])} | "
          f"{b['bascule'] or '—'} | {b['delai_j'] if b['delai_j'] is not None else '—'} | "
          f"{pc(b['baisse_btc_avant_bascule'])} | {pv or '—'} |")
    a("")
    ar = res["analyses"]["fixe"]["aller_retours"]
    a(f"Aller-retours autour de la SMA 200 (bascule annulée en moins de 30 jours ; le mode est le "
      f"même pour toutes les variantes) : **{ar['n']}**.")
    a("")
    a("| essai | frais des aller-retours | rendement contre le témoin sur ces fenêtres |")
    a("|---|---|---|")
    for k in ("fixe", "vol", "annexe40", "or", "mixte"):
        x = res["analyses"][k]["aller_retours"]
        a(f"| {NOMS[k]} | {pc(x['frais_total'], 3)} | {pc(x['ecart_temoin_total'], 2, True)} |")
    a("")
    if ar["detail"]:
        a("Détail : " + " ; ".join(f"{x['bascule']} → {x['retour']} ({x['duree_j']} j, vers "
                                   f"{x['vers']})" for x in ar["detail"]) + ".")
        a("")
    # --------------------------------------------------------------------------------- coince
    a("## 7. Où ça coince")
    a("")
    for k in ("fixe", "vol", "annexe40", "or", "mixte"):
        an = res["analyses"][k]
        m = runs[k]["mesures"]
        a(f"### {NOMS[k]}")
        a("")
        a("| début | creux | récupération | profondeur | mode au début | exposition au début |")
        a("|---|---|---|---|---|---|")
        for x in an["pires_drawdowns"]:
            a(f"| {x['debut']} | {x['creux']} | {x['recuperation'] or 'pas encore'} | "
              f"{pc(x['profondeur'])} | {x['mode_au_debut']} | {nb(x['expo_au_debut'], 3)} |")
        a("")
        c = an["contributions"]
        a("Contributions (somme des rendements quotidiens) : " + " ; ".join(
            f"{x.replace('poche:', 'poche ').replace('baissiere:', 'poche baissière ')} "
            f"{pc(v, 1, True)} (pendant le drawdown max : {pc(c['drawdown_max'][x], 1, True)})"
            for x, v in c["total"].items()) + ".")
        a("")
        cf = an["conflits"]
        a(f"Frais + financement : {pc(m['frais'] + (m['financement'] or 0), 2)}. Jours en rampe : "
          f"{m['jours_en_rampe']}. Jours de conflit (BTC baissier, ETH ou SOL au-dessus de sa "
          f"SMA 200) : {cf['jours']} ; effet (ce que les poches auraient fait investies) : "
          + " ; ".join(f"{a_} {cf['par_poche'][a_]['jours']} j, {pc(cf['par_poche'][a_]['effet'], 1, True)}"
                       for a_ in cf["par_poche"])
          + f" ; total {pc(cf['effet_total'], 1, True)}. Jours inverses (BTC haussier, ETH ou SOL "
          f"sous sa SMA 200) : {cf['inverse']['jours']} ; rendement des poches ces jours-là : "
          + " ; ".join(f"{a_} {v['jours']} j, {pc(v['rendement_poche'], 1, True)}"
                       for a_, v in cf["inverse"]["par_poche"].items())
          + f" ; total {pc(cf['inverse']['total'], 1, True)}.")
        a("")
        vr = an["vol_realisee"]
        a("Volatilité réalisée des poches investies (Ei × r, √365) contre la cible : " + " ; ".join(
            f"{x} {pc(v['vol'])} sur {v['jours']} j (cible {pc(v['cible'], 0)})"
            for x, v in vr.items()) + ".")
        a("")
    pb = res["perp_bitstamp"]
    a(f"Mode global perpétuel contre Bitstamp, du {pb['debut']} au {pb['fin']} ({pb['jours']} "
      f"jours) : **{pb['jours_differents']} jours différents**"
      + (f" ({', '.join(pb['dates'][:20])}{'…' if len(pb['dates']) > 20 else ''})."
         if pb["dates"] else "."))
    a("")
    # --------------------------------------------------------------------------------- robustesse
    rob = res["robustesse"]
    a("## 8. Robustesse : BTC seul depuis 2014")
    a("")
    a(f"**σ̂ = écart-type 30 jours** des rendements log journaliers de Bitstamp au comptant pour ce "
      f"test : les bougies 5 min ne remontent qu'au 08/09/2019. Funding fixe de 0,01 % par "
      f"règlement de 8 h avant le 10/09/2019, puis funding réel du perpétuel BTC. Rendements du "
      f"{rob['debut']} au {res['periode']['fin']} ({rob['n_jours']} jours). Poche unique 100 % "
      "BTC, poche baissière 25 % BTC.")
    a("")
    a(ENTETE)
    for k in ("fixe", "vol"):
        a(_ligne_mesures(f"{NOMS[k]} (BTC seul)", rob["runs"][k]["mesures"]))
        a(_ligne_mesures(f"Témoin expo constante ({NOMS[k]}, BTC seul)",
                         rob["runs"][k]["temoin"]["mesures"]))
    a(_ligne_mesures("BTC buy and hold (Bitstamp)", rob["hold_btc"]))
    a("")
    for k in ("fixe", "vol"):
        n = rob["runs"][k]["nulls"]
        lv = rob["runs"][k]["levier"]
        a(f"- {NOMS[k]} (BTC seul) : p circulaire {nb(n['p_circulaire'], 3)}, p segments "
          f"{nb(n['p_segments'], 3)}, p retenue {nb(n['p_retenue'], 3)} ({n['verdict_d4']}) ; "
          f"utile au critère de la règle 1 : {oui(rob['runs'][k]['utile'])} ; jours en levier "
          f"{lv['jours']}, financement de ces jours {pc(lv['financement'], 3)}.")
    a("")
    a("| plus haut | creux | baisse du BTC | bascule | délai (jours) | baisse avant la bascule |")
    a("|---|---|---|---|---|---|")
    for b in rob["grands_bears"]:
        a(f"| {b['pic']} | {b['creux']} | {pc(b['baisse_btc'])} | {b['bascule'] or '—'} | "
          f"{b['delai_j'] if b['delai_j'] is not None else '—'} | "
          f"{pc(b['baisse_btc_avant_bascule'])} |")
    a("")
    # --------------------------------------------------------------------------------- red team
    a("## 9. Red team")
    a("")
    ana = res["analyses"]
    mv, ma = runs["vol"]["mesures"], runs["annexe40"]["mesures"]
    a(f"1. **Cible de 25 % trop proche de la limite de drawdown de 25 %, levier jusqu'à ×2.** "
      f"Drawdown max : « Variante expo vol » {pc(mv['mdd'])}, « Test annexe – cible 40 % » "
      f"{pc(ma['mdd'])}. Jours avec Ei > 1 : {res['levier']['vol']['jours']} (expo vol), "
      f"{res['levier']['annexe40']['jours']} (annexe). → "
      f"{'confirmé' if mv['mdd'] < -0.25 else 'infirmé'} pour la « Variante expo vol » "
      f"(drawdown {'au-delà' if mv['mdd'] < -0.25 else 'en deçà'} de 25 %)"
      f"{' ; levier jamais utilisé à la cible de 25 %' if res['levier']['vol']['jours'] == 0 else ''}.")
    sl = {k: ana[k]["sortie_lente"] for k in ("fixe", "vol", "annexe40")}
    pire = sl["fixe"]["pire"]
    a(f"2. **Sortie lente sur 5 jours pendant un krach.** Coût total des rampes vers le "
      f"baissier par rapport à une sortie immédiate : " + " ; ".join(
          f"{NOMS[k]} {pc(v['cout_total'], 2, True)} sur {v['n']} rampes" for k, v in sl.items())
      + (f". Pire rampe (expo fixe) : {pire['bascule']}, coût {pc(pire['cout'], 2, True)}, BTC "
         f"{pc(pire['btc_rampe'], 1, True)} pendant la rampe" if pire else "")
      + f". → {'confirmé' if sl['fixe']['cout_total'] > 0 else 'infirmé'} sur la période (coût "
      f"{'positif' if sl['fixe']['cout_total'] > 0 else 'négatif ou nul'}).")
    sol_vol = ana["vol"]["vol_realisee"]["SOL"]
    c_sol = ana["vol"]["contributions"]["total"].get("poche:SOL")
    sol = _sol_replis(res)
    a(f"3. **Peu d'historique pour SOL.** Première barre 5 min du perpétuel : {sol['premiere']} ; "
      f"le HAR de SOL n'a ses 730 jours de RV que le {sol['har_des_le']}, il est remplacé avant "
      f"par l'écart-type 30 jours ({sol['jours_repli']} jours de décision de la période "
      f"principale sur {sol['jours']}). Volatilité réalisée de "
      f"la poche SOL (expo vol) {pc(sol_vol['vol'])} contre {pc(sol_vol['cible'], 0)} ; "
      f"contribution de SOL {pc(c_sol, 1, True)}. → confirmé comme limite (non mesurable comme "
      "effet).")
    nb_bears = len(res["grands_bears"])
    a(f"4. **Un seul grand bear (2022).** Grands bears (≥ 30 %) sur la période principale : "
      f"{nb_bears} ; depuis 2014 (Bitstamp) : {len(rob['grands_bears'])}. → "
      f"{'confirmé' if nb_bears <= 1 else 'infirmé'} sur la période principale.")
    cf = ana["vol"]["conflits"]
    a(f"5. **Sortie forcée par le BTC.** Jours de conflit : {cf['jours']} ; ce qu'ETH et SOL "
      f"auraient fait investis ces jours-là (expo vol) : {pc(cf['effet_total'], 1, True)}. → "
      f"{'confirmé (gain manqué)' if cf['effet_total'] > 0 else 'infirmé (la sortie a évité une perte)'}.")
    cb = ana["vol"]["contributions"]["total"].get("baissiere:BTC")
    cbo = ana["or"]["contributions"]["total"].get("baissiere:XAU")
    a(f"6. **Poche baissière BTC sans multiplicateur.** Contribution de la poche baissière BTC "
      f"(expo vol) : {pc(cb, 1, True)} ; poche or (« Variante poche or ») : "
      f"{pc(cbo, 1, True)}. → {'confirmé (la poche BTC perd)' if (cb or 0) < 0 else 'infirmé (la poche BTC gagne)'}.")
    a("")
    # --------------------------------------------------------------------------------- prediction
    pr = res["prediction"]
    a("## 10. Comparaison avec la prédiction de Jonas (lecture chiffrée)")
    a("")
    h = pr["har"]
    a(f"- **HAR ≈ écart-type 30 jours** : écart relatif des QLIKE moyennes (Contrôle HAR) "
      + ", ".join(f"{k} {pc(v)}" for k, v in h["ecarts_relatifs"].items())
      + f" ; {h['actifs_a_moins_de_10pc']} actif(s) sur 3 à moins de 10 % → **{h['statut']}**.")
    a(f"- **Volatilité peu efficace** (« Variante expo vol » échoue à la règle 1) : utile = "
      f"{oui(pr['volatilite']['vol_utile'])} → **{pr['volatilite']['statut']}**.")
    lv = pr["levier"]
    a(f"- **Levier mal utilisé** (test annexe : gain de la part en levier < financement payé, "
      f"sur {lv['jours']} jours en levier) : gain {pc(lv['gain_part_en_levier'], 3)}, financement "
      f"{pc(lv['financement'], 3)} → **{lv['statut']}**.")
    dd = pr["drawdown"]
    a(f"- **Drawdown > 40 %** pour au moins une variante ou le test annexe : "
      + ", ".join(f"{NOMS[k]} {pc(v)}" for k, v in dd["mdd"].items())
      + f" → **{dd['statut']}**.")
    a("- **SMA unique** : **non mesurable** ici ; voir le retard de sortie et les aller-retours "
      "(section 6).")
    a("")
    SORTIE.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(SORTIE)
