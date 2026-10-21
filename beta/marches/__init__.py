"""Les vrais marches (Jonas, 20-21/10) : indices, or, VIX et USD/JPY a la source.

Ni Binance ni freqtrade : Yahoo (yfinance) pour les indices et le VIX, le World Gold Council pour
l'or comptant (fixing LBMA de l'apres-midi, Yahoo n'a que le future GC=F), FRED pour USD/JPY
(H.10, avec ses dates de publication ALFRED). Structure PARALLELE au lake, comme `vision` :
`data/marches/<NOM>-1d.parquet` + `data/marches/etat.json` (couverture, trous, provenance,
revisions). Lecture : `collecte.lire("SPX")`.

Noms neufs, choisis pour ne rien heurter : dans le lake, SP500 / NASDAQ / XAUUSD (yfinance 1d
depuis 2010 : ^GSPC, ^IXIC Composite, future GC=F) et XAU / QQQ / SPY (perpetuels Binance) gardent
leur sens. Rien de ce qui tourne ne lit ce dossier.
"""
