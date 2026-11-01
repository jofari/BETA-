# Contrôle HAR — préenregistrement

- **Figé le** : 01/11/2026 (UTC). C'est avant tout code de calcul du Contrôle HAR, et avant tout calcul de RV 5 min, de HAR ou de QLIKE sur BTC, ETH ou SOL.
- **Source** : prompt de Jonas du 01/11/2026 (« GO phase 2 : « Contrôle HAR » »). Il est recopié mot pour mot entre les marqueurs `=== PROMPT CONTRÔLE HAR ===` et `=== FIN PROMPT ===`.
- **Spec** : `VC6_V1/spec_figee.md` et son addendum du 01/11/2026. La spec y définit σ̂i : « volatilité prévue retenue au « Contrôle HAR », annualisée en √365 ».
- **Statut** : test de mesure. Il est journalisé dans `EXPERIMENTS.jsonl` avec `diagnostic=True`, famille invest. Le compteur ne bouge pas : « aucun essai ajouté au compteur ».
- **Données** : copies figées de l'étape A, au 31/10/2026. Leur SHA-256 est vérifié avant toute lecture (table en fin de document).

=== PROMPT CONTRÔLE HAR ===
GO phase 2 : « Contrôle HAR ». Relis VC6_V1/spec_figee.md.
Test de mesure : aucun essai ajouté au compteur.

Pour chaque actif (BTC, ETH, SOL) :

1. Volatilité réalisée journalière : RV = somme des rendements log 5 min au carré, par jour UTC.
   Un jour où plus de 10 % des barres 5 min manquent est exclu de l'évaluation et compté. Tu ne combles aucun trou.

2. Modèle HAR :
   - cible = RV moyenne des 5 jours suivants ;
   - régresseurs = RV du jour, RV moyenne sur 5 jours, RV moyenne sur 22 jours ;
   - moindres carrés (MCO), fenêtre glissante de 730 jours, réestimée chaque jour avec les données ≤ t uniquement.
   Avant 730 jours de RV : écart-type 30 jours à la place.
   Prévision ≤ 0 : écart-type 30 jours ce jour-là, et tu comptes ces cas.

3. Référence : écart-type 30 jours des rendements log journaliers, à la même échelle (variance journalière).

4. Critère : perte QLIKE moyenne sur la variance réalisée des 5 jours suivants.
   - QLIKE = RV/h − ln(RV/h) − 1.
   - Évaluation uniquement sur les jours où HAR dispose de ses 730 jours.
   - Test de Diebold-Mariano, pour information seulement.

5. Règle : si HAR a une QLIKE moyenne plus haute que l'écart-type 30 jours pour un actif, σ̂ de cet actif = écart-type 30 jours.

Sorties dans VC6_V1/controle_har/ :
- tableau par actif : QLIKE HAR, QLIKE écart-type 30 jours, p de Diebold-Mariano, jours évalués, jours exclus, prévisions ≤ 0 remplacées ;
- σ̂ retenu par actif, ajouté en addendum daté à spec_figee.md.

STOP. Tu me rends le tableau et tu attends mon GO.
=== FIN PROMPT ===

## Applications, sans choix de Claude

Le prompt ne dit pas tout mot pour mot. Chaque point ci-dessous l'applique de la seule façon cohérente avec son texte, avec la spec ou avec un usage déjà écrit dans BETA, et dit d'où il vient.

1. **Données.**
   - Bougies 5 min : copies figées `BTC_perp_5m`, `ETH_perp_5m` et `SOL_perp_5m` de l'étape A. Ce sont les perpétuels Binance USDT-M, seules bougies 5 min de BETA et de DS1.
   - Rendements journaliers : clôtures des copies figées `BTC_perp_1d`, `ETH_perp_1d` et `SOL_perp_1d`.
     - C'est le même instrument que les bougies 5 min, donc la même échelle que la RV.
     - Pour ETH et SOL, c'est aussi le point 2 de l'addendum du 01/11.
     - Pour le BTC, la série du mode global (Bitstamp ou perpétuel) reste une question ouverte de la phase 3. Elle ne touche pas ce contrôle.
   - La clôture du jour D est celle de la bougie 1d ouverte en D à 00:00 UTC. Le programme vérifie qu'elle est égale à la clôture de la dernière bougie 5 min de D, celle de 23:55.
   - Fin des données : 31/10/2026 (étape A).
