"""R6 — que vaut ce que `news_window` bloque ?

C'est la porte la plus active du systeme : 1 284 evaluations rejetees par elle, soit
91,75 % de tout ce qui est rejete. Personne n'a jamais mesure ce qu'elle jette. Une porte
qui bloque neuf refus sur dix et qui ne discrimine rien est le pire cas possible : elle
divise l'echantillon par dix sans rien apporter, et le manque de signaux est precisement le
goulot du projet.

Protocole : chaque evaluation — bloquee ou acceptee — est etiquetee en triple barriere sur
la bougie qui suit, dans les DEUX sens, avec le meme stop (2 ATR), la meme cible (+1,5 R) et
le meme horizon (96 h). On compare ensuite le R moyen des bloquees a celui des acceptees,
sens par sens.

**Amendement au preenregistrement, ecrit avant la mesure** : le sens qu'AritV1 aurait pris
n'est pas journalise pour les evaluations rejetees (`direction_macro` vaut `both` dans
1 388 cas sur 1 774). Comparer « le R des bloquees » a « le R des acceptees » sans fixer le
sens melangerait l'effet de la porte et celui de la direction. R6 se scinde donc en deux
tests, R6-long et R6-short, et la famille declaree passe de 6 a 8. L'alternative — ne garder
que les 336 evaluations a direction connue — aurait selectionne un sous-groupe non
aleatoire, ce qui est pire.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from beta.lake import lecture, strategie
from beta.moteur import espace_r
from beta.protocole import experiences
from beta.stats import bootstrap, descriptif

log = logging.getLogger("beta.recherche.r6")

ID_EXPERIENCE = "R6"
PORTE = "news_window"
TIMEFRAME = "1h"
TP1_R = 1.5
HORIZON_BOUGIES = 96
STOP_ATR = 2.0
N_MIN = 30


def _etiqueter_paire(paire: str, evaluations: pd.DataFrame, sens: int) -> pd.DataFrame:
    """Triple barriere sur chaque evaluation d'une paire, dans un sens impose."""
    debut = (evaluations["ts_bougie"].min() - pd.Timedelta(hours=24)).isoformat()
    fin = (evaluations["ts_bougie"].max() + pd.Timedelta(hours=HORIZON_BOUGIES + 2)
           ).isoformat()
    df = lecture.load(paire, TIMEFRAME, debut=debut, fin=fin)
    if df.empty:
        return pd.DataFrame()

    dates = pd.to_datetime(df["date"], utc=True)
    signal = np.zeros(len(df), dtype=int)
    origine: dict[int, int] = {}
    for idx, ligne in evaluations.iterrows():
        position = int(dates.searchsorted(ligne["ts_bougie"], side="right")) - 1
        if position < 0 or position >= len(df) - 1 or signal[position]:
            continue
        signal[position] = sens
        origine[position] = idx

    trades = espace_r.evaluer(df, pd.DataFrame({"sens": signal}), take_profit_r=TP1_R,
                              horizon_bougies=HORIZON_BOUGIES, stop_atr=STOP_ATR,
                              paire=paire)
    if trades.empty:
        return trades
    trades["evaluation"] = trades["index_entree"].map(origine)
    return trades.dropna(subset=["evaluation"])


