"""VC6 V1, Temps 2 : le moteur jour par jour (spec figee et applications 6 a 16).

Indices : D_0 .. D_N sont les jours de decision ; le jour de rendement j (1 .. N) va de la
cloture de D_{j-1} a celle de D_j. La decision prise a la cloture de D_{j-1} s'applique au
rendement du jour j (`anticipation=True` prend volontairement celle de D_j : test c).

Lignes de position, en fraction du capital : une par poche (x_i = w_i Ei) et une par actif de la
poche baissiere. Les frais portent sur la position NETTE de chaque actif (application 14).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from beta.vc6 import regles as R


@dataclass
class Entrees:
    jours: pd.DatetimeIndex                  # D_0 .. D_N
    baissier: np.ndarray                     # (N+1,) mode decide a chaque D_k
    sigma: dict[str, np.ndarray]             # poche -> sigma annualise a D_k
    funding_annuel: dict[str, np.ndarray]    # poche -> somme des reglements du jour D_k x 365
    funding_jour: dict[str, np.ndarray]      # poche -> somme des reglements du jour D_k
    rendements: dict[str, np.ndarray]        # actif -> C(D_k)/C(D_{k-1}) - 1 (k = 0 : NaN)

    @property
    def n(self) -> int:
        return len(self.jours) - 1


@dataclass
class Parametres:
    poids: dict[str, float] = field(default_factory=lambda: dict(R.POIDS))
    sizing: str = "vol"                      # "vol" ou "fixe"
    cible: float | None = 0.25
    e_fixe: float = 1.0
    baissiere: dict[str, float] = field(default_factory=lambda: {"BTC": R.POCHE_BAISSIERE})
    rampe: int = R.RAMPE
    bande: float = R.BANDE
    frais_pb: float = R.FRAIS_PB
    marge: float = R.MARGE
    k_sigma: float = R.K_SIGMA_LIQ
    clip: tuple[float, float] = (R.CLIP_BAS, R.CLIP_HAUT)
    funding_seuil: float = R.FUNDING_SEUIL
    regime: bool = True
    anticipation: bool = False


def cible_poche(sigma: float, f_annuel: float, p: Parametres) -> tuple[float, bool]:
    """Ei cible (application 8) et True si la securite de liquidation la reduit."""
    if p.sizing == "fixe":
        e = p.e_fixe
    elif p.sizing == "vol":
        e = min(max(p.cible / sigma, p.clip[0]), p.clip[1])
    else:
        raise ValueError(f"sizing inconnu : {p.sizing}")
    if f_annuel > p.funding_seuil:
        e = min(e, 1.0)
    limite = 1.0 / (p.marge + p.k_sigma * sigma / math.sqrt(R.JOURS_AN))
    if e > limite:
        return limite, True
    return e, False


def simuler(ent: Entrees, p: Parametres, baissier: np.ndarray | None = None) -> dict:
    """Rejoue la strategie. `baissier` remplace la serie de modes (nulls)."""
    mode = ent.baissier if baissier is None else baissier
    poches = list(p.poids)
    lignes = [("poche", a) for a in poches] + [("baissiere", a) for a in p.baissiere]
    actifs = sorted({a for _, a in lignes})
    n, L = ent.n, len(lignes)
    sig = {a: ent.sigma[a].tolist() for a in poches}
    fan = {a: ent.funding_annuel[a].tolist() for a in poches}
    fj = {a: ent.funding_jour[a].tolist() for a in poches}
    ret = {a: ent.rendements[a].tolist() for a in actifs}
    md = [bool(x) for x in mode]
    w = [p.poids[a] for a in poches]
    k_poche = len(poches)
    actif_ligne = [actifs.index(a) for _, a in lignes]
    bw = [p.baissiere[a] for a in p.baissiere]

    y_tab = np.zeros((n, L))
    cible_tab = np.zeros((n, L))
    e_tab = np.zeros((n, k_poche))
    contraint = np.zeros((n, k_poche), dtype=bool)
    rampe_tab = np.zeros(n, dtype=bool)
    mode_tab = np.zeros(n, dtype=bool)
    frais = np.zeros(n)
    financement = np.zeros(n)
    levier_brut = np.zeros(n)
    r = np.zeros(n)
    y_prev = None
    net_prev = None
    depart = None
    k_rampe = 0
    prev_bear = None
    taux = p.frais_pb / 1e4
    for j in range(1, n + 1):
        d = j if p.anticipation else j - 1
        bear = md[d] if p.regime else False
        cible = [0.0] * L
        if bear:
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
                y = [depart[l] + f * (cible[l] - depart[l]) for l in range(L)]
            else:
                y = [cible[l] if abs(cible[l] - y_prev[l]) > p.bande * abs(y_prev[l])
                     else y_prev[l] for l in range(L)]
        prev_bear = bear
        net = [0.0] * len(actifs)
        for l in range(L):
            net[actif_ligne[l]] += y[l]
        cout = 0.0 if net_prev is None else taux * sum(abs(a - b) for a, b in zip(net, net_prev))
        fin = 0.0
        lev = 0.0
        for i, a in enumerate(poches):
            exces = max(y[i] / w[i] - 1.0, 0.0) * w[i]
            if exces > 0:
                fin += exces * fj[a][j]
                lev += exces * ret[a][j]
        brut = sum(y[l] * ret[lignes[l][1]][j] for l in range(L))
        r[j - 1] = brut - cout - fin
        frais[j - 1], financement[j - 1], levier_brut[j - 1] = cout, fin, lev
        y_tab[j - 1] = y
        cible_tab[j - 1] = cible
        e_tab[j - 1] = [y[i] / w[i] for i in range(k_poche)]
        rampe_tab[j - 1] = k_rampe > 0
        mode_tab[j - 1] = bear
        y_prev, net_prev = y, net
    contrib = {f"{t}:{a}": y_tab[:, l] * np.asarray(ent.rendements[a][1:])
               for l, (t, a) in enumerate(lignes)}
    return {"r": r, "y": y_tab, "cible": cible_tab, "lignes": lignes, "e": e_tab, "poches": poches,
            "contraint": contraint, "en_rampe": rampe_tab, "baissier": mode_tab,
            "frais": frais, "financement": financement, "levier_brut": levier_brut,
            "expo_totale": y_tab.sum(axis=1), "contributions": contrib}


def temoin(ent: Entrees, poids: dict[str, float], e_moyenne: float) -> dict:
    """« Temoin expo constante » : x_i = E moyenne x w_i chaque jour, sans frais (application 16)."""
    n = ent.n
    r = np.zeros(n)
    fin = np.zeros(n)
    for a, w in poids.items():
        r += e_moyenne * w * ent.rendements[a][1:]
        fin += max(e_moyenne - 1.0, 0.0) * w * ent.funding_jour[a][1:]
    return {"r": r - fin, "financement": fin, "e": e_moyenne,
            "expo_totale": np.full(n, e_moyenne)}
