"""Calibration de S3 sous H0 : le p percentile de la porte contre le p « centre » propose.

    /root/venvs/arit/bin/python scripts/calibration_s3.py            # ~5 min, une graine fixe

Pourquoi ce script existe (audit des portes du 05/11/2026) : l'audit affirmait que le p de S3,
p = (1 + #{theta* <= 0}) / (B + 1), n'est pas centre sous H0 et serait « environ 2 fois trop
flatteur dans la queue », et proposait p = (1 + #{theta* - theta_obs >= theta_obs}) / (B + 1).
Un p-value se juge a son taux de faux positifs sous H0, pas a sa valeur sur UN echantillon :
ce script le mesure, pour les deux formules, sur des R a esperance nulle.

Le bootstrap est le meme que celui de `beta.stats.bootstrap` (stationnaire, blocs de longueur
geometrique de moyenne l, bouclage circulaire), vectorise pour tenir en quelques minutes ; la
premiere ligne le compare au module sur cinq echantillons (meme loi, pas le meme flux
aleatoire : les p doivent etre proches, pas identiques).

Resultat du 05/11/2026 (graine 12345, 4 000 echantillons, B = 1 000, l = 5) : au seuil de 5 %,
percentile 4,9-6,3 %, centre 4,5-7,0 % ; le centre est PIRE en asymetrie a gauche. S3 garde
donc sa formule (`tests/test_audit_portes_0511.py::test_s3_garde_le_p_percentile`).
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.stats import bootstrap  # noqa: E402

GRAINE = 12345
N_ECHANTILLONS = 4000
B = 1000
ELL = 5.0
CAS = (("TP 2R / SL 1R (asymetrie a droite)", (2.0, -1.0), (1 / 3, 2 / 3)),
       ("TP 0,5R / SL 1R (asymetrie a gauche)", (0.5, -1.0), (2 / 3, 1 / 3)),
       ("symetrique +1R / -1R", (1.0, -1.0), (0.5, 0.5)))
TAILLES = (60, 300)


def moyennes_bootstrap(x: np.ndarray, b: int, ell: float,
                       rng: np.random.Generator) -> np.ndarray:
    """b moyennes de rejeux stationnaires de x (Politis-Romano), vectorisees sur b."""
    n = len(x)
    p = 1.0 / ell
    idx = np.empty((b, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, b)
    for t in range(1, n):
        nouveau_bloc = rng.random(b) < p
        idx[:, t] = np.where(nouveau_bloc, rng.integers(0, n, b), (idx[:, t - 1] + 1) % n)
    return x[idx].mean(axis=1)


def p_valeurs(tirages: np.ndarray, observe: float, b: int) -> tuple[float, float]:
    """(p percentile de la porte, p centre propose par l'audit)."""
    return (((tirages <= 0).sum() + 1) / (b + 1),
            ((tirages - observe >= observe).sum() + 1) / (b + 1))


def taux_de_rejet(gains, probas, n: int) -> dict[float, tuple[float, float]]:
    rng = np.random.default_rng(GRAINE)
    p = np.empty((N_ECHANTILLONS, 2))
    for i in range(N_ECHANTILLONS):
        x = rng.choice(np.asarray(gains), size=n, p=probas)
        p[i] = p_valeurs(moyennes_bootstrap(x, B, ELL, rng), float(x.mean()), B)
    return {a: (float((p[:, 0] <= a).mean()), float((p[:, 1] <= a).mean()))
            for a in (0.05, 0.01)}


def main() -> int:
    rng = np.random.default_rng(3)
    controle = []
    for i in range(5):
        x = rng.choice([2.0, -1.0], size=80, p=[0.42, 0.58])
        module = bootstrap.intervalle(x, ell=ELL, n_repetitions=4000, graine=i)["p_value"]
        vecto = p_valeurs(moyennes_bootstrap(x, 4000, ELL, rng), float(x.mean()), 4000)[0]
        controle.append(f"{module:.4f}/{vecto:.4f}")
    print("controle module/vectorise (p percentile, B = 4000) : " + ", ".join(controle))
    print(f"taux de faux positifs sous H0 ({N_ECHANTILLONS} echantillons, B = {B}, l = {ELL:g}, "
          f"graine {GRAINE}) :")
    for titre, gains, probas in CAS:
        for n in TAILLES:
            t = taux_de_rejet(gains, probas, n)
            print(f"  {titre}, n = {n} : seuil 5 % -> percentile {t[0.05][0]:.3f}, "
                  f"centre {t[0.05][1]:.3f} ; seuil 1 % -> percentile {t[0.01][0]:.4f}, "
                  f"centre {t[0.01][1]:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
