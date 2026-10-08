"""Voie C — suivi FORWARD de la config figee le 2026-10-03. Ne passe aucun ordre.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/voie_c_suivi.py

Chaque jour (timer beta-suivi, apres beta-maj), pour chaque journee CLOSE d >= DEBUT_SUIVI
pas encore journalisee, ajoute une ligne a SUIVI_VOIE_C.jsonl : la position tenue pendant d,
son rendement brut et net, et la consigne pour d+1 (cible, et ordres si la bande est
franchie). Le journal ne fait que CROITRE : une ligne ecrite n'est jamais reecrite.

Pourquoi c'est la seule validation qui reste : l'historique 2021-2026 a servi a choisir
(5800 configs regardees, DSR ~0). Les journees posterieures au 2026-09-05 n'avaient jamais ete
chargees par aucun script de la voie C avant le gel de CONFIG_FIGEE (commit de ce fichier).
Celles du 06/09 au 02/10 sont donc journalisees en « rattrapage » : hors echantillon, mais
ecrites apres coup ; a partir du 03/10, « live ».

Garde-fous :
- CONFIG_FIGEE ne bouge plus. Son empreinte est dans chaque ligne ; le script refuse de
  tourner si elle differe de celle du journal. Changer de config = NOUVEAU journal, et le
  dire dans DECISIONS.md.
- Une journee deja journalisee dont le recalcul differe (donnee revisee) n'est PAS reecrite :
  avertissement seulement.
- Lake en retard (derniere bougie close < hier) = sortie en erreur, donc unite « failed ».
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from beta import config  # noqa: E402
from beta.strategies import voie_c_optim as vo  # noqa: E402
from beta.strategies import voie_c_verif as vv  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.voie_c_suivi")

# ⚠️ FIGEE le 2026-10-03. Ne pas modifier : ouvrir un nouveau suivi a la place.
CONFIG_FIGEE = {"cible": 0.20, "fenetre": 30, "lmin": 0.25, "lmax": 2.0, "seuil_levier": 0.25,
                "pas": 1, "bande": 0.20}
DATE_GEL = "2026-10-03"
DEBUT_SUIVI = pd.Timestamp("2026-09-06", tz="UTC")
# Meme point de depart que toutes les mesures : l'etat (bande, hysteresis) au 06/09 est
# donc exactement celui du backtest, pas un portefeuille qui demarre a plat.
DEPART_SIMULATION = pd.Timestamp("2021-06-12", tz="UTC")

JOURNAL = config.RACINE / "SUIVI_VOIE_C.jsonl"


def empreinte(cfg: dict) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:16]


def lire_journal(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def calculer() -> dict:
    """Tout le chemin depuis DEPART_SIMULATION, sur TOUTES les donnees du lake."""
    index = vc.calendrier_commun(vc.PAIRES)
    closes = vc.clotures(vc.PAIRES, index)
    funding_j = vc.funding_quotidien(vc.PAIRES, index)
    rendements = closes.pct_change()
    ch = vv.chaine(closes, funding_j, CONFIG_FIGEE)

    jours = index[index >= DEPART_SIMULATION]
    cible = ch["cible"].reindex(jours).to_numpy(dtype=float)
    rend = rendements.reindex(jours).to_numpy(dtype=float)
    fund = funding_j.reindex(jours).to_numpy(dtype=float)
    tenu = np.zeros_like(cible)
    r_net, r_brut = vo.derouler_bande(cible, rend, fund, CONFIG_FIGEE["pas"],
                                      CONFIG_FIGEE["bande"], vc.BPS_TAKER, positions=tenu)

    # Consigne pour le lendemain du dernier jour clos : cible = composite et levier connus a
    # la cloture d'aujourd'hui ; derive = position tenue, emportee par le rendement du jour.
    voulu = (ch["composite"].iloc[-1] * ch["levier"].iloc[-1]).fillna(0.0).to_numpy()
    derive = tenu[-1] * (1.0 + rend[-1]) / (1.0 + r_brut[-1])
    ecart = float(np.abs(voulu - derive).sum())
    trade = ecart > CONFIG_FIGEE["bande"]
    return {
        "jours": jours, "tenu": tenu, "r_net": r_net, "r_brut": r_brut,
        "btc": (rendements["BTC"] - funding_j["BTC"]).reindex(jours).to_numpy(dtype=float),
        "levier": ch["levier"].shift(1).reindex(jours).to_numpy(dtype=float),
        "sigma": ch["sigma"].shift(1).reindex(jours).to_numpy(dtype=float),
        "demain": {"cible": voulu, "derive": derive, "ecart": ecart, "trade": trade,
                   "levier": float(ch["levier"].iloc[-1])},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--journal", type=Path, default=JOURNAL)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")

    signe = empreinte(CONFIG_FIGEE)
    journal = lire_journal(args.journal)
    autres = {l["config"] for l in journal} - {signe}
    if autres:
        log.error("le journal porte une autre config (%s) : CONFIG_FIGEE a ete modifiee. "
                  "Ouvrir un nouveau journal, ne pas melanger.", ", ".join(sorted(autres)))
        return 2

    r = calculer()
    jours = r["jours"]
    deja = {l["date"]: l for l in journal}
    m_fwd = np.asarray(jours >= DEBUT_SUIVI)
    equite = np.cumprod(np.where(m_fwd, 1.0 + r["r_net"], 1.0))
    equite_btc = np.cumprod(np.where(m_fwd, 1.0 + np.nan_to_num(r["btc"]), 1.0))
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    aujourdhui = pd.Timestamp(dt.datetime.now(dt.timezone.utc).date(), tz="UTC")

    nouvelles = []
    for i in np.flatnonzero(m_fwd):
        jour = f"{jours[i]:%Y-%m-%d}"
        if jour in deja:
            if abs(deja[jour]["r_net"] - r["r_net"][i]) > 1e-9:
                log.warning("%s : recalcul %.6f != journal %.6f (donnee revisee ?) — "
                            "journal conserve", jour, r["r_net"][i], deja[jour]["r_net"])
            continue
        ligne = {
            "date": jour,
            # live = ecrite le lendemain de la cloture, comme le fera le timer ; tout le
            # reste est du rattrapage, si propre soit-il.
            "type": ("live" if jours[i] + pd.Timedelta(days=1) >= aujourdhui
                     else "rattrapage"),
            "ecrit_le": maintenant, "config": signe,
            "levier": round(float(r["levier"][i]), 6), "sigma": round(float(r["sigma"][i]), 6),
            "positions": {p: round(float(w), 6) for p, w in zip(vc.PAIRES, r["tenu"][i])},
            "r_brut": float(r["r_brut"][i]), "r_net": float(r["r_net"][i]),
            "equite": float(equite[i]), "btc_r": float(r["btc"][i]),
            "equite_btc": float(equite_btc[i]),
        }
        if i == len(jours) - 1:
            d = r["demain"]
            ligne["consigne_lendemain"] = {
                "trade": bool(d["trade"]), "ecart": round(d["ecart"], 6),
                "levier": round(d["levier"], 6),
                "cible": {p: round(float(w), 6) for p, w in zip(vc.PAIRES, d["cible"])},
                "ordres": ({p: round(float(w), 6) for p, w in
                            zip(vc.PAIRES, d["cible"] - d["derive"])} if d["trade"] else {}),
            }
        nouvelles.append(ligne)

    if nouvelles:
        with args.journal.open("a", encoding="utf-8") as f:
            for ligne in nouvelles:
                f.write(json.dumps(ligne, ensure_ascii=True) + "\n")
    log.info("%d journee(s) ajoutee(s) au journal (%s)", len(nouvelles), args.journal.name)

    fwd = pd.Series(r["r_net"][m_fwd], index=jours[m_fwd])
    if len(fwd):
        eq = (1 + fwd).cumprod()
        log.info("suivi depuis %s : %d j, net %+.2f%% (BTC %+.2f%%), maxDD %.2f%%, "
                 "vol %.1f%%, levier en vigueur %.2f",
                 f"{DEBUT_SUIVI:%Y-%m-%d}", len(fwd), (eq.iloc[-1] - 1) * 100,
                 (equite_btc[-1] - 1) * 100, (eq / eq.cummax() - 1).min() * 100,
                 fwd.std(ddof=1) * np.sqrt(365) * 100 if len(fwd) > 1 else float("nan"),
                 r["levier"][-1])
    d = r["demain"]
    log.info("consigne pour %s : %s (ecart %.1f%% / bande %.0f%%), levier %.2f",
             f"{jours[-1] + pd.Timedelta(days=1):%Y-%m-%d}",
             "REEQUILIBRER" if d["trade"] else "ne rien faire", d["ecart"] * 100,
             CONFIG_FIGEE["bande"] * 100, d["levier"])

    hier = pd.Timestamp(dt.datetime.now(dt.timezone.utc).date(), tz="UTC") - pd.Timedelta(days=1)
    if jours[-1] < hier:
        log.error("lake en retard : derniere journee close %s, attendue %s. "
                  "Voir `journalctl -u beta-maj`.", f"{jours[-1]:%Y-%m-%d}", f"{hier:%Y-%m-%d}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
