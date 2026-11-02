"""VC6 V1, Temps 2 : calculs INDEPENDANTS du moteur pour les tests de coherence a et b.

    /root/venvs/beta/bin/python -I VC6_V1/temps2/verif_independante.py <racine BETA> <sortie.json>

N'importe rien de BETA : relit les copies figees avec pandas, refait la cloture de 23:55 et la
SMA 200 a sa facon (rolling pandas), et ecrit trois valeurs finales :
- a1 : BTC seul, 100 % si cloture >= SMA 200, sinon 0 ; decision a t, rendement t+1 ;
- a2 : BTC seul, exposition 1 en haussier, poche baissiere 25 % BTC, rampe de 5 jours lineaire,
       sans frais ni bande (expo constante) ;
- b  : panier BTC 50 / ETH 25 / SOL 25 reequilibre chaque jour, toujours investi.
Periode : rendements du 01/06/2021 au 31/10/2026.
"""

import json
import pathlib
import sys

import pandas as pd

racine = pathlib.Path(sys.argv[1])
DEBUT, FIN = pd.Timestamp("2021-06-01"), pd.Timestamp("2026-10-31")


def cloture(actif):
    df = pd.read_parquet(racine / f"data/vc6_v1/sources_figees/{actif}_perp_5m.parquet",
                         columns=["date", "close"])
    t = pd.to_datetime(df["date"], utc=True)
    garde = (t.dt.hour == 23) & (t.dt.minute == 55)
    s = pd.Series(df["close"][garde].to_numpy(), index=t[garde].dt.tz_localize(None).dt.floor("D"))
    return s.sort_index()


btc = cloture("BTC")
sma = btc.rolling(200).mean()
haussier = (btc >= sma).astype(float)
r = btc.pct_change()
jours = pd.date_range(DEBUT, FIN, freq="D")
veille = jours - pd.Timedelta(days=1)

# a1 : SMA 200 binaire
pos = haussier.reindex(veille).to_numpy()
a1 = float((1 + pos * r.reindex(jours).to_numpy()).prod())

# a2 : rampe de 5 jours entre 1 (haussier) et 0,25 (baissier)
cible = haussier.map({1.0: 1.0, 0.0: 0.25})
expo, valeur, prec_mode, depart, k = None, 1.0, None, None, 0
for j, v in zip(jours, veille):
    m, c = haussier[v], cible[v]
    if expo is None:
        expo = c
    else:
        if m != prec_mode:
            depart, k = expo, 1
        elif 0 < k < 5:
            k += 1
        else:
            k = 0
        expo = depart + k / 5 * (c - depart) if k else c
    prec_mode = m
    valeur *= 1 + expo * r[j]
a2 = float(valeur)

# b : panier reequilibre chaque jour
rp = sum(w * cloture(a).pct_change().reindex(jours)
         for a, w in (("BTC", 0.5), ("ETH", 0.25), ("SOL", 0.25)))
b = float((1 + rp).prod())

pathlib.Path(sys.argv[2]).write_text(json.dumps({"a1": a1, "a2": a2, "b": b}, indent=1))
print(json.dumps({"a1": a1, "a2": a2, "b": b}))
