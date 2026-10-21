# Temps 1, étape A (laboratoire) — Phase 1 : découverte

Rédigé le 21/10/2026 à 17:40 UTC, **avant toute ligne de code** du module (seules des sondes de
lecture ont tourné, hors dépôt). Objet : tester si un détecteur de régime protège mieux des grandes
baisses qu'une SMA 200, à exposition moyenne égale, sur de longs historiques actions. Les actions
servent de laboratoire, on ne les trade pas. Aucune donnée crypto.

## 0. Décisions de Jonas prises avant d'écrire (21/10, ~17:30 UTC)

| Question | Réponse | Conséquence |
|---|---|---|
| Quel « Nasdaq » ? | **Nasdaq-100 `^NDX`** | Nom neuf `NDX`. Le `NASDAQ` du lake (= Composite `^IXIC`, 1d depuis 2010) n'est pas touché. |
| Quel or avant 2000 ? Yahoo n'a que le contrat à terme `GC=F` (depuis le 30/08/2000), donc COUCHE1 serait incalculable sur 1991-2001. | **Fixing LBMA de l'après-midi, via l'API publique du World Gold Council** | Quotidien depuis le 01/01/1970. C'est un **écart à « yfinance »**, repris au § 7 du rapport. |

## 1. Le moteur TI1 réutilisé tel quel (run de référence `84d75b9fef3e`)

Aucun de ces fichiers n'est modifié. Le nouveau code les importe.

| Fichier | Ce qui est réutilisé | Rôle dans l'étape A |
|---|---|---|
| `beta/invest/moteur.py` | `panier`, `rendement`, `exposition` + `Mapping("paliers")`, `temoin_constant`, `UN_JOUR` | Buy and hold de l'actif cible (poids 1), exposition décidée à la clôture J et appliquée en J+1, frais κ, témoin à exposition constante |
| `beta/invest/metriques.py` | `standard`, `courbe`, `drawdown`, `episodes`, `survie` (dont `faux_signaux`), `captures`, `pour_nulls` | Ulcer, MDD, CAGR, exposition moyenne, changements, épisodes ≥ 20 %, protection, retard, faux signaux et leur coût, captures |
| `beta/invest/nulls.py` | `flux`, `decalage_circulaire` (m = 90 j), `melange_segments`, `distribution_nulle`, `p_value`, `p_retenue` (D4), `verdict` | Les deux nulls, B = 1000, graine 0, p retenue = la pire des deux |
| `beta/protocole/experiences.py` | `preenregistrer`, `exiger`, `enregistrer_run`, `compteur`, `marquer_mesuree` | Préenregistrement, verrou, compteur d'essais |

Ce que je ne réutilise pas, et pourquoi :
- `beta/invest/donnees.py` : il charge le panier crypto et les votes du socle ;
- `beta/invest/campagne.py`, fonction `evaluer` : elle calcule toujours un hold BTC (`moteur.hold(d.closes, "BTC", …)`) et le funding des perpétuels. Le nouveau module recompose les mêmes appels au moteur sans ces deux lignes : même ordre, mêmes métriques, mêmes nulls ;
- `beta/invest/analyse.py` (kappa, ablations) : sans objet ici.

**Comment le moteur se branche sans modification.** Le moteur TI1 suppose un calendrier de
7 jours sur 7. Il annualise sur 365 jours (CAGR, Sharpe en racine de 365) et ses captures se
calculent sur des semaines civiles complètes de 7 jours (`captures` exige 7 jours par semaine).
Si on lui donnait seulement les séances de bourse, le CAGR serait faux et les captures vides. Les
clôtures de l'actif cible sont donc posées sur un **calendrier civil, comblées par la dernière
valeur connue** : le rendement est nul les jours sans séance. Le signal décidé à la clôture d'une
séance J reste en vigueur jusqu'à la séance suivante. Aux dates de séance, on obtient exactement la
même courbe qu'un calcul fait séance par séance (vérifié par un test). Les frais d'un changement
décidé un vendredi sont pris le samedi plutôt que le lundi : le total est le même.

## 2. Données S&P 500, Nasdaq et or trouvées sur le VPS (avant installation)

Les trous sont comptés en jours ouvrés (lundi-vendredi) absents entre deux observations. Aucune
fermeture régulière de bourse ne dépasse 5 jours ouvrés : le 11 septembre 2001, par exemple, a fermé
la bourse 4 jours.

