"""Le chemin complet d'une candidate : donnees -> signaux -> trades -> batterie -> verdict.

C'est le seul endroit du projet ou les trois etages se rencontrent. Il est volontairement
mince : tout ce qui est decision statistique vit dans `beta.stats`, tout ce qui est
geometrie vit dans `beta.moteur.espace_r`, et rien de tout cela ne remonte ici.

Un run ne peut pas exister sans preenregistrement (`contrats.Run` s'en charge), et le
verdict qui en sort ne peut pas etre CONFIRMEE si une porte a echoue ou n'a pas tourne
(`contrats.Verdict` s'en charge). Le pipeline n'a donc aucun moyen de contourner le
protocole, meme par erreur — c'est ce qui permet de le lancer en boucle sur des dizaines de
candidates sans le relire a chaque fois.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from beta import config
from beta.lake import lecture
from beta.moteur import espace_r
from beta.moteur.contrats import Candidate, Run, Verdict
from beta.protocole import experiences, holdout
from beta.stats import batterie, synthetique

log = logging.getLogger("beta.moteur.pipeline")

RESULTATS = config.DATA / "runs"
N_CHEMINS_SYNTHETIQUES = 200
CAPITAL = 100_000.0
RISQUE_PAR_TRADE_PCT = 1.0


def _bornes_du_split(run: Run) -> tuple[str | None, str | None]:
    """Traduit le split en bornes de dates. Le hold-out n'est pas une option par defaut.

    Passer par des bornes plutot que par un filtre pose apres coup evite de charger en
    memoire des donnees qu'on n'a pas le droit de regarder : ce qui n'est pas lu ne peut
    pas fuiter dans une moyenne.
    """
    debut, fin = run.debut, run.fin
    coupure = holdout.DEBUT.date().isoformat()
    if run.split == holdout.TRAIN:
        fin = min(fin, coupure) if fin else coupure
    else:
        debut = max(debut, coupure) if debut else coupure
    return debut, fin


def series_du_run(run: Run) -> dict[str, pd.DataFrame]:
    """OHLCV de chaque paire du run, deja borne au split autorise.

    Le funding rate est joint comme colonne `funding_rate` (chantier D5) : la colonne vaut
    le taux dont le reglement est STRICTEMENT anterieur a l'ouverture de la bougie — donc
    connu au moment de l'entree, sans look-ahead. Une paire sans funding reste utilisable :
    la colonne est simplement absente, et les candidates qui n'en ont pas besoin l'ignorent.
    """
    debut, fin = _bornes_du_split(run)
    series = {}
    for paire in run.paires:
        try:
            df = lecture.load(paire, run.timeframe, debut=debut, fin=fin)
            df = _joindre_funding(df, paire)
            df = _joindre_macro(df)
            series[paire] = df
        except lecture.DataError as exc:
            log.error("%s %s indisponible : %s", paire, run.timeframe, exc)
    return series


def _joindre_funding(df: pd.DataFrame, paire: str) -> pd.DataFrame:
    """Joint la colonne funding_rate a l'OHLCV, sans look-ahead.

    merge_asof direction backward + allow_exact_matches=False : pour chaque bougie, le taux
    retenu est celui dont le reglement est STRICTEMENT avant l'ouverture de la bougie. Un
    taux regle exactement a l'ouverture est ecarte (il n'est pas encore certain a cet
    instant). Si le funding est absent, rend df inchange.
    """
    try:
        f = lecture.funding(paire)
    except lecture.DataError:
        return df
    if f.empty or df.empty:
        return df
    df = df.sort_values("date")
    # Le lake (DuckDB) rend du datetime64[us], le feather du [ms] : merge_asof exige le
    # meme dtype. On aligne le funding sur l'OHLCV.
    f = f.copy()
    f["date"] = f["date"].astype(df["date"].dtype)
    joint = pd.merge_asof(df, f, on="date", direction="backward",
                          allow_exact_matches=False)
    return joint


def _joindre_macro(df: pd.DataFrame) -> pd.DataFrame:
    """Joint les colonnes macro (fng + series globales FRED) a l'OHLCV, decalees d'un jour.

    Toutes les series macro sont quotidiennes et publiees en fin de journee : on decale leur
    date d'un jour puis merge_asof backward (allow_exact_matches=False). Une bougie ne voit
    donc que la valeur de la veille ou d'avant — jamais celle du jour en cours. Macro absente
    => df inchange.
    """
    try:
        fng = lecture.fear_greed()
    except lecture.DataError:
        fng = pd.DataFrame({"date": [], "fng": []})
    globales = lecture.macro_globales()
    if df.empty or (fng.empty and globales.empty):
        return df

    fng_i = fng.set_index("date") if "date" in fng.columns else fng
    macro = fng_i.join(globales, how="outer") if not globales.empty else fng_i
    # Le F&G est quotidien (week-end compris) mais FRED ne l'est pas : le join externe cree
    # des lignes week-end avec NaN sur les colonnes FRED. On les forward-fill (valeur de
    # vendredi) AVANT le decalage, sinon le NaN du week-end se propage au lundi via le lag.
    macro = macro.ffill()
    macro = macro.reset_index()
    macro["date"] = macro["date"] + pd.Timedelta(days=1)
    macro["date"] = macro["date"].astype(df["date"].dtype)
    df = df.sort_values("date")
    return pd.merge_asof(df, macro, on="date", direction="backward",
                         allow_exact_matches=False)


def trades_du_run(run: Run, series: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Applique la candidate a chaque paire et empile les trades. Une ligne = un signal."""
    morceaux = []
    for paire, df in series.items():
        if df.empty:
            continue
        signaux = run.candidate.appliquer(df)
        trades = espace_r.evaluer(
            df, signaux, take_profit_r=run.take_profit_r,
            horizon_bougies=run.horizon_bougies, stop_atr=run.stop_atr,
            cout_aller_retour_pct=run.cout_aller_retour_pct, paire=paire)
        if not trades.empty:
            morceaux.append(trades)
    if not morceaux:
        return espace_r._vide()
    return pd.concat(morceaux, ignore_index=True).sort_values("ts_entree") \
        .reset_index(drop=True)


