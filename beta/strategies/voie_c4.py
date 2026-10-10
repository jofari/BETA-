"""VC4 — la chaine de VC3, decidee a chaque ouverture de session au lieu d'une fois par jour.

Preenregistrement : `scripts/preenregistrer_vc4.py` (Jonas, 10/10). La config est celle de VC3
plus une cle `cadence` (les instants de decision). Rien n'est reecrit de la voie C2 : les votes,
le moteur haussier et le deroulement (`voie_c2.derouler`) sont ceux de VC3, nourris a la
granularite des INSTANTS :

    instants  semaine : Tokyo, Londres, New York (heures locales, heure d'ete IANA) ;
              week-end : 00:00 UTC. Chaque jour commence donc par une decision a 00:00 UTC.
    prix(t)   cloture de la derniere bougie 5 min close a t (ouverte a t - 5 min).
    ancrage   pour chaque heure UTC h ou l'on decide, une serie QUOTIDIENNE « ancree » :
              clotures_h[d] = prix a d + 1 jour + h. C'est la convention des bougies 1d du lake
              (la bougie d se clot a d + 1 jour 00:00) decalee de h : a h = 00:00, ce sont
              EXACTEMENT les clotures de VC3. La ligne d de la chaine (qui ne lit que les
              lignes <= d - 1) sert l'instant d + h et ne lit que des prix <= d + h.
    macro     votes de VC3 du jour civil UTC de l'instant (memes delais de publication) ; seul
              le vote momentum BTC est recalcule, sur la serie ancree.
    periodes  la position decidee a t_i est tenue jusqu'a t_(i+1) ; rendement = prix(t_(i+1))
              / prix(t_i) - 1. Rendement QUOTIDIEN = produit des periodes du jour.

Verifie par les tests : une cadence reduite a 00:00 UTC chaque jour redonne VC3 a l'identique ;
troncature et perturbation des donnees posterieures a un instant ne changent pas sa decision.
"""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from beta.lake.lecture import load
from beta.strategies import voie_c2 as c2
from beta.strategies import voie_c_voltarget as vc

CINQ_MIN = pd.Timedelta(minutes=5)
TOLERANCE_PRIX = pd.Timedelta(minutes=30)      # au-dela, le prix d'un instant est « absent »
UN_JOUR = pd.Timedelta(days=1)


# =========================================================================================
# Donnees : clotures 5 min indexees par leur heure de CLOTURE
# =========================================================================================

def donnees_5m(debut: pd.Timestamp | None = None,
               fin: pd.Timestamp | None = None) -> dict[str, pd.Series]:
    """Clotures 5 min de chaque paire, indexees par l'heure de CLOTURE (ouverture + 5 min),
    coupees a `fin` incluse (heure de cloture)."""
    sortie = {}
    for paire in vc.PAIRES:
        df = load(paire, "5m", debut=None if debut is None else str(debut - CINQ_MIN),
                  colonnes=("close",))
        serie = pd.Series(df["close"].to_numpy(dtype=float),
                          index=pd.DatetimeIndex(df["date"]) + CINQ_MIN)
        sortie[paire] = serie if fin is None else serie[serie.index <= fin]
    return sortie


def tronquer_5m(cinq: dict[str, pd.Series], fin: pd.Timestamp) -> dict[str, pd.Series]:
    return {p: s[s.index <= fin] for p, s in cinq.items()}


# =========================================================================================
# Les instants de decision
# =========================================================================================

def instants(debut: pd.Timestamp, fin: pd.Timestamp, cadence: dict) -> pd.DatetimeIndex:
    """Les instants (UTC) de tous les jours UTC de [debut, fin], dans l'ordre."""
    sortie = set()
    for jour in pd.date_range(debut.normalize(), fin.normalize(), freq="D", tz="UTC"):
        regles = cadence["week_end"] if jour.weekday() >= 5 else cadence["semaine"]
        for r in regles:
            heure, minute = (int(x) for x in r["heure"].split(":"))
            local = dt.datetime(jour.year, jour.month, jour.day, heure, minute,
                                tzinfo=ZoneInfo(r["fuseau"]))
            t = pd.Timestamp(local).tz_convert("UTC")
            if t.normalize() != jour:
                raise ValueError(f"{r} tombe le {t:%Y-%m-%d} UTC, pas le {jour:%Y-%m-%d}")
            sortie.add(t)
    return pd.DatetimeIndex(sorted(sortie))


