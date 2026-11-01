# Temps 1 – complément ETH et SOL (T1C)

> Préenregistré le 01/11/2026, avant tout code de calcul et tout calcul. C'est l'étape C du prompt
> de Jonas du 01/11/2026 (« On lance le backtest V1 de VC6 »). Son résultat dit, pour VC6, si la
> poche ETH (puis SOL) suit sa propre SMA 200 ou celle du BTC. Ce test ne modifie ni les règles, ni
> les rapports, ni les verdicts de « Temps 1 – justesse » (T1J) et de « Temps 1 – fiabilité » (T1F).

---

## Prompt de Jonas (étape C, mot pour mot)

ÉTAPE C — « Temps 1 – complément ETH et SOL »
- Même code, même juge, même protocole que « Temps 1 – justesse » et « Temps 1 – fiabilité ».
- Seul changement : l'actif testé (ETH, puis SOL). Détecteur = SMA 200 de l'actif lui-même, sur clôtures journalières depuis le début disponible de chaque actif.
- Si le code du Temps 1 doit être modifié au-delà du changement d'actif, tu t'arrêtes et tu me montres la modification avant de la faire.
- Aucun essai ajouté au compteur (même configuration de détecteur, règle du 24/10).
- Retenu si p_justesse < 0,05. Sinon, l'actif suivra le régime de la SMA 200 du BTC.
- Sorties dans VC6_V1/temps1_complement_eth_sol/ : un tableau par actif (p_justesse, fiabilité, phases baissières couvertes, période) et une ligne de conclusion par actif.

---

## Applications, sans choix de Claude

Ce qui suit applique le prompt et les règles déjà figées de T1J et de T1F. Aucune règle nouvelle.

**1. Code.** Les modules de T1J (`beta/temps1_justesse/`, commit `8afdbe7`) et de T1F
(`beta/temps1_fiabilite/`, commit `590688e`) sont réutilisés sans modification. La campagne
vérifie octet pour octet qu'ils sont identiques à ces commits, sinon elle s'arrête. Le nouveau
module `beta/temps1_complement/` lit les clôtures d'ETH et de SOL, appelle ces fonctions et écrit le
rapport. Il n'appelle que celles-ci :
- de T1J : `juge.juger`, `juge.premier_trimestre`, `juge.sigma_sp_ref`, `detecteurs.sma` avec
  n = 200 (la fonction du détecteur SMA200), `mesures.mesurer` ;
- de T1F : `campagne.plage`, `campagne.tirages`, `campagne.resumer`, `campagne.diagnostic_f0`,
  `campagne.resume_f0`.

La lecture D4 passe par `resumer`, qui appelle `beta.invest.nulls.verdict`. Le code du Temps 1
n'a pas à être modifié.

**2. Données.** BETA et DS1 n'ont qu'une seule clôture journalière d'ETH et de SOL : celle du
perpétuel Binance USDT-M (inventaire de l'étape A, `VC6_V1/INVENTAIRE_DONNEES.md` : aucune série au
comptant).
- Début disponible : 27/11/2019 pour ETH, 14/09/2020 pour SOL.
- Lecture sur les copies figées de l'étape A, jusqu'au 31/10/2026 (date de fin figée). La campagne
  vérifie leur SHA-256 avant de lire :
  - `data/vc6_v1/sources_figees/ETH_perp_1d.parquet` (SHA-256 `19eec6a3c1882cfb484a54891c1dbf586ce519d50665b135d0c1153005cc172f`) ;
  - `data/vc6_v1/sources_figees/SOL_perp_1d.parquet` (SHA-256 `58e10ba349297c52ccf30ffc5364811c4ddf95d819c6bdefab078217d9d57c42`).
- Clôture du jour D = clôture de la bougie 1d ouverte le jour D à 00:00 UTC. C'est la convention du
  BTC de T1J (jour civil UTC clos). Calendrier 7 j / 7, sans comblement.

**3. Juge.** Le juge principal de T1J, inchangé :
- baisse de référence 20 % ;
- σ_actif(q) = écart-type des rendements log quotidiens des 2 années civiles avant le trimestre q,
  × √252 ;
- σ_S&P_ref = la constante de T1J. Elle est recalculée sur la copie figée des données de T1J
  (`tests/donnees/t1j_a3d6d80952500d57.parquet`, empreinte vérifiée) et doit égaler la valeur de la
  mesure de T1J, 0,18257135761750884. Sinon, arrêt ;
- le juge démarre au premier trimestre civil précédé de 2 ans de données, comme pour le BTC
  (décision 6 du 24/10) ;
- le dernier cycle, encore en cours, est exclu.