def _resultats_synthetiques(run: Run, series: dict[str, pd.DataFrame],
                            generateur: str, n_chemins: int) -> list[float]:
    """Rejoue la candidate sur des marches fabriques. Retourne le R total de chaque chemin.

    Le rejeu se fait sur la PREMIERE paire seulement : le cout est lineaire en nombre de
    paires, et le temoin n'a pas besoin d'etre plus riche que la question qu'il pose
    (« cette forme de signal gagne-t-elle sur une serie sans structure ? »). C'est une
    limite assumee, elle est ecrite dans les reserves du verdict.
    """
    if not series:
        return []
    paire, df = next(iter(series.items()))
    fabrique = synthetique.GENERATEURS[generateur]
    totaux = []
    for i, faux in enumerate(fabrique(df, n_chemins, graine=run.graine)):
        try:
            signaux = run.candidate.appliquer(faux)
            trades = espace_r.evaluer(
                faux, signaux, take_profit_r=run.take_profit_r,
                horizon_bougies=run.horizon_bougies, stop_atr=run.stop_atr,
                cout_aller_retour_pct=run.cout_aller_retour_pct, paire=f"{paire}~{i}")
        except Exception as exc:                     # noqa: BLE001 - un chemin ne doit pas
            log.debug("chemin synthetique %d ecarte : %s", i, exc)   # tuer le temoin entier
            continue
        totaux.append(float(trades["r"].dropna().sum()) if not trades.empty else 0.0)
    return totaux


