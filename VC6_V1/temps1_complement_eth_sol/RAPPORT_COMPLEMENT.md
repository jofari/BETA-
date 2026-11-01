# Temps 1 – complément ETH et SOL (T1C)

Calculé le 2026-11-01T17:19:40+00:00 UTC. Rapport écrit par `scripts/temps1_complement.py`, sans interprétation au-delà de la conclusion mécanique. Les verdicts de T1J et de T1F ne sont pas modifiés. Préenregistrement : `PREENREGISTREMENT.md` (même dossier).

## 1. Résultat par actif

Retenu si p_justesse du test 1 < 0,05 (règle 7 du préenregistrement) ; sinon, l'actif suivra le régime de la SMA 200 du BTC. p_latence et le test 1 bis sont rapportés : ils ne décident rien.

### ETH

| p_justesse | fiabilité | phases baissières couvertes | période |
|---|---|---|---|
| 0,313 (test 1, indistinguable du hasard) | p_latence 0,637 (test 1, indistinguable du hasard) ; test 1 bis : p_justesse 0,491 (indistinguable du hasard), p_latence 0,694 (indistinguable du hasard) | 2 bear(s) complet(s) dans la période mesurée : 2022-01-02 → 2022-06-18 (−74,0 %) ; 2024-03-11 → 2025-04-08 (−63,8 %). Bear en cours depuis le 2025-08-22 (−53,3 % au 2026-10-31), exclu. Rien n'est jugé avant le 2022-01-01 | période mesurée 2022-01-02 → 2025-08-22 (3,6 ans) ; juge depuis le 2022-01-01 ; données 2019-11-27 → 2026-10-31 |

**Conclusion ETH : non retenu** (p_justesse 0,313 ≥ 0,05) : ETH suivra le régime de la SMA 200 du BTC.

### SOL

| p_justesse | fiabilité | phases baissières couvertes | période |
|---|---|---|---|
| — | — | 0 bear(s) complet(s) dans la période mesurée. Bear en cours depuis le 2025-01-18 (−63,6 % au 2026-10-31), exclu. Rien n'est jugé avant le 2022-10-01 | juge depuis le 2022-10-01 ; données 2020-09-14 → 2026-10-31 |

**Conclusion SOL : indécidable** (aucun bear complet du juge entre 2022-10-01 et 2026-10-31). Aucun verdict pour cet actif : arrêt, la suite revient à Jonas.

## 2. Empreintes et données

- **Code** : `54092e7`. Modules de T1J (commit `8afdbe7`) et de T1F (commit `590688e`) réutilisés, vérifiés identiques octet pour octet.
- **Règles** : `56f2183129b16e66` ; préenregistrement `PREENREGISTREMENT.md` `de688a640c05caf9` ; règles de T1J `c0959f429d9dcf8f`, de T1F `77b7f85b49132d77` ; registre : `EXPERIMENTS.jsonl`, id `T1C`, diagnostic.
- **σ_S&P_ref** (juge de T1J) : 18,3 % (0.18257135761750884), recalculé sur la copie figée de T1J et égal à la valeur de sa mesure.
- **Compteur** (aucun essai) : global 147 → 147, invest 54 → 54, trading actif 93 → 93.
- **Tirages** : 1000 par actif et par test, graine 0.
- **Empreinte des clôtures lues** : `04a0c7a84b4094ae` ; date de fin figée : 2026-10-31.

| actif | série | copie figée | SHA-256 vérifié | début | fin | clôtures | jours manquants |
|---|---|---|---|---|---|---|---|
| ETH | perpetuel Binance USDT-M ETH, bougie 1d (lake BETA) | `data/vc6_v1/sources_figees/ETH_perp_1d.parquet` | `19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f` | 2019-11-27 | 2026-10-31 | 2531 | 0 |
| SOL | perpetuel Binance USDT-M SOL, bougie 1d (lake BETA) | `data/vc6_v1/sources_figees/SOL_perp_1d.parquet` | `58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42` | 2020-09-14 | 2026-10-31 | 2239 | 0 |

## 3. Les bears du juge

