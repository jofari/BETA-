"""Les donnees de STRATEGIE : ce qu'une strategie a decide, et ce que ca a donne.

L'autre moitie du lake. Le lake OHLCV dit ce que le marche a fait ; celui-ci dit ce que la
strategie en a fait — entrees, sorties, RAISONS, R, rendement.

Trois tables, parce que trois questions differentes :

| Table         | Repond a                                        | Source complete |
|---------------|-------------------------------------------------|-----------------|
| `trades`      | qu'est-ce qui a ete pris, et qu'est-ce que ca a rapporte ? | zip de backtest |
| `evaluations` | qu'est-ce qui a ete regarde, et POURQUOI c'est passe ou non ? | journal JSONL |
| `gestion`     | qu'est-ce qui s'est passe PENDANT la position ?  | journal JSONL   |

Constat qui explique ce decoupage (18/08) : le journal ne porte **aucun evenement de sortie
finale** — ses 4 084 evenements `gestion` sont des deplacements de stop (`SL`) et des prises
partielles (`G4`). Les sorties completes n'existent que dans le zip freqtrade. Inversement,
le zip ignore tout des signaux **rejetes** : les 1 427 `gate_check` du journal sont la seule
trace de ce qui n'a PAS ete pris, et de la porte qui a bloque. Aucune des deux sources ne
suffit seule, et croire le contraire, c'est mesurer sur un echantillon tronque.

La table `trades` est volontairement AGNOSTIQUE de sa source : un trade issu d'un backtest
freqtrade, d'un rejeu hors-ligne ou du futur moteur BETA a le meme schema. C'est ce qui
permettra a `stats/` de ne jamais savoir d'ou viennent les R qu'on lui donne.
"""

from __future__ import annotations

import json
import logging
import pathlib
import zipfile

import pandas as pd

from beta import config
from beta.protocole import holdout

log = logging.getLogger("beta.lake.strategie")

TABLES = ("trades", "evaluations", "gestion")

# Schema de `trades`. Une colonne absente d'une source reste a NaN — jamais inventee.
COLONNES_TRADES = (
    "source", "strategie", "run", "paire", "sens", "split",
    "ts_entree", "prix_entree", "ts_sortie", "prix_sortie", "raison_sortie",
    "r", "rendement_pct", "rendement_abs", "duree_h",
    "sl_initial", "mfe_r", "mae_r", "stake", "frais", "funding", "tag_entree",
)


class StrategieError(RuntimeError):
    """Source de donnees de strategie absente ou inexploitable."""


def chemin_table(nom: str) -> pathlib.Path:
    if nom not in TABLES:
        raise StrategieError(f"table inconnue : {nom} (connues : {TABLES})")
    return config.LAKE / f"strategie-{nom}.parquet"


# --------------------------------------------------------------------------------------
# Source 1 : les zips de backtest freqtrade — la seule qui porte les SORTIES
# --------------------------------------------------------------------------------------

def _ts_depuis_signal_id(signal_id: str) -> pd.Timestamp:
    """Date de la BOUGIE, extraite du signal_id (`BNBUSDT-2021.01.05.T000000Z`).

    ⚠️ PIEGE MAJEUR du journal d'ARIT, constate le 18/08 : `ts_utc` ne porte PAS la meme
    chose selon l'evenement. Sur `entry` c'est bien l'horodatage de la bougie ; sur
    `gestion` c'est l'horodatage d'EXECUTION du backtest (2026-08-04T15:28:50 pour un trade
    de janvier 2021). Se fier a `ts_utc` fait basculer cinq ans d'historique dans le
    hold-out et vide silencieusement toute mesure — c'est exactement ce qui est arrive au
    premier import.

    Le `signal_id`, lui, est construit a partir de la bougie : il est la seule source fiable.
    """
    if not isinstance(signal_id, str) or "-" not in signal_id:
        return pd.NaT
    _, _, partie = signal_id.partition("-")
    try:
        return pd.to_datetime(partie, format="%Y.%m.%d.T%H%M%SZ", utc=True)
    except (ValueError, TypeError):
        return pd.NaT


