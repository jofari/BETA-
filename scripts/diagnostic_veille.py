"""Diagnostic de la VEILLE des voies C2 (VC2, VC3, VC4, VC5) — Jonas, 19/11/2026.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/diagnostic_veille.py

Question : quelle part de la perte des voies vient des jours de veille, et ce trou est-il
deja visible dans le backtest (2021-06-12 -> aujourd'hui), en particulier en 2022 ?

DIAGNOSTIC DESCRIPTIF. Aucune hypothese nouvelle, aucune variante, aucun reglage : le
programme relit les journaux forward (SUIVI_*.jsonl) et rejoue les configurations
PREENREGISTREES telles quelles (`voie_c2.config` verifie leur empreinte). Il n'avance aucun
compteur et ne rend aucun verdict. Le hold-out de l'allocation quotidienne est deja consomme
depuis le 13/10 (invariant n° 5) : rejouer la chaine dessus ne choisit rien.

Ecrit rapports/DIAGNOSTIC_VEILLE_2026-11-19/RAPPORT.md et RESUME_DISCORD.md.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.strategies import voie_c2 as c2  # noqa: E402

log = logging.getLogger("diagnostic_veille")
SORTIE = RACINE / "rapports" / "DIAGNOSTIC_VEILLE_2026-11-19"
ETATS = (c2.HAUSSIER, c2.VEILLE, c2.BAISSIER)
VOIES_JOURNAL = ("VC2", "VC3", "VC4", "VC5")
VOIES_BACKTEST = ("VC2", "VC3", "VC5")  # VC4 est intrajournaliere : pas de rejeu ici


def pct(x: float) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x * 100:+.2f} %".replace(".", ",")


def nb(x: float, c: int = 2) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x:.{c}f}".replace(".", ",")


def part(x: float) -> str:
    return "—" if x is None or not np.isfinite(x) else f"{x * 100:.1f} %".replace(".", ",")


def compose(r) -> float:
    r = np.asarray(r, float)
    return float(np.prod(1.0 + r) - 1.0) if len(r) else float("nan")


# =========================================================================================
# 1. Forward : les journaux tels qu'ecrits par les timers
# =========================================================================================

def lire_journal(nom: str) -> pd.DataFrame:
    lignes = [json.loads(l) for l in (RACINE / f"SUIVI_{nom}.jsonl").read_text().splitlines()
              if l.strip()]
    df = pd.DataFrame(lignes)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def par_etat(df: pd.DataFrame, col_r: str, col_btc: str, col_brut: str | None) -> list[dict]:
    """Une ligne par etat : jours, brut moyen, rendement compose de la voie et de BTC,
    part de la perte totale (en somme de log-rendements)."""
    log_tot = float(np.log1p(df[col_r]).sum())
    out = []
    for e in ETATS:
        s = df[df["etat"] == e]
        lg = float(np.log1p(s[col_r]).sum()) if len(s) else 0.0
        out.append({"etat": e, "jours": len(s),
                    "brut": float(s[col_brut].mean()) if col_brut and len(s) else float("nan"),
                    "r_voie": compose(s[col_r]), "r_btc": compose(s[col_btc]),
                    "part": lg / log_tot if log_tot != 0 else float("nan")})
    return out


def table_etats(lignes: list[dict]) -> list[str]:
    t = ["| Régime | Jours | Exposition brute moyenne | Rendement de la voie | Rendement BTC "
         "les mêmes jours | Part du résultat total (log) |", "|---|---|---|---|---|---|"]
    for x in lignes:
        t.append(f"| {x['etat']} | {x['jours']} | {nb(x['brut'])} | {pct(x['r_voie'])} | "
                 f"{pct(x['r_btc'])} | {part(x['part'])} |")
    return t


def episodes(etat: pd.Series, r: pd.Series, btc: pd.Series, brut: pd.Series,
             cible: str = c2.VEILLE) -> pd.DataFrame:
    """Les suites de jours consecutifs dans l'etat `cible`."""
    bloc = (etat != etat.shift()).cumsum()
    rows = []
    for _, idx in etat[etat == cible].groupby(bloc[etat == cible]).groups.items():
        rows.append({"debut": idx[0], "fin": idx[-1], "jours": len(idx),
                     "brut_debut": float(brut.loc[idx[0]]), "brut_fin": float(brut.loc[idx[-1]]),
                     "r_voie": compose(r.loc[idx]), "r_btc": compose(btc.loc[idx])})
    return pd.DataFrame(rows)


