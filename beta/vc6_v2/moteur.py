"""VC6 V2 : le moteur jour par jour des deux essais (VC6_V2/spec_figee.md, preenregistrement).

Meme decoupage que la V1 (`beta.vc6.moteur`, dont il reprend `Entrees` et le temoin) : D_0 .. D_N
sont les jours de decision ; la decision prise a la cloture de D_{j-1} s'applique au rendement du
jour j. Deux etages :
1. `positions` decide les positions, en fraction du capital, jour par jour : cibles, filtre de
   financement, securite de liquidation, rampe, bande ;
2. `pnl` en tire le rendement net : frais sur la position nette de chaque actif, financement de la
   part en levier. Le null des positions de « V2 – HAR sans regime » rappelle `pnl` sur une serie
   tiree. Meme arithmetique, dans le meme ordre, que la V1 : a regles egales, les rendements sont
   identiques au bit pres (test a).

Ce qui change par rapport a la V1 :
- `regime=False` (« V2 – HAR sans regime ») : poches investies en permanence, bande chaque jour ;
- `baissiere_vol=True` (« V2 – poche baissiere sous HAR ») : en baissier, cible de la poche
  baissiere = poids x E_BTC, E_BTC = clip(cible / sigma_BTC ; 0,2 ; 1) ; `e_baissiere_force` fixe
  E_BTC (test a : 1).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from beta.vc6.moteur import Entrees, temoin
from beta.vc6_v2 import regles as R

__all__ = ["Entrees", "Parametres", "MoteurError", "parametres_essai", "cible_poche",
           "e_baissiere", "positions", "pnl", "simuler", "temoin", "SIGMA_MAX_BAISSIERE"]

# Au-dela de ce sigma annualise, la securite de liquidation contraindrait une exposition de 1 :
# 1 / (marge + 3 sigma / sqrt(365)) < 1. La poche baissiere ne l'applique pas (application 8) :
# le moteur s'arrete si ce cas se presente.
SIGMA_MAX_BAISSIERE = (1.0 - R.MARGE) * math.sqrt(R.JOURS_AN) / R.K_SIGMA_LIQ


class MoteurError(RuntimeError):
    """Cas que la spec ne prevoit pas : arret, aucun chiffre ne sort."""


@dataclass
class Parametres:
    poids: dict[str, float] = field(default_factory=lambda: dict(R.POIDS))
    sizing: str = "vol"                      # "vol" ou "fixe"
    cible: float = R.CIBLE
    e_fixe: float = 1.0
    regime: bool = True
    baissiere: dict[str, float] = field(default_factory=lambda: {"BTC": R.POCHE_BAISSIERE})
    baissiere_vol: bool = True
    clip_baissiere: tuple[float, float] = R.CLIP_BAISSIERE
    e_baissiere_force: float | None = None
    rampe: int = R.RAMPE
    bande: float = R.BANDE
    frais_pb: float = R.FRAIS_PB
    marge: float = R.MARGE
    k_sigma: float = R.K_SIGMA_LIQ
    clip: tuple[float, float] = (R.CLIP_BAS, R.CLIP_HAUT)
    funding_seuil: float = R.FUNDING_SEUIL


def parametres_essai(cle: str, poids: dict[str, float] | None = None) -> Parametres:
    e = R.ESSAIS[cle]
    return Parametres(poids=dict(poids or R.POIDS), regime=e["regime"],
                      baissiere=dict(e["baissiere"]), baissiere_vol=e["baissiere_vol"])


def cible_poche(sigma: float, f_annuel: float, p: Parametres) -> tuple[float, bool]:
    """Ei cible d'une poche (V1, application 8) et True si la securite de liquidation la reduit."""
    if p.sizing == "fixe":
        e = p.e_fixe
    elif p.sizing == "vol":
        e = min(max(p.cible / sigma, p.clip[0]), p.clip[1])
    else:
        raise MoteurError(f"sizing inconnu : {p.sizing}")
    if f_annuel > p.funding_seuil:
        e = min(e, 1.0)
    limite = 1.0 / (p.marge + p.k_sigma * sigma / math.sqrt(R.JOURS_AN))
    if e > limite:
        return limite, True
    return e, False


def e_baissiere(sigma_btc: float, p: Parametres) -> float:
    """E_BTC de la poche baissiere : clip(cible / sigma_BTC ; 0,2 ; 1), sans levier."""
    if p.e_baissiere_force is not None:
        return p.e_baissiere_force
    if not sigma_btc > 0 or sigma_btc > SIGMA_MAX_BAISSIERE:
        raise MoteurError(f"sigma du BTC {sigma_btc} : poche baissiere hors du cas prevu")
    return min(max(p.cible / sigma_btc, p.clip_baissiere[0]), p.clip_baissiere[1])