def _risque_unitaire(entree: float, sl: float) -> float:
    """Distance au stop initial, en unites de prix. C'est le denominateur de tout R.

    ⚠️ Le zip freqtrade ne permet PAS de le calculer pour ARIT : `initial_stop_loss_ratio`
    y vaut −0,99 sur tous les trades, parce que c'est le stoploss de SECOURS declare dans la
    strategie — ARIT pose son vrai stop par `custom_stoploss`, que le zip n'archive pas.
    Calculer R = profit_ratio / 0,99 donnerait un R numeriquement egal au rendement, avec un
    ecart-type de 0,02 la ou un vrai R vaut ~1,2. Faux, et credible : la pire combinaison.

    Le stop structurel vit dans le journal (`entry.sl_initial`), d'ou la jointure. Sans lui,
    on rend NaN — jamais un R invente.
    """
    if not entree or pd.isna(entree) or pd.isna(sl) or not sl:
        return float("nan")
    risque = abs(float(entree) - float(sl))
    return risque if risque > 0 else float("nan")


def lire_zip(chemin: pathlib.Path) -> pd.DataFrame:
    """Trades d'un zip de backtest freqtrade, au schema commun."""
    try:
        with zipfile.ZipFile(chemin) as z:
            noms = [n for n in z.namelist() if n.endswith(".json") and "config" not in n]
            if not noms:
                raise StrategieError(f"{chemin.name} : aucun resultat JSON")
            brut = json.loads(z.read(noms[0]))
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError, KeyError) as exc:
        raise StrategieError(f"{chemin.name} illisible : {exc}") from exc

    lignes = []
    for strategie, resultat in brut.get("strategy", {}).items():
        for t in resultat.get("trades", []):
            ouverture = pd.to_datetime(t.get("open_date"), utc=True)
            fermeture = pd.to_datetime(t.get("close_date"), utc=True)
            entree = t.get("open_rate")
            signe = -1.0 if t.get("is_short") else 1.0
            lignes.append({
                "source": f"backtest:{chemin.stem}", "strategie": strategie,
                "run": chemin.stem, "paire": t.get("pair"),
                "sens": "short" if t.get("is_short") else "long",
                "ts_entree": ouverture, "prix_entree": entree,
                "ts_sortie": fermeture, "prix_sortie": t.get("close_rate"),
                "raison_sortie": t.get("exit_reason"),
                # r / mfe_r / mae_r restent NaN ICI : le zip n'archive pas le stop
                # structurel d'ARIT. Ils sont poses par `attacher_stop_du_journal()`.
                "r": float("nan"), "mfe_r": float("nan"), "mae_r": float("nan"),
                "sl_initial": float("nan"),
                "rendement_pct": (t.get("profit_ratio") or 0) * 100,
                "rendement_abs": t.get("profit_abs"),
                "duree_h": (t.get("trade_duration") or 0) / 60,
                "stake": t.get("stake_amount"),
                "frais": (t.get("fee_open") or 0) + (t.get("fee_close") or 0),
                "funding": t.get("funding_fees"), "tag_entree": t.get("enter_tag"),
                "_favorable": t.get("max_rate" if signe > 0 else "min_rate"),
                "_adverse": t.get("min_rate" if signe > 0 else "max_rate"),
                "_signe": signe,
            })
    df = pd.DataFrame(lignes,
                      columns=[*COLONNES_TRADES, "_favorable", "_adverse", "_signe"])
    if not df.empty:
        df["split"] = holdout.split(df["ts_entree"])
    return df