def partition() -> tuple[pd.DataFrame, dict]:
    """Separe les signaux bloques des signaux acceptes — et dit si c'est seulement possible.

    Le diagnostic rendu est plus important que la partition elle-meme. Mesure du 19/08 :

        824 lignes de journal  ->  63 signaux bloques et 53 acceptes distincts
        dont 53 signaux presents dans LES DEUX groupes

    Autrement dit `news_window` ne separe pas une population de signaux d'une autre : elle
    bloque un signal a un instant, puis le laisse passer plus tard, quand la fenetre de news
    est retombee. « Bloque » et « accepte » sont deux ETATS du meme signal, pas deux
    groupes. La comparaison preenregistree en R6 suppose une partition qui n'existe pas.
    """
    evaluations = strategie.lire("evaluations", train_seulement=True)
    if evaluations.empty:
        return pd.DataFrame(), {"n_lignes": 0}
    evaluations = evaluations.copy()
    evaluations["groupe"] = np.where(
        evaluations["failed_gate"].fillna("") == PORTE, "bloque",
        np.where(evaluations["decision"].isin(("enter", "signal")), "accepte", "autre"))
    retenues = evaluations[evaluations["groupe"].isin(("bloque", "accepte"))]
    distincts = retenues.drop_duplicates(subset=["pair", "signal_id", "groupe"])
    ambigus = distincts.duplicated(subset=["pair", "signal_id"], keep=False)
    diagnostic = {
        "n_lignes_journal": len(retenues),
        "n_signaux_bloques": int((distincts["groupe"] == "bloque").sum()),
        "n_signaux_acceptes": int((distincts["groupe"] == "accepte").sum()),
        "n_signaux_ambigus": int(ambigus.sum() // 2),
        "n_exploitables": int((~ambigus).sum()),
    }
    if diagnostic["n_signaux_ambigus"]:
        log.warning("%d signaux sont a la fois bloques et acceptes : news_window est une "
                    "porte temporaire, pas un filtre de population",
                    diagnostic["n_signaux_ambigus"])
    return distincts[~ambigus], diagnostic


def etiqueter(sens: int) -> pd.DataFrame:
    """Toutes les evaluations du train, etiquetees dans un sens, avec leur groupe.

    Deduplication par `signal_id`, et c'est la mesure la plus importante du module : le
    journal du train porte 824 lignes, mais seulement **63 signaux bloques et 53 acceptes
    distincts**. Les ~13 lignes par signal sont des `gate_check` repetes (dette T4 : `ts_utc`
    est l'heure d'execution du backtest, pas celle de la bougie). Les compter comme autant
    d'observations independantes multiplierait le N par treize et diviserait le MDE par
    3,6 — une puissance statistique purement imaginaire.

    Le chiffre de CHANTIERS.md (« news_window bloque 756 signaux sur 824 ») decrit donc des
    LIGNES DE JOURNAL, pas des signaux. Le vrai echantillon est vingt fois plus petit.
    """
    retenues, _ = partition()
    if retenues.empty:
        return pd.DataFrame()

    morceaux = []
    for paire, groupe in retenues.groupby("pair"):
        try:
            trades = _etiqueter_paire(paire, groupe, sens)
        except lecture.DataError as exc:
            log.error("%s non etiquetable : %s", paire, exc)
            continue
        if trades.empty:
            continue
        trades = trades.set_index("evaluation")
        morceaux.append(pd.DataFrame({
            "paire": paire, "groupe": retenues.loc[trades.index, "groupe"],
            "ts": retenues.loc[trades.index, "ts_bougie"],
            "r": trades["r"].astype(float),
            "raison_sortie": trades["raison_sortie"]}))
    return pd.concat(morceaux, ignore_index=True) if morceaux else pd.DataFrame()


def mesurer(clore: bool = True) -> dict:
    """R6-long et R6-short. L'ecart teste est (bloques - acceptes), comme preenregistre."""
    experiences.exiger(ID_EXPERIENCE)
    _, diagnostic = partition()
    resultats = {}
    for nom, sens in (("long", 1), ("short", -1)):
        etiquetees = etiqueter(sens)
        if etiquetees.empty:
            resultats[nom] = {"n_bloques": 0, "n_acceptes": 0}
            continue
        bloques = etiquetees.loc[etiquetees["groupe"] == "bloque", "r"].dropna().to_numpy()
        acceptes = etiquetees.loc[etiquetees["groupe"] == "accepte", "r"].dropna().to_numpy()
        resultats[nom] = _comparer(bloques, acceptes)

    verdict, motif = _conclure(resultats, diagnostic)
    resultat = {"id": ID_EXPERIENCE, "verdict": verdict, "motif": motif,
                "diagnostic": diagnostic, "par_sens": resultats,
                "p_brute": min((r.get("p_value", np.nan) for r in resultats.values()
                                if np.isfinite(r.get("p_value", np.nan))), default=np.nan)}
    if clore:
        experiences.clore(ID_EXPERIENCE, verdict, motif, detail=resultats,
                          diagnostic=diagnostic)
    return resultat


def _comparer(bloques: np.ndarray, acceptes: np.ndarray) -> dict:
    """Ecart de R moyen entre les deux groupes, avec son MDE et son test bootstrap.

    Les groupes sont INDEPENDANTS (pas de trade commun) : le MDE se calcule sur l'ecart-type
    combine et la taille effective des deux groupes, pas sur le seul grand groupe. C'est le
    petit groupe — 95 acceptees — qui commande la puissance.
    """
    n_b, n_a = len(bloques), len(acceptes)
    resultat = {"n_bloques": n_b, "n_acceptes": n_a,
                "r_bloques": float(np.mean(bloques)) if n_b else float("nan"),
                "r_acceptes": float(np.mean(acceptes)) if n_a else float("nan")}
    if n_b < 2 or n_a < 2:
        return {**resultat, "ecart": float("nan"), "mde_r": float("nan"),
                "p_value": float("nan")}
    var_combinee = ((n_b - 1) * np.var(bloques, ddof=1)
                    + (n_a - 1) * np.var(acceptes, ddof=1)) / (n_b + n_a - 2)
    sigma = float(np.sqrt(var_combinee))
    n_effectif = 1.0 / (1.0 / n_b + 1.0 / n_a)          # taille harmonique des deux groupes
    ecart = resultat["r_bloques"] - resultat["r_acceptes"]
    # Test bootstrap sur l'ecart : on rebootstrappe les deux groupes separement, ce qui
    # conserve leur dependance temporelle interne (bloques et acceptes sont des grappes).
    rng = np.random.default_rng(0)
    tirages = np.array([
        np.mean(bloques[bootstrap.indices(n_b, n_b, bootstrap.longueur_optimale(bloques),
                                          rng)])
        - np.mean(acceptes[bootstrap.indices(n_a, n_a,
                                             bootstrap.longueur_optimale(acceptes), rng)])
        for _ in range(2000)])
    p_bilaterale = 2 * min((tirages <= 0).mean(), (tirages >= 0).mean())
    return {**resultat, "ecart": float(ecart), "sigma_combine": sigma,
            "mde_r": descriptif.mde(int(n_effectif * 2), sigma),
            "ic_bas": float(np.percentile(tirages, 2.5)),
            "ic_haut": float(np.percentile(tirages, 97.5)),
            "p_value": float(min(1.0, p_bilaterale + 1 / 2001))}


def _conclure(resultats: dict, diagnostic: dict) -> tuple[str, str]:
    """La regle preenregistree : la porte est inutile si l'ecart est sous le MDE.

    Avec, avant elle, la question qui la precede : les deux groupes existent-ils ?
    """
    ambigus = diagnostic.get("n_signaux_ambigus", 0)
    exploitables = diagnostic.get("n_exploitables", 0)
    if ambigus and exploitables < N_MIN:
        return "indecidable", (
            f"les deux groupes ne sont pas disjoints : {ambigus} des "
            f"{diagnostic['n_signaux_bloques']} signaux bloques sont AUSSI acceptes "
            f"ailleurs. news_window est une porte temporaire — elle retarde un signal, "
            f"elle n'en ecarte pas une population. Il reste {exploitables} signaux "
            f"exploitables sur {diagnostic['n_lignes_journal']} lignes de journal : "
            "l'hypothese telle que preenregistree n'est pas mesurable sur ces donnees.")
    lisibles = {nom: r for nom, r in resultats.items()
                if r.get("n_acceptes", 0) >= N_MIN and np.isfinite(r.get("ecart", np.nan))}
    if not lisibles:
        return "indecidable", (
            f"moins de {N_MIN} signaux acceptes etiquetables "
            f"({diagnostic.get('n_signaux_acceptes', 0)} distincts au journal, "
            f"{exploitables} exploitables) : la porte ne peut pas etre jugee")
    morceaux, protege, indiscernable = [], False, True
    for nom, r in lisibles.items():
        morceaux.append(f"{nom} : bloques {r['r_bloques']:+.4f} R contre acceptes "
                        f"{r['r_acceptes']:+.4f} R, ecart {r['ecart']:+.4f} "
                        f"(MDE {r['mde_r']:.4f}, p = {r['p_value']:.4f})")
        if abs(r["ecart"]) >= r["mde_r"]:
            indiscernable = False
            if r["ecart"] < 0 and r["p_value"] <= 0.05:
                protege = True
    if protege:
        return "infirmee", ("news_window protege reellement — " + " ; ".join(morceaux))
    if indiscernable:
        return "confirmee", ("news_window ne discrimine rien de mesurable — "
                             + " ; ".join(morceaux))
    return "indecidable", " ; ".join(morceaux)