| Fichier | Contenu réel | Début | Fin | Obs. | Trous > 5 séances | Utilisable pour le labo ? |
|---|---|---|---|---|---|---|
| `BETA-/data/lake/SP500-1d.parquet` | S&P 500 `^GSPC` (Yahoo) | 2010-01-04 | 2026-10-20 | 4 225 | 0 | Non : commence en 2010 |
| `BETA-/data/lake/NASDAQ-1d.parquet` | Nasdaq **Composite** `^IXIC` (Yahoo) | 2010-01-04 | 2026-10-20 | 4 225 | 0 | Non : mauvais indice, et 2010 |
| `BETA-/data/lake/XAUUSD-1d.parquet` | Or, **contrat à terme** COMEX `GC=F` (pas le comptant) | 2010-01-04 | 2026-10-20 | 4 225 | 0 | Non : contrat à terme, et 2010 |
| `BETA-/data/macro/global/vix.csv` | VIX, FRED `VIXCLS` | 1990-01-02 | 2026-10-19 | 9 298 | 0 | Contenu bon, mais je prends `^VIX` de Yahoo, comme demandé (§ 3) |
| `BETA-/data/macro/global/nasdaq100.csv` | Nasdaq-100, FRED `NASDAQ100` (clôtures seules) | 1986-01-02 | 2026-10-19 | 10 280 | 0 | Non retenu : Yahoo `^NDX` est demandé ; c'est le vote du socle, à ne pas toucher |
| `ARIT2.0/user_data/data/macro/…` (vix, nasdaq100) | copies d'ARIT | 1990 / 1986 | 09/10-2026 | — | 0 | Non : lecture seule, et doublons |
| `bac_venv_beta/BETA-/data/…` | sauvegarde du 16/10 (bascule du venv) | — | — | — | — | Non : copie figée |
| `BETA-/data/lake/{XAU,QQQ,SPY}_USDT_USDT-*` | perpétuels Binance (or, QQQ, SPY) | 2025-12-11 / 2026-04-06 | 2026-10-20 | 314 / 198 | — | **Exclus** : bourse crypto, et règle 4 |