# =========================================================================================
# 2. Backtest : la chaine preenregistree rejouee sur tout le lake
# =========================================================================================

def rejouer(nom: str, d: dict) -> pd.DataFrame:
    cfg = c2.config(nom)
    res = c2.calculer(d, cfg)
    jours = res["jours"]
    pos = pd.DataFrame(res["positions"], index=jours, columns=list(cfg["paires"]))
    voulu = res["cible"].fillna(0.0).abs().sum(axis=1)
    if cfg.get("plafond_brut") is not None:
        voulu = voulu.clip(upper=cfg["plafond_brut"])
    rend_btc = d["closes"]["BTC"].pct_change().reindex(jours)
    return pd.DataFrame({"etat": res["etat"], "r_net": res["r_net"], "r_btc": rend_btc.fillna(0.0),
                         "brut": pos.abs().sum(axis=1), "brut_voulu": voulu,
                         "turnover": res["turnover"]}, index=jours)


def max_dd(r: pd.Series) -> float:
    e = (1.0 + r).cumprod()
    return float((e / e.cummax() - 1.0).min())


# =========================================================================================
# Rapport
# =========================================================================================

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    SORTIE.mkdir(parents=True, exist_ok=True)
    R: list[str] = []
    resume: list[str] = []
    R += ["# Diagnostic de la veille des voies C2 — " + f"{dt.date.today():%d/%m/%Y}", "",
          "Écrit par `scripts/diagnostic_veille.py`. **Diagnostic descriptif** : aucune "
          "variante, aucun réglage, aucun essai consommé, aucun verdict. Configurations "
          "préenregistrées rejouées telles quelles (empreintes vérifiées).", "",
          "Rappel de la règle de veille (préenregistrée le 07/10) : aucun ajout ; l'exposition "
          "ne baisse, au prorata, que si le brut voulu par le moteur haussier passe sous le "
          "brut tenu de plus que la bande (0,2).", ""]

    # ---------- 1. Forward
    R += ["## 1. Forward (journaux SUIVI_*.jsonl)", ""]
    for nom in VOIES_JOURNAL:
        df = lire_journal(nom)
        tot = compose(df["r_net"])
        R += [f"### {nom} — du {df['date'].iloc[0]:%d/%m/%Y} au {df['date'].iloc[-1]:%d/%m/%Y} "
              f"({len(df)} jours) : voie {pct(tot)}, BTC {pct(compose(df['btc_r']))}", ""]
        R += table_etats(par_etat(df, "r_net", "btc_r", "brut")) + [""]
        ep = episodes(df.set_index("date")["etat"], df.set_index("date")["r_net"],
                      df.set_index("date")["btc_r"], df.set_index("date")["brut"])
        if len(ep):
            R += ["Épisodes de veille :", "",
                  "| Début | Fin | Jours | Brut au début | Brut à la fin | Voie | BTC |",
                  "|---|---|---|---|---|---|---|"]
            for _, x in ep.iterrows():
                R.append(f"| {x.debut:%d/%m} | {x.fin:%d/%m} | {x.jours} | {nb(x.brut_debut)} | "
                         f"{nb(x.brut_fin)} | {pct(x.r_voie)} | {pct(x.r_btc)} |")
            R.append("")
        pe = par_etat(df, "r_net", "btc_r", "brut")
        v = next(x for x in pe if x["etat"] == c2.VEILLE)
        resume.append(f"- **{nom}** forward {pct(tot)} (BTC {pct(compose(df['btc_r']))}) ; "
                      f"veille : {v['jours']} j, exposition moyenne {nb(v['brut'])}, "
                      f"voie {pct(v['r_voie'])} contre BTC {pct(v['r_btc'])}, "
                      f"{part(v['part'])} de la perte totale")

    # ---------- 2. Backtest
    log.info("chargement du lake")
    d = c2.donnees()
    R += ["## 2. Backtest (chaîne préenregistrée rejouée du 12/06/2021 à la dernière clôture)", "",
          "VC4 (décidée trois fois par jour) n'est pas rejouée ici.", ""]
    resume_bt: list[str] = []
    for nom in VOIES_BACKTEST:
        log.info("rejeu %s", nom)
        bt = rejouer(nom, d)
        R += [f"### {nom} — voie {pct(compose(bt['r_net']))}, maxDD {pct(max_dd(bt['r_net']))} ; "
              f"BTC {pct(compose(bt['r_btc']))}, maxDD {pct(max_dd(bt['r_btc']))}", ""]
        df = bt.reset_index()
        R += table_etats(par_etat(df, "r_net", "r_btc", "brut")) + [""]

        # Par annee
        R += ["Par année, jours de veille seulement :", "",
              "| Année | Jours de veille | Brut tenu moyen | Brut voulu par le moteur | "
              "Voie en veille | BTC en veille | Voie sur l'année | BTC sur l'année |",
              "|---|---|---|---|---|---|---|---|"]
        for an, g in bt.groupby(bt.index.year):
            v = g[g["etat"] == c2.VEILLE]
            R.append(f"| {an} | {len(v)} | {nb(v['brut'].mean())} | {nb(v['brut_voulu'].mean())} | "
                     f"{pct(compose(v['r_net']))} | {pct(compose(v['r_btc']))} | "
                     f"{pct(compose(g['r_net']))} | {pct(compose(g['r_btc']))} |")
        R.append("")

        # Reductions effectives en veille
        v = bt[bt["etat"] == c2.VEILLE]
        n_red = int((v["turnover"] > 1e-9).sum())
        ecart = (v["brut"] - v["brut_voulu"])
        R += [f"Jours de veille où la voie a réellement vendu : **{n_red} sur {len(v)}**. "
              f"Écart moyen brut tenu − brut voulu en veille : {nb(ecart.mean())} "
              f"(jours où l'écart dépasse la bande 0,2 sans vente, à cause du calcul au "
              f"prorata : {int(((ecart > 0.2) & (v['turnover'] <= 1e-9)).sum())}).", ""]

        # Pires episodes de veille
        ep = episodes(bt["etat"], bt["r_net"], bt["r_btc"], bt["brut"])
        ep = ep.sort_values("r_btc").reset_index(drop=True)
        R += [f"{len(ep)} épisodes de veille. Les 10 où BTC a le plus baissé :", "",
              "| Rang | Début | Fin | Jours | Brut au début | Brut à la fin | Voie | BTC |",
              "|---|---|---|---|---|---|---|---|"]
        for i, x in ep.head(10).iterrows():
            R.append(f"| {i + 1} | {x.debut:%d/%m/%Y} | {x.fin:%d/%m/%Y} | {x.jours} | "
                     f"{nb(x.brut_debut)} | {nb(x.brut_fin)} | {pct(x.r_voie)} | {pct(x.r_btc)} |")
        R.append("")
        recent = ep[ep["debut"] >= pd.Timestamp("2026-10-01", tz="UTC")]
        rang = ""
        if len(recent):
            x = recent.sort_values("r_btc").iloc[0]
            k = int(ep.index[ep["debut"] == x.debut][0]) + 1
            rang = (f" ; épisode du {x.debut:%d/%m} au {x.fin:%d/%m} : rang {k} sur {len(ep)} "
                    f"par la baisse de BTC (voie {pct(x.r_voie)}, BTC {pct(x.r_btc)})")
        pe = par_etat(df, "r_net", "r_btc", "brut")
        vv = next(x for x in pe if x["etat"] == c2.VEILLE)
        y22 = bt[(bt.index.year == 2022) & (bt["etat"] == c2.VEILLE)]
        resume_bt.append(f"- **{nom}** backtest : veille {vv['jours']} j, voie {pct(vv['r_voie'])} "
                         f"contre BTC {pct(vv['r_btc'])} ; en 2022, veille {len(y22)} j, voie "
                         f"{pct(compose(y22['r_net']))} contre BTC {pct(compose(y22['r_btc']))} ; "
                         f"ventes en veille {n_red}/{len(v)} j{rang}")

    (SORTIE / "RAPPORT.md").write_text("\n".join(R) + "\n", encoding="utf-8")
    disc = ([f"# 🟠 Diagnostic de la veille des voies C — {dt.date.today():%d/%m/%Y}",
             "Écrit par le programme `scripts/diagnostic_veille.py`. Descriptif : aucun réglage, "
             "aucun essai, aucun verdict.", "", "## Forward"] + resume
            + ["", "## Backtest (12/06/2021 → dernière clôture)"] + resume_bt
            + ["", "Détail : `rapports/DIAGNOSTIC_VEILLE_2026-11-19/RAPPORT.md`."])
    (SORTIE / "RESUME_DISCORD.md").write_text("\n".join(disc) + "\n", encoding="utf-8")
    log.info("ecrit %s", SORTIE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