def attacher_stop_du_journal(trades: pd.DataFrame, entrees: pd.DataFrame) -> pd.DataFrame:
    """Joint le stop structurel du journal aux trades du zip, puis en derive R, MFE et MAE.

    Jointure sur (paire, horodatage d'entree) : les deux sources decrivent les memes
    entrees, mais aucune ne porte l'identifiant de l'autre. Un trade dont le stop n'est pas
    retrouve garde `r` a NaN : il comptera dans `n` mais pas dans `n_avec_r`, et l'ecart
    entre ces deux nombres est la mesure honnete de ce qu'on ignore.
    """
    interne = [c for c in trades.columns if c.startswith("_")]
    if trades.empty or entrees.empty or "sl_initial" not in entrees.columns:
        log.warning("stops du journal indisponibles : les R restent NaN")
        return trades.drop(columns=interne)

    cle = entrees.copy()
    cle["ts_entree"] = pd.to_datetime(cle["ts_utc"], utc=True)
    garde = [c for c in ("pair", "ts_entree", "sl_initial", "conviction", "regime")
             if c in cle.columns]
    cle = (cle[garde].rename(columns={"pair": "paire", "sl_initial": "sl_journal"})
           .drop_duplicates(subset=["paire", "ts_entree"]))

    out = trades.merge(cle, on=["paire", "ts_entree"], how="left")
    risque = pd.Series(
        [_risque_unitaire(e, s)
         for e, s in zip(out["prix_entree"], out["sl_journal"], strict=True)],
        index=out.index)
    out["sl_initial"] = out["sl_journal"]
    # rendement_pct est en % du prix d'entree : le ramener en unites de prix avant de le
    # diviser par le risque, sinon le R depend du niveau de prix de la paire.
    out["r"] = out["rendement_pct"] / 100 * out["prix_entree"] / risque
    out["mfe_r"] = out["_signe"] * (out["_favorable"] - out["prix_entree"]) / risque
    out["mae_r"] = out["_signe"] * (out["_adverse"] - out["prix_entree"]) / risque
    retrouves = int(out["r"].notna().sum())
    log.info("stop structurel retrouve pour %d trades sur %d%s", retrouves, len(out),
             "" if retrouves == len(out) else " — les autres gardent r = NaN")
    return out.drop(columns=[c for c in out.columns if c.startswith("_")] + ["sl_journal"])


def importer_backtests(dossier: pathlib.Path | None = None) -> pd.DataFrame:
    """Tous les zips d'un dossier, concatenes. Les runs a zero trade sont ignores en silence
    (ce sont des runs de periode vide, pas des erreurs)."""
    dossier = dossier or config.ARIT / "user_data" / "backtest_results"
    if not dossier.exists():
        raise StrategieError(f"dossier de backtests absent : {dossier}")
    morceaux = []
    for zip_ in sorted(dossier.glob("*.zip")):
        try:
            df = lire_zip(zip_)
        except StrategieError as exc:
            log.warning("%s ignore : %s", zip_.name, exc)
            continue
        if df.empty:
            log.debug("%s : aucun trade", zip_.name)
            continue
        log.info("%-42s %3d trades · %s -> %s", zip_.stem[:42], len(df),
                 str(df["ts_entree"].min())[:10], str(df["ts_sortie"].max())[:10])
        morceaux.append(df)
    return (pd.concat(morceaux, ignore_index=True) if morceaux
            else pd.DataFrame(columns=list(COLONNES_TRADES)))


# --------------------------------------------------------------------------------------
# Source 2 : le journal de decisions — la seule qui porte les REJETS
# --------------------------------------------------------------------------------------

