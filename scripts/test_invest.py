"""Test invest (TI1) — les mesures, en ligne de commande. L'onglet affiche ce qu'elle calcule.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/test_invest.py --campagne
    ... scripts/test_invest.py --periode stress --indicateurs momentum_btc,fear_greed \
            --mapping paliers                        # une config exploratoire : +1 au compteur
    ... scripts/test_invest.py --diagnostic-pit      # ecarts de votes PIT, sans P&L ni compteur
    ... scripts/test_invest.py --liste               # ce qui est deja calcule

Decision D3 (Jonas, 20/10) : le dashboard du VPS reste en lecture seule ; les calculs passent par
cette commande. Une config deja calculee n'est ni recalculee ni recomptee (`--recalculer` refait
le calcul, sans recompter). TI1 est preenregistree (`scripts/preenregistrer_ti1.py`) : rien ne se
mesure sans elle.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from beta.invest import campagne as ca  # noqa: E402
from beta.invest import donnees as dn  # noqa: E402
from beta.invest.moteur import Mapping  # noqa: E402
from beta.protocole import experiences  # noqa: E402

log = logging.getLogger("beta.test_invest")


def _p(x) -> str:
    return "   —  " if x is None else f"{x:6.3f}"


def _pct(x) -> str:
    return "    —  " if x is None else f"{100 * x:6.1f} %"


def afficher_synthese(syn: dict) -> None:
    print(f"\nTI1 — compteur d'essais : {syn['compteur']} · donnees {syn['donnees']['empreinte']}"
          f" (PIT : {syn['donnees']['pit']}, fin {syn['donnees']['fin']})")
    for nom, p in syn["periodes"].items():
        rouge = "  <-- MOINS DE 3 EPISODES : puissance faible" if p["puissance_faible"] else ""
        print(f"\n== {nom} : {p['debut']} -> {p['fin']} · {p['n_jours']} j · "
              f"{p['n_episodes']} episode(s) >= 20 % · {p['changements_regime']} changements "
              f"de regime (socle){rouge}")
        print(f"  {'signal':24s} {'Ulcer':>7s} {'MDD':>8s} {'Prot':>8s} {'expo':>6s} "
              f"{'p circ':>6s} {'p seg':>6s} {'p ret.':>6s} {'q BH':>6s}  verdict")
        for x in p["synthese"]["c1"]:
            print(f"  {x['libelle']:24s} {x['ulcer']:7.3f} {_pct(x['mdd'])} "
                  f"{_pct(x['protection'])} {x['expo_moyenne']:6.2f} {_p(x['p_circulaire'])} "
                  f"{_p(x['p_segments'])} {_p(x['p_retenue'])} {_p(x['q_bh'])}  {x['verdict']}")


def config_depuis_args(a: argparse.Namespace) -> ca.Config:
    indicateurs = tuple(v for v in dn.VOTES if v in a.indicateurs.split(",")) \
        if a.indicateurs != "tous" else dn.VOTES
    inconnus = set(a.indicateurs.split(",")) - set(dn.VOTES) - {"tous"}
    if inconnus or not indicateurs:
        raise SystemExit(f"indicateurs inconnus : {sorted(inconnus)} (connus : {dn.VOTES})")
    debut, fin = ca.PERIODES[a.periode]
    return ca.Config(periode=a.periode, debut=debut, fin=fin, indicateurs=indicateurs,
                     mapping=Mapping(a.mapping, a.theta_h, a.theta_b, a.e_haut, a.e_neutre,
                                     a.e_def),
                     kappa_pb=a.kappa, theta_episode=a.theta, theta_f=a.theta_f,
                     horizon_j=a.horizon, b=a.b, graine=a.graine, m_j=a.m, pit=a.pit,
                     rf=a.rf, nulls=not a.sans_nulls)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--campagne", action="store_true", help="les 24 mesures preenregistrees")
    ap.add_argument("--diagnostic-pit", action="store_true")
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("--recalculer", action="store_true")
    ap.add_argument("--periode", choices=sorted(ca.PERIODES), default="principale")
    ap.add_argument("--indicateurs", default="tous", help="liste separee par des virgules")
    ap.add_argument("--mapping", choices=("socle", "paliers"), default="socle")
    ap.add_argument("--theta-h", type=float, default=0.4)
    ap.add_argument("--theta-b", type=float, default=0.4)
    ap.add_argument("--e-haut", type=float, default=1.0)
    ap.add_argument("--e-neutre", type=float, default=0.7)
    ap.add_argument("--e-def", type=float, default=0.25)
    ap.add_argument("--kappa", type=float, default=10.0, help="pb par unite de |dE|")
    ap.add_argument("--theta", type=float, default=0.20, help="seuil des episodes")
    ap.add_argument("--theta-f", type=float, default=0.10)
    ap.add_argument("--horizon", type=int, default=60)
    ap.add_argument("--b", type=int, default=1000)
    ap.add_argument("--graine", type=int, default=0)
    ap.add_argument("--m", type=int, default=90)
    ap.add_argument("--pit", choices=("publication", "socle"), default="publication")
    ap.add_argument("--rf", action="store_true")
    ap.add_argument("--sans-nulls", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")

    if a.liste:
        for chemin in sorted(ca.DOSSIER.glob("*.json")):
            if chemin.name.startswith("campagne_"):
                continue
            r = json.loads(chemin.read_text(encoding="utf-8"))
            print(f"{r['run_id']}  {r['statut']:12s} {r['periode']['nom']:10s} "
                  f"{r['libelle']:28s} verdict {r['verdict']}")
        return 0

    fin = pd.Timestamp(ca.FIN, tz="UTC")
    p0 = min(pd.Timestamp(d, tz="UTC") for d, _ in ca.PERIODES.values()) - pd.Timedelta(days=1)
    d = dn.charger(fin, p0, pit=a.pit)
    if d.trous_acceptes:
        log.info("trou(s) accepte(s) : %s (D6)", ", ".join(d.trous_acceptes))

    if a.diagnostic_pit:
        if a.pit != "publication":
            raise SystemExit("--diagnostic-pit compare le decalage fixe a la publication")
        bornes = {n: (pd.Timestamp(x, tz="UTC"), pd.Timestamp(y, tz="UTC"))
                  for n, (x, y) in ca.PERIODES.items()}
        diag = dn.diagnostic_pit(d.votes_socle, d.votes, d.cfg_socle, bornes)
        for nom, x in diag.items():
            print(f"\n== {nom} ({x['jours']} j) : etat du regime different {x['etat']['jours']} j")
            for vote, v in x["votes"].items():
                print(f"  {vote:24s} {v['jours']:4d} j  {v['par_jour']}")
        return 0

    if a.campagne:
        afficher_synthese(ca.lancer_campagne(d, recalculer=a.recalculer))
        return 0

    cfg = config_depuis_args(a)
    res = ca.mesurer(cfg, d, statut="exploratoire", recalculer=a.recalculer)
    m = res["metriques"]["strategie"]
    print(f"{res['run_id']} {res['libelle']} ({cfg.periode}) — Ulcer {m['ulcer']:.3f}, "
          f"MDD {m['mdd']:.1%}, protection {m['protection']}, verdict {res['verdict']} "
          f"(exploratoire, compteur {experiences.compteur()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
