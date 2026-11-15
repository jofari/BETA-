"""La fiche de robustesse d'un run : tous les outils informatifs, sur des trades deja mesures.

CE N'EST NI UNE PORTE NI UN VERDICT (15/11/2026). La fiche relit `trades`, `equity` et la
courbe du hold d'un run DEJA enregistre : aucun signal n'est rejoue, aucune donnee de marche
n'est relue, aucun essai n'est consomme, et l'issue du run (`verdict.json`) n'est ni lue pour
decider, ni modifiee. Elle n'a aucun seuil : elle donne des chiffres a lire a cote des portes.

Les series journalieres sont celles de S7 et S10 (somme des R clotures chaque jour, 0 sans
cloture) : le Sharpe journalier de la fiche est donc sur la meme base que la PBO du lot.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.stats import multitest, pbo, risque, robustesse, sharpe

JOURS_AN = 365.0
AVERTISSEMENT = ("INFORMATIF : ni porte ni verdict. Chiffres calcules par le programme sur "
                 "les trades deja mesures du run ; l'issue du run reste celle de la batterie.")


AVERTISSEMENT_MD = ("**INFORMATIF : ni porte ni verdict.** Chiffres calculés par le programme "
                    "sur les trades déjà mesurés du run ; l'issue du run reste celle de la "
                    "batterie.")


def pnl_journalier(trades: pd.DataFrame) -> pd.Series:
    """Somme des R clotures chaque jour UTC, 0 sans cloture (la base de S7 et de S10)."""
    matrice = pbo.rendements_lot({"x": trades})
    return matrice["x"] if "x" in matrice.columns else pd.Series(dtype=float)


def _hold_journalier(courbe_hold: dict | None) -> pd.Series:
    """Rendements journaliers du hold, depuis la courbe stockee par S8 (`batterie.json`)."""
    if not courbe_hold or not courbe_hold.get("ts"):
        return pd.Series(dtype=float)
    serie = pd.Series(courbe_hold["valeur"], dtype=float,
                      index=pd.to_datetime(courbe_hold["ts"], utc=True).floor("D"))
    return serie.pct_change().dropna()


def construire(trades: pd.DataFrame, equity: pd.DataFrame | None = None,
               courbe_hold: dict | None = None, n_essais: int | None = None,
               graine: int = 0) -> dict:
    """Assemble la fiche. Chaque bloc absent de ses donnees dit pourquoi, il ne se remplit pas."""
    r = (trades["r"].dropna().to_numpy(dtype=float) if "r" in trades.columns
         else np.empty(0, dtype=float))
    jour = pnl_journalier(trades)
    fiche: dict = {"avertissement": AVERTISSEMENT, "n_trades": int(len(r)),
                   "n_jours": int(len(jour)), "n_essais": n_essais}

    # --- Sharpe : incertitude, duree exigee -------------------------------------------
    par_trade = sharpe.psr(r)
    par_jour = sharpe.psr(jour.to_numpy())
    lo = sharpe.facteur_lo(jour.to_numpy(), int(JOURS_AN))
    sr_j = par_jour["sharpe"]
    annuel_naif = sr_j * math.sqrt(JOURS_AN) if np.isfinite(sr_j) else float("nan")
    annuel_lo = sr_j * lo["facteur"] if np.isfinite(sr_j) else float("nan")
    bloc = {"par_trade": par_trade, "par_jour": par_jour, "lo": lo,
            "sharpe_annuel_naif": annuel_naif, "sharpe_annuel_lo": annuel_lo,
            "longueur_minimale_trades": sharpe.longueur_minimale(
                par_trade["sharpe"], 0.0, par_trade["skew"], par_trade["kurtosis"])}
    if n_essais:
        seuil = multitest.sharpe_attendu_du_maximum(n_essais, 1.0 / max(len(r) - 1, 1))
        bloc["sharpe_seuil_n_essais"] = seuil
        bloc["longueur_minimale_trades_n_essais"] = sharpe.longueur_minimale(
            par_trade["sharpe"], seuil, par_trade["skew"], par_trade["kurtosis"])
        bloc["duree_minimale_backtest_ans"] = sharpe.duree_minimale_backtest(
            n_essais, annuel_lo)
        bloc["duree_backtest_ans"] = len(jour) / JOURS_AN
    fiche["sharpe"] = bloc

    # --- Queues et chemin --------------------------------------------------------------
    j = jour.to_numpy()
    fiche["queues"] = {"unite": "R par jour", "sortino_annuel": risque.sortino(j),
                       "omega": risque.omega(j),
                       # Sur les R par TRADE : le P&L journalier compte trop de jours a zero.
                       "ratio_des_queues": risque.ratio_des_queues(r),
                       **{f"var_cvar_{int(n * 100)}": risque.var_cvar(j, n)
                          for n in (0.95, 0.99)},
                       "cornish_fisher_99": risque.var_cornish_fisher(j, 0.99)}
    if equity is not None and not equity.empty:
        courbe = (equity.set_index(pd.to_datetime(equity["ts"], utc=True))["equity"]
                  .resample("1D").last().ffill().dropna())
        fiche["chemin"] = {**risque.chemin(courbe), "pires": risque.drawdowns(courbe, 5)}
    else:
        fiche["chemin"] = {"raison": "courbe d'equity absente"}
    fiche["drawdown_par_blocs"] = {"unite": "R", **risque.drawdown_par_blocs(r, graine=graine)}

    # --- Marche retire -----------------------------------------------------------------
    hold = _hold_journalier(courbe_hold)
    if hold.empty or jour.empty:
        fiche["contre_le_hold"] = {"raison": "courbe du hold absente (S8 non executee)"}
    else:
        fiche["contre_le_hold"] = {
            "regression": risque.alpha_beta(jour, hold),
            "volatilite_egale": risque.a_volatilite_egale(jour, hold),
            "note": "candidate en R par jour : l'alpha se lit par son t, pas par sa valeur"}
        commun = pd.concat([jour, hold], axis=1, join="inner").dropna()
        if len(commun) >= 30:
            a, b = commun.iloc[:, 0].to_numpy(), commun.iloc[:, 1].to_numpy()
            fiche["contre_le_hold"]["ecart_de_sharpe"] = {
                "memmel": sharpe.difference_memmel(a, b),
                "bootstrap": sharpe.difference_bootstrap(a, b, graine=graine)}

    # --- D'ou vient le resultat --------------------------------------------------------
    fiche["concentration"] = robustesse.concentration(trades)
    fiche["stress_couts"] = robustesse.stress_couts(trades)
    fiche["par_annee"] = robustesse.par_annee(trades)
    fiche["sans_une_paire"] = robustesse.sans_une_paire(trades)
    return fiche


# =========================================================================================
# Mise en page : le programme ecrit, personne n'arrondit a la main
# =========================================================================================

def _n(x, d: int = 3, signe: bool = False) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "infini" if isinstance(x, float) and math.isinf(x) else "n/d"
    texte = f"{x:+.{d}f}" if signe else f"{x:.{d}f}"
    return texte.replace(".", ",")


def _p(x, d: int = 1) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/d"
    return f"{100 * x:.{d}f}".replace(".", ",") + " %"


def markdown(fiche: dict, titre: str) -> str:
    """La fiche en clair. Aucun adjectif, aucun verdict : des chiffres et leur definition."""
    s, lignes = fiche["sharpe"], [f"# Fiche de robustesse — {titre}", "",
                                  f"> {AVERTISSEMENT_MD}", ""]
    pt, pj = s["par_trade"], s["par_jour"]
    lignes += [
        f"{fiche['n_trades']} trades, {fiche['n_jours']} jours"
        + (f", N = {fiche['n_essais']} essais au compteur du run" if fiche["n_essais"] else ""),
        "", "## Le Sharpe et son incertitude", "",
        "| Mesure | Valeur |", "|---|---|",
        f"| Sharpe par trade | {_n(pt['sharpe'], 4, True)} (intervalle à 95 % : "
        f"{_n(pt['ic_bas'], 4, True)} à {_n(pt['ic_haut'], 4, True)}) |",
        f"| Probabilité que le vrai Sharpe par trade dépasse 0 (PSR) | {_p(pt['psr'])} |",
        f"| Asymétrie, aplatissement des R | {_n(pt['skew'], 2, True)}, "
        f"{_n(pt['kurtosis'], 2)} |",
        f"| Trades nécessaires pour distinguer ce Sharpe de 0 (à 95 %) | "
        f"{_n(s['longueur_minimale_trades'], 0)} |"]
    if fiche["n_essais"]:
        lignes += [
            f"| Sharpe par trade attendu du meilleur de N essais sans edge | "
            f"{_n(s['sharpe_seuil_n_essais'], 4, True)} |",
            f"| Trades nécessaires pour dépasser ce seuil (à 95 %) | "
            f"{_n(s['longueur_minimale_trades_n_essais'], 0)} |"]
    lignes += [
        f"| Sharpe annuel, racine de 365 | {_n(s['sharpe_annuel_naif'], 2, True)} |",
        f"| Sharpe annuel, corrigé de l'autocorrélation (Lo) | "
        f"{_n(s['sharpe_annuel_lo'], 2, True)} (autocorrélation d'ordre 1 : "
        f"{_n(s['lo']['rho_1'], 3, True)}) |",
        f"| PSR du Sharpe journalier | {_p(pj['psr'])} |"]
    if fiche["n_essais"]:
        lignes += [
            f"| Durée minimale de backtest pour ce Sharpe annuel après N essais | "
            f"{_n(s['duree_minimale_backtest_ans'], 1)} ans (le run en couvre "
            f"{_n(s['duree_backtest_ans'], 1)}) |"]

    q = fiche["queues"]
    lignes += ["", "## Queues (P&L journalier en R)", "", "| Mesure | Valeur |", "|---|---|",
               f"| Sortino annuel | {_n(q['sortino_annuel'], 2, True)} |",
               f"| Omega (seuil 0) | {_n(q['omega'], 3)} |",
               f"| Rapport des queues des R par trade (centile 95 / centile 5) | {_n(q['ratio_des_queues'], 2)} |"]
    for niveau in (95, 99):
        v = q[f"var_cvar_{niveau}"]
        lignes.append(f"| Perte d'un mauvais jour à {niveau} % (VaR), moyenne des pires (CVaR) | "
                      f"{_n(v['var'], 2)} R, {_n(v['cvar'], 2)} R ({v['n_queue']} jours) |")
    cf = q["cornish_fisher_99"]
    lignes.append(f"| VaR à 99 % : loi normale, puis corrigée des queues | "
                  f"{_n(cf.get('var_normale'), 2)} R, {_n(cf.get('var_cf'), 2)} R"
                  + (" (hors domaine de validité : lire la CVaR)" if cf.get("hors_domaine")
                     else "") + " |")

    c = fiche["chemin"]
    lignes += ["", "## Chemin (courbe d'equity du moteur, risque fixe)", ""]
    if "raison" in c:
        lignes.append(f"Non calculé : {c['raison']}.")
    else:
        lignes += ["| Mesure | Valeur |", "|---|---|",
                   f"| Drawdown maximal | {_p(c['drawdown_max'], 2)} |",
                   f"| Moyenne des 5 % pires drawdowns courants (CDaR) | {_p(c['cdar'], 2)} |",
                   f"| Indice Ulcer | {_p(c['ulcer'], 2)} |",
                   f"| Part du temps sous le dernier sommet | {_p(c['part_sous_l_eau'])} |",
                   f"| Plus long épisode | {c['plus_long_episode']} jours"
                   + (" (non rattrapé à la fin)" if c["non_rattrape"] else "") + " |", "",
                   "| Pic | Creux | Retour | Profondeur | Baisse (j) | Retour (j) |",
                   "|---|---|---|---|---|---|"]
        for e in c["pires"]:
            lignes.append(f"| {str(e['pic'])[:10]} | {str(e['creux'])[:10]} | "
                          f"{str(e['fin'])[:10] if e['fin'] else 'non rattrapé'} | "
                          f"{_p(e['profondeur'], 2)} | {e['duree_baisse']} | "
                          f"{e['duree_retour'] if e['duree_retour'] is not None else 'n/d'} |")
    b = fiche["drawdown_par_blocs"]
    if "raison" not in b:
        lignes += ["", f"Drawdown maximal rejoué {b['n_tirages']} fois, en R : observé "
                   f"{_n(b['observe'], 1)} ; par blocs de {_n(b['ell'], 1)} trades, médiane "
                   f"{_n(b['blocs']['median'], 1)}, 5 % pires {_n(b['blocs']['p5'], 1)} ; trades "
                   f"indépendants, médiane {_n(b['iid']['median'], 1)}. "
                   f"{_n(b['centile_observe'], 0)} % des tirages par blocs ont un drawdown au "
                   "moins aussi sévère que l'observé."]

    h = fiche["contre_le_hold"]
    lignes += ["", "## Contre le hold, marché retiré", ""]
    if "raison" in h:
        lignes.append(f"Non calculé : {h['raison']}.")
    else:
        g, v = h["regression"], h["volatilite_egale"]
        lignes += ["| Mesure | Valeur |", "|---|---|",
                   f"| Jours communs | {g['n']} |",
                   f"| Bêta au hold, corrélation, R² | {_n(g.get('beta'), 3, True)}, "
                   f"{_n(g.get('correlation'), 3, True)}, {_n(g.get('r2'), 3)} |",
                   f"| t de l'alpha (Newey-West, {g.get('retards', 'n/d')} retards), "
                   f"p unilatérale | {_n(g.get('t_alpha'), 2, True)}, {_n(g.get('p_alpha'), 3)} |",
                   f"| Sharpe annuel : candidate, hold | {_n(v.get('sharpe_candidate'), 2, True)}, "
                   f"{_n(v.get('sharpe_reference'), 2, True)} |",
                   f"| À volatilité égale ({_p(v.get('volatilite_reference_annuelle'))} par an) : "
                   f"écart de rendement annuel | {_p(v.get('ecart_annuel'), 1)} |"]
        e = h.get("ecart_de_sharpe")
        if e:
            m, bo = e["memmel"], e["bootstrap"]
            racine = math.sqrt(JOURS_AN)
            lignes += [
                f"| Écart de Sharpe annuel, test de Memmel (p unilatérale) | "
                f"{_n(m['ecart'] * racine, 2, True)}, p = {_n(m['p_value'], 3)} |",
                f"| Écart de Sharpe annuel, bootstrap par blocs (intervalle à 95 %, p) | "
                f"{_n(bo['ic_bas'] * racine, 2, True)} à {_n(bo['ic_haut'] * racine, 2, True)}, "
                f"p = {_n(bo['p_value'], 3)} |"]

    k = fiche["concentration"]
    lignes += ["", "## D'où vient le résultat", ""]
    if k.get("n", 0) >= 2:
        lignes += [f"- Les {k['n_tete']} meilleurs trades ({_p(k['part_tete'], 0)}) portent "
                   f"{_p(k['part_gains_tete'])} des gains. R moyen : {_n(k['r_moyen'], 4, True)} ; "
                   f"sans eux : {_n(k['r_moyen_sans_tete'], 4, True)} ; sans le seul meilleur : "
                   f"{_n(k['r_moyen_sans_le_meilleur'], 4, True)}.",
                   f"- Meilleurs trades à retirer pour annuler le R total : {k['n_pour_annuler']} "
                   f"sur {k['n']} ({_p(k['part_pour_annuler'])})."]
    st = fiche["stress_couts"]
    if "raison" in st:
        lignes.append(f"- Stress des coûts non calculé : {st['raison']}.")
    else:
        par = ", ".join(f"× {_n(l['multiple'], 1)} : {_n(l['r_moyen'], 4, True)} R"
                        for l in st["par_multiple"])
        lignes += [f"- R moyen brut {_n(st['r_brut_moyen'], 4, True)}, coût moyen "
                   f"{_n(st['cout_moyen_r'], 4)} R par trade. R moyen selon le multiple des "
                   f"coûts du modèle — {par}.",
                   f"- Multiple des coûts qui annule le R moyen : {_n(st['multiple_mort'], 2)}"
                   + (" (le R moyen brut est déjà négatif ou nul)."
                      if st["r_brut_moyen"] <= 0 else ".")]
    sp = fiche["sans_une_paire"]
    if sp.get("paires"):
        lignes.append(f"- Sans {sp['pire']} (la paire qui porte le plus) : R moyen "
                      f"{_n(sp['r_moyen_sans_pire'], 4, True)} contre {_n(sp['r_moyen'], 4, True)} ; "
                      f"le signe {'tient' if sp['signe_tient'] else 'ne tient pas'}.")
    pa = fiche["par_annee"]
    if pa["annees"]:
        lignes += ["", f"Années positives : {pa['annees_positives']} sur {pa['n_annees']} ; "
                   f"meilleure année {pa['meilleure_annee']}, R total sans elle : "
                   f"{_n(pa['r_total_sans_meilleure_annee'], 1, True)}.", "",
                   "| Année | Trades | R moyen | R total | MDE (R) |", "|---|---|---|---|---|"]
        lignes += [f"| {l['annee']} | {l['n']} | {_n(l['r_moyen'], 4, True)} | "
                   f"{_n(l['r_total'], 1, True)} | {_n(l['mde_r'], 4)} |" for l in pa["annees"]]
    return "\n".join(lignes) + "\n"
