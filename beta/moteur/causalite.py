"""L'epreuve de causalite d'une candidate, sur les series qu'on lui donne.

Le coeur de l'epreuve de l'atelier (`beta.atelier.epreuve`), sorti ici le 04/11/2026 pour que
le MOTEUR la refasse avant toute mesure, sur les series memes du run.

Pourquoi (R13 et R14, 04/11/2026) : l'epreuve de l'atelier tournait sur une serie TEMOIN — BTC
en 4h par defaut, BTC dans le timeframe demande sinon — jamais sur la serie que la candidate
allait trader. Une regle ancree sur l'ouverture de New York ne signale pas en 4h, donc etait
refusee a tort ; avec `--timeframe 5m`, elle etait eprouvee sur BTC, pas sur l'or. Et une
candidate ecrite directement dans `beta/candidates/` ne passait par aucune epreuve du tout.
Le comptage des signaux et l'epreuve de causalite de R13 et R14 ont donc ete faits hors de
BETA, par un script improvise. Jonas : « une partie du test est passee par toi, pas par BETA ».

Deux controles, et des comptes :

1. **determinisme** — deux appels sur le meme DataFrame rendent la meme sortie ;
2. **causalite** — `signaux(df[:t])` doit rendre EXACTEMENT `signaux(df)[:t]`, a trois
   coupures. Toute lecture du futur deplace au moins une valeur du prefixe ;
3. **comptes** — signaux, longs, courts, sur la serie entiere : le nombre de signaux AVANT
   mesure sort de BETA, pas d'un script a cote.

Rien ici ne lit un rendement : aucun prix futur, aucun R. C'est ce qui permet de lancer
l'epreuve avant le preenregistrement — pour savoir combien de signaux la regle donnera sur la
periode — sans rien apprendre de son resultat.

Une violation du CONTRAT (`appliquer` leve) remonte telle quelle : c'est a l'appelant de dire
ce qu'elle signifie (un refus pour l'atelier, une candidate ecartee pour le moteur).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Coupures de l'epreuve de causalite, en fraction de la serie. Trois suffisent : une fonction
# qui regarde le futur echoue a la premiere, et les deux autres ne servent qu'a distinguer un
# debordement d'une bougie d'une normalisation globale.
COUPURES = (0.40, 0.70, 0.95)
COUPE_MIN = 50

TOLERANCE = 1e-9            # colonnes auxiliaires : un ecart flottant n'est pas une faute


class EpreuveRefusee(RuntimeError):
    """La candidate a tourne et l'epreuve la refuse : aucune mesure ne doit suivre.

    `rapport` porte le detail (refus, reserves, comptes par serie), pour que l'appelant puisse
    le journaliser sans le recalculer.
    """

    def __init__(self, rapport: dict):
        self.rapport = rapport
        super().__init__("epreuve de causalite refusee : " + " ; ".join(rapport.get("refus")
                                                                         or ["?"]))


def comparer(reference: pd.DataFrame, tronque: pd.DataFrame) -> tuple[int, int | None, float]:
    """Compare un prefixe de signaux au meme prefixe calcule sur la serie tronquee.

    Rend (nombre de lignes ou `sens` differe, premiere de ces lignes, plus grand ecart sur
    les colonnes auxiliaires). `sens` se compare a l'identique — c'est un entier, et c'est
    la seule colonne dont le moteur se sert. Les colonnes auxiliaires (`force`,
    `stop_distance`) tolerent un ecart flottant : un chiffre qui bouge de 1e-16 n'est pas
    une lecture du futur, c'est de l'arithmetique.
    """
    a = reference["sens"].to_numpy()
    b = tronque["sens"].to_numpy()
    differences = np.flatnonzero(a != b)
    premiere = int(differences[0]) if differences.size else None

    ecart = 0.0
    for colonne in (set(reference.columns) & set(tronque.columns)) - {"sens"}:
        try:
            x = reference[colonne].to_numpy(dtype=float)
            y = tronque[colonne].to_numpy(dtype=float)
        except (TypeError, ValueError):
            continue                                       # colonne non numerique : ignoree
        fini = np.isfinite(x) & np.isfinite(y)
        if fini.any():
            ecart = max(ecart, float(np.max(np.abs(x[fini] - y[fini]))))
        if (np.isnan(x) != np.isnan(y)).any():
            ecart = max(ecart, float("inf"))
    return int(differences.size), premiere, ecart


def _bornes(df: pd.DataFrame) -> tuple[str | None, str | None]:
    if "date" not in df.columns or df.empty:
        return None, None
    dates = pd.to_datetime(df["date"], utc=True)
    return str(dates.iloc[0]), str(dates.iloc[-1])


def eprouver_serie(candidate, df: pd.DataFrame) -> dict:
    """Determinisme, causalite et comptes d'une candidate sur UNE serie.

    Rend `{refus, reserves, mesures}`. Les messages de refus sont ceux de l'atelier depuis le
    19/08, mot pour mot : un refus dit ce qu'il faut corriger, quel que soit l'etage qui parle.
    """
    refus: list[str] = []
    reserves: list[str] = []

    signaux = candidate.appliquer(df)                      # contrat : leve si viole

    encore = candidate.appliquer(df)
    ecarts, premiere, _ = comparer(signaux, encore)
    if ecarts:
        refus.append(f"deux appels sur le MEME DataFrame donnent des signaux differents "
                     f"({ecarts} lignes, la premiere en {premiere}) : la candidate garde "
                     "un etat, elle n'est pas une fonction pure")

    coupures: list[int] = []
    for fraction in COUPURES:
        coupe = max(COUPE_MIN, int(len(df) * fraction))
        if coupe >= len(df):
            continue
        coupures.append(coupe)
        try:
            partiel = candidate.appliquer(df.iloc[:coupe])
        except Exception as exc:                           # noqa: BLE001
            refus.append(f"la candidate echoue sur une serie tronquee a {coupe} bougies "
                         f"({type(exc).__name__}: {exc}) — elle suppose une longueur "
                         "minimale qu'un run ne lui garantit pas")
            continue
        ecarts, premiere, ecart_aux = comparer(signaux.iloc[:coupe], partiel)
        if ecarts:
            refus.append(
                f"CAUSALITE : coupee a {coupe} bougies, la candidate change {ecarts} "
                f"signaux du passe (le premier en {premiere}). Une fonction causale ne le "
                "peut pas : elle lit donc quelque chose apres la ligne qu'elle decide")
        elif ecart_aux > TOLERANCE:
            reserves.append(f"coupee a {coupe}, une colonne auxiliaire bouge de "
                            f"{ecart_aux:.2e} — sans effet sur `sens`, mais a savoir")
    if not coupures:
        reserves.append(f"serie de {len(df)} bougies : trop courte pour une seule coupure, "
                        "la causalite n'a pas ete eprouvee")

    sens = signaux["sens"]
    n_signaux = int((sens != 0).sum())
    premiere_bougie, derniere_bougie = _bornes(df)
    mesures = {"n_bougies": len(df), "premiere": premiere_bougie,
               "derniere": derniere_bougie, "n_signaux": n_signaux,
               "n_long": int((sens > 0).sum()), "n_short": int((sens < 0).sum()),
               "part_en_position": round(n_signaux / max(len(df), 1), 4),
               "coupures": coupures,
               "causalite": "non eprouvee" if not coupures else (
                   "refusee" if any(r.startswith(("CAUSALITE", "la candidate echoue"))
                                    for r in refus) else "ok"),
               "determinisme": "refuse" if any(r.startswith("deux appels") for r in refus)
               else "ok"}
    return {"refus": refus, "reserves": reserves, "mesures": mesures}