def executer(run: Run, *, equities_voisines: dict[str, pd.DataFrame] | None = None,
             univers_candidates: dict[str, np.ndarray] | None = None,
             famille: pd.DataFrame | None = None, n_essais: int | None = None,
             generateur_synthetique: str = "phase",
             n_chemins: int = N_CHEMINS_SYNTHETIQUES,
             enregistrer: bool = True) -> tuple[Verdict, dict]:
    """Le run complet. Rend (verdict, artefacts) — artefacts contient trades et courbes.

    `famille` ferme la dette T9. Sans elle, `batterie.evaluer` laissait
    `portes["S1_benjamini_hochberg"]` a `None`, et comme `issue()` n'accorde CONFIRMEE que
    si les NEUF portes ont tourne, le plafond du banc etait INDECIDABLE : aucune candidate
    ne pouvait etre confirmee, jamais. Elle se construit dans `cribler()`, parce qu'une
    correction de tests multiples sur une famille d'un seul element ne corrige rien.

    `n_essais` fige N pour tout un lot. Depuis A1, chaque run journalise fait monter le
    compteur ; laisser chaque candidate lire `compteur()` a son tour jugerait la derniere
    du lot plus severement que la premiere, pour la seule raison qu'elle est passee apres.
    """
    series = series_du_run(run)
    if not series:
        raise lecture.DataError(f"aucune serie disponible pour {run.paires} "
                                f"en {run.timeframe} — construire le lake d'abord")

    tous = trades_du_run(run, series)
    sequence = espace_r.enchainer(tous)
    courbe = espace_r.equity(sequence, CAPITAL, RISQUE_PAR_TRADE_PCT)

    synthetiques = _resultats_synthetiques(run, series, generateur_synthetique, n_chemins) \
        if n_chemins else []

    n = experiences.compteur() if n_essais is None else int(n_essais)
    resultat = batterie.evaluer(
        sequence, equity=courbe, series_marche=series,
        n_essais=n, cout_aller_retour_pct=run.cout_aller_retour_pct,
        resultats_synthetiques=synthetiques, equities_voisines=equities_voisines,
        nom=run.candidate.nom, univers_candidates=univers_candidates,
        famille=famille, graine=run.graine)

    reserves = list(resultat["reserves"])
    reserves.append(f"chemins synthetiques rejoues sur {next(iter(series))} seulement "
                    f"({generateur_synthetique}, {len(synthetiques)} chemins)")
    reserves.append(f"{len(tous)} signaux mesures, {len(sequence)} retenus apres "
                    "elimination des chevauchements")

    if famille is None:
        reserves.append("S1 non executee : run hors lot, donc sans famille declaree — "
                        "l'issue ne peut pas depasser INDECIDABLE")

    verdict = Verdict(
        run=run, issue=batterie.issue(resultat["portes"], len(sequence)),
        metriques=resultat["metriques"], portes=resultat["portes"],
        reserves=tuple(reserves), n_essais_cumules=n)

    artefacts = {"trades": tous, "sequence": sequence, "equity": courbe,
                 "detail": resultat["detail"], "series": list(series)}
    if enregistrer:
        _ecrire(verdict, artefacts)
    log.info("%s", verdict.texte())
    return verdict, artefacts


