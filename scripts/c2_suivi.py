"""Voie C2 (VC2, VC3) — suivi FORWARD au cours de cloture. Ne passe aucun ordre.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/c2_suivi.py --id VC3

Chaque jour (timers beta-suivi-vc3 et beta-suivi-vc2, 00:50 UTC, apres beta-maj), pour chaque
journee CLOSE d >= debut du rattrapage pas encore journalisee, ajoute une ligne a
SUIVI_<id>.jsonl : l'etat du regime et ses 5 votes, la position tenue pendant d, son
rendement brut et net, et les deux holds de reference (BTC, equipondere ; funding deduit pour
une config en perpetuels) ; sur la derniere ligne, la consigne pour d+1, que le paper trading
(`scripts/paper.py`) execute. Le journal ne fait que CROITRE : une ligne ecrite n'est jamais
reecrite.

Deux experiences, et deux statuts differents dans le registre :
    VC3  CONFIRMEE le 07/10 (`scripts/mesurer_vc3.py`) : dry-run de 6 mois, live des le
         2026-10-08, criteres du registre (maxDD >= -25 %, vol 10-30 %).
    VC2  INFIRMEE le 07/10 (`scripts/mesurer_vc2.py`) : suivie a la demande de Jonas (08/10),
         a titre INFORMATIF seulement. Aucun critere de dry-run, aucune alarme ; un bon
         resultat forward ne la rehabilite pas — il faudrait un nouveau preenregistrement.

Tout vient du registre : la config, relue et verifiee par `voie_c2.config`, et les dates de
rattrapage et de live. Seules les empreintes sont epinglees ici, pour qu'un nouveau
preenregistrement sous le meme id ne passe pas en silence.

Le chemin est celui de la mesure : simule depuis le 2021-06-12 sur toutes les donnees du
lake. L'etat au debut du suivi (episode baissier, plus haut de l'equite, bande) est donc
exactement celui du backtest, pas un portefeuille qui demarre a plat.

La consigne de d+1 n'est pas un calcul a part : c'est la ligne d+1 de la meme chaine, sur les
donnees prolongees d'une journee fictive (cloture de d recopiee). La ligne d+1 ne lit que ce
qui est public a d+1 00:00 UTC — c'est ce que verifie l'epreuve de perturbation de
`voie_c2` —, donc la valeur fictive ne la touche pas. Chaque jour, le script verifie en plus
que la prolongation laisse identiques toutes les journees deja closes.

Rattrapage ou live : une journee est « live » si elle est >= debut du live ET ecrite le
lendemain de sa cloture, comme le fait le timer. Tout le reste est du rattrapage, si propre
soit-il — y compris une journee que le timer aurait manquee.

Sortie non nulle = unite « failed » (`systemctl --failed`) :
    1  lake en retard (derniere journee close < hier), ou trou dans le calendrier du suivi
    2  empreinte differente de celle epinglee, ou journal d'une autre config
    3  la prolongation d'un jour change une journee deja close (causalite rompue)
    4  experience admise au dry-run seulement : maxDD depuis le debut du live < -25 %. Le
       journal est ecrit quand meme ; ce n'est pas une panne, c'est une alarme, et la suite
       est une decision de Jonas.
La vol realisee (critere 10-30 %, racine de 252) est affichee, pas jugee : sur quelques
semaines elle ne veut rien dire, elle se lit a 6 mois.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.protocole import experiences  # noqa: E402
from beta.strategies import voie_c2 as c2  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.c2_suivi")

# ⚠️ Les empreintes preenregistrees le 2026-10-07. Ne pas les changer : une autre config est
# une autre experience, avec son propre journal.
EMPREINTES = {"VC2": "744700fa7d8980fc", "VC3": "7adef08a837a8c50"}
MAXDD_MIN = -0.25                   # critere du dry-run (registre, regle « forward »)
VOL_MIN, VOL_MAX = 0.10, 0.30       # idem, lu a 6 mois seulement
DUREE_DRY_RUN = pd.DateOffset(months=6)
UN_JOUR = pd.Timedelta(days=1)


class CausaliteError(RuntimeError):
    """La prolongation d'un jour a change une journee deja close."""