2. **Jour UTC et rendements 5 min.**
   - Le jour D compte les barres ouvertes de D 00:00 à D 23:55 UTC, soit 288 attendues.
   - Le rendement log d'une barre est ln(clôture / clôture de la barre précédente). Il n'existe que si la barre précédente est ouverte exactement 5 min avant. La première barre de D se rapporte donc à la dernière barre de D − 1, et aucun rendement ne franchit un trou.
   - RV_D = somme des carrés des rendements des barres de D.
3. **Jour exclu.**
   - Barres manquantes de D = 288 − barres présentes. D est exclu si elles dépassent 10 % de 288, donc à partir de 29 barres manquantes.
   - Un jour exclu n'a pas de RV. Il n'entre ni dans un régresseur, ni dans une cible, ni dans l'évaluation, ni dans le décompte des 730 jours. Aucune moyenne qui le contiendrait n'est formée (« tu ne combles aucun trou »).
   - Les barres plates à volume nul (arrêts de Binance, inventaire de l'étape A) sont des barres présentes. Elles sont comptées et rapportées, rien de plus.
4. **Modèle HAR.**
   - Régression MCO de la cible y_t = moyenne(RV_{t+1}, …, RV_{t+5}) sur quatre termes : une constante, RV_t, la moyenne de RV_{t−4} à RV_t, la moyenne de RV_{t−21} à RV_t.
   - Tout est en niveau, en variance journalière.
   - La constante vient du modèle HAR de Corsi (2009). Le HAR de recherche de BETA en a aussi une (`beta/strategies/voie_c6_indicateurs.har_rv`, 16-20/10).
5. **Fenêtre glissante de 730 jours.**
   - À la date t, les MCO n'utilisent que les RV des 730 derniers jours qui ont une RV, jusqu'à t inclus.
   - Les lignes retenues sont celles dont les trois régresseurs et la cible sont entièrement dans cette fenêtre : 704 lignes au plus, s de t − 708 à t − 5.
   - La prévision de t applique les coefficients aux régresseurs de t.
   - Raison : c'est la seule lecture où « fenêtre glissante de 730 jours » et « avant 730 jours de RV » désignent la même chose. Le HAR existe dès que la fenêtre est pleine.
6. **Replis.**
   - Avant 730 jours de RV, la prévision est celle de l'écart-type 30 jours du même jour. Il en va de même les jours où la prévision HAR est ≤ 0.
   - Les prévisions ≤ 0 sont comptées sur les jours évalués, et aussi sur tous les jours où le HAR est estimé.
7. **Écart-type 30 jours.**
   - C'est l'écart-type d'échantillon des 30 derniers rendements log journaliers jusqu'à t inclus (ddof = 1, autour de la moyenne), au carré. On obtient une variance journalière, comme la RV.
   - ddof = 1 est la convention de pandas, et celle de la référence R30 de `beta/strategies/voie_c6_vol.py`.
8. **QLIKE.**
   - À la date t, RV = moyenne des RV de t+1 à t+5 (la cible du HAR), et h = prévision faite à t.
   - Les jours évalués sont ceux où le HAR a ses 730 jours de RV et où la cible est complète : t + 5 ≤ 31/10/2026, et aucun jour exclu de t+1 à t+5.
   - Les deux modèles sont évalués sur exactement les mêmes jours. La QLIKE moyenne est la moyenne arithmétique sur ces jours.
9. **Diebold-Mariano, pour information.**
   - d_t = QLIKE HAR − QLIKE écart-type 30 jours, sur les jours évalués.
   - Variance de long terme de Newey-West : noyau de Bartlett, retard int(4 · (n/100)^(2/9)). Ce retard dépasse les 4 jours de recouvrement des cibles dès que n ≥ 100.
   - Statistique normale, p bilatérale. C'est la même formule que `beta/strategies/voie_c6_vol.diebold_mariano` (16-20/10).
   - Le test ne décide rien.
10. **Règle 5.**
    - σ̂ = écart-type 30 jours si la QLIKE moyenne du HAR est strictement plus haute que celle de l'écart-type 30 jours. Sinon σ̂ = HAR, avec ses replis (point 6).
    - L'annualisation en √365 de la spec s'applique en phase 3.
11. **Épreuve de causalité** (invariant 7 de BETA).
    - Les prévisions du HAR et de l'écart-type 30 jours sont recalculées avec les seules données connues à chaque 31/12, de 2021 à 2025.
    - Elles doivent être identiques à celles calculées sur tout l'historique. Un écart arrête la campagne, et aucun chiffre ne sort.
12. **Compteur.** `diagnostic=True`, famille invest. Le prompt dit « aucun essai ajouté au compteur ».
13. **Noms.** « Contrôle HAR » et les noms du Temps 1 sont écrits en entier dans les fichiers et rapports (addendum du 01/11).
14. **Sorties.**
    - Dans `VC6_V1/controle_har/` : `RAPPORT_CONTROLE_HAR.md`, `RAPPORT_CONTROLE_HAR.csv` et `RESUME_DISCORD.md`.
    - La synthèse JSON va dans `data/controle_har/`.
    - L'addendum « σ̂ retenu » est écrit par le programme à partir de la synthèse, puis ajouté à `spec_figee.md`.
15. **Rien d'autre.** Ni comblement, ni plancher, ni troncature des valeurs extrêmes, ni autre modèle, ni autre fenêtre.

## Signalé, non tranché (sans effet sur le calcul)

- **PBO (invariant 13).**
  - Choisir, pour chaque actif, entre le HAR et l'écart-type 30 jours, c'est choisir entre deux prévisions.
  - Le prompt règle ce choix par sa règle 5, sans PBO, et en fait un test de mesure.
  - La PBO de S10 se calcule sur des rendements (Sharpe, par CSCV), pas sur une perte de prévision.
  - `n_configurations` n'est donc pas déclaré, et aucune PBO n'est calculée. Jonas tranche s'il en veut une.
- **Série BTC de la phase 3** (Bitstamp ou perpétuel) : toujours ouverte. Elle est sans effet ici (application 1).

## Déjà connu au moment du gel

- **Inventaire de l'étape A** : bougies 5 min et clôtures lues en entier (début, fin, barres manquantes, hash). Aucune RV 5 min, aucun HAR et aucune QLIKE n'ont été calculés sur ces copies.
- **Recherche du 16/10/2026, non préenregistrée** (`beta/strategies/voie_c6_vol.py`).
  - On a regardé un HAR **différent** :
    - RV journalière de Garman-Klass tirée de l'OHLC 1d, pas des bougies 5 min ;
    - horizon d'un jour ;
    - fenêtre de 250 jours.
  - Il était comparé à l'écart-type 30 jours (R30) sur 837 jours, de mi-2024 à octobre 2026.
  - QLIKE contre la RV de Garman-Klass :
    - BTC : HAR 0,608, R30 0,614 ;
    - ETH : HAR 0,684, R30 0,637 ;
    - SOL : HAR 0,604, R30 0,546.
  - Contre r² clôture-clôture, le HAR était moins bon que R30 sur les trois actifs.
  - Ces chiffres ont été vus. Ils ne portent pas sur la mesure figée ici.
- **Fiches de recherche des 14 et 19/10** (`/root/rapports/`) : pronostic tiré de la littérature, non vérifié, selon lequel un HAR-RV battrait l'écart-type 30 jours.

## Données lues : copies figées de l'étape A

Dossier `data/vc6_v1/sources_figees/`, hors git comme tout `data/`.

| actif | bougies 5 min | SHA-256 | clôtures journalières | SHA-256 |
|---|---|---|---|---|
| BTC | `BTC_perp_5m.parquet` | `42e62509f051ece9fd86f2a19848e36d53b88b0661243b9aae91320e4caf3618` | `BTC_perp_1d.parquet` | `1bd26426c4cf103bb4b19766aa0a67cefbfe18d9532fe0997592935cab25cb93` |
| ETH | `ETH_perp_5m.parquet` | `5e1a62bff2d7a21e2971e321d03e789d074a814c3f329c327e9af7c2ce7a592f` | `ETH_perp_1d.parquet` | `19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f` |
| SOL | `SOL_perp_5m.parquet` | `0771ad9ed20d60bc1b5e17d16e384fda03f2b2ec447656e938c182923f4fe75d` | `SOL_perp_1d.parquet` | `58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42` |
