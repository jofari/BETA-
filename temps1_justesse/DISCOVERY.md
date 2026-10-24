# Temps 1 — test de justesse des détecteurs de régime — Phase 1 : découverte

Rédigé le 24/10/2026, **avant toute ligne de code du test** et avant tout calcul de détecteur,
de juge ou de mesure. Seules la collecte des données et des sondes de couverture ont tourné.
Je n'ai pas lu le rapport de T1A (règle 1 du prompt).

## 1. Données trouvées sur le VPS

Tout est lu par `beta/marches` (`collecte.lire(nom)`) : une seule porte, hors lake, hors Binance.

```
série      source                               début       fin         obs.    trous > 5 séances
SPX        Yahoo ^GSPC                          1927-12-30  2026-10-23  24 821  1 (03→15/03/1933)
NDX        Yahoo ^NDX (Nasdaq-100)              1985-10-01  2026-10-23  10 346  0
XAU_LBMA   fixing LBMA PM, World Gold Council   1970-01-01  2026-10-22  14 742  0
BTC_DS1    DS1 bougies_1d, Bitstamp BTC/USD     2011-08-18  2026-10-23   5 546  0 (7 j sur 7)
VIXCLS     FRED VIXCLS                          1990-01-02  2026-10-22   9 301  0
DEXJPUS    FRED DEXJPUS (H.10)                  1971-01-04  2026-10-16  13 984  1 (13→31/08/1971)
```

- Les deux trous sont hors de toute période utile (1933 et 1971).
- **Préchauffe de 252 séances avant le 01/01/1991** : SPX, NDX, or et DEXJPUS sont largement couverts. VIXCLS a 253 séances en 1990 : **c'est juste suffisant**.
- **Juge** : σ_actif(q) demande 2 ans avant chaque trimestre. C'est couvert pour SPX, NDX et l'or dès 1991T1. Pour le BTC, le juge démarre au **01/10/2013**, premier trimestre qui suit 2 ans d'historique (décision 6 de Jonas).

### Ce qui a été ajouté pour ce test (collecteurs seulement, décision 9)

- **DS1** (commit `47fe19f`, poussé et déployé) : table `bougies_1d` (migration 004), avec Bitstamp depuis le 18/08/2011 et Coinbase depuis le 20/07/2015, rangées côte à côte. Lot `ds1 bougies` lancé chaque jour à 00:15 UTC.
  - Contrôle croisé sur 4 114 jours communs : écart de clôture médian **0,03 %**, 90 jours au-delà de 1 %, maximum 6,1 %.
- **beta/marches** : deux séries neuves.
  - `VIXCLS` (FRED), que le prompt demande à la place de `^VIX` (Yahoo).
  - `BTC_DS1`, lue dans DS1 par `docker exec psql`, en lecture seule et sans mot de passe dans BETA.

### DEXJPUS et ALFRED

- **ALFRED est indisponible.** La colonne `publie_le` est vide sur toute la série, et l'accès sans clé n'est toujours pas établi (`sources.premieres_publications`).
- On applique donc **le repli du prompt** : la valeur du jour t devient utilisable 2 jours ouvrés US après t, jours fériés fédéraux compris. C'est signalé dans le rapport.

## 2. Décisions de Jonas du 24/10, reprises telles quelles

1. Le BTC vient de DS1 : Bitstamp, clôture du jour civil UTC.
2. Le test compte dans la famille **invest**.
3. **+9 essais** : 3 candidats (MOM126, C1_V1, C1_V2) × 3 actifs jugés (témoin actions, or, BTC). La bande SMA compte en essais informatifs.
4. Témoin actions : les épisodes SPX et NDX sont mis ensemble, et la majorité se prend sur l'ensemble. Toute autre mesure du témoin = moyenne des deux valeurs.
5. La couche 1 se calcule sur les séances US. Les autres jours, elle garde sa dernière valeur.
6. Le juge BTC démarre après 2 ans d'historique.
7. Épisodes neutres : **1 000 tirages par paire** détecteur × actif, graine 0.
8. Le σ de référence du S&P est celui de la période labo, aussi pour 2024 → fin et pour le BTC.
9. On modifie les collecteurs seulement. Le test vit dans `beta/temps1_justesse` et `temps1_justesse/`, et T1A n'est pas touché.

Le rapport est **écrit par le programme**, sans interprétation (demande de Jonas du 24/10).

## 3. Hypothèses d'implémentation (lecture littérale, sans choix de ma part)

