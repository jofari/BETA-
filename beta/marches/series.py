"""Les series des vrais marches : une source, un identifiant, un fuseau de seance.

`fuseau` sert a une seule chose : savoir si la bougie du jour est close (Yahoo sert la seance en
cours avec un « close » qui bouge). `publication` dit si la serie porte ses dates de premiere
publication (ALFRED) : une valeur n'est utilisable qu'apres sa publication, pas a sa date.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Serie:
    nom: str                       # slug de fichier et cle de l'etat : SPX-1d.parquet
    source: str                    # 'yahoo' | 'wgc' | 'fred' | 'ds1'
    identifiant: str               # ticker Yahoo, identifiant FRED, ou libelle WGC
    description: str
    fuseau: str                    # fuseau de la seance (cloture de la bougie du jour)
    depuis: str = ""               # borne basse documentee (la source sert tout ce qu'elle a)
    publication: str = ""          # 'alfred' : dates de premiere publication


SERIES: tuple[Serie, ...] = (
    Serie("SPX", "yahoo", "^GSPC", "S&P 500, indice de prix (dividendes exclus)",
          "America/New_York", "1927-12-30"),
    Serie("NDX", "yahoo", "^NDX", "Nasdaq-100, indice de prix (Jonas 21/10 : pas le Composite)",
          "America/New_York", "1985-10-01"),
    Serie("VIX", "yahoo", "^VIX", "CBOE VIX, cloture 16:15 ET", "America/Chicago",
          "1990-01-02"),
    Serie("XAU_LBMA", "wgc", "LBMA Gold Price PM, USD/oz",
          "or comptant : fixing LBMA de l'apres-midi (15:00 Londres), via le World Gold Council "
          "(Jonas 21/10 : Yahoo n'a que le future GC=F, depuis 2000)", "Europe/London",
          "1970-01-01"),
    Serie("DEXJPUS", "fred", "DEXJPUS",
          "USD/JPY, yens pour 1 dollar, H.10 (cours acheteur de midi a New York), publie chaque "
          "semaine", "America/New_York", "1971-01-04", publication="alfred"),
    Serie("VIXCLS", "fred", "VIXCLS",
          "CBOE VIX, cloture, telle que publiee par FRED (Jonas 24/10, test de justesse : « FRED, "
          "serie VIXCLS ») ; ^VIX Yahoo reste a cote", "America/Chicago", "1990-01-02"),
    Serie("BTC_DS1", "ds1", "bitstamp",
          "BTC/USD spot, cloture du jour civil UTC (Bitstamp), lue dans la base souveraine DS1 "
          "(table bougies_1d, Jonas 24/10)", "UTC", "2011-08-18"),
)


def par_nom(nom: str) -> Serie:
    for s in SERIES:
        if s.nom == nom.upper():
            return s
    raise KeyError(f"serie inconnue : {nom} (connues : {', '.join(s.nom for s in SERIES)})")
