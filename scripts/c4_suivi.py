"""VC4 — suivi forward a chaque ouverture de session. Ne passe aucun ordre.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/arit/bin/python scripts/c4_suivi.py

Timers : `beta-suivi-vc4` (00:50 UTC chaque jour, apres beta-maj : decision de 00:00 et journee
close de la veille) et `beta-vc4-sessions` (ouvertures de Londres et de New York + 2 min, en
semaine, apres `scripts/rafraichir_5m.py`). A chaque passage :

  1. la chaine VC4 (`voie_c4.calculer`) sur tout l'historique, jusqu'au dernier instant dont le
     prix est dans le lake ;
  2. garde de causalite : la meme chaine, bougies 5 min coupees a l'instant precedent, doit
     redonner a l'identique toutes les decisions jusqu'a cet instant (sinon sortie 3, rien
     n'est ecrit) ;
  3. CONSIGNES_VC4.jsonl : une ligne par instant de decision >= debut du rattrapage, pas encore
     journalise — position decidee, ordres (ce qui change), etat, votes. C'est ce que le paper
     (`scripts/paper.py --voie VC4`) execute, une fois par instant ;
  4. SUIVI_VC4.jsonl : une ligne par journee CLOSE (00:00 -> 00:00 UTC), au format des autres
     suivis (rendement du jour, equite, holds de reference), plus le detail des decisions.

Les journaux ne font que CROITRE. Une consigne est « live » si son instant est >= debut du live
et qu'elle est ecrite dans les 3 h (le timer) ; une journee, si elle est ecrite le lendemain de
sa cloture. Tout le reste est du rattrapage. Une decision deja journalisee qui ressort
differente (donnee revisee) est signalee et le journal est conserve, comme pour VC3.

Sorties : 1 donnees en retard (bougie 1d de la veille absente, ou prix d'un instant echu
absent), 2 empreinte, 3 causalite, 4 maxDD live < -25 % (alarme du dry-run), 5 vol du live hors
de 10-30 % a la fin du dry-run.
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
from beta.strategies import voie_c4 as c4  # noqa: E402
from beta.strategies import voie_c_voltarget as vc  # noqa: E402

log = logging.getLogger("beta.c4_suivi")

ID = "VC4"
# ⚠️ L'empreinte preenregistree le 2026-10-10. Ne pas la changer : une autre config est une autre
# experience, avec ses propres journaux.
EMPREINTE = "c63eb0b2a8cd25df"
CRITERES = {"maxdd_min": -0.25, "vol_min": 0.10, "vol_max": 0.30}    # ceux de VC3
DUREE_DRY_RUN = pd.DateOffset(months=6)
FRAICHEUR_LIVE = pd.Timedelta(hours=3)
UN_JOUR = pd.Timedelta(days=1)
TOLERANCE = 1e-6                     # les poids sont journalises a 6 decimales


class CausaliteError(RuntimeError):
    """Les donnees posterieures a un instant changent une decision deja prise."""


def lire(chemin: Path) -> list[dict]:
    if not chemin.exists():
        return []
    return [json.loads(l) for l in chemin.read_text(encoding="utf-8").splitlines() if l.strip()]


def _poids(w: np.ndarray) -> dict[str, float]:
    return {p: round(float(x), 6) for p, x in zip(vc.PAIRES, w)}


def bilan(r: np.ndarray) -> dict:
    """Comme `c2_suivi.bilan` : le plus haut part du capital initial."""
    equite = np.cumprod(1.0 + r)
    plus_haut = np.maximum(np.maximum.accumulate(equite), 1.0)
    return {"net": float(equite[-1] - 1.0),
            "mdd": float(min((equite / plus_haut - 1.0).min(), 0.0)),
            "vol": float(np.std(r, ddof=1) * np.sqrt(vc.PPA)) if len(r) > 1 else float("nan")}


def garde(d: dict, cinq: dict, cfg: dict, r: dict, aujourdhui: pd.Timestamp) -> None:
    """Les decisions jusqu'a l'avant-dernier instant, recalculees SANS les bougies posterieures,
    doivent etre identiques. Leve CausaliteError sinon."""
    if len(r["instants"]) < 2:
        return
    t_prec = r["instants"][-2]
    court = c4.calculer(d, c4.tronquer_5m(cinq, t_prec), cfg, fin=aujourdhui)
    n = int(np.flatnonzero(court["instants"] == t_prec)[0]) + 1
    if not court["instants"][:n].equals(r["instants"][:n]):
        raise CausaliteError("les instants de decision different")
    ecart = float(np.abs(court["positions"][:n] - r["positions"][:n]).max())
    etats = int((court["etat"].to_numpy()[:n] != r["etat"].to_numpy()[:n]).sum())
    if ecart > 0.0 or etats:
        raise CausaliteError(f"les bougies posterieures a {t_prec} changent les decisions "
                             f"passees (ecart de position {ecart:.2e}, {etats} etat(s))")


def lignes_consignes(r: dict, deja: set[str], debut: pd.Timestamp, debut_live: pd.Timestamp,
                     maintenant: pd.Timestamp) -> list[dict]:
    """Une ligne par instant >= debut pas encore journalise. Les ordres partent de la position
    precedente emportee par les prix, comme dans `voie_c2.derouler`."""
    pos, prix = r["positions"], r["prix"].to_numpy(dtype=float)
    ecrit_le = maintenant.isoformat(timespec="seconds")
    sortie = []
    for i, t in enumerate(r["instants"]):
        cle = t.isoformat()
        if t < debut or cle in deja:
            continue
        derive = (np.zeros(len(vc.PAIRES)) if i == 0 else
                  np.nan_to_num(pos[i - 1] * (prix[i] / prix[i - 1]) / (1.0 + r["r_brut"][i - 1])))
        ordres = pos[i] - derive
        if abs(float(np.abs(ordres).sum()) - float(r["turnover"][i])) > 1e-9:
            raise CausaliteError(f"{cle} : ordres != turnover de la chaine")
        votes = {k: int(v) for k, v in r["votes"].iloc[i].items()}
        trade = bool(r["turnover"][i] > 0.0)
        live = t >= debut_live and maintenant - t <= FRAICHEUR_LIVE
        sortie.append({
            "instant": cle, "type": "live" if live else "rattrapage", "ecrit_le": ecrit_le,
            "config": EMPREINTE, "etat": str(r["etat"].iat[i]), "votes": votes,
            "somme": sum(votes.values()),
            "levier": round(float(r["levier"].iat[i]), 6),
            "sigma": round(float(r["sigma"].iat[i]), 6),
            "position": _poids(pos[i]), "brut": round(float(np.abs(pos[i]).sum()), 6),
            "turnover": round(float(r["turnover"][i]), 6), "trade": trade,
            "ordres": _poids(ordres) if trade else {},
        })
    return sortie


def lignes_journees(r: dict, d: dict, journal: list[dict], debut: pd.Timestamp,
                    debut_live: pd.Timestamp, aujourdhui: pd.Timestamp,
                    maintenant: pd.Timestamp) -> tuple[list[dict], np.ndarray, pd.DatetimeIndex]:
    """Les journees closes (debut <= D < aujourd'hui) pas encore journalisees, et la serie
    complete des rendements quotidiens depuis le debut (pour le bilan du dry-run)."""
    jours = r["jours"][(r["jours"] >= debut) & (r["jours"] < aujourdhui)]
    r_jour = r["r_net_jour"].reindex(jours).to_numpy(dtype=float)
    r_hold = d["closes"].pct_change().reindex(jours).fillna(0.0)
    equite = np.cumprod(1.0 + r_jour)
    equite_btc = np.cumprod(1.0 + r_hold["BTC"].to_numpy())
    equite_equi = (1.0 + r_hold).cumprod().mean(axis=1).to_numpy()
    deja = {l["date"] for l in journal}
    instants = r["instants"]
    jour_de = instants.normalize()
    ecrit_le = maintenant.isoformat(timespec="seconds")
    sortie = []
    for k, jour in enumerate(jours):
        date = f"{jour:%Y-%m-%d}"
        if date in deja:
            continue
        sel = np.flatnonzero(np.asarray(jour_de == jour))
        dernier = sel[-1]
        votes = {n: int(v) for n, v in r["votes"].iloc[dernier].items()}
        live = jour >= debut_live and jour + UN_JOUR >= aujourdhui
        sortie.append({
            "date": date, "type": "live" if live else "rattrapage", "ecrit_le": ecrit_le,
            "config": EMPREINTE, "etat": str(r["etat"].iat[dernier]), "votes": votes,
            "somme": sum(votes.values()),
            "levier": round(float(r["levier"].iat[dernier]), 6),
            "sigma": round(float(r["sigma"].iat[dernier]), 6),
            "positions": _poids(r["positions"][dernier]),
            "brut": round(float(np.abs(r["positions"][dernier]).sum()), 6),
            "turnover": round(float(r["turnover"][sel].sum()), 6),
            "frais": float(r["frais"][sel].sum()), "funding": 0.0,
            "r_brut": float(np.prod(1.0 + r["r_brut"][sel]) - 1.0), "r_net": float(r_jour[k]),
            "equite": float(equite[k]),
            "btc_r": float(r_hold["BTC"].iat[k]), "equite_btc": float(equite_btc[k]),
            "equite_equi": float(equite_equi[k]),
            "decisions": [{"instant": f"{instants[i]:%H:%M}", "etat": str(r["etat"].iat[i]),
                           "brut": round(float(np.abs(r["positions"][i]).sum()), 6),
                           "turnover": round(float(r["turnover"][i]), 6)} for i in sel],
        })
    return sortie, r_jour, jours


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repertoire", type=Path, default=config.RACINE,
                    help="ou vivent CONSIGNES_VC4.jsonl et SUIVI_VC4.jsonl (defaut : la racine)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    chemin_c = args.repertoire / f"CONSIGNES_{ID}.jsonl"
    chemin_j = args.repertoire / f"SUIVI_{ID}.jsonl"

    cfg = c2.config(ID)
    if c2.empreinte(cfg) != EMPREINTE:
        log.error("%s : empreinte du registre %s != %s epinglee : autre experience, autres "
                  "journaux.", ID, c2.empreinte(cfg), EMPREINTE)
        return 2
    consignes, journal = lire(chemin_c), lire(chemin_j)
    autres = {l["config"] for l in consignes + journal} - {EMPREINTE}
    if autres:
        log.error("journaux d'une autre config (%s) : ne pas melanger", ", ".join(sorted(autres)))
        return 2
    entree = experiences.exiger(ID)
    debut = pd.Timestamp(entree["debut_rattrapage"], tz="UTC")
    debut_live = pd.Timestamp(entree["debut_live"], tz="UTC")
    admise = entree.get("derniere_issue") == "confirmee"

    maintenant = pd.Timestamp(dt.datetime.now(dt.UTC))
    aujourdhui = maintenant.normalize()
    d = c2.donnees()
    if d["closes"].index[-1] < aujourdhui - UN_JOUR:
        log.error("lake en retard : derniere bougie 1d close %s, attendue %s. Voir "
                  "`journalctl -u beta-maj`.", f"{d['closes'].index[-1]:%Y-%m-%d}",
                  f"{aujourdhui - UN_JOUR:%Y-%m-%d}")
        return 1
    cinq = c4.donnees_5m(debut=d["closes"].index[0])
    r = c4.calculer(d, cinq, cfg, fin=aujourdhui)
    echus = c4.instants(aujourdhui, aujourdhui, cfg["cadence"])
    echus = echus[echus <= maintenant - pd.Timedelta(minutes=1)]
    manquants = echus.difference(r["instants"])
    if len(manquants):
        log.error("prix absent du lake pour l'instant echu %s : lancer scripts/rafraichir_5m.py",
                  ", ".join(f"{t:%H:%M}" for t in manquants))
        return 1
    try:
        garde(d, cinq, cfg, r, aujourdhui)
    except CausaliteError as exc:
        log.error("%s — rien n'est ecrit", exc)
        return 3

    # Decisions deja journalisees : une donnee revisee se signale, le journal reste.
    position_de = {t.isoformat(): i for i, t in enumerate(r["instants"])}
    for c in consignes:
        i = position_de.get(c["instant"])
        if i is None:
            continue
        ecart = max(abs(c["position"][p] - float(r["positions"][i][k]))
                    for k, p in enumerate(vc.PAIRES))
        if ecart > TOLERANCE or c["etat"] != r["etat"].iat[i]:
            log.warning("%s : recalcul %s (ecart de position %.2e) != journal %s (donnee "
                        "revisee ?) — journal conserve", c["instant"], r["etat"].iat[i], ecart,
                        c["etat"])
    try:
        nouvelles_c = lignes_consignes(r, {c["instant"] for c in consignes}, debut, debut_live,
                                       maintenant)
    except CausaliteError as exc:
        log.error("%s — rien n'est ecrit", exc)
        return 3
    nouvelles_j, r_jour, jours = lignes_journees(r, d, journal, debut, debut_live, aujourdhui,
                                                 maintenant)
    for chemin, nouvelles in ((chemin_c, nouvelles_c), (chemin_j, nouvelles_j)):
        if nouvelles:
            with chemin.open("a", encoding="utf-8") as f:
                for ligne in nouvelles:
                    f.write(json.dumps(ligne, ensure_ascii=True) + "\n")
    log.info("%s : %d consigne(s) et %d journee(s) ajoutee(s)", ID, len(nouvelles_c),
             len(nouvelles_j))

    code = 0
    if len(jours):
        b = bilan(r_jour)
        log.info("suivi depuis %s : %d j clos, net %+.2f%%, maxDD %.2f%%", f"{debut:%Y-%m-%d}",
                 len(jours), b["net"] * 100, b["mdd"] * 100)
        live = np.asarray(jours >= debut_live)
        fin = debut_live + DUREE_DRY_RUN
        if admise and live.any():
            bl = bilan(r_jour[live])
            log.info("dry-run, jour %d (du %s au %s) : net %+.2f%%, maxDD %.2f%% (critere >= "
                     "%.0f%%), vol %.1f%%", int(live.sum()), f"{debut_live:%Y-%m-%d}",
                     f"{fin:%Y-%m-%d}", bl["net"] * 100, bl["mdd"] * 100,
                     CRITERES["maxdd_min"] * 100, bl["vol"] * 100)
            if bl["mdd"] < CRITERES["maxdd_min"]:
                log.error("CRITERE DU DRY-RUN FRANCHI : maxDD live %.2f%%. La suite est une "
                          "decision de Jonas.", bl["mdd"] * 100)
                code = 4
            if jours[-1] >= fin and not CRITERES["vol_min"] <= bl["vol"] <= CRITERES["vol_max"]:
                log.error("CRITERE DU DRY-RUN FRANCHI : vol realisee du live %.1f%%. La suite "
                          "est une decision de Jonas.", bl["vol"] * 100)
                code = code or 5
        elif admise:
            log.info("dry-run : premiere journee live le %s", f"{debut_live:%Y-%m-%d}")
    i = len(r["instants"]) - 1
    log.info("consigne de %s UTC : %s (somme %+d), %s, brut %.2f",
             f"{r['instants'][i]:%Y-%m-%d %H:%M}",
             str(r["etat"].iat[i]).upper(), int(r["votes"].iloc[i].sum()),
             "REEQUILIBRER" if r["turnover"][i] > 0 else "garder les positions (aucun ordre)",
             float(np.abs(r["positions"][i]).sum()))
    return code


if __name__ == "__main__":
    sys.exit(main())