- **Calendriers** : chaque actif jugé est mesuré sur SES séances (SPX et NDX : séances US ; or : jours de fixing à Londres ; BTC : 7 jours sur 7).
  - SMA et MOM se calculent sur les clôtures de l'actif jugé.
  - Chaque indicateur de la couche 1 se calcule sur ses propres observations (VIX, USD/JPY, SPX, or), puis prend sa dernière valeur connue à chaque séance US.
  - Le signal C1 d'une séance US vaut ensuite jusqu'à la séance US suivante, sur le calendrier de l'actif jugé.
- **SMA n** : moyenne des n dernières clôtures, celle du jour comprise. Pas de signal tant que n clôtures ne sont pas là, et la préchauffe le garantit.
- **σ63 et σ annualisé** : écart-type d'échantillon (ddof = 1), sur les 63 dernières valeurs, celle du jour comprise.
- **σ_actif(q)** : rendements log quotidiens des 2 années civiles avant le premier jour du trimestre, × √252 pour tous les actifs, BTC compris, comme `σ_jour = σ_actif / √252` du prompt.
- **Juge** : bear = jours [pic, creux[, bull = jours [creux, pic suivant[. Ce qui précède le premier pivot et le dernier cycle en cours est exclu de toutes les mesures, jours compris.
- **Fausses alertes et bascules par an** : le nombre d'années vaut (jours civils de la période) / 365,25. Un épisode du détecteur est coupé aux bornes de la période.
- **Règle 3, « majorité des épisodes »** : strictement plus de la moitié. À égalité d'épisode, le candidat n'est pas « plus faible ».

## 4. Ambiguïtés qui changent les chiffres : arrêt, décision de Jonas

Chacune a une proposition, mais **je n'en applique aucune sans réponse**.

**A. Les ratés dans la médiane de f_entrée.** Le prompt compte les ratés « à part ». Lu littéralement, la médiane ne porte que sur les bears détectés. Un détecteur qui rate 4 bears sur 5 mais en attrape un au sommet aurait alors une médiane de 0 et dominerait tout le monde.
- Proposition : **un raté compte f = 1** dans la médiane et le pire cas. Le nombre de ratés reste rapporté à part.

**B. Un bear à cheval sur deux périodes** (pic en 2023, creux en 2024, par exemple). Il faut décider à quelle période il appartient.
- Proposition : le juge tourne sur tout l'historique. Un épisode n'appartient à une période que si **son pic et son creux sont tous les deux dedans**. Les épisodes à cheval sont listés, et aucune mesure ne les utilise.

**C. Épisodes neutres, le prix de départ.** « |ln(P fin / P début)| ≤ σ_jour × √n » : si P début est la clôture du premier jour neutre, un épisode d'1 jour est toujours juste.
- Proposition : **P début = clôture de la veille du premier jour neutre**, P fin = clôture du dernier jour. Cela fait n rendements pour √n.

**D. Plusieurs candidats retenus.** La règle 2 (plus petite médiane) se lit par actif, et le témoin et l'or peuvent désigner deux gagnants différents.
- Proposition : la règle 2 s'applique sur la **moyenne des médianes témoin et or**. À égalité, c'est le meilleur pire cas moyen qui l'emporte. La domination (règle 1) se juge entre SMA200, MOM126, C1_V1 et C1_V2, la bande restant informative (décision 3).

**E. DEXJPUS au repli = risque de donnée future.** Le H.10 paraît **une fois par semaine**, le lundi, pour la semaine écoulée. Avec un décalage de 2 jours ouvrés, Y lit une valeur 1 à 5 jours avant sa vraie parution, ce que la règle 4 interdit.
- Proposition : tenir compte du calendrier de parution. La valeur de la semaine S devient utilisable **à la clôture du premier jour ouvré qui suit la fin de S + 1 jour ouvré**, c'est-à-dire le mardi. C'est plus prudent que le repli. Sinon, garder le repli du prompt et le signaler.

**F. Le compte des essais informatifs.**
- Proposition : bande SMA (4 × 3 actifs = 12) + variantes du juge (3 × 8 détecteurs × 3 actifs = 72) = **84 essais informatifs**, notés sur une ligne à part et sans effet sur aucun compteur.

## 5. Compteur

- Famille invest : **38 aujourd'hui**, et pas 117. Le prompt reprend la valeur du préenregistrement du 22/10, mais T1A l'a fait passer à 131 le 21/10, puis les compteurs ont été séparés le 23/10.
- Avant le premier run : **+9**, soit **38 → 47**.
