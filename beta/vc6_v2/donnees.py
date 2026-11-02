"""VC6 V2 : les entrees du moteur, lues sur les copies figees de la V1 (SHA-256 verifies).

Memes fonctions de lecture que la V1 (`beta.vc6.donnees`, `beta.vc6.campagne`) et memes calculs :
cloture de la barre 5 min de 23:55, sigma HAR apres replis du « Controle HAR », funding du jour.
La periode principale n'a pas d'or (la V2 n'en lit pas). En plus : la RV journaliere du « Controle
HAR », pour le test c seulement.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from beta import config
from beta.controle_har import campagne as har_campagne
from beta.controle_har import donnees as har_donnees
from beta.vc6 import campagne as c1
from beta.vc6 import donnees as dn1
from beta.vc6_v2 import moteur as mt
from beta.vc6_v2 import regles as R

UN = pd.Timedelta(days=1)


class DonneesError(RuntimeError):
    """Copie absente ou modifiee depuis le gel : aucun chiffre ne sort."""


def verifier_copies() -> None:
    for nom, attendu in R.SHA256.items():
        chemin = config.RACINE / "data" / "vc6_v1" / "sources_figees" / f"{nom}.parquet"
        if not chemin.exists():
            raise DonneesError(f"copie figee absente : {chemin}")
        if har_donnees.sha256(chemin) != attendu:
            raise DonneesError(f"{chemin.name} a change depuis le gel (SHA-256)")


def charger_principal() -> dict:
    """Clotures, sigma HAR, RV et funding des trois perpetuels."""
    verifier_copies()
    barres = {a: dn1.barres_5m(a) for a in R.POCHES}
    closes = dn1.clotures_perp(barres)
    prev = {a: har_campagne.previsions(b) for a, b in barres.items()}
    return {"closes": closes,
            "sigma": pd.DataFrame({a: np.sqrt(R.JOURS_AN * prev[a]["har"]) for a in R.POCHES}),
            "rv": pd.DataFrame({a: prev[a]["rv"] for a in R.POCHES}),
            "funding": {a: dn1.funding_jour(a) for a in R.POCHES}}


def entrees_principal(d: dict, debut: str = R.DEBUT_PRINCIPAL, fin: str = R.FIN) -> mt.Entrees:
    """Comme `beta.vc6.campagne.entrees_principal`, sans l'or."""
    jours = pd.date_range(pd.Timestamp(debut) - UN, pd.Timestamp(fin), freq="D")
    closes = d["closes"]
    sma = closes["BTC"].rolling(R.SMA).mean()
    baissier = c1._reindexer((closes["BTC"] < sma).where(sma.notna()), jours, "mode BTC")
    return mt.Entrees(
        jours=jours, baissier=baissier.astype(bool),
        sigma={a: c1._reindexer(d["sigma"][a], jours, f"sigma {a}") for a in R.POCHES},
        funding_annuel={a: c1._reindexer(d["funding"][a]["somme"] * R.JOURS_AN, jours,
                                         f"funding {a}") for a in R.POCHES},
        funding_jour={a: c1._reindexer(d["funding"][a]["somme"], jours, f"funding {a}")
                      for a in R.POCHES},
        rendements={a: c1._reindexer(closes[a].pct_change(), jours, f"rendement {a}")
                    for a in R.POCHES})


def entrees_robustesse() -> tuple[mt.Entrees, pd.Series]:
    """BTC seul depuis 2014 sur Bitstamp : les entrees de la V1 (application 26)."""
    verifier_copies()
    return c1.entrees_robustesse(R.DEBUT_ROBUSTESSE, R.FIN)


def entrees_anticipees(ent: mt.Entrees, rv: pd.DataFrame) -> tuple[mt.Entrees, dict]:
    """Test c : sigma de la decision D_k remplace par la volatilite realisee du jour D_{k+1},
    sqrt(365 RV), la RV couvrant exactement le rendement du jour D_{k+1}. Un jour sans RV (exclu au
    « Controle HAR ») garde sigma ; ces jours sont comptes."""
    sigma, garde = {}, {}
    for a, s in ent.sigma.items():
        rv_jours = rv[a].reindex(ent.jours).to_numpy(dtype=float)
        anticipe = np.sqrt(R.JOURS_AN * rv_jours[1:])
        ok = np.isfinite(anticipe) & (anticipe > 0)
        nouveau = s.copy()
        nouveau[:-1] = np.where(ok, anticipe, s[:-1])
        sigma[a] = nouveau
        garde[a] = int((~ok).sum())
    return mt.Entrees(jours=ent.jours, baissier=ent.baissier, sigma=sigma,
                      funding_annuel=ent.funding_annuel, funding_jour=ent.funding_jour,
                      rendements=ent.rendements), garde
