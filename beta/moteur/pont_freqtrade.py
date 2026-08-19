"""M3 — le pont freqtrade : le seul verdict PORTEFEUILLE du banc d'essai.

`espace_r` mesure la geometrie d'un signal, trade par trade, en R. C'est ce qu'il faut pour
cribler des centaines de candidates, et ce n'est PAS un resultat de portefeuille : il ignore
les frais de financement, la concurrence entre positions pour les slots, le compounding, la
taille de position variable et les protections. Une candidate peut avoir un excellent R
moyen et un compte en perte — le cas se produit des que les meilleurs signaux tombent
pendant qu'on est deja pris ailleurs.

D'ou ce pont, et sa regle d'usage : **une seule candidate y passe, celle qui a survecu a la
batterie.** L'exporter avant est une perte de temps ; l'exporter pour « voir » revient a
ajouter un essai au compteur sans l'avoir preenregistre.

Le fichier genere importe la candidate depuis `beta.candidates` au lieu de recopier sa
logique : sans cela, la strategie freqtrade et la candidate BETA divergeraient au premier
correctif, et l'on comparerait deux choses differentes en croyant valider la meme.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import sys

from beta import config
from beta.moteur.contrats import ContratError, Run, Verdict

log = logging.getLogger("beta.moteur.pont")

DOSSIER_STRATEGIES = config.USERDIR / "strategies"
TIMEOUT_BACKTEST_S = 3600

# `--enable-protections` et `--timeframe-detail 5m` ne sont pas optionnels : sans le detail
# 5 min, freqtrade evalue stop et cible sur la bougie entiere et se trompe systematiquement
# dans le sens favorable ; sans les protections, on mesure une strategie que l'on ne
# lancerait jamais telle quelle.
DRAPEAUX_IMPOSES = ("--enable-protections", "--timeframe-detail", "5m")

MODELE = '''"""Strategie freqtrade generee par BETA — NE PAS EDITER A LA MAIN.

Candidate : {nom} ({module}, empreinte {empreinte})
Experience : {experience}
Run BETA   : {run_id}