def _ecrire(verdict: Verdict, artefacts: dict) -> None:
    """Un dossier par run : le verdict, le detail de la batterie, les trades.

    Ecrit sous `data/`, donc jetable (invariant n° 7). Ce qui doit survivre a un effacement
    de `data/` est le PREENREGISTREMENT, qui vit dans EXPERIMENTS.jsonl a la racine.
    """
    # Le journal des runs vit a la RACINE, pas ici : il doit survivre a un effacement de
    # `data/`, sinon le nombre de mesures effectuees redevient inconnu au premier nettoyage.
    experiences.enregistrer_run(
        verdict.run.id, verdict.run.id_experience, verdict.run.candidate.nom,
        verdict.run.candidate.empreinte, verdict.issue)

    # T10 : sans cette ligne, EXPERIMENTS.jsonl continuait d'annoncer `preenregistre` une
    # hypothese deja mesuree. La CLOTURE reste un geste separe — sous une meme hypothese,
    # l'atelier mesure plusieurs candidates, et clore a la premiere interdirait les autres.
    experiences.marquer_mesuree(verdict.run.id_experience, verdict.run.id, verdict.issue)

    dossier = RESULTATS / verdict.run.id
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "verdict.json").write_text(
            json.dumps(verdict.dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        (dossier / "batterie.json").write_text(
            json.dumps(artefacts["detail"], indent=2, ensure_ascii=False, default=str),
            encoding="utf-8")
        artefacts["sequence"].to_parquet(dossier / "trades.parquet", index=False)
        artefacts["equity"].to_parquet(dossier / "equity.parquet", index=False)
    except (OSError, ValueError) as exc:
        log.warning("resultats du run %s non ecrits (%s)", verdict.run.id, exc)


def _p_representative(detail: dict) -> float:
    """La p-value d'une candidate pour S1 : la PIRE des trois longueurs de bloc.

    `bootstrap.sensibilite` rend une p par longueur, et `bootstrap.stable` exige qu'elles
    passent TOUTES. Nourrir Benjamini-Hochberg avec la meilleure des trois contredirait la
    porte d'a cote et choisirait un chiffre apres l'avoir vu — la fraude que S1 est
    justement la pour empecher.
    """
    lignes = detail.get("S3_bootstrap") or []
    valeurs = [float(x["p_value"]) for x in lignes
               if x.get("p_value") is not None and np.isfinite(float(x["p_value"]))]
    return max(valeurs) if valeurs else float("nan")


def _famille_du_lot(premiers: dict[str, tuple[Verdict, dict]]) -> pd.DataFrame:
    """La famille declaree du lot, complete par des lignes a p = 1 si elle est incomplete.

    Meme construction que `scripts/mesurer.py` et pour la meme raison : BH a besoin du m de
    la famille DECLAREE, pas du nombre de tests qui ont abouti. Sans ce remplissage, ne
    mesurer que les deux candidates les plus prometteuses d'un lot de dix relacherait
    mecaniquement le seuil des deux — il suffirait d'abandonner les huit autres en cours de
    route pour se donner raison.
    """
    lignes = [{"nom": verdict.run.candidate.nom, "p_brute": _p_representative(art["detail"])}
              for _, (verdict, art) in premiers.items()]
    lignes = [x for x in lignes if np.isfinite(x["p_brute"])]
    if not lignes:
        return pd.DataFrame()

    declare = 0
    for _, (verdict, _) in premiers.items():
        taille = verdict.run.preenregistrement.get("famille_taille") or 0
        declare = max(declare, int(taille))
    declare = max(declare, len(premiers))

    for i in range(len(lignes), declare):
        lignes.append({"nom": f"(non mesuree {i + 1})", "p_brute": 1.0})
    table = pd.DataFrame(lignes)
    table["m_declare"] = declare
    return table


def cribler(candidates: dict[str, Candidate], paires: tuple[str, ...], timeframe: str,
            **options) -> dict[str, Verdict]:
    """Passe un lot de candidates a la batterie, puis leur applique S1, S7 et S9 ENSEMBLE.

    Le second passage n'est pas une elegance : les trois portes qui comparent les candidates
    entre elles (correction BH sur la famille, reality check du maximum, correlation des
    equity) n'ont aucun sens candidate par candidate. Les calculer au premier passage
    donnerait des resultats faux dans le sens flatteur — chaque candidate se croirait seule
    au monde.

    **N est fige avant le premier passage** (A1) : `compteur() + taille du lot`. Le lot est
    donc paye d'avance, avant qu'aucun resultat ne soit connu, et les dix candidates d'un
    meme lot sont jugees au meme seuil. Sur-estimer legerement N quand une candidate est
    re-criblee a l'identique est le sens conservateur : cela durcit, cela ne flatte pas.
    """
    n_lot = experiences.compteur() + len(candidates)
    log.info("criblage de %d candidate(s) a N = %d essais cumules figes",
             len(candidates), n_lot)

    premiers: dict[str, tuple[Verdict, dict]] = {}
    for nom, candidate in candidates.items():
        try:
            run = Run(candidate=candidate, paires=paires, timeframe=timeframe, **options)
            premiers[nom] = executer(run, n_chemins=0, n_essais=n_lot, enregistrer=False)
        except Exception as exc:                     # noqa: BLE001 - une candidate cassee
            log.error("candidate '%s' ecartee du criblage : %s", nom, exc)

    equities = {nom: art["equity"] for nom, (_, art) in premiers.items()}
    univers = {nom: art["sequence"]["r"].dropna().to_numpy()
               for nom, (_, art) in premiers.items()
               if not art["sequence"].empty}
    famille = _famille_du_lot(premiers)

    verdicts = {}
    for nom, (verdict, _) in premiers.items():
        run = verdict.run
        try:
            final, _ = executer(run, equities_voisines={k: v for k, v in equities.items()
                                                        if k != nom},
                                univers_candidates=univers, famille=famille,
                                n_essais=n_lot)
            verdicts[nom] = final
        except Exception as exc:                     # noqa: BLE001
            log.error("second passage de '%s' echoue : %s", nom, exc)
            verdicts[nom] = verdict
    return verdicts