**4. Période.** Comme pour le BTC dans T1J (étape B) : du premier trimestre jugé à la dernière date,
le 31/10/2026. La période mesurée est M = [premier pivot du juge, dernier pivot[ (clarification B).
La colonne « période » donne le premier trimestre jugé et M, avec sa durée en années.

**5. Détecteur.** SMA 200 de l'actif lui-même : bear si la clôture est sous la moyenne des 200
dernières clôtures (jour compris), bull sinon.

**6. Mesures et test contre le hasard.** On reprend les mesures de T1J et les tests de T1F.
- Mesures observées (T1J) : médiane et pire cas de f_entrée, ratés, fausses alertes par an,
  justesse, médiane de f_sortie, bascules par an.
- Test 1, qui décide : 1 000 signaux aléatoires (graine 0) sur M. La suite des états est gardée ;
  les durées sont permutées entre épisodes du même état.
- Test 1 bis, rapporté : décalage circulaire de k séances, k uniforme dans [90, N − 90].
- p_justesse = part des tirages dont la justesse est ≥ celle observée.
- p_latence = part des tirages dont la médiane de f_entrée est ≤ celle observée.
- Lecture D4 : p < 0,05 réel ; 0,05 ≤ p < 0,20 non concluant ; sinon indistinguable du hasard.
- Test 2 de T1F (état au pic, f_entrée diagnostic) : rapporté.

**7. Règle de décision.** Par actif :
- **retenu si p_justesse du test 1 < 0,05**. La poche suit alors la SMA 200 de l'actif lui-même ;
- sinon, l'actif suivra le régime de la SMA 200 du BTC.

Le test 1 bis, p_latence et le test 2 sont rapportés et ne décident rien.

**8. Colonne « fiabilité ».** Elle donne p_latence du test 1 et sa lecture D4, avec les valeurs du
test 1 bis à côté. Le verdict de fiabilité de T1F porte sur p_latence et exige le témoin actions ET
l'or : il ne se transpose pas tel quel à un actif seul.

**9. Phases baissières couvertes.** Les bears complets du juge dans M (pic, creux, baisse). À part :
le bear en cours, exclu, et la date de début du juge. Les bears antérieurs à cette date ne sont pas
couverts.

**10. Indécidable.** On applique la règle de T1J. Pour un actif, une mesure peut être impossible :
aucun bear complet dans M, préchauffe insuffisante, signal indéfini, épreuve de causalité ratée.
Dans ce cas, cet actif n'a aucun verdict, le programme s'arrête et le rapport le dit. Ce n'est pas
le cas « sinon » de la règle 7 : la suite revient à Jonas.

**11. Épreuve de causalité (T1J).** On reprend chaque date de coupure de T1J postérieure au début de
l'actif. Le signal SMA 200, recalculé avec les seules données connues à cette date, doit égaler le
signal calculé sur tout l'historique.

**12. Compteur.** Aucun essai (même configuration de détecteur, règle du 24/10).
- T1C est journalisée dans `EXPERIMENTS.jsonl` avec `diagnostic=True`, famille invest.
- Aucun run n'est journalisé dans `RUNS.jsonl`.
- Compteurs attendus, inchangés : global 147, invest 54, trading 93.

**13. Non calculé.** Les variantes du juge de T1J (baisse de référence 15 % et 25 %, σ unique). Ce ne
sont pas des essais, et elles n'entrent pas dans la règle de décision du complément. Rien d'autre
n'est ajouté.

**14. Rapport.** Il est écrit par le programme, sans interprétation au-delà de la conclusion
mécanique : `VC6_V1/temps1_complement_eth_sol/RAPPORT_COMPLEMENT.md` et ses CSV. Il contient :
- un tableau par actif (p_justesse, fiabilité, phases baissières couvertes, période) ;
- une ligne de conclusion par actif ;
- puis les tableaux détaillés de T1J et de T1F.

**Déjà connu au moment du préenregistrement.**
- Les rapports de T1J et de T1F (24/10). La SMA 200 du BTC y a p_justesse = 0,007 (test 1) et
  0,048 (test 1 bis). Sur les quatre actifs de T1J (et le témoin), la SMA 200 a au test 1 un
  p_justesse compris entre 0,000 et 0,007, et un p_latence compris entre 0,708 et 0,986.
- Pour l'inventaire de l'étape A, ETH et SOL ont été lus en entier (début, fin, trous, hash),
  jusqu'à la clôture du 31/10/2026 (ETH 2 254,54 ; SOL 95,44).
- Aucun juge, aucune SMA et aucun tirage n'a été calculé sur ETH ou SOL.
