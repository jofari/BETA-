"""D'ou vient le resultat : quelques trades, une annee, une paire, ou des couts sous-estimes ?

OUTILS INFORMATIFS (15/11/2026). Aucun n'est une porte ni un verdict ; aucun seuil de
decision ne vit ici (une regle ne change que par decision de Jonas, `DECISIONS.md`).

Un R moyen positif peut reposer sur tres peu de chose. Quatre lectures, toutes sur les
trades DEJA mesures (rien n'est rejoue, aucun signal nouveau, aucun essai consomme) :

- **concentration** — quelle part des gains vient des 5 % de meilleurs trades, et combien de
  meilleurs trades faut-il retirer pour que le total tombe a zero ? Un edge porte par trois
  trades sur quatre cents n'est pas un edge, c'est trois evenements ;
- **stress des couts** — le R moyen si les couts etaient 1,5, 2 ou 3 fois ceux du modele, et
  le multiple qui l'annule. Le modele de couts est une estimation (frais forfaitaires,
  spread d'un tick, funding au prorata) : un resultat qui meurt a 1,3 fois le cout modele
  vit dans la marge d'erreur de ce modele ;
- **par annee** — n, R moyen et MDE de chaque annee, part de la meilleure annee. S6 coupe
  en six plis de duree egale ; l'annee civile est ce qu'un lecteur reconnait (2021, 2022) ;
- **sans une paire** — le R moyen en retirant chaque paire a son tour. Si retirer SOL
  renverse le signe, la candidate mesure SOL.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from beta.stats import descriptif

MULTIPLES_COUT = (1.0, 1.5, 2.0, 3.0)
PART_TETE = 0.05
N_MIN_MDE = 10


def _r(trades: pd.DataFrame) -> np.ndarray:
    if "r" not in trades.columns:
        return np.empty(0, dtype=float)
    return trades["r"].dropna().to_numpy(dtype=float)


def concentration(trades: pd.DataFrame, part_tete: float = PART_TETE) -> dict:
    """Part des gains portee par les meilleurs trades, et ce qui reste sans eux.

    `part_gains_tete` : somme des R des `part_tete` meilleurs trades / somme des R positifs.
    `n_pour_annuler` : le plus petit nombre de meilleurs trades a retirer pour que le R total
    devienne <= 0 (0 si le total est deja <= 0). `r_moyen_sans_tete` : le R moyen des trades
    restants une fois la tete retiree.
    """
    r = _r(trades)
    n = len(r)
    if n < 2:
        return {"n": n}
    tries = np.sort(r)[::-1]
    k = max(1, math.ceil(part_tete * n))
    gains = float(tries[tries > 0].sum())
    total = float(r.sum())
    n_annuler = 0
    if total > 0:
        reste = total - np.cumsum(tries)
        n_annuler = int(np.argmax(reste <= 0)) + 1 if (reste <= 0).any() else n
    return {"n": n, "part_tete": part_tete, "n_tete": k,
            "part_gains_tete": float(tries[:k].clip(min=0).sum() / gains) if gains > 0
            else float("nan"),
            "r_total": total, "r_moyen": float(r.mean()),
            "r_moyen_sans_tete": float(tries[k:].mean()) if n > k else float("nan"),
            "r_moyen_sans_le_meilleur": float(tries[1:].mean()),
            "n_pour_annuler": n_annuler,
            "part_pour_annuler": n_annuler / n}


def stress_couts(trades: pd.DataFrame,
                 multiples: tuple[float, ...] = MULTIPLES_COUT) -> dict:
    """Le R moyen si les couts du modele etaient multiplies, et le multiple qui l'annule.

    R(m) = r_brut - m x cout_r, trade par trade : memes trades, memes sorties, seuls les
    couts changent (une approximation — un cout plus haut ne deplace pas les barrieres).
    `multiple_mort` = R brut moyen / cout moyen : sous 1, la candidate perd deja au cout du
    modele ; entre 1 et 2, elle vit dans la marge d'erreur d'un modele de couts. Colonnes
    `r_brut` / `cout_r` absentes (trades importes de freqtrade) => {} avec la raison.
    """
    if not {"r_brut", "cout_r"} <= set(trades.columns):
        return {"raison": "colonnes r_brut / cout_r absentes : trades sans detail de couts"}
    t = trades[["r_brut", "cout_r"]].dropna()
    if len(t) < 2:
        return {"raison": "moins de 2 trades"}
    brut, cout = t["r_brut"].to_numpy(dtype=float), t["cout_r"].to_numpy(dtype=float)
    cout_moyen, brut_moyen = float(cout.mean()), float(brut.mean())
    detail = {c: float(trades[c].dropna().mean())
              for c in ("frais_r", "spread_r", "funding_r") if c in trades.columns}
    return {"n": len(t), "r_brut_moyen": brut_moyen, "cout_moyen_r": cout_moyen,
            "detail_couts_r": detail,
            "par_multiple": [{"multiple": float(m), "r_moyen": float((brut - m * cout).mean()),
                              "win_rate": float(((brut - m * cout) > 0).mean())}
                             for m in multiples],
            # R brut deja <= 0 : aucun multiple positif ne l'annule, le rapport n'a pas de sens.
            "multiple_mort": (brut_moyen / cout_moyen if cout_moyen > 0 and brut_moyen > 0
                              else float("nan"))}


def par_annee(trades: pd.DataFrame, colonne_date: str = "ts_entree") -> dict:
    """n, R moyen, R total et MDE de chaque annee civile (UTC) d'ENTREE.

    `part_meilleure_annee` = R total de la meilleure annee / R total (NaN si le total est
    <= 0). `annees_positives` sur `n_annees`. Chaque ligne porte son MDE : une annee a 12
    trades ne dit rien, et le tableau doit le montrer.
    """
    if colonne_date not in trades.columns or "r" not in trades.columns or trades.empty:
        return {"annees": [], "n_annees": 0}
    t = trades[[colonne_date, "r"]].dropna()
    annees = pd.to_datetime(t[colonne_date], utc=True).dt.year
    lignes = []
    for annee, groupe in t.groupby(annees.to_numpy()):
        r = groupe["r"].to_numpy(dtype=float)
        sigma = float(r.std(ddof=1)) if len(r) > 1 else float("nan")
        lignes.append({"annee": int(annee), "n": len(r), "r_moyen": float(r.mean()),
                       "r_total": float(r.sum()),
                       # Sous 10 trades, l'ecart-type lui-meme n'est pas estime : pas de MDE.
                       "mde_r": (descriptif.mde(len(r), sigma, n_eff=descriptif.n_effectif(r))
                                 if len(r) >= N_MIN_MDE else float("nan"))})
    total = sum(l["r_total"] for l in lignes)
    meilleure = max(lignes, key=lambda l: l["r_total"]) if lignes else None
    return {"annees": lignes, "n_annees": len(lignes),
            "annees_positives": sum(l["r_total"] > 0 for l in lignes),
            "meilleure_annee": meilleure["annee"] if meilleure else None,
            "part_meilleure_annee": (meilleure["r_total"] / total
                                     if meilleure and total > 0 else float("nan")),
            "r_total_sans_meilleure_annee": (total - meilleure["r_total"]
                                             if meilleure else float("nan"))}


def sans_une_paire(trades: pd.DataFrame) -> dict:
    """Le R moyen en retirant chaque paire a son tour (jackknife par paire).

    `pire` = la paire dont le retrait laisse le R moyen le plus bas : celle qui porte le
    resultat. `signe_tient` : le R moyen garde-t-il le signe de l'ensemble sans elle ?
    """
    if not {"paire", "r"} <= set(trades.columns):
        return {"paires": [], "raison": "colonnes paire / r absentes"}
    t = trades[["paire", "r"]].dropna()
    paires = sorted(t["paire"].unique())
    if len(paires) < 2:
        return {"paires": [], "raison": "une seule paire : rien a retirer"}
    ensemble = float(t["r"].mean())
    lignes = []
    for paire in paires:
        reste = t.loc[t["paire"] != paire, "r"]
        lignes.append({"sans": paire, "n": int(len(reste)),
                       "n_retires": int(len(t) - len(reste)),
                       "r_moyen": float(reste.mean()) if len(reste) else float("nan")})
    pire = min(lignes, key=lambda l: l["r_moyen"])
    return {"r_moyen": ensemble, "paires": lignes, "pire": pire["sans"],
            "r_moyen_sans_pire": pire["r_moyen"],
            "signe_tient": bool(np.sign(pire["r_moyen"]) == np.sign(ensemble))}
