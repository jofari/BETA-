# CLAUDE.md — `beta/marches/` : les vrais marchés

> Famille 2 (utile dans ce dossier) : se charge quand on travaille ici. Texte déplacé de la
> racine le 15/11/2026.

**Les vrais marchés** (Jonas, 20-21/10 : « pas la version de Binance », « sortir de freqtrade »).
Le paquet `beta/marches` est une structure **parallèle** au lake, comme `vision`. Fichiers dans
`data/marches/` : `<NOM>-<tf>.parquet`, plus `etat.json` et `etat_intraday.json`. Rien de ce
qui tourne ne la lit ; seuls les labos `beta/temps1` (T1A) et `beta/temps1_justesse` (T1J,
test de justesse du 24/10) l'utilisent. Noms **neufs**, sans collision
avec le lake (test) : `SP500`, `NASDAQ` et `XAUUSD` gardent leur sens ci-dessus.
- Quotidien (`collecte.lire("SPX")`, timer `beta-marches`, 23:10 UTC) :
  - `SPX` : S&P 500 `^GSPC`, Yahoo, depuis 1927 ;
  - `NDX` : Nasdaq-100 `^NDX`, Yahoo, depuis 1985 ;
  - `VIX` : `^VIX`, Yahoo, depuis 1990 ;
  - `XAU_LBMA` : or comptant au fixing LBMA PM, via l'API du World Gold Council, à requêter
    **par année** (une plage courte rend un autre prix, 7 jours sur 7), depuis 1970 ;
  - `DEXJPUS` : USD/JPY H.10, FRED, hebdomadaire ; colonne `publie_le` = première publication
    ALFRED.
  - `VIXCLS` : le VIX tel que publié par FRED (T1J, 24/10), à côté de `^VIX` ;
  - `BTC_DS1` : clôture journalière BTC/USD Bitstamp, lue dans la base souveraine DS1 (table
    `bougies_1d`, lot DS1 de 00:15 UTC) par `docker exec psql`, en lecture seule, depuis 2011.
  - Règles : la séance du jour n'est jamais écrite avant sa clôture, et une réécriture du passé
    par la source part dans `revisions.jsonl`.
- Intraday (`intraday.lire("SPX", "5m")`, avec un 4h dérivé du 1h sur la grille UTC) :
  - `SPX`, `NDX` : Yahoo 5m (60 jours à la source, s'allonge à chaque passage) et 1h (730 jours),
    timer `beta-marches-direct` toutes les 5 min ;
  - `XAU_SPOT` : or comptant XAU/USD, bougies BID Dukascopy à la minute agrégées en 5m/1h/1d. La
    journée en cours vient des ticks horaires (retard ≤ ~1 h) ; l'historique depuis 2003 est
    rattrapé par `beta-marches-histo`. ⚠️ Dukascopy bride : une requête à la fois, 4 s entre deux,
    arrêt propre après trois 503 et reprise à l'heure suivante.
- Qualité, vérifiée le 21/10 :
  - `SP500` du lake = `SPX`, à l'identique ;
  - **FRED `NASDAQ100` (vote du socle) est faux sur 407 séances de 2003-2005** (31/12/2003 : 1 459,06
    contre 1 467,92 officiel) : Yahoo `^NDX` est juste. Le socle ne lit que 2019+ ;
  - FRED `VIXCLS` et `^VIX` diffèrent sur 11 séances, mais jamais de part et d'autre de 25.
