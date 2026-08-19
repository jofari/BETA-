"""S3 — bootstrap par blocs stationnaire (Politis & Romano, 1994).

Le bootstrap ordinaire retire les observations une a une, ce qui suppose qu'elles sont
independantes. Des rendements de trading ne le sont pas : ils arrivent en grappes (une
tendance produit une serie de gains, un regime hostile une serie de pertes). Retirer au
hasard casse cette structure et donne des intervalles de confiance BEAUCOUP trop etroits —
donc des edges qui paraissent solides et ne le sont pas.

Le bootstrap par blocs retire des morceaux consecutifs. Chez Politis-Romano, la longueur de
chaque bloc est **geometrique** de moyenne l, et non fixe : la serie rebootstrappee est
alors stationnaire, ce qu'une longueur fixe ne garantit pas.

Deux regles de methode, ecrites ici parce qu'elles sont faciles a violer sans le voir :

1. **l est fixe AVANT de regarder le resultat.** Choisir l apres coup, c'est choisir son
   intervalle de confiance ;
2. **la sensibilite a l est publiee**, sur trois longueurs. Un resultat qui ne survit qu'a
   une seule valeur de l n'est pas un resultat, c'est un artefact de reglage.
"""

from __future__ import annotations

import numpy as np

# Longueurs de bloc de la publication de sensibilite. Fixees ici, une fois pour toutes :
# les avoir en constante empeche de les « ajuster » run par run.
LONGUEURS_SENSIBILITE = (5, 20, 50)
N_REPETITIONS = 2000
ALPHA = 0.05


def longueur_optimale(x: np.ndarray) -> float:
    """Regle empirique l = n^(1/3), plancher a 2. Approximation deliberee.

    Politis-White (2004) donnent un estimateur automatique fonde sur l'autocorrelation ; il
    est meilleur, mais il DEPEND des donnees, donc il fait entrer le resultat dans le choix
    du parametre. La regle en n^(1/3) est moins fine et immunisee contre ca. La sensibilite
    publiee sur trois longueurs joue le role que l'optimisation aurait joue.
    """
    n = len(x)
    return max(2.0, float(n) ** (1.0 / 3.0)) if n else 2.0


def indices(n: int, taille: int, ell: float, rng: np.random.Generator) -> np.ndarray:
    """Indices d'un tirage par blocs stationnaire, avec bouclage circulaire de la serie.

    Le bouclage (modulo n) est ce qui rend le tirage stationnaire : sans lui, les blocs qui
    tomberaient a la fin de la serie seraient tronques, et les dernieres observations
    seraient sous-representees.
    """
    if n <= 0:
        return np.empty(0, dtype=int)
    p = 1.0 / max(ell, 1.0)
    sortie = np.empty(taille, dtype=int)
    position = 0
    while position < taille:
        depart = rng.integers(0, n)
        longueur = min(int(rng.geometric(p)), taille - position)
        sortie[position:position + longueur] = (depart + np.arange(longueur)) % n
        position += longueur
    return sortie


def rejouer(x: np.ndarray, ell: float | None = None, n_repetitions: int = N_REPETITIONS,
            graine: int = 0) -> np.ndarray:
    """Matrice (n_repetitions, len(x)) des series rebootstrappees."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    ell = longueur_optimale(x) if ell is None else ell
    rng = np.random.default_rng(graine)
    return np.array([x[indices(n, n, ell, rng)] for _ in range(n_repetitions)])


def distribution(x: np.ndarray, statistique=np.mean, ell: float | None = None,
                 n_repetitions: int = N_REPETITIONS, graine: int = 0) -> np.ndarray:
    """La statistique recalculee sur chaque rejeu. Tout le reste en decoule."""
    tirages = rejouer(x, ell, n_repetitions, graine)
    return np.array([statistique(ligne) for ligne in tirages])


def intervalle(x: np.ndarray, statistique=np.mean, ell: float | None = None,
               n_repetitions: int = N_REPETITIONS, alpha: float = ALPHA,
               graine: int = 0) -> dict:
    """IC percentile et p-value bootstrap unilaterale (H0 : statistique <= 0).

    La p-value est la fraction des rejeux ou la statistique passe sous 0, corrigee de
    +1/(B+1) : sans cette correction, une p-value peut valoir exactement 0, ce qui
    affirmerait une impossibilite que B tirages ne peuvent pas etablir.
    """
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return {"n": len(x), "observe": float("nan"), "ic_bas": float("nan"),
                "ic_haut": float("nan"), "p_value": float("nan"), "ell": float("nan")}
    ell = longueur_optimale(x) if ell is None else ell
    tirages = distribution(x, statistique, ell, n_repetitions, graine)
    observe = float(statistique(x))
    n_defavorables = int((tirages <= 0).sum())
    return {
        "n": len(x), "observe": observe,
        "ic_bas": float(np.percentile(tirages, 100 * alpha / 2)),
        "ic_haut": float(np.percentile(tirages, 100 * (1 - alpha / 2))),
        "p_value": (n_defavorables + 1) / (n_repetitions + 1),
        "ell": float(ell), "n_repetitions": n_repetitions,
    }


def sensibilite(x: np.ndarray, statistique=np.mean,
                longueurs: tuple[int, ...] = LONGUEURS_SENSIBILITE,
                n_repetitions: int = N_REPETITIONS, graine: int = 0) -> list[dict]:
    """Le meme test sur trois longueurs de bloc. A publier ENTIER, jamais la meilleure ligne.

    Si la p-value passe de 0,02 a 0,21 entre l = 5 et l = 50, le resultat depend du reglage
    et non des donnees : c'est une information decisive, et c'est precisement celle qu'on
    perd en ne publiant qu'une valeur.
    """
    return [{**intervalle(x, statistique, float(ell), n_repetitions, graine=graine),
             "ell_demande": ell} for ell in longueurs]


def stable(resultats: list[dict], seuil_p: float = ALPHA) -> bool:
    """Le resultat tient-il sur TOUTES les longueurs de bloc ? Une seule suffit a le tuer."""
    valeurs = [r["p_value"] for r in resultats]
    return bool(valeurs) and all(p == p and p <= seuil_p for p in valeurs)