def lire_journal(dossier: pathlib.Path | None = None) -> dict[str, pd.DataFrame]:
    """Le journal JSONL, eclate par type d'evenement.

    `gate_check` est le plus precieux et le moins evident : c'est la trace des signaux
    REJETES, et de la porte exacte qui a bloque. Sans elle, on ne mesure que ce qui est
    passe — un echantillon selectionne par les regles qu'on cherche justement a evaluer.
    """
    dossier = dossier or config.ARIT / "user_data" / "logs" / "decisions"
    if not dossier.exists():
        raise StrategieError(f"journal absent : {dossier}")
    par_type: dict[str, list[dict]] = {}
    fichiers = sorted(dossier.glob("*.jsonl"))
    for fichier in fichiers:
        try:
            contenu = fichier.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("%s illisible : %s", fichier.name, exc)
            continue
        for n, ligne in enumerate(contenu.splitlines(), 1):
            if not ligne.strip():
                continue
            try:
                evenement = json.loads(ligne)
            except json.JSONDecodeError:
                log.warning("%s ligne %d illisible, ignoree", fichier.name, n)
                continue
            par_type.setdefault(evenement.get("event_type", "?"), []).append(evenement)
    log.info("journal : %d fichiers · %s", len(fichiers),
             " · ".join(f"{k} {len(v)}" for k, v in sorted(par_type.items())))
    return {t: pd.json_normalize(lignes) for t, lignes in par_type.items()}


def _horodater(df: pd.DataFrame) -> pd.DataFrame:
    """Pose `ts_bougie` (la date reelle) et le `split` qui en decoule.

    `ts_bougie` vient du `signal_id`, avec repli sur `ts_utc`. Voir le piege documente dans
    `_ts_depuis_signal_id` : `ts_utc` porte l'heure d'execution du backtest sur certains
    types d'evenements, ce qui projette tout l'historique dans le hold-out.
    """
    df = df.copy()
    df["ts_utc"] = pd.to_datetime(df["ts_utc"], utc=True, errors="coerce")
    depuis_id = (df["signal_id"].map(_ts_depuis_signal_id) if "signal_id" in df.columns
                 else pd.Series(pd.NaT, index=df.index))
    df["ts_bougie"] = depuis_id.fillna(df["ts_utc"])
    df["split"] = holdout.split(df["ts_bougie"])
    return df.sort_values("ts_bougie").reset_index(drop=True)


def evaluations_depuis_journal(par_type: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """`evaluation` + `gate_check` fusionnes : ce qui a ete regarde, et pourquoi ou pourquoi pas."""
    morceaux = []
    for nom in ("evaluation", "gate_check"):
        df = par_type.get(nom)
        if df is None or df.empty:
            continue
        df = df.copy()
        df["source"] = f"journal:{nom}"
        morceaux.append(df)
    if not morceaux:
        return pd.DataFrame()
    return _horodater(pd.concat(morceaux, ignore_index=True))


def gestion_depuis_journal(par_type: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Les evenements de vie d'une position : deplacements de stop, prises partielles."""
    df = par_type.get("gestion")
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["source"] = "journal:gestion"
    return _horodater(df)


# --------------------------------------------------------------------------------------
# Ecriture et lecture
# --------------------------------------------------------------------------------------

def ecrire(nom: str, df: pd.DataFrame) -> pathlib.Path:
    cible = chemin_table(nom)
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(cible, index=False, compression="zstd")
    except (OSError, ValueError) as exc:
        raise StrategieError(f"ecriture de {nom} impossible : {exc}") from exc
    log.info("%-12s %6d lignes -> %s", nom, len(df), cible.name)
    return cible


def lire(nom: str, train_seulement: bool = False) -> pd.DataFrame:
    """Une table de strategie. `train_seulement` est la voie sure pour toute mesure."""
    chemin = chemin_table(nom)
    if not chemin.exists():
        raise StrategieError(f"{nom} absent du lake. Lancer scripts/import_strategie.py.")
    try:
        df = pd.read_parquet(chemin)
    except (OSError, ValueError) as exc:
        raise StrategieError(f"lecture de {nom} impossible : {exc}") from exc
    if train_seulement and "split" in df.columns:
        df = df[df["split"] == holdout.TRAIN].copy()
    return df