USD/JPY : **aucun fichier** sur le VPS. Conclusion : les données présentes ne couvrent pas la
préchauffe de 1990 ; il faut les installer, ce que le prompt demande (« avec le maximum
d'historique possible »).

## 3. Sources vérifiées pour l'installation (sondes du 21/10, 17:20-17:40 UTC)

| Série | Source | Identifiant | Début | Fin | Contrôle |
|---|---|---|---|---|---|
| S&P 500 | Yahoo (yfinance 1.7.0) | `^GSPC` | 1927-12-30 | séance du jour | 330,22 au 31/12/1990 ; 1 527,46 au 24/03/2000 ; 676,53 au 09/03/2009 : conformes |
| Nasdaq-100 | Yahoo | `^NDX` | 1985-10-01 | séance du jour | 4 704,73 au 27/03/2000 : conforme ; rebasage de 1994 déjà corrigé (aucun saut) |
| VIX | Yahoo | `^VIX` | 1990-01-02 | séance du jour | 80,86 au 20/11/2008 ; 82,69 au 16/03/2020 : conformes |
| Or comptant | World Gold Council (`fsapi.gold.org`, API publique de ses graphiques) | fixing LBMA PM, USD/oz | 1970-01-01 | J−1 | 850 $ au 21/01/1980 ; 1 895 $ au 05/09/2011 : conformes. À requêter **par année** (une plage courte renvoie un autre prix, 7 jours sur 7). Avant 2019, les fériés londoniens sont remplis par la valeur précédente. |
| USD/JPY | FRED `DEXJPUS` (H.10, cours acheteur de midi à New York) + dates de publication ALFRED | `DEXJPUS` | 1971 | — | **FRED et ALFRED en maintenance à 17:20 UTC** (page « We'll be back soon », API comprise) |
| Calendrier du H.10 | federalreserve.gov | — | — | — | Le H.10 est **hebdomadaire** : dernière publication le lundi 19/10/2026 |

Sources écartées : LBMA (Cloudflare, 403), Stooq (défi JavaScript), Nasdaq Data Link (Incapsula,
403), Bundesbank (fixing de Francfort en DM, arrêté en 1998), `GC=F` (2000 seulement), `JPY=X`
(1996 seulement).

## 4. Hypothèses d'implémentation

**H1 — Calendrier.** La décision se prend à chaque séance de l'actif cible (dates Yahoo). Chaque
indicateur se calcule sur **ses propres séances** :
- SMA de l'or sur 200 fixings ;
- variation de USD/JPY sur 21 observations du H.10 ;
- T sur les séances du S&P 500.

Chaque indicateur prend ensuite sa dernière valeur connue à la clôture J. Le moteur tourne sur le
calendrier civil (§ 1).

**H2 — Détecteurs**, sur les clôtures :
- SMA_n vrai si clôture(J) > moyenne simple des n dernières clôtures, J comprise (n = 126, 168, 200, 210, 252). Égalité = faux.
- MOM126 vrai si clôture(J) / clôture(J−126) − 1 > 0.
- COUCHE1 :
  - V = VIX(J) > 25 ;
  - Y = USDJPY(k) / USDJPY(k−21) − 1 < −0,05, où k est la dernière observation **publiée** ;
  - T = SPX(J) < SMA200 du SPX(J) ;
  - G = or(f) > SMA200 de l'or(f), où f est le dernier fixing ;
  - liquidité si V ou Y → 0,25 ; sinon monétaire si T et G → 0,7 ; sinon expansion → 1,0.

  Égalités strictes partout, telles qu'écrites dans le prompt.

**H3 — Branchement sur le moteur.** Chaque état devient un score :
- vrai, ou expansion → +1 ;
- monétaire → 0 ;
- faux, ou liquidité → −1.

`moteur.exposition` avec `Mapping("paliers")` (seuils ±0,4, paliers 1,0 / 0,7 / 0,25 : les valeurs
par défaut de TI1) rend exactement les expositions du prompt. Les nulls mélangent ce score, comme
dans TI1.

**H4 — Point-in-time.**
- S&P 500, Nasdaq-100 : clôture du jour.
- VIX : clôture du jour. Elle tombe à 16:15 ET, 15 minutes après la clôture des actions. Même idéalisation « décidé à la clôture » que le moteur TI1. Signalé, non corrigé.
- Or : le fixing PM (15:00 Londres) précède la clôture de New York, donc il est utilisable le jour même.
- DEXJPUS : une observation publiée à la date V (ALFRED, première publication) sert à partir de la clôture de la **première séance strictement après V**. Le H.10 sort à 16:15 ET, après la clôture.
- Repli prévu par le prompt si ALFRED reste indisponible : décalage de 2 jours ouvrés US (fériés fédéraux), signalé dans le rapport. ⚠️ Le H.10 étant hebdomadaire, ce repli laisserait voir certaines valeurs de 1 à 5 jours avant leur publication réelle.

**H5 — Trous.** Une séance de l'actif cible sans valeur pour une série reçoit la dernière valeur
connue. Je compte, par série et par période : les séances comblées, et les trous de plus de 5
séances.

**H6 — Préchauffe.** Chaque détecteur doit être entièrement défini dès la première décision
(clôture du 31/12/1990 pour le labo, du 29/12/2023 pour l'informative), sinon arrêt. Tous
regardent au plus 252 séances en arrière : charger plus d'historique ne change aucun chiffre.

**H7 — Périodes.** Les dates sont les premier et dernier jours de rendement (convention TI1) :
- labo : V0 = clôture du 31/12/1990, rendements du 01/01/1991 au 31/12/2023 ;
- informative : du 01/01/2024 à la dernière séance commune au moment du calcul, figée et écrite dans le rapport.

**H8 — Moteur tel quel.**
- κ = 10 pb **par unité de |ΔE|** : un passage 1,0 → 0,25 coûte 7,5 pb.
- Pas de rémunération du cash (rf = 0).
- Pas de coût d'entrée.
- Indices **de prix**, dividendes exclus.
- Épisodes de baisse ≥ 20 % du buy and hold de la cible.
- Faux signal : passage en défensif (E ≤ 0,25) sans baisse de 10 % dans les 60 jours.
- Captures sur semaines civiles complètes.
- Décalage circulaire ≥ 90 jours civils.

**H9 — Témoin et portes.**
- Témoin : exposition constante égale à la moyenne de E sur la période, mêmes frais (`temoin_constant`).
- Porte 1 : p retenue (D4, Ulcer) < 0,05.
- Porte 2 : Ulcer < Ulcer du témoin.
- Porte 3 : Ulcer < Ulcer de SMA200, même actif, même période.
- Les portes ne jugent que la période labo.
- Les fenêtres de la bande (126, 168, 210, 252) n'ont pas de portes : elles sont « n/a » au tableau principal. Les afficher inviterait à choisir la meilleure fenêtre, ce que la règle 2 interdit.

**H10 — Verdict mécanique.**
- Un candidat (MOM126, COUCHE1) qui passe les 3 portes sur les 2 actifs est **retenu**.
- Si les deux passent, les deux sont déclarés retenus : le prompt ne prévoit pas de départage, et je n'en invente pas.
- Sinon, si SMA200 passe les portes 1 et 2 sur les 2 actifs → **SMA200 retenue**.
- Sinon → **aucun timing démontré**.

**H11 — Compteur.** Un run par couple (détecteur × actif) couvre les deux périodes : 14 runs.
Préenregistrement `T1A`, puis les 14 runs journalisés **avant le premier calcul**. Valeur attendue :
117 → 131.

**H12 — Graines.**
`nulls.flux(0, null, "<détecteur>:<actif>", période)`, même dérivation que TI1, clés propres à
chaque couple.

**H13 — Isolement.** Tout le nouveau code est neuf : `beta/marches/` (collecteur des vrais marchés),
`beta/temps1/` (labo), scripts et unités systemd à part. Rien ne change dans ce qui tourne :
- VC1 à VC6 ;
- `beta-maj` ;
- le lake et son catalogue ;
- les runs et les onglets existants.

Les news investingLive et FXStreet vont dans un service DS1 à part. `ds1-news` n'est pas redémarré.

## 5. Points bloquants

- **Aucun point bloquant définitif.** L'or est réglé par la décision de Jonas, le moteur se
  réutilise sans modification (§ 1) et le S&P 500, le Nasdaq-100 et le VIX couvrent la préchauffe.
- **Bloquant temporaire : FRED et ALFRED sont en maintenance.** DEXJPUS (valeurs et dates de
  publication) n'est pas téléchargeable pour l'instant. J'installe tout le reste et je réessaie.
  Aucune mesure ne part avant d'avoir DEXJPUS, et autant que possible avec ALFRED.

→ Je continue.
