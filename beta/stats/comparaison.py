"""Le banc COMPARATIF : ce qu'on ne peut pas savoir en regardant une candidate a la fois.

Les portes S1 a S6 et S8 jugent une candidate contre le hasard et contre le hold. Elles ne
disent rien de la question qui decide vraiment quoi mettre en production : **celle-ci
apporte-t-elle quelque chose que je n'ai pas deja ?**

Trois choses ne se voient qu'a plusieurs, et ce module les rassemble :

1. **Le meilleur d'un lot est presque toujours bon par accident** (S7, White 2000 /
   Hansen 2005). Prendre vingt candidates de bruit pur et garder la meilleure produit un
   Sharpe flatteur a tous les coups. La p-value du MAXIMUM, elle, ne se laisse pas avoir —
   et elle conserve la correlation entre candidates, la ou Bonferroni la jette.
2. **Deux candidates rentables et correlees a 0,9 n'en font pas deux** (S9). Les tenir
   toutes les deux double l'exposition au meme facteur en croyant diversifier. C'est
   exactement ce que F1 demande d'eviter, et ca ne se voit sur AUCUNE metrique individuelle.
3. **La reference n'est pas seulement le hold.** S8 compare au buy-and-hold, ce qui repond
   a « est-ce un edge ? ». Il manquait « est-ce mieux que ce que je fais deja ? » — donc la
   comparaison a **AritV1**, la strategie qui tourne.

⚠️ **AritV1 se compare par sa COURBE, jamais par son R par trade.** Ses trades sortent avec
sa propre mecanique (trailing, portes de gestion, protections freqtrade) ; un R d'AritV1 et
un R du moteur BETA ne mesurent pas la meme chose et les moyenner serait une faute. Les
rendements journaliers des deux courbes, eux, sont comparables : c'est la seule mise en
regard honnete, et elle est ecrite en reserve dans chaque ligne du classement.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.stats import diversification, multitest, reference

log = logging.getLogger("beta.stats.comparaison")

# Au-dela, deux candidates sont consideree comme une seule testee deux fois. Meme seuil que
# la porte S9 : un seuil de comparaison different de celui de la porte ferait dire deux
# choses differentes au meme chiffre.
SEUIL_REDONDANCE = diversification.SEUIL

# Sous ce nombre de candidates, S7 n'a pas d'objet : le maximum d'un ensemble a un element
# est cet element, et sa p-value serait celle d'un test simple deguisee en correction.
MIN_CANDIDATES_S7 = 2


def equity_arit(train_seulement: bool = True) -> pd.DataFrame | None:
    """La courbe d'AritV1, construite avec la MEME convention que les candidates.

    Meme sizing (risque fixe de 1 % du capital initial), meme absence de composition, meme
    fonction (`espace_r.equity`). C'est ce qui rend les deux courbes superposables : si on
    laissait ARIT avec son compounding freqtrade et les candidates sans, l'ecart mesurerait
    la convention de sizing avant de mesurer quoi que ce soit d'autre.

    ⚠️ Ce que cette courbe NE rend PAS comparable : le R par trade. Les R d'AritV1 viennent
    de ses propres sorties (trailing, portes de gestion, protections) ; ceux d'une candidate
    viennent de la triple barriere du moteur. Les mettre dans la meme moyenne serait une
    faute. Seuls les rendements journaliers des courbes se comparent.

    Rend None si les donnees de strategie ne sont pas importees — l'absence est une
    information, pas une panne : `python beta.py strategie` les importe.
    """
    from beta.lake import strategie
    from beta.moteur import espace_r, pipeline

    try:
        trades = strategie.lire("trades", train_seulement=train_seulement)
    except strategie.StrategieError as exc:
        log.info("AritV1 hors comparaison : %s", exc)
        return None
    if trades.empty:
        return None
    trades = trades.sort_values("ts_entree").reset_index(drop=True)
    return espace_r.equity(trades, pipeline.CAPITAL, pipeline.RISQUE_PAR_TRADE_PCT)


def _serie_journaliere(equity: pd.DataFrame) -> pd.Series:
    if equity is None or equity.empty:
        return pd.Series(dtype=float)
    courbe = (equity.set_index(pd.to_datetime(equity["ts"], utc=True))["equity"]
              .resample("1D").last().ffill().dropna())
    return courbe.pct_change().dropna()


def _ecart_contre(equity: pd.DataFrame, temoin: pd.Series) -> dict:
    """Ecart de rendement et de Sharpe entre une candidate et un temoin, periode COMMUNE.

    L'intersection des dates n'est pas un detail : comparer une candidate de 2020-2024 a une
    reference de 2019-2026 fait gagner ou perdre la comparaison sur les annees que l'une des
    deux n'a pas vues. On tronque donc aux dates que les deux ont en commun, et on dit
    combien il en restait.
    """
    mienne = _serie_journaliere(equity)
    if mienne.empty or temoin.empty:
        return {"n_jours_communs": 0, "ecart_rendement_pct": float("nan"),
                "ecart_sharpe": float("nan"), "correlation": float("nan")}
    commun = mienne.index.intersection(temoin.index)
    if len(commun) < 10:
        return {"n_jours_communs": len(commun), "ecart_rendement_pct": float("nan"),
                "ecart_sharpe": float("nan"), "correlation": float("nan")}
    a, b = mienne.loc[commun], temoin.loc[commun]
    return {
        "n_jours_communs": len(commun),
        "ecart_rendement_pct": float(100 * ((1 + a).prod() - (1 + b).prod())),
        "ecart_sharpe": float(reference.sharpe_annuel(a) - reference.sharpe_annuel(b)),
        "correlation": float(a.corr(b)) if a.std() > 0 and b.std() > 0 else float("nan"),
    }


def classer(verdicts: dict, equities: dict[str, pd.DataFrame],
            univers_r: dict[str, np.ndarray] | None = None,
            equity_arit: pd.DataFrame | None = None, graine: int = 0) -> dict:
    """Le classement d'un lot. Rend tableau, reality check, matrice et redondances.

    `verdicts` : {nom: Verdict}. `equities` : {nom: DataFrame ts/equity}.
    `univers_r` : {nom: R par trade} pour S7. `equity_arit` : la courbe d'AritV1, facultative.

    Le tri est fait sur le R moyen, **pas** sur une issue : classer par verdict mettrait en
    tete les candidates qui ont eu la chance qu'une porte ne tourne pas. Le tableau porte
    donc l'issue en colonne, et le lecteur voit lui-meme qu'un bon R moyen INFIRME reste
    infirme.
    """
    temoin_arit = _serie_journaliere(equity_arit) if equity_arit is not None \
        else pd.Series(dtype=float)

    lignes = []
    for nom, verdict in verdicts.items():
        metriques = getattr(verdict, "metriques", {}) or {}
        ligne = {
            "candidate": nom,
            "experience": getattr(getattr(verdict, "run", None), "id_experience", ""),
            "issue": getattr(verdict, "issue", ""),
            "n": metriques.get("n"),
            "r_moyen": metriques.get("r_moyen"),
            "mde_r": metriques.get("mde_r"),
            "r_total": metriques.get("r_total"),
            "win_rate": metriques.get("win_rate"),
            "portes_echouees": len(getattr(verdict, "portes_echouees", []) or []),
            "portes_non_executees": len(getattr(verdict, "portes_non_executees", []) or []),
        }
        if not temoin_arit.empty:
            contre = _ecart_contre(equities.get(nom), temoin_arit)
            ligne.update({f"vs_arit_{cle}": valeur for cle, valeur in contre.items()})
        lignes.append(ligne)

    tableau = pd.DataFrame(lignes)
    if not tableau.empty and "r_moyen" in tableau.columns:
        tableau = tableau.sort_values("r_moyen", ascending=False).reset_index(drop=True)
        tableau.insert(0, "rang", tableau.index + 1)

    rc = {"n_candidates": len(univers_r or {}), "p_value": float("nan"), "meilleure": None}
    if univers_r and len(univers_r) >= MIN_CANDIDATES_S7:
        rc = multitest.reality_check(univers_r, graine=graine)

    matrice = diversification.matrice(equities)
    return {
        "tableau": tableau,
        "reality_check": rc,
        "matrice_correlation": matrice,
        "redondances": diversification.redondances(equities, SEUIL_REDONDANCE),
        "reserves": _reserves(verdicts, univers_r, matrice, temoin_arit,
                              equity_arit),
    }


def _reserves(verdicts: dict, univers_r: dict | None, matrice: pd.DataFrame,
              temoin_arit: pd.Series, equity_arit: pd.DataFrame | None = None) -> list[str]:
    """Ce que la comparaison ne dit PAS. Une comparaison sans reserve est une comparaison
    dont on a oublie de compter les candidates."""
    reserves = []
    n = len(univers_r or {})
    if n < MIN_CANDIDATES_S7:
        reserves.append(
            f"{n} candidate(s) : le reality check (S7) n'a pas d'objet, et aucune candidate "
            "ne peut donc etre CONFIRMEE — il faut au moins deux candidates pour que le "
            "banc comparatif dise quoi que ce soit")
    if matrice.empty and len(verdicts) > 1:
        reserves.append("matrice de correlation vide : les courbes ne se recouvrent pas "
                        "assez (moins de 10 jours communs)")
    if temoin_arit.empty:
        reserves.append("AritV1 absent de la comparaison : seul le buy-and-hold sert de "
                        "reference, donc « mieux que ce qui tourne deja » n'est pas mesure")
    else:
        n_arit = 0 if equity_arit is None else len(equity_arit)
        reserves.append(
            "la comparaison a AritV1 porte sur les COURBES journalieres seulement, jamais "
            "sur le R par trade : ses sorties sont les siennes (trailing, portes de "
            "gestion), celles des candidates viennent de la triple barriere du moteur")
        if n_arit and n_arit < 150:
            reserves.append(
                f"la courbe d'AritV1 repose sur {n_arit} trades : son Sharpe journalier est "
                "instable a ce nombre, et un ecart de Sharpe contre elle se lit comme un "
                "ordre de grandeur, pas comme une mesure")
    return reserves


def texte(classement: dict) -> str:
    """Le classement en clair, pour le terminal. Les reserves en dernier, jamais omises."""
    tableau = classement["tableau"]
    if tableau.empty:
        return "aucune candidate a comparer"

    colonnes = ["rang", "candidate", "issue", "n", "r_moyen", "mde_r", "portes_echouees"]
    if "vs_arit_ecart_sharpe" in tableau.columns:
        colonnes.append("vs_arit_ecart_sharpe")
    lignes = [tableau[[c for c in colonnes if c in tableau.columns]].to_string(index=False)]

    rc = classement["reality_check"]
    if np.isfinite(rc.get("p_value", float("nan"))):
        lignes.append(f"\nS7 reality check : p = {rc['p_value']:.4f} sur "
                      f"{rc['n_candidates']} candidates, meilleure = {rc['meilleure']}")
        lignes.append("  (H0 : aucune ne bat la reference. p > 0,05 => le meilleur du lot "
                      "est explicable par le hasard du choix)")

    for redondance in classement["redondances"]:
        lignes.append(f"\nREDONDANTES : {redondance['a']} et {redondance['b']} correlees a "
                      f"{redondance['correlation']:+.2f} — elles n'en font qu'une")

    for reserve in classement["reserves"]:
        lignes.append(f"\nreserve : {reserve}")
    return "\n".join(lignes)
