"""Instantane fige des donnees de T1J (empreinte a3d6d80952500d57), pour les tests.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/figer_donnees_t1j.py

Jonas, 25/10 : un test lit une copie figee de ses donnees, jamais la source vivante. La source a
reecrit le passe apres la mesure de T1J (24/10 13:21 UTC) : Yahoo a revise la cloture NDX du
23/10 le 24/10 a 23:11 UTC, et `test_donnees_de_t1j_reconstituees_a_l_identique` echouait
depuis. Ce script reconstitue les donnees de T1J : les series vivantes de data/marches coupees
aux dates de fin de T1J, puis chaque revision journalisee APRES la mesure
(data/marches/revisions.jsonl) remise a sa valeur d'avant, de la plus recente a la plus
ancienne. Il n'ecrit rien si l'empreinte ne retombe pas exactement sur celle de T1J.

Sortie : tests/donnees/t1j_<empreinte>.parquet (serie, date, close) et .json (dates de fin,
revisions annulees, provenance). Ne modifie aucun resultat ni aucun rapport.
"""

from __future__ import annotations

import json
import logging
import pathlib
import sys
from datetime import UTC, datetime

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.marches import collecte  # noqa: E402
from beta.temps1_fiabilite import campagne as ca  # noqa: E402
from beta.temps1_fiabilite import regles as R  # noqa: E402
from beta.temps1_justesse import donnees as dn  # noqa: E402

log = logging.getLogger("beta.figer_donnees_t1j")

DOSSIER = pathlib.Path(__file__).resolve().parents[1] / "tests" / "donnees"


class FigeError(RuntimeError):
    """Les donnees de T1J ne se reconstituent pas a l'identique : rien n'est ecrit."""


def reconstituer() -> tuple[dict[str, pd.Series], dict]:
    t1j = ca.synthese_t1j()
    mesure_le = pd.Timestamp(t1j["calcule_le"])
    cov = t1j["donnees"]["couverture"]
    d = dn.charger()
    vivantes = {**d.prix, "VIX": d.vix, "USDJPY": d.usdjpy}
    series = {nom: s[s.index <= pd.Timestamp(cov[nom]["fin"])].copy()
              for nom, s in vivantes.items()}
    nom_de = {cov[nom]["serie"]: nom for nom in series}
    lignes = [json.loads(x) for x in collecte.REVISIONS.read_text(encoding="utf-8").splitlines()
              if x.strip()]
    apres_mesure = [r for r in lignes if pd.Timestamp(r["le"]) > mesure_le and r["serie"] in nom_de]
    annulees = []
    for r in sorted(apres_mesure, key=lambda r: pd.Timestamp(r["le"]), reverse=True):
        if r["dates_disparues"] or r["valeurs_changees"] != len(r["exemples"]):
            raise FigeError(f"revision incomplete dans le journal : {r}")
        nom = nom_de[r["serie"]]
        for ex in r["exemples"]:
            jour = pd.Timestamp(ex["date"])
            if jour not in series[nom].index:
                continue
            if series[nom][jour] != ex["apres"]:
                raise FigeError(f"{nom} {ex['date']} : {series[nom][jour]} au lieu de la valeur "
                                f"revisee {ex['apres']}")
            series[nom][jour] = ex["avant"]
            annulees.append({"serie": r["serie"], "journalisee_le": r["le"], "date": ex["date"],
                             "remise_a": ex["avant"], "valeur_vivante": ex["apres"]})
    meta = {"empreinte": dn._empreinte(series),
            "fins": {nom: f"{s.index.max():%Y-%m-%d}" for nom, s in sorted(series.items())},
            "series_source": {nom: cov[nom]["serie"] for nom in sorted(series)},
            "n": {nom: len(s) for nom, s in sorted(series.items())},
            "mesure_t1j_le": t1j["calcule_le"], "revisions_annulees": annulees,
            "source": "data/marches (collecte.lire) + data/marches/revisions.jsonl",
            "script": "scripts/figer_donnees_t1j.py",
            "fige_le": datetime.now(UTC).isoformat(timespec="seconds")}
    return series, meta


def lire(chemin: pathlib.Path) -> dict[str, pd.Series]:
    long = pd.read_parquet(chemin)
    return {nom: pd.Series(g["close"].to_numpy(dtype=float), index=pd.DatetimeIndex(g["date"]),
                           name="close")
            for nom, g in long.groupby("serie", sort=True)}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    try:
        series, meta = reconstituer()
    except FigeError as exc:
        log.error("ARRET : %s", exc)
        return 1
    if meta["empreinte"] != R.EMPREINTE_DONNEES_T1J:
        log.error("ARRET : empreinte %s au lieu de %s, rien n'est ecrit", meta["empreinte"],
                  R.EMPREINTE_DONNEES_T1J)
        return 1
    DOSSIER.mkdir(parents=True, exist_ok=True)
    base = DOSSIER / f"t1j_{meta['empreinte']}"
    long = pd.concat([pd.DataFrame({"serie": nom, "date": s.index,
                                    "close": s.to_numpy(dtype=float)})
                      for nom, s in sorted(series.items())], ignore_index=True)
    long.to_parquet(base.with_suffix(".parquet"), index=False)
    relue = dn._empreinte(lire(base.with_suffix(".parquet")))
    if relue != meta["empreinte"]:
        base.with_suffix(".parquet").unlink()
        log.error("ARRET : le fichier relu a l'empreinte %s, il est retire", relue)
        return 1
    base.with_suffix(".json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    log.info("instantane ecrit : %s (.parquet + .json), empreinte %s, %d revision(s) annulee(s)",
             base, meta["empreinte"], len(meta["revisions_annulees"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
