"""S5 — chemins synthetiques : la strategie rejouee sur des marches qui n'ont pas existe.

Toutes les autres pieces de la batterie rebrassent les TRADES. Celle-ci rebrasse le MARCHE :
on fabrique des series qui ressemblent a la vraie sous tous les angles qu'on sait mesurer,
et on rejoue la candidate dessus. Si elle gagne autant sur des marches sans structure
exploitable, elle n'exploite rien — elle encaisse une propriete generique des prix
(la derive, la volatilite groupee), pas un edge.

Deux generateurs, volontairement differents :

- **GBM** — mouvement brownien geometrique calibre sur la derive et la volatilite reelles.
  Marche sans memoire d'aucune sorte. C'est le temoin le plus severe : une strategie qui
  gagne sur du GBM gagne sur du bruit ;
- **phase randomization** — transformee de Fourier des rendements, phases remplacees par du
  hasard, transformee inverse. La serie obtenue a EXACTEMENT le meme spectre de puissance,
  donc la meme autocorrelation lineaire et la meme volatilite globale que la vraie ; seules
  les dependances non lineaires (et la chronologie) sont detruites. C'est le temoin le plus
  fin, et le plus difficile a battre honnetement.

Lecture : on compare le resultat reel a la DISTRIBUTION des resultats synthetiques. La
question n'est pas « la strategie gagne-t-elle sur du synthetique ? » — souvent oui, une
strategie longue gagne sur toute serie derivant vers le haut. Elle est : « gagne-t-elle
NETTEMENT PLUS sur le vrai marche ? »
"""

from __future__ import annotations

import numpy as np
import pandas as pd

N_CHEMINS = 200
CENTILE_EXIGE = 95.0


def _log_rendements(closes: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        lr = np.diff(np.log(closes))
    return lr[np.isfinite(lr)]


def _reconstruire_ohlcv(modele: pd.DataFrame, closes: np.ndarray,
                        rng: np.random.Generator) -> pd.DataFrame:
    """Habille une serie de clotures synthetiques en OHLCV plausible.

    Les meches sont reprises du marche reel, en PROPORTION du prix et melangees : la
    triple barriere depend entierement de l'amplitude intra-bougie, et une serie
    synthetique sans meches donnerait un taux de stop absurde — donc un temoin trop facile
    a battre, ce qui est le pire des deux cotes.
    """
    reel = modele["close"].to_numpy(dtype=float)
    haut_ratio = np.where(reel > 0, modele["high"].to_numpy(dtype=float) / reel, 1.0)
    bas_ratio = np.where(reel > 0, modele["low"].to_numpy(dtype=float) / reel, 1.0)
    ouverture_ratio = np.where(reel > 0, modele["open"].to_numpy(dtype=float) / reel, 1.0)
    melange = rng.permutation(len(closes))
    haut = closes * np.clip(haut_ratio[melange], 1.0, None)
    bas = closes * np.clip(bas_ratio[melange], None, 1.0)
    ouverture = closes * ouverture_ratio[melange]
    volume = (modele["volume"].to_numpy(dtype=float)[melange]
              if "volume" in modele.columns else np.ones(len(closes)))
    return pd.DataFrame({"date": modele["date"].to_numpy(), "open": ouverture,
                         "high": np.maximum.reduce([haut, ouverture, closes]),
                         "low": np.minimum.reduce([bas, ouverture, closes]),
                         "close": closes, "volume": volume})


def gbm(df: pd.DataFrame, n_chemins: int = N_CHEMINS, graine: int = 0):
    """Generateur de series GBM calibrees sur `df`. Rend un iterateur de DataFrame OHLCV."""
    closes = df["close"].to_numpy(dtype=float)
    lr = _log_rendements(closes)
    if len(lr) < 2:
        return
    mu, sigma = float(lr.mean()), float(lr.std(ddof=1))
    rng = np.random.default_rng(graine)
    depart = float(closes[0])
    for _ in range(n_chemins):
        pas = rng.normal(mu, sigma, size=len(closes) - 1)
        yield _reconstruire_ohlcv(df, depart * np.exp(np.concatenate([[0.0],
                                                                      pas.cumsum()])), rng)


def phase_randomization(df: pd.DataFrame, n_chemins: int = N_CHEMINS, graine: int = 0):
    """Surrogates a spectre conserve. Meme autocorrelation lineaire, chronologie detruite."""
    closes = df["close"].to_numpy(dtype=float)
    lr = _log_rendements(closes)
    if len(lr) < 4:
        return
    rng = np.random.default_rng(graine)
    spectre = np.fft.rfft(lr - lr.mean())
    amplitudes = np.abs(spectre)
    depart = float(closes[0])
    for _ in range(n_chemins):
        phases = rng.uniform(0, 2 * np.pi, size=len(spectre))
        phases[0] = 0.0                      # composante continue : phase nulle, sinon
        if len(lr) % 2 == 0:                 # la serie reconstruite serait complexe
            phases[-1] = 0.0
        serie = np.fft.irfft(amplitudes * np.exp(1j * phases), n=len(lr)) + lr.mean()
        chemin = depart * np.exp(np.concatenate([[0.0], serie.cumsum()]))
        # irfft rend len(lr) points ; on complete pour retrouver la longueur de `df`.
        if len(chemin) < len(closes):
            chemin = np.concatenate([chemin, np.full(len(closes) - len(chemin),
                                                     chemin[-1])])
        yield _reconstruire_ohlcv(df, chemin[:len(closes)], rng)


GENERATEURS = {"gbm": gbm, "phase": phase_randomization}


def comparer(observe: float, synthetiques: list[float],
             centile_exige: float = CENTILE_EXIGE) -> dict:
    """Ou tombe le resultat reel dans la distribution synthetique ?

    `passe` est vrai si le reel depasse le centile exige. Un resultat au 60e centile dit
    que la strategie fait, sur le vrai marche, ce qu'elle ferait sur du bruit : c'est un
    echec, meme si le backtest est en profit.
    """
    valeurs = np.array([v for v in synthetiques if np.isfinite(v)], dtype=float)
    if not len(valeurs) or not np.isfinite(observe):
        return {"n_chemins": len(valeurs), "centile": float("nan"), "passe": False,
                "observe": observe}
    centile = float((valeurs <= observe).mean() * 100.0)
    return {"n_chemins": len(valeurs), "observe": float(observe), "centile": centile,
            "seuil": float(np.percentile(valeurs, centile_exige)),
            "synthetique_median": float(np.median(valeurs)),
            "passe": centile >= centile_exige}
