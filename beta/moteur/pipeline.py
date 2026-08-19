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
    """OHLCV de chaque paire du run, deja borne au split autorise."""
    debut, fin = _bornes_du_split(run)
    series = {}
    for paire in run.paires:
        try:
            series[paire] = lecture.load(paire, run.timeframe, debut=debut, fin=fin)
        except lecture.DataError as exc:
            log.error("%s %s indisponible : %s", paire, run.timeframe, exc)
    return series


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
             generateur_synthetique: str = "phase",
             n_chemins: int = N_CHEMINS_SYNTHETIQUES,
             enregistrer: bool = True) -> tuple[Verdict, dict]:
    """Le run complet. Rend (verdict, artefacts) — artefacts contient trades et courbes."""
    series = series_du_run(run)
    if not series:
        raise lecture.DataError(f"aucune serie disponible pour {run.paires} "
                                f"en {run.timeframe} — construire le lake d'abord")

    tous = trades_du_run(run, series)
    sequence = espace_r.enchainer(tous)
    courbe = espace_r.equity(sequence, CAPITAL, RISQUE_PAR_TRADE_PCT)

    synthetiques = _resultats_synthetiques(run, series, generateur_synthetique, n_chemins) \
        if n_chemins else []

    resultat = batterie.evaluer(
        sequence, equity=courbe, series_marche=series,
        n_essais=experiences.compteur(), cout_aller_retour_pct=run.cout_aller_retour_pct,
        resultats_synthetiques=synthetiques, equities_voisines=equities_voisines,
        nom=run.candidate.nom, univers_candidates=univers_candidates, graine=run.graine)

    reserves = list(resultat["reserves"])
    reserves.append(f"chemins synthetiques rejoues sur {next(iter(series))} seulement "
                    f"({generateur_synthetique}, {len(synthetiques)} chemins)")
    reserves.append(f"{len(tous)} signaux mesures, {len(sequence)} retenus apres "
                    "elimination des chevauchements")

    verdict = Verdict(
        run=run, issue=batterie.issue(resultat["portes"], len(sequence)),
        metriques=resultat["metriques"], portes=resultat["portes"],
        reserves=tuple(reserves), n_essais_cumules=experiences.compteur())

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


def cribler(candidates: dict[str, Candidate], paires: tuple[str, ...], timeframe: str,
            **options) -> dict[str, Verdict]:
    """Passe un lot de candidates a la batterie, puis leur applique S7 et S9 ENSEMBLE.

    Le second passage n'est pas une elegance : les deux portes qui comparent les candidates
    entre elles (reality check du maximum, correlation des equity) n'ont aucun sens
    candidate par candidate. Les calculer au premier passage donnerait des resultats faux
    dans le sens flatteur — chaque candidate se croirait seule au monde.
    """
    premiers: dict[str, tuple[Verdict, dict]] = {}
    for nom, candidate in candidates.items():
        try:
            run = Run(candidate=candidate, paires=paires, timeframe=timeframe, **options)
            premiers[nom] = executer(run, n_chemins=0, enregistrer=False)
        except Exception as exc:                     # noqa: BLE001 - une candidate cassee
            log.error("candidate '%s' ecartee du criblage : %s", nom, exc)

    equities = {nom: art["equity"] for nom, (_, art) in premiers.items()}
    univers = {nom: art["sequence"]["r"].dropna().to_numpy()
               for nom, (_, art) in premiers.items()
               if not art["sequence"].empty}

    verdicts = {}
    for nom, (verdict, _) in premiers.items():
        run = verdict.run
        try:
            final, _ = executer(run, equities_voisines={k: v for k, v in equities.items()
                                                        if k != nom},
                                univers_candidates=univers)
            verdicts[nom] = final
        except Exception as exc:                     # noqa: BLE001
            log.error("second passage de '%s' echoue : %s", nom, exc)
            verdicts[nom] = verdict
    return verdicts