Editer ce fichier ferait diverger la confirmation freqtrade de la candidate qu'elle est
censee confirmer. Pour changer quelque chose, changer la candidate et reexporter.
"""

from __future__ import annotations

import sys

import pandas as pd
from freqtrade.strategy import IStrategy

sys.path.insert(0, r"{racine}")

from beta.candidates import {module} as _candidate_module  # noqa: E402

_CANDIDATE = _candidate_module.creer()


class {classe}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "{timeframe}"
    can_short = True
    process_only_new_candles = True
    use_custom_stoploss = True
    startup_candle_count = {warmup}

    # Le stop reel est porte par custom_stoploss (distance en ATR, comme dans le criblage).
    # Ce stoploss-la n'est qu'un garde-fou de dernier recours, volontairement tres large.
    stoploss = -0.99
    minimal_roi = {{"0": 10}}

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        from beta.moteur import espace_r

        signaux = _CANDIDATE.appliquer(dataframe)
        dataframe["beta_sens"] = signaux["sens"]
        atr = espace_r.atr(dataframe)
        dataframe["beta_risque"] = (signaux["stop_distance"]
                                    if "stop_distance" in signaux.columns
                                    else {stop_atr} * atr)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        risque_valide = dataframe["beta_risque"] > 0
        dataframe.loc[(dataframe["beta_sens"] > 0) & risque_valide, "enter_long"] = 1
        dataframe.loc[(dataframe["beta_sens"] < 0) & risque_valide, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        return dataframe          # sortie par barriere uniquement, comme dans le criblage

    def custom_stoploss(self, pair, trade, current_time, current_rate, after_fill,
                        **kwargs) -> float:
        """Stop fixe a la distance mesuree a l'entree. Aucun trailing : c'est le point de R1."""
        risque = self._risque(pair, trade)
        if not risque or not trade.open_rate:
            return -0.99
        return -(risque / trade.open_rate)

    def custom_exit(self, pair, trade, current_time, current_rate, current_profit, **kwargs):
        """Cible a +{take_profit_r} R, mesuree sur le meme risque que le stop."""
        risque = self._risque(pair, trade)
        if not risque or not trade.open_rate:
            return None
        gain_r = ((current_rate - trade.open_rate) * (-1 if trade.is_short else 1)) / risque
        if gain_r >= {take_profit_r}:
            return "cible_r"
        duree_h = (current_time - trade.open_date_utc).total_seconds() / 3600.0
        if duree_h >= {horizon_h}:
            return "horizon"
        return None

    def _risque(self, pair: str, trade) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return 0.0
        ligne = dataframe.loc[dataframe["date"] <= trade.open_date_utc]
        if ligne.empty:
            return 0.0
        valeur = float(ligne["beta_risque"].iloc[-1])
        return valeur if valeur > 0 else 0.0
'''


def nom_de_classe(nom: str) -> str:
    return "Beta" + "".join(morceau.capitalize() for morceau in nom.replace("-", "_")
                            .split("_") if morceau)


def exporter(run: Run, module_candidate: str, verdict: Verdict | None = None,
             dossier: pathlib.Path | None = None, forcer: bool = False) -> pathlib.Path:
    """Ecrit la strategie freqtrade correspondant a une candidate. Rend le chemin du fichier.

    Refuse une candidate qui n'a pas survecu a la batterie, sauf `forcer=True` — auquel cas
    le refus devient un avertissement journalise. Le garde-fou n'est pas la pour empecher
    une exploration deliberee, mais pour empecher l'export machinal d'une candidate qu'on
    n'a pas encore le droit de prendre au serieux.
    """
    if verdict is not None and not verdict.survit and not forcer:
        raise ContratError(
            f"{run.candidate.nom} n'a pas survecu a la batterie (issue {verdict.issue}, "
            f"portes echouees : {verdict.portes_echouees or 'aucune'}). "
            "Le pont freqtrade est reserve aux survivantes ; passer forcer=True pour "
            "outrepasser, en sachant que le run comptera dans le compteur d'essais.")
    if verdict is None:
        log.warning("export sans verdict : la confirmation portefeuille n'a de sens "
                    "qu'apres la batterie")

    dossier = dossier or DOSSIER_STRATEGIES
    dossier.mkdir(parents=True, exist_ok=True)
    classe = nom_de_classe(run.candidate.nom)
    contenu = MODELE.format(
        nom=run.candidate.nom, module=module_candidate,
        empreinte=run.candidate.empreinte, experience=run.id_experience, run_id=run.id,
        racine=str(config.RACINE), classe=classe, timeframe=run.timeframe,
        stop_atr=run.stop_atr, take_profit_r=run.take_profit_r,
        horizon_h=run.horizon_bougies * _minutes(run.timeframe) / 60.0,
        warmup=max(100, run.horizon_bougies))
    chemin = dossier / f"{classe}.py"
    chemin.write_text(contenu, encoding="utf-8")
    log.info("strategie exportee : %s", chemin)
    return chemin


def _minutes(timeframe: str) -> int:
    from beta.lake import univers
    return univers.pas_minutes(timeframe)


def commande(run: Run, chemin_strategie: pathlib.Path) -> list[str]:
    """La ligne de commande freqtrade du run. Construite ici pour rester verifiable."""
    from beta.lake import univers
    debut = (run.debut or "20190901").replace("-", "")
    fin = (run.fin or "").replace("-", "")
    plage = f"{debut}-{fin}" if fin else f"{debut}-"
    return [sys.executable, "-m", "freqtrade", "backtesting",
            "--userdir", str(config.USERDIR),
            "--datadir", str(config.BRUT),
            "--strategy", chemin_strategie.stem,
            "--strategy-path", str(chemin_strategie.parent),
            "--timeframe", run.timeframe,
            "--timerange", plage,
            "--pairs", *[univers.resoudre(p).symbole for p in run.paires],
            "--trading-mode", config.TRADING_MODE,
            "--export", "trades",
            *DRAPEAUX_IMPOSES]


def confirmer(run: Run, module_candidate: str, verdict: Verdict | None = None,
              forcer: bool = False) -> dict:
    """Exporte puis lance le backtest freqtrade. Rend le compte rendu d'execution.

    Le resultat n'est PAS interprete ici : il est importe par
    `beta.lake.strategie.importer_backtests`, comme n'importe quel autre backtest. Un
    backtest de confirmation qui aurait son propre chemin de lecture finirait par avoir ses
    propres conventions, et ne serait plus comparable au reste.
    """
    chemin = exporter(run, module_candidate, verdict, forcer=forcer)
    argv = commande(run, chemin)
    log.info("freqtrade : %s", " ".join(argv))
    try:
        proces = subprocess.run(argv, capture_output=True, text=True,
                                timeout=TIMEOUT_BACKTEST_S, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        log.error("backtest de confirmation impossible : %s", exc)
        return {"ok": False, "erreur": str(exc), "strategie": str(chemin)}
    if proces.returncode:
        log.error("freqtrade a echoue (code %d)\n%s", proces.returncode,
                  proces.stderr[-2000:])
    return {"ok": proces.returncode == 0, "code": proces.returncode,
            "strategie": str(chemin), "commande": argv,
            "sortie": proces.stdout[-4000:], "erreur": proces.stderr[-4000:]}