def prix_aux_instants(cinq: dict[str, pd.Series], quand: pd.DatetimeIndex) -> pd.DataFrame:
    """Le prix de chaque paire a chaque instant : derniere cloture 5 min <= l'instant."""
    return pd.DataFrame({p: s.reindex(quand, method="ffill", tolerance=TOLERANCE_PRIX)
                         for p, s in cinq.items()}, index=quand)[list(vc.PAIRES)]


def clotures_ancrees(cinq: dict[str, pd.Series], calendrier: pd.DatetimeIndex,
                     heure: pd.Timedelta) -> pd.DataFrame:
    """Serie quotidienne ancree a l'heure `heure` : ligne d = prix a d + 1 jour + heure."""
    quand = calendrier + UN_JOUR + heure
    prix = prix_aux_instants(cinq, quand)
    return prix.set_axis(calendrier)


# =========================================================================================
# La chaine
# =========================================================================================

def prolonger(d: dict) -> dict:
    """Les donnees quotidiennes plus la journee en cours, pas encore close : cloture de la
    veille recopiee (comme `c2_suivi.prolonger`). La ligne du jour ne lit que les lignes
    precedentes : la valeur recopiee ne touche aucune decision du jour."""
    closes = d["closes"]
    demain = pd.DatetimeIndex([closes.index[-1] + UN_JOUR], name=closes.index.name)
    return {**d, "closes": pd.concat([closes, closes.iloc[[-1]].set_axis(demain)])}


def calculer(d: dict, cinq: dict[str, pd.Series], cfg: dict,
             depart: pd.Timestamp = c2.DEPART_SIMULATION,
             fin: pd.Timestamp | None = None) -> dict:
    """VC4, PURE : donnees quotidiennes de VC3 + clotures 5 min -> decisions a chaque instant.

    `fin` (jour UTC inclus) : dernier jour simule ; par defaut le dernier jour du calendrier
    quotidien. Il peut le depasser d'UN jour (la journee en cours, bougie 1d pas encore close).
    Un instant sans prix (au-dela des donnees) n'est pas simule ; la derniere periode court
    jusqu'au 00:00 UTC suivant si son prix existe, sinon elle reste ouverte (rendement 0).
    """
    if fin is not None and fin > d["closes"].index[-1]:
        if fin - d["closes"].index[-1] > UN_JOUR:
            raise ValueError("au plus un jour au-dela de la derniere bougie quotidienne close")
        d = prolonger(d)
    closes = d["closes"]
    cal = closes.index
    fin = cal[-1] if fin is None else fin
    quand = instants(depart, fin, cfg["cadence"])
    prix = prix_aux_instants(cinq, quand)
    quand = quand[prix.notna().all(axis=1).to_numpy()]
    prix = prix.loc[quand]
    # le prix qui clot la derniere periode : le 00:00 UTC suivant, s'il existe deja
    terminal = prix_aux_instants(cinq, pd.DatetimeIndex([fin + UN_JOUR]))
    suivant = pd.concat([prix.iloc[1:], terminal]).set_axis(quand)

    v_jour = c2.votes(d, cfg)                       # macro et F&G du jour civil, comme VC3
    seuils = cfg["seuils_etat"]
    dec_prix = cfg["decalages"]["prix_j"]
    fen_vote = cfg["vote_momentum"]["fenetre"]
    fen_alts = cfg["baissier"]["fenetre_mom_alts"]
    alts = list(vc.PAIRES[1:])
    jours = quand.normalize()
    heures = quand - jours

    n, k = len(quand), len(vc.PAIRES)
    cible = np.full((n, k), np.nan)
    alt_en_baisse = np.zeros((n, k - 1), dtype=bool)
    votes = pd.DataFrame(index=quand, columns=v_jour.columns, dtype=float)
    leviers, sigmas = np.full(n, np.nan), np.full(n, np.nan)
    for h in pd.unique(heures):
        sel = np.flatnonzero(np.asarray(heures == h))
        lignes = jours[sel]
        ancre = clotures_ancrees(cinq, cal, pd.Timedelta(h))
        mh = c2.moteur_haussier(ancre, cfg["haussier"])
        btc = ancre["BTC"]
        mom = np.sign(btc / btc.shift(fen_vote) - 1.0).shift(dec_prix).fillna(0.0)
        baisse = ((ancre[alts] / ancre[alts].shift(fen_alts) - 1.0) < 0.0).shift(1)
        baisse = baisse.fillna(False).astype(bool)
        v = v_jour.reindex(lignes).copy()
        v["momentum_btc"] = mom.reindex(lignes).to_numpy()
        votes.iloc[sel] = v.to_numpy()
        cible[sel] = mh["cible"].reindex(lignes).to_numpy(dtype=float)
        alt_en_baisse[sel] = baisse.reindex(lignes).to_numpy(dtype=bool)
        leviers[sel] = mh["levier"].shift(1).reindex(lignes).to_numpy(dtype=float)
        sigmas[sel] = mh["sigma"].shift(1).reindex(lignes).to_numpy(dtype=float)

    somme = votes.sum(axis=1).to_numpy()
    etat = np.where(somme >= seuils["haussier"], c2.HAUSSIER,
                    np.where(somme <= seuils["baissier"], c2.BAISSIER, c2.VEILLE))
    rend = (suivant / prix - 1.0).to_numpy(dtype=float)       # periode ouverte : NaN -> 0
    sortie = c2.derouler(etat, cible, rend, np.zeros((n, k)), alt_en_baisse, cfg)

    r_net = pd.Series(sortie["r_net"], index=quand)
    jours_simules = pd.DatetimeIndex(sorted(set(jours)))
    quotidien = (1.0 + r_net).groupby(jours).prod().reindex(jours_simules) - 1.0
    return {"instants": quand, "prix": prix, "votes": votes,
            "etat": pd.Series(etat, index=quand), "cible": cible,
            "levier": pd.Series(leviers, index=quand), "sigma": pd.Series(sigmas, index=quand),
            "jours": jours_simules, "r_net_jour": quotidien, **sortie}