def journal_par_defaut(id_exp: str) -> Path:
    return config.RACINE / f"SUIVI_{id_exp}.jsonl"


def lire_journal(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def dates_du_registre(id_exp: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Debut du rattrapage et debut du live, tels que preenregistres."""
    entree = experiences.exiger(id_exp)
    return (pd.Timestamp(entree["debut_rattrapage"], tz="UTC"),
            pd.Timestamp(entree["debut_live"], tz="UTC"))


def admise_au_dry_run(id_exp: str) -> bool:
    """Seule une experience CONFIRMEE par sa regle preenregistree a un dry-run a juger."""
    return experiences.exiger(id_exp).get("derniere_issue") == "confirmee"


def prolonger(d: dict) -> dict:
    """Les donnees plus la journee de demain, pas encore close : cloture de d recopiee.

    Les autres series sont laissees telles quelles : la ligne de demain ne lit que ce qui est
    date <= aujourd'hui (F&G), <= hier (FRED), et une valeur datee de demain n'existe pas.
    """
    closes = d["closes"]
    demain = pd.DatetimeIndex([closes.index[-1] + UN_JOUR], name=closes.index.name)
    return {**d, "closes": pd.concat([closes, closes.iloc[[-1]].set_axis(demain)])}


def suivre(d: dict, cfg: dict) -> dict:
    """La chaine sur les journees closes, et la consigne pour le lendemain."""
    res = c2.calculer(d, cfg)
    ext = c2.calculer(prolonger(d), cfg)
    n = len(res["jours"])
    ecarts = {
        "votes": float(np.abs(ext["votes"].to_numpy()[:n] - res["votes"].to_numpy()).max()),
        "etats": float((ext["etat"].to_numpy()[:n] != res["etat"].to_numpy()).sum()),
        "positions": float(np.abs(ext["positions"][:n] - res["positions"]).max()),
        "r_net": float(np.abs(ext["r_net"][:n] - res["r_net"]).max()),
    }
    if any(e != 0.0 for e in ecarts.values()):
        raise CausaliteError(f"la journee fictive change des journees closes : {ecarts}")

    # Les ordres partent de la position d'aujourd'hui emportee par le rendement du jour, comme
    # dans `voie_c2.derouler` ; le turnover de la ligne de demain doit en etre la somme.
    rend = d["closes"].pct_change().reindex(res["jours"]).to_numpy(dtype=float)
    derive = np.nan_to_num(res["positions"][-1] * (1.0 + rend[-1]) / (1.0 + res["r_brut"][-1]))
    position = ext["positions"][-1]
    if abs(float(np.abs(position - derive).sum()) - float(ext["turnover"][-1])) > 1e-9:
        raise CausaliteError("ordres de la consigne != turnover de la chaine")
    votes = {k: int(v) for k, v in ext["votes"].iloc[-1].items()}
    res["consigne"] = {
        "date": ext["jours"][-1], "etat": str(ext["etat"].iat[-1]), "votes": votes,
        "somme": sum(votes.values()), "turnover": float(ext["turnover"][-1]),
        "trade": bool(ext["turnover"][-1] > 0.0), "position": position,
        "ordres": position - derive,
        "donnees": {k: f"{v.index.max():%Y-%m-%d}" for k, v in d.items()},
    }
    return res


def nature(jour: pd.Timestamp, debut_live: pd.Timestamp, aujourdhui: pd.Timestamp) -> str:
    """« live » : >= debut du live ET ecrite le lendemain de sa cloture. Sinon « rattrapage »."""
    return "live" if jour >= debut_live and jour + UN_JOUR >= aujourdhui else "rattrapage"


def trous(jours: pd.DatetimeIndex) -> list[str]:
    """Les journees absentes d'un calendrier quotidien (le lake ment s'il y en a)."""
    if jours.empty:
        return []
    complet = pd.date_range(jours[0], jours[-1], freq="D")
    return [f"{j:%Y-%m-%d}" for j in complet.difference(jours)]


def bilan(r: np.ndarray) -> dict:
    """Rendement cumule, maxDD et vol annualisee (racine de 252, convention de la cible)."""
    equite = np.cumprod(1.0 + r)
    return {"net": float(equite[-1] - 1.0),
            "mdd": float((equite / np.maximum.accumulate(equite) - 1.0).min()),
            "vol": float(np.std(r, ddof=1) * np.sqrt(vc.PPA)) if len(r) > 1 else float("nan")}


def _poids(w: np.ndarray) -> dict[str, float]:
    return {p: round(float(x), 6) for p, x in zip(vc.PAIRES, w)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", required=True, choices=sorted(EMPREINTES))
    ap.add_argument("--journal", type=Path, default=None,
                    help="defaut : SUIVI_<id>.jsonl a la racine du depot")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    id_exp = args.id
    chemin = args.journal or journal_par_defaut(id_exp)

    cfg = c2.config(id_exp)                  # le verrou : preenregistree, empreinte du registre
    signe = c2.empreinte(cfg)
    if signe != EMPREINTES[id_exp]:
        log.error("%s : empreinte du registre %s != %s epinglee. Une autre config est une autre "
                  "experience : nouveau journal, ne pas melanger.", id_exp, signe,
                  EMPREINTES[id_exp])
        return 2
    journal = lire_journal(chemin)
    autres = {l["config"] for l in journal} - {signe}
    if autres:
        log.error("le journal porte une autre config (%s). Ouvrir un nouveau journal, ne pas "
                  "melanger.", ", ".join(sorted(autres)))
        return 2

    debut, debut_live = dates_du_registre(id_exp)
    admise = admise_au_dry_run(id_exp)
    d = c2.donnees()
    try:
        r = suivre(d, cfg)
    except CausaliteError as exc:
        log.error("%s — rien n'est ecrit", exc)
        return 3
    jours = r["jours"]
    idx = np.flatnonzero(np.asarray(jours >= debut))
    manquants = trous(jours[idx])
    if manquants:
        log.error("trou(s) dans le calendrier du suivi : %s — rien n'est ecrit (une ligne "
                  "porterait plusieurs jours). Voir `journalctl -u beta-maj`.",
                  ", ".join(manquants))
        return 1

    # Les holds de reference dans le meme instrument que l'experience : en perpetuels, le
    # long paie le funding, comme dans la mesure de VC2.
    perpetuel = cfg.get("instrument", "perpetuel") == "perpetuel"
    r_hold = d["closes"].pct_change().reindex(jours[idx]).fillna(0.0)
    if perpetuel:
        r_hold = r_hold - d["funding"].reindex(jours[idx]).fillna(0.0)
    instrument = "perpetuel" if perpetuel else "spot"
    r_net = r["r_net"][idx]
    equite = np.cumprod(1.0 + r_net)
    equite_btc = np.cumprod(1.0 + r_hold["BTC"].to_numpy())
    equite_equi = (1.0 + r_hold).cumprod().mean(axis=1).to_numpy()
    deja = {l["date"]: l for l in journal}
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    aujourdhui = pd.Timestamp(dt.datetime.now(dt.timezone.utc).date(), tz="UTC")

    nouvelles = []
    for k, i in enumerate(idx):
        jour = f"{jours[i]:%Y-%m-%d}"
        if jour in deja:
            ancien = deja[jour]
            if abs(ancien["r_net"] - r["r_net"][i]) > 1e-9 or ancien["etat"] != r["etat"].iat[i]:
                log.warning("%s : recalcul %s %.6f != journal %s %.6f (donnee revisee ?) — "
                            "journal conserve", jour, r["etat"].iat[i], r["r_net"][i],
                            ancien["etat"], ancien["r_net"])
            continue
        votes = {n: int(v) for n, v in r["votes"].iloc[i].items()}
        ligne = {
            "date": jour,
            "type": nature(jours[i], debut_live, aujourdhui),
            "ecrit_le": maintenant, "config": signe,
            "etat": str(r["etat"].iat[i]), "votes": votes, "somme": sum(votes.values()),
            "levier": round(float(r["levier"].iat[i]), 6),
            "sigma": round(float(r["sigma"].iat[i]), 6),
            "positions": _poids(r["positions"][i]),
            "brut": round(float(np.abs(r["positions"][i]).sum()), 6),
            "turnover": round(float(r["turnover"][i]), 6), "frais": float(r["frais"][i]),
            "funding": float(r["funding"][i]),
            "r_brut": float(r["r_brut"][i]), "r_net": float(r["r_net"][i]),
            "equite": float(equite[k]),
            "btc_r": float(r_hold["BTC"].iat[k]), "equite_btc": float(equite_btc[k]),
            "equite_equi": float(equite_equi[k]),
        }
        if i == len(jours) - 1:
            c = r["consigne"]
            ligne["consigne_lendemain"] = {
                "date": f"{c['date']:%Y-%m-%d}", "etat": c["etat"], "votes": c["votes"],
                "somme": c["somme"], "trade": c["trade"], "turnover": round(c["turnover"], 6),
                "brut": round(float(np.abs(c["position"]).sum()), 6),
                "position": _poids(c["position"]),
                "ordres": _poids(c["ordres"]) if c["trade"] else {},
                "donnees": c["donnees"],
            }
        nouvelles.append(ligne)

    if nouvelles:
        with chemin.open("a", encoding="utf-8") as f:
            for ligne in nouvelles:
                f.write(json.dumps(ligne, ensure_ascii=True) + "\n")
    log.info("%s : %d journee(s) ajoutee(s) au journal (%s)", id_exp, len(nouvelles),
             chemin.name)

    code = 0
    if len(idx):
        b = bilan(r_net)
        part = r["etat"].iloc[idx].value_counts()
        log.info("suivi depuis %s : %d j, net %+.2f%% | hold BTC %s %+.2f%% | equipondere "
                 "%+.2f%% | maxDD %.2f%% | %s", f"{debut:%Y-%m-%d}", len(idx), b["net"] * 100,
                 instrument, (equite_btc[-1] - 1) * 100, (equite_equi[-1] - 1) * 100,
                 b["mdd"] * 100,
                 ", ".join(f"{e} {part.get(e, 0)} j" for e in (c2.HAUSSIER, c2.VEILLE,
                                                                 c2.BAISSIER)))
        live = np.asarray(jours[idx] >= debut_live)
        fin = debut_live + DUREE_DRY_RUN
        if not admise:
            log.info("%s infirmee par sa regle preenregistree : suivi INFORMATIF, aucun critere "
                     "de dry-run", id_exp)
        elif live.any():
            bl = bilan(r_net[live])
            log.info("dry-run, jour %d (du %s au %s) : net %+.2f%%, maxDD %.2f%% (critere >= "
                     "%.0f%%), vol %.1f%% (critere %.0f-%.0f%%, lu a 6 mois)", int(live.sum()),
                     f"{debut_live:%Y-%m-%d}", f"{fin:%Y-%m-%d}", bl["net"] * 100,
                     bl["mdd"] * 100, MAXDD_MIN * 100, bl["vol"] * 100, VOL_MIN * 100,
                     VOL_MAX * 100)
            if bl["mdd"] < MAXDD_MIN:
                log.error("CRITERE DU DRY-RUN FRANCHI : maxDD live %.2f%% < %.0f%%. La suite "
                          "est une decision de Jonas.", bl["mdd"] * 100, MAXDD_MIN * 100)
                code = 4
        else:
            log.info("dry-run : premiere journee live le %s (fin le %s)",
                     f"{debut_live:%Y-%m-%d}", f"{fin:%Y-%m-%d}")
    c = r["consigne"]
    log.info("consigne pour %s : %s (votes %s = %+d), %s (turnover %.1f%%), brut %.2f",
             f"{c['date']:%Y-%m-%d}", c["etat"].upper(),
             " ".join(f"{v:+d}" for v in c["votes"].values()), c["somme"],
             "REEQUILIBRER" if c["trade"] else "ne rien faire", c["turnover"] * 100,
             float(np.abs(c["position"]).sum()))

    hier = pd.Timestamp(dt.datetime.now(dt.timezone.utc).date(), tz="UTC") - UN_JOUR
    if jours[-1] < hier:
        log.error("lake en retard : derniere journee close %s, attendue %s. "
                  "Voir `journalctl -u beta-maj`.", f"{jours[-1]:%Y-%m-%d}", f"{hier:%Y-%m-%d}")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
