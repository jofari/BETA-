"""Onglet « Test invest » (TI1) : relit ce que `scripts/test_invest.py` a calcule.

Rien ne se calcule ici (decision D3 de Jonas, 20/10) : le dashboard du VPS reste en lecture
seule, et chaque calcul avance le compteur d'essais — un geste qui se fait en ligne de commande,
la ou il se voit. La liste des runs ne porte pas leurs series (quelques centaines de Ko par
run) : l'onglet les demande une a une (`/api/invest/run`).
"""

from __future__ import annotations

import json
import re

from beta.invest import campagne

COMMANDE = ("ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/test_invest.py "
            "--periode {periode} --indicateurs {indicateurs} --mapping {mapping} "
            "--theta {theta} --kappa {kappa} --b {b} --graine {graine}")
IDENTIFIANT = re.compile(r"^[0-9a-f]{12}$")


def _resume(r: dict) -> dict:
    cfg, m = r["config"], r["metriques"]["strategie"]
    return {"run_id": r["run_id"], "statut": r.get("statut"), "calcule_le": r.get("calcule_le"),
            "periode": r["periode"]["nom"], "libelle": r["libelle"], "signal": r["signal"],
            "mapping": cfg["mapping"]["nom"], "indicateurs": cfg["indicateurs"],
            "kappa_pb": cfg["kappa_pb"], "theta_episode": cfg["theta_episode"], "b": cfg["b"],
            "graine": cfg["graine"], "pit": cfg["pit"], "nulls": cfg["nulls"],
            "verdict": r.get("verdict"),
            "p_retenue": (r.get("nulls") or {}).get("p_retenue"),
            "ulcer": m.get("ulcer"), "mdd": m.get("mdd"), "protection": m.get("protection"),
            "expo_moyenne": m.get("expo_moyenne")}


# Un run ne change pas une fois ecrit : son resume se garde tant que le fichier ne bouge pas
# (relire les 24 JSON de la campagne a chaque ouverture de l'onglet prenait ~0,7 s).
_CACHE: dict[str, tuple[int, dict]] = {}


def _lire(chemin) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _resume_en_cache(chemin) -> dict:
    mtime = chemin.stat().st_mtime_ns
    garde = _CACHE.get(str(chemin))
    if garde is None or garde[0] != mtime:
        garde = (mtime, _resume(_lire(chemin)))
        _CACHE[str(chemin)] = garde
    return garde[1]


def vue() -> dict:
    dossier = campagne.DOSSIER
    runs, synthese = [], None
    if dossier.is_dir():
        for chemin in sorted(dossier.glob("*.json")):
            if chemin.name == f"campagne_{campagne.ID_EXP}.json":
                synthese = _lire(chemin)
            elif IDENTIFIANT.match(chemin.stem):
                runs.append(_resume_en_cache(chemin))
    return {"runs": runs, "campagne": synthese, "commande": COMMANDE,
            "periodes": campagne.PERIODES, "experience": campagne.ID_EXP}


def run(params: dict) -> dict:
    identifiant = (params.get("id") or [""])[0]
    if not IDENTIFIANT.match(identifiant):
        raise ValueError("identifiant de run invalide (12 caracteres hexadecimaux attendus)")
    chemin = campagne.DOSSIER / f"{identifiant}.json"
    if not chemin.is_file():
        raise FileNotFoundError(f"run {identifiant} absent de data/test_invest/")
    return json.loads(chemin.read_text(encoding="utf-8"))
