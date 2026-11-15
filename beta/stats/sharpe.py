"""Ce qu'un Sharpe vaut vraiment : son incertitude, la duree qu'il exige, sa comparaison.

OUTILS INFORMATIFS (15/11/2026). Aucun n'est une porte, aucun n'entre dans `batterie.issue`,
aucun seuil de decision ne vit ici : une regle ne change que par decision de Jonas
(`DECISIONS.md`). Ils servent a LIRE un resultat deja mesure, et comme le reste de la
batterie ils ne savent que le degrader.

Un Sharpe est une ESTIMATION. Le publier sans son erreur-type, c'est publier une moyenne
sans son n — exactement ce que le MDE interdit cote R par trade. Quatre questions :

- **PSR** (Bailey & Lopez de Prado, 2012) : quelle probabilite que le vrai Sharpe depasse une
  reference, compte tenu de la longueur de la serie, de son asymetrie et de ses queues ? Le
  DSR de S2 est ce meme calcul avec, pour reference, le Sharpe attendu du maximum de N essais ;
- **longueur minimale** (MinTRL, meme article) : combien d'observations faut-il pour que ce
  Sharpe soit distinguable de la reference ? C'est le MDE du Sharpe, lu a l'envers ;
- **duree minimale de backtest** (MinBTL, Bailey, Borwein, Lopez de Prado & Zhu, 2014) : apres
  N essais, sur combien d'annees un Sharpe annuel donne cesse-t-il d'etre ce que le hasard
  produit a coup sur ? Sous cette duree, le meilleur des N essais atteint ce Sharpe sans edge ;
- **difference de deux Sharpe** : la candidate fait-elle MIEUX que la reference, ou seulement
  autrement ? Jobson & Korkie (1981) corrige par Memmel (2003), et un bootstrap par blocs
  apparie qui ne suppose ni normalite ni independance (dans l'esprit de Ledoit & Wolf, 2008).

Et une correction : **Lo (2002)**. Annualiser par racine(q) suppose des rendements
independants. Avec une autocorrelation positive (tendance, lissage), racine(q) SURESTIME le
Sharpe annuel ; `facteur_lo` rend le facteur correct.

Tout est en Sharpe PAR OBSERVATION sauf mention contraire, comme `multitest.sharpe`.
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from beta.stats import bootstrap, multitest

CONFIANCE = 0.95
N_REPETITIONS = 2000


def _propre(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    return x[np.isfinite(x)]


def moments(x) -> dict:
    """n, Sharpe par observation, asymetrie, aplatissement (3 pour une normale)."""
    x = _propre(x)
    n = len(x)
    sr = multitest.sharpe(x)
    if n < 4 or not np.isfinite(sr):
        return {"n": n, "sharpe": sr, "skew": float("nan"), "kurtosis": float("nan")}
    return {"n": n, "sharpe": sr, "skew": float(stats.skew(x)),
            "kurtosis": float(stats.kurtosis(x, fisher=False))}


def erreur_type(sr: float, n: int, skew: float = 0.0, kurtosis: float = 3.0) -> float:
    """Erreur-type du Sharpe par observation (Mertens 2002 ; Lo 2002 si normal).

    sigma(SR) = racine((1 - skew x SR + (kurtosis - 1) / 4 x SR^2) / (n - 1)). Avec skew = 0
    et kurtosis = 3 : racine((1 + SR^2 / 2) / (n - 1)), la formule de Lo. Une queue gauche
    epaisse (skew < 0 avec SR > 0) ELARGIT l'erreur : c'est le cas de tout systeme a stop.
    """
    if n < 2 or not np.isfinite(sr):
        return float("nan")
    variance = (1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr ** 2) / (n - 1)
    return math.sqrt(variance) if variance > 0 else float("nan")


def psr(x, sharpe_reference: float = 0.0) -> dict:
    """Probabilistic Sharpe Ratio : P(vrai Sharpe > reference), en Sharpe par observation.

    Ce n'est PAS la probabilite que la strategie marche : c'est la confiance qu'un Sharpe
    observe sur CETTE longueur, avec CES queues, ne vienne pas d'un vrai Sharpe egal a la
    reference. Aucune correction du nombre d'essais ici — c'est le role du DSR (S2).
    """
    m = moments(x)
    es = erreur_type(m["sharpe"], m["n"], m["skew"], m["kurtosis"])
    sortie = {**m, "sharpe_reference": float(sharpe_reference), "erreur_type": es,
              "psr": float("nan"), "ic_bas": float("nan"), "ic_haut": float("nan")}
    if not np.isfinite(es) or es <= 0:
        return sortie
    z = stats.norm.ppf(0.5 + CONFIANCE / 2.0)
    sortie.update(psr=float(stats.norm.cdf((m["sharpe"] - sharpe_reference) / es)),
                  ic_bas=m["sharpe"] - z * es, ic_haut=m["sharpe"] + z * es)
    return sortie


def longueur_minimale(sr: float, sharpe_reference: float = 0.0, skew: float = 0.0,
                      kurtosis: float = 3.0, confiance: float = CONFIANCE) -> float:
    """MinTRL : le nombre d'observations pour que PSR(reference) atteigne `confiance`.

    n = 1 + (1 - skew x SR + (kurtosis - 1) / 4 x SR^2) x (z / (SR - reference))^2.
    Infini si le Sharpe observe ne depasse pas la reference : aucune longueur n'y suffira.
    """
    if not np.isfinite(sr) or sr <= sharpe_reference:
        return float("inf")
    z = stats.norm.ppf(confiance)
    facteur = 1.0 - skew * sr + (kurtosis - 1.0) / 4.0 * sr ** 2
    if facteur <= 0:
        return float("nan")
    return 1.0 + facteur * (z / (sr - sharpe_reference)) ** 2


def duree_minimale_backtest(n_essais: int, sharpe_annuel: float) -> float:
    """MinBTL, en ANNEES : sous cette duree, le meilleur de N essais sans edge atteint ce Sharpe.

    MinBTL = (E[max de N normales] / Sharpe annuel)^2, avec E[max] par la meme formule que
    S2 (`multitest.sharpe_attendu_du_maximum`). Lecture : avec N = 99 essais, E[max] ~ 2,5 ;
    un Sharpe annuel de 1 demande donc ~6,3 ans de backtest pour ne plus etre l'attendu du
    hasard. Borne basse : les essais reels sont correles, mais leur nombre reel est aussi
    plus grand que celui qu'on a compte.
    """
    if not np.isfinite(sharpe_annuel) or sharpe_annuel <= 0:
        return float("inf")
    return (multitest.sharpe_attendu_du_maximum(n_essais, 1.0) / sharpe_annuel) ** 2


def facteur_lo(x, q: int) -> dict:
    """Facteur d'annualisation corrige de l'autocorrelation (Lo 2002, eq. 20).

    eta(q) = q / racine(q + 2 x somme_{k=1}^{q-1} (q - k) x rho_k). Sans autocorrelation,
    eta = racine(q). Les rho_k sont estimes jusqu'a min(q - 1, n^(1/3)) — la regle de bloc du
    bootstrap, fixee d'avance — et nuls au-dela : estimer 364 autocorrelations sur 1 500
    jours ajouterait du bruit, pas de l'information.
    """
    x = _propre(x)
    n, q = len(x), int(q)
    naif = math.sqrt(q) if q > 0 else float("nan")
    if n < 4 or q < 2:
        return {"q": q, "facteur": naif, "facteur_naif": naif, "n_retards": 0, "rho_1": 0.0}
    centre = x - x.mean()
    variance = float(centre @ centre)
    if variance <= 0:
        return {"q": q, "facteur": float("nan"), "facteur_naif": naif, "n_retards": 0,
                "rho_1": float("nan")}
    retards = min(q - 1, max(1, int(n ** (1.0 / 3.0))), n - 2)
    rho = [float(centre[:-k] @ centre[k:]) / variance for k in range(1, retards + 1)]
    somme = sum((q - k) * r for k, r in enumerate(rho, start=1))
    denominateur = q + 2.0 * somme
    return {"q": q, "facteur_naif": naif, "n_retards": retards, "rho_1": rho[0],
            "facteur": q / math.sqrt(denominateur) if denominateur > 0 else float("nan")}


def _apparies(a, b) -> tuple[np.ndarray, np.ndarray]:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    if len(a) != len(b):
        raise ValueError(f"series de longueurs differentes ({len(a)} et {len(b)}) : les "
                         "aligner sur un calendrier commun d'abord")
    garde = np.isfinite(a) & np.isfinite(b)
    return a[garde], b[garde]


def difference_memmel(a, b) -> dict:
    """Test de Jobson-Korkie corrige par Memmel : H0, les deux Sharpe sont egaux.

    z = (SR_a - SR_b) / racine(V), V = [2 (1 - rho) + (SR_a^2 + SR_b^2 - 2 SR_a SR_b rho^2) / 2] / n.
    Suppose des rendements NORMAUX et INDEPENDANTS dans le temps : sur des series a queues
    epaisses ou autocorrelees, lire `difference_bootstrap` a cote. p unilaterale (H1 : a > b).
    """
    a, b = _apparies(a, b)
    n = len(a)
    sa, sb = multitest.sharpe(a), multitest.sharpe(b)
    sortie = {"n": n, "sharpe_a": sa, "sharpe_b": sb, "ecart": sa - sb,
              "correlation": float("nan"), "z": float("nan"), "p_value": float("nan")}
    if n < 4 or not (np.isfinite(sa) and np.isfinite(sb)):
        return sortie
    rho = float(np.corrcoef(a, b)[0, 1])
    variance = (2.0 * (1.0 - rho) + 0.5 * (sa ** 2 + sb ** 2 - 2.0 * sa * sb * rho ** 2)) / n
    sortie["correlation"] = rho
    if not np.isfinite(variance) or variance <= 0:
        return sortie
    z = (sa - sb) / math.sqrt(variance)
    sortie.update(z=float(z), p_value=float(stats.norm.sf(z)))
    return sortie


def difference_bootstrap(a, b, ell: float | None = None,
                         n_repetitions: int = N_REPETITIONS, graine: int = 0) -> dict:
    """Ecart de Sharpe par bootstrap par blocs stationnaire APPARIE (memes dates tirees).

    Tirer les memes indices pour les deux series garde leur correlation, et les blocs gardent
    la dependance temporelle. IC percentile de l'ecart ; p unilaterale (H0 : SR_a <= SR_b)
    par recentrage : part des tirages ou (ecart* - ecart observe) >= ecart observe, avec la
    correction +1 / (B + 1) de S3. Version percentile, non studentisee : plus simple que
    Ledoit-Wolf (2008), un peu moins precise sur de petites series.
    """
    a, b = _apparies(a, b)
    n = len(a)
    observe = multitest.sharpe(a) - multitest.sharpe(b)
    sortie = {"n": n, "ecart": observe, "ic_bas": float("nan"), "ic_haut": float("nan"),
              "p_value": float("nan"), "ell": float("nan"), "n_repetitions": n_repetitions}
    if n < 10 or not np.isfinite(observe):
        return sortie
    ell = bootstrap.longueur_optimale(a) if ell is None else float(ell)
    rng = np.random.default_rng(graine)
    ecarts = np.full(n_repetitions, np.nan)
    for i in range(n_repetitions):
        idx = bootstrap.indices(n, n, ell, rng)
        ecarts[i] = multitest.sharpe(a[idx]) - multitest.sharpe(b[idx])
    valides = ecarts[np.isfinite(ecarts)]
    if len(valides) < n_repetitions // 2:
        return sortie
    alpha = 1.0 - CONFIANCE
    sortie.update(
        ic_bas=float(np.percentile(valides, 100 * alpha / 2)),
        ic_haut=float(np.percentile(valides, 100 * (1 - alpha / 2))),
        p_value=(int((valides - observe >= observe).sum()) + 1) / (len(valides) + 1),
        ell=float(ell), n_repetitions=int(len(valides)))
    return sortie