def positions(ent: Entrees, p: Parametres, baissier: np.ndarray | None = None) -> dict:
    """Les positions decidees chaque jour. `baissier` remplace la serie des modes (null du mode)."""
    mode = ent.baissier if baissier is None else baissier
    poches = list(p.poids)
    if p.baissiere_vol and set(p.baissiere) - {"BTC"}:
        raise MoteurError("poche baissiere sous HAR : prevue pour le BTC seulement")
    lignes = [("poche", a) for a in poches] + [("baissiere", a) for a in p.baissiere]
    n, L = ent.n, len(lignes)
    k_poche = len(poches)
    sig = {a: ent.sigma[a].tolist() for a in poches}
    fan = {a: ent.funding_annuel[a].tolist() for a in poches}
    sig_btc = ent.sigma["BTC"].tolist() if p.baissiere_vol and p.baissiere else None
    md = [bool(x) for x in mode]
    w = [p.poids[a] for a in poches]
    bw = [p.baissiere[a] for a in p.baissiere]

    y_tab = np.zeros((n, L))
    cible_tab = np.zeros((n, L))
    contraint = np.zeros((n, k_poche), dtype=bool)
    rampe_tab = np.zeros(n, dtype=bool)
    mode_tab = np.zeros(n, dtype=bool)
    eb_tab = np.full(n, np.nan)
    y_prev = None
    depart = None
    k_rampe = 0
    prev_bear = None
    for j in range(1, n + 1):
        d = j - 1
        bear = md[d] if p.regime else False
        cible = [0.0] * L
        if bear:
            if p.baissiere_vol and bw:
                eb = e_baissiere(sig_btc[d], p)
                eb_tab[j - 1] = eb
                for b, x in enumerate(bw):
                    cible[k_poche + b] = x * eb
            else:
                for b, x in enumerate(bw):
                    cible[k_poche + b] = x
        else:
            for i, a in enumerate(poches):
                e, c = cible_poche(sig[a][d], fan[a][d], p)
                cible[i] = w[i] * e
                contraint[j - 1, i] = c
        if y_prev is None:
            y = cible
        else:
            if bear != prev_bear:
                depart, k_rampe = y_prev, 1
            elif 0 < k_rampe < p.rampe:
                k_rampe += 1
            else:
                k_rampe = 0
            if k_rampe:
                f = k_rampe / p.rampe
                y = [depart[q] + f * (cible[q] - depart[q]) for q in range(L)]
            else:
                y = [cible[q] if abs(cible[q] - y_prev[q]) > p.bande * abs(y_prev[q])
                     else y_prev[q] for q in range(L)]
        prev_bear = bear
        y_tab[j - 1] = y
        cible_tab[j - 1] = cible
        rampe_tab[j - 1] = k_rampe > 0
        mode_tab[j - 1] = bear
        y_prev = y
    return {"y": y_tab, "cible": cible_tab, "lignes": lignes, "poches": poches,
            "contraint": contraint, "en_rampe": rampe_tab, "baissier": mode_tab,
            "e_baissiere": eb_tab}


def pnl(ent: Entrees, lignes: list[tuple[str, str]], poches: list[str], poids: dict[str, float],
        y_tab: np.ndarray, frais_pb: float) -> dict:
    """Rendement net de positions donnees (V1, applications 11 et 14). Aucun frais le premier
    jour (position de depart) ; ensuite 10 pb x somme des variations de la position nette de chaque
    actif ; financement = somme des max(Ei - 1 ; 0) x w_i x funding du jour du rendement."""
    y_tab = np.asarray(y_tab, dtype=float)
    n, L = y_tab.shape
    if n != ent.n or L != len(lignes):
        raise MoteurError(f"positions de forme {y_tab.shape}, attendu ({ent.n}, {len(lignes)})")
    actifs = sorted({a for _, a in lignes})
    actif_ligne = [actifs.index(a) for _, a in lignes]
    ret = {a: ent.rendements[a].tolist() for a in actifs}
    fj = {a: ent.funding_jour[a].tolist() for a in poches}
    w = [poids[a] for a in poches]
    taux = frais_pb / 1e4
    r = np.zeros(n)
    frais = np.zeros(n)
    financement = np.zeros(n)
    levier_brut = np.zeros(n)
    net_prev = None
    for j in range(1, n + 1):
        y = y_tab[j - 1].tolist()
        net = [0.0] * len(actifs)
        for q in range(L):
            net[actif_ligne[q]] += y[q]
        cout = 0.0 if net_prev is None else taux * sum(
            abs(a - b) for a, b in zip(net, net_prev, strict=True))
        fin = 0.0
        lev = 0.0
        for i, a in enumerate(poches):
            exces = max(y[i] / w[i] - 1.0, 0.0) * w[i]
            if exces > 0:
                fin += exces * fj[a][j]
                lev += exces * ret[a][j]
        brut = sum(y[q] * ret[lignes[q][1]][j] for q in range(L))
        r[j - 1] = brut - cout - fin
        frais[j - 1], financement[j - 1], levier_brut[j - 1] = cout, fin, lev
        net_prev = net
    return {"r": r, "frais": frais, "financement": financement, "levier_brut": levier_brut}


def simuler(ent: Entrees, p: Parametres, baissier: np.ndarray | None = None) -> dict:
    """Rejoue un essai. `baissier` remplace la serie des modes (null de « V2 – poche baissiere
    sous HAR »)."""
    pos = positions(ent, p, baissier)
    res = pnl(ent, pos["lignes"], pos["poches"], p.poids, pos["y"], p.frais_pb)
    k = len(pos["poches"])
    w = np.array([p.poids[a] for a in pos["poches"]])
    contrib = {f"{t}:{a}": pos["y"][:, q] * np.asarray(ent.rendements[a][1:])
               for q, (t, a) in enumerate(pos["lignes"])}
    return {**pos, **res, "e": pos["y"][:, :k] / w, "expo_totale": pos["y"].sum(axis=1),
            "contributions": contrib}