Juge principal de T1J : baisse de référence 20 %, σ de l'actif sur les 2 années civiles avant chaque trimestre (× √252), σ_S&P_ref constante. Il démarre au premier trimestre précédé de 2 ans de données. Un bear n'est mesuré que si ses deux bornes sont dans la période mesurée [premier pivot, dernier pivot[.

### ETH

Juge à partir du 2022-01-01 ; θ_baisse de 43,5 % à 66,5 %, θ_hausse de 76,8 % à 198,3 %.
Dernier pivot : pic du 2025-08-22 ; le cycle qui suit est en cours, exclu.

| pic | creux | baisse | dans la période mesurée |
|---|---|---|---|
| 2022-01-02 | 2022-06-18 | −74,0 % | oui |
| 2024-03-11 | 2025-04-08 | −63,8 % | oui |

Bear en cours depuis le pic du 2025-08-22 (−53,3 % à la dernière date), exclu.

### SOL

Juge à partir du 2022-10-01 ; θ_baisse de 54,2 % à 78,4 %, θ_hausse de 118,6 % à 362,1 %.
Dernier pivot : pic du 2025-01-18 ; le cycle qui suit est en cours, exclu.

*Aucun bear complet.*

Bear en cours depuis le pic du 2025-01-18 (−63,6 % à la dernière date), exclu.

## 4. Mesures observées de la SMA 200 (fonctions de T1J)

f_entrée : 0 = bascule bear au pic, 1 = au creux ; un raté compte 1. f_sortie : 0 = bascule bull au creux, 1 = au pic suivant ; un raté compte 1.

| actif | médiane f_entrée | pire cas | ratés / bears | fausses alertes / an | justesse | médiane f_sortie | bascules / an | ratés de sortie / bulls |
|---|---|---|---|---|---|---|---|---|
| ETH | 0,27 | 0,39 | 0 / 2 | 1,10 | 0,56 | 0,25 | 5,50 | 0 / 2 |
| SOL | — | — | — | — | — | — | — | — |

### ETH — entrées

| pic | creux | baisse | f_entrée | bascule bear | retard |
|---|---|---|---|---|---|
| 2022-01-02 | 2022-06-18 | −74,0 % | 0,15 | 2022-01-06 | 4 j |
| 2024-03-11 | 2025-04-08 | −63,8 % | 0,39 | 2024-07-04 | 115 j |

### ETH — sorties

| creux | pic suivant | f_sortie | bascule bull |
|---|---|---|---|
| 2022-06-18 | 2024-03-11 | 0,14 | 2023-01-12 |
| 2025-04-08 | 2025-08-22 | 0,36 | 2025-06-09 |

## 5. Tests contre le hasard de même agitation (fonctions de T1F)

Test 1 (décide) : la suite des états est gardée, les durées sont permutées entre épisodes du même état. Test 1 bis (rapporté) : décalage circulaire dans [90, N − 90]. p_latence = part des tirages de médiane f_entrée ≤ observée ; p_justesse = part des tirages de justesse ≥ observée. Lecture D4 : p < 0,05 réel ; 0,05 ≤ p < 0,20 non concluant ; p ≥ 0,20 indistinguable du hasard.

| actif | test | f_entrée observée | f_entrée aléatoire, médiane [5 % ; 95 %] | p_latence | justesse observée | justesse aléatoire, médiane [5 % ; 95 %] | p_justesse | lecture D4 (latence / justesse) | fausses alertes / an : observées, aléatoires (médiane) |
|---|---|---|---|---|---|---|---|---|---|
| ETH | 1 | 0,27 | 0,19 [0,01 ; 0,55] | 0,637 | 0,56 | 0,49 [0,27 ; 0,71] | 0,313 | indistinguable du hasard / indistinguable du hasard | 1,10 ; 1,38 |
| ETH | 1 bis | 0,27 | 0,16 [0,00 ; 0,50] | 0,694 | 0,56 | 0,52 [0,28 ; 0,70] | 0,491 | indistinguable du hasard / indistinguable du hasard | 1,10 ; 1,38 |

Plages des tirages (périodes mesurées) : ETH 2022-01-02 → 2025-08-22 (1328 séances).

## 6. Test 2 — diagnostic des f = 0 (rapporté, ne décide rien)

État de la SMA 200 au jour du pic de chaque bear du juge. La f_entrée diagnostic ignore les épisodes bear commencés plus de 21 séances avant le pic (raté = 1). Cette variante n'est pas une règle.

| actif | pic | creux | en bear au pic | f_entrée | f diagnostic |
|---|---|---|---|---|---|
| ETH | 2022-01-02 | 2022-06-18 | non | 0,15 | 0,15 |
| ETH | 2024-03-11 | 2025-04-08 | non | 0,39 | 0,39 |

## 7. Épreuve de causalité

SMA 200 recalculée avec les seules clôtures connues à chaque date de coupure de T1J postérieure au début de l'actif, comparée au signal calculé sur tout l'historique.
- ETH : aucun écart.
- SOL : aucun écart.

## 8. Écarts au prompt et leurs raisons

- **Données** : ETH et SOL n'ont, dans BETA et DS1, qu'une clôture journalière : celle du perpétuel Binance USDT-M (inventaire de l'étape A). « Début disponible » = la cotation du perpétuel. Le BTC de T1J était jugé au comptant (Bitstamp).
- **Fiabilité** : p_latence et sa lecture D4, par actif. Le verdict de fiabilité de T1F (témoin actions ET or) ne se transpose pas à un actif seul (application 8).
- **Variantes du juge** (15 %, 25 %, σ unique) : non calculées (application 13).
- **Annualisation** : celle des règles figées de T1J (√252), y compris pour des actifs cotés 7 j / 7, comme le BTC de T1J.