# =========================================================================================
# Epreuves de causalite
# =========================================================================================

def epreuve_causalite(d: dict, cinq: dict[str, pd.Series], cfg: dict,
                      t: pd.Timestamp) -> dict[str, float]:
    """Ecarts max (0 attendu) a l'instant t entre la chaine complete et deux chaines « a t ».

    1. troncature : clotures 5 min coupees a t, donnees quotidiennes coupees a la veille de
       t (la bougie du jour se clot a minuit suivant) ; macro coupee au jour de t.
    2. perturbation : tout ce qui n'est pas public a t est fausse — clotures 5 min apres t
       (x 1,5), bougie 1d du jour de t (x 1,5), F&G date du jour, FRED et Nasdaq dates de la
       veille et du jour. Votes, etat et position a t ne doivent pas bouger.
    """
    jour = t.normalize()
    complet = calculer(d, cinq, cfg, fin=jour)
    i_t = int(np.flatnonzero(complet["instants"] == t)[0])

    def ecarts_a_t(autre: dict, nom: str) -> dict[str, float]:
        j = int(np.flatnonzero(autre["instants"] == t)[0])
        return {f"{nom} votes": float(np.abs(autre["votes"].iloc[j].to_numpy(float)
                                             - complet["votes"].iloc[i_t].to_numpy(float)).max()),
                f"{nom} etat": float(autre["etat"].iat[j] != complet["etat"].iat[i_t]),
                f"{nom} position": float(np.abs(autre["positions"][j]
                                                - complet["positions"][i_t]).max())}

    veille = jour - UN_JOUR
    court = {k: (v[v.index <= veille] if k == "closes" else v[v.index <= jour])
             for k, v in d.items()}
    ecarts = ecarts_a_t(calculer(court, tronquer_5m(cinq, t), cfg, fin=jour), "troncature")

    fausse = {k: v.copy() for k, v in d.items()}
    if jour in fausse["closes"].index:
        fausse["closes"].loc[jour] = fausse["closes"].loc[jour] * 1.5
    fausse["fng"].loc[jour] = 1.0
    for cle in ("DFII10", "T10YIE", "NASDAQ100"):
        serie = fausse[cle]
        for j in (veille, jour):
            serie.loc[j] = serie.iloc[-1] * (0.5 if cle == "NASDAQ100" else 1.0) + 5.0
        fausse[cle] = serie.sort_index()
    cinq_faux = {p: s.where(s.index <= t, s * 1.5) for p, s in cinq.items()}
    ecarts.update(ecarts_a_t(calculer(fausse, cinq_faux, cfg, fin=jour), "perturbation"))
    return ecarts
