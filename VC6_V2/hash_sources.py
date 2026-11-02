"""VC6 V2, etape B : empreintes des copies figees lues par la V2 (les memes que la V1).

    /root/venvs/beta/bin/python VC6_V2/hash_sources.py

Recalcule le SHA-256 de chaque copie de data/vc6_v1/sources_figees/ que la V2 lit, le compare au gel
de la V1 (VC6_V1/sources_figees.json et beta.vc6.regles.SHA256) et s'arrete au premier ecart.
Ecrit VC6_V2/sources_figees.json, puis ajoute a VC6_V2/spec_figee.md la table des donnees figees et
l'empreinte du bloc de la spec (une relance reecrit cette section, jamais la spec). Les bornes et le
nombre de lignes sont relus dans chaque copie.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import sys

import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.vc6 import regles as R1  # noqa: E402

log = logging.getLogger("vc6_v2.hash_sources")
SPEC = RACINE / "VC6_V2" / "spec_figee.md"
SORTIE = RACINE / "VC6_V2" / "sources_figees.json"
GEL_V1 = RACINE / "VC6_V1" / "sources_figees.json"
TITRE = "## Données figées (mêmes copies que la V1)"
USAGE = {
    "BTC_perp_5m": "clôture de 23:55, σ̂ HAR, mode global (SMA 200), volatilité réalisée (test c)",
    "ETH_perp_5m": "clôture de 23:55, σ̂ HAR, volatilité réalisée (test c)",
    "SOL_perp_5m": "clôture de 23:55, σ̂ HAR, volatilité réalisée (test c)",
    "BTC_funding": "filtre de financement et financement payé",
    "ETH_funding": "filtre de financement et financement payé",
    "SOL_funding": "filtre de financement et financement payé",
    "BTC_bitstamp_1d": "robustesse BTC seul depuis 2014 (clôtures, écart-type 30 jours)",
    "URTH_1d": "référence ETF monde",
}
CLE_GEL = {"URTH_1d": "URTH"}        # nom de la source dans VC6_V1/sources_figees.json


def sha256(chemin: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(chemin, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def bloc_spec(texte: str) -> str:
    """Le bloc de la spec, lignes-marqueurs comprises (une seule de chaque, en debut de ligne)."""
    lignes = texte.split("\n")
    debut = [i for i, x in enumerate(lignes) if x == "=== SPEC VC6 V2 ==="]
    fin = [i for i, x in enumerate(lignes) if x == "=== FIN SPEC ==="]
    if len(debut) != 1 or len(fin) != 1 or fin[0] <= debut[0]:
        raise SystemExit("marqueurs de la spec introuvables ou en double : arret")
    return "\n".join(lignes[debut[0]:fin[0] + 1])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s  %(message)s")
    gel = json.loads(GEL_V1.read_text(encoding="utf-8"))
    sortie = {"fin_figee": gel["fin_figee"], "fige_le_v1": gel["fige_le"], "sources": {}}
    lignes = []
    for nom, usage in USAGE.items():
        info = gel["sources"][CLE_GEL.get(nom, nom)]
        chemin = RACINE / info["copie"]
        h = sha256(chemin)
        if h != info["sha256_copie"] or h != R1.SHA256[nom]:
            raise SystemExit(f"{nom} : SHA-256 {h} different du gel de la V1 : arret")
        dates = pd.to_datetime(pd.read_parquet(chemin, columns=["date"])["date"], utc=True)
        if len(dates) != info["lignes_copie"]:
            raise SystemExit(f"{nom} : {len(dates)} lignes, {info['lignes_copie']} au gel : arret")
        debut, fin = f"{dates.min():%Y-%m-%d %H:%M}", f"{dates.max():%Y-%m-%d %H:%M}"
        sortie["sources"][nom] = {"copie": info["copie"], "origine": info["origine"],
                                  "sha256": h, "egal_au_gel_v1": True, "premiere_ligne": debut,
                                  "derniere_ligne": fin, "lignes": len(dates), "usage_v2": usage}
        lignes.append(f"| {info['origine']} | `{info['copie']}` | {debut} UTC | {fin} UTC | "
                      f"{len(dates)} | `{h}` | oui | {usage} |")
    texte = SPEC.read_text(encoding="utf-8")
    empreinte = hashlib.sha256(bloc_spec(texte).encode("utf-8")).hexdigest()
    sortie["sha256_bloc_spec"] = empreinte
    SORTIE.write_text(json.dumps(sortie, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if TITRE in texte:                       # reecrite a l'identique si on relance
        texte = texte[:texte.index("\n" + TITRE)]
    ajout = [
        "", TITRE, "",
        "Écrit par `VC6_V2/hash_sources.py` : SHA-256 de chaque copie recalculé le 02/11/2026 et "
        "comparé au gel de la V1 (`VC6_V1/sources_figees.json`, `beta/vc6/regles.py`). Arrêt au "
        "premier écart ; aucun écart. Détail : `VC6_V2/sources_figees.json`.", "",
        "| source | copie figée | première ligne | dernière ligne | lignes | SHA-256 recalculé le "
        "02/11/2026 | = gel de la V1 | usage dans la V2 |",
        "|---|---|---|---|---|---|---|---|", *lignes, "",
        "Bornes, reprises du gel de la V1 : séries journalières jusqu'au 31/10/2026 inclus (ETF : "
        "dernière séance le 30/10/2026) ; bougies 5 min ouvertes avant le 01/11/2026 00:00 UTC ; "
        "funding réglé jusqu'au 01/11/2026 00:00 UTC inclus.", "",
        "Les autres copies figées de la V1 (bougies 1d des perpétuels, Coinbase, or) ne sont pas "
        "lues par la V2.", "",
        "## Empreinte de la spec", "",
        f"SHA-256 du bloc de la spec, de la ligne `=== SPEC VC6 V2 ===` à la ligne "
        f"`=== FIN SPEC ===` comprises (UTF-8, lignes jointes par un saut de ligne) : "
        f"`{empreinte}`.", ""]
    SPEC.write_text(texte.rstrip("\n") + "\n" + "\n".join(ajout), encoding="utf-8")
    log.info("spec_figee.md complete ; bloc de la spec %s", empreinte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
