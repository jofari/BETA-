# PBO de la grille de la voie C (PBOC) — préenregistrement

> Préenregistré le 26/10/2026, **avant tout calcul** sur la graine 0, sur les graines 1001 à 1100 et sur les données de la voie C. Diagnostic, famille invest : **aucun essai ajouté au compteur**. Ce texte reprend mot pour mot la phase 3 du prompt de Jonas du 25/10/2026, ses réponses du 25/10 (21:16 UTC) et du 26/10, puis les lectures nécessaires pour le coder.

---

## 1. Phase 3 du prompt du 25/10/2026 (mot pour mot)

Écris d'abord `pbo_voie_c/PREENREGISTREMENT.md`, committe-le, affiche son hash, puis seulement calcule.

- **Méthode** : CSCV (Bailey, Borwein, López de Prado et Zhu).
- **Données** : rendements quotidiens de la grille de la voie C (`voie_c_optim.py`), du **20/06/2021 au 05/09/2026**. Les 8 jours les plus anciens (12/06 → 19/06/2021) sont retirés pour avoir des blocs égaux.
- **Blocs** : S = 16 blocs de 119 jours.
- **Dédoublonnage** : deux configurations sont des doublons si leurs rendements quotidiens sont identiques, ou proportionnels (même stratégie, seule la cible de volatilité change). On en garde une seule par groupe. Rapporte le nombre de configurations avant et après.
- **Métrique de classement** : Sharpe (il ne dépend pas de l'échelle, contrairement à l'Ulcer).
- **Lecture** : PBO proche de 0 = robuste ; proche de 50 % = hasard ; au-dessus de 50 % = surajustement.
- **Décision fixée avant** : PBO < 20 % → la voie C reste candidate ; sinon → la voie C est marquée « surajustée » dans `DECISIONS.md`.
- **Statut** : diagnostic, famille invest. Aucun essai ajouté au compteur.
- **Rappel** : ces données contiennent l'OOS de la grille et la partie du hold-out allant du 01/01/2025 au 05/09/2026, déjà vues. La PBO est un diagnostic de surajustement de la grille, pas une validation hors échantillon. Écris-le dans le préenregistrement.

**Rapport** écrit par le script : `pbo_voie_c/RAPPORT_PBO.md` avec hash du code, des données et du préenregistrement ; nombre de configurations avant et après dédoublonnage ; PBO ; distribution des rangs hors échantillon de la meilleure configuration ; verdict mécanique. Aucune interprétation au-delà du verdict.

## 2. Réponses de Jonas du 25/10/2026, 21:16 UTC (mot pour mot)

1. Dédoublonnage : option b. Une configuration par groupe où seule la cible de volatilité change (960 groupes). Cible gardée, fixée sans regarder les performances : 20 % (celle de la config figée et de VC2 à VC4) ; si 20 % n'est pas dans la grille, la valeur la plus proche de 20 %.
2. Fenêtre : ta lecture. Moteur parti du 12/06/2021 comme la grille, puis retrait des 8 premiers jours de l'évaluation (évaluation du 20/06/2021 au 05/09/2026, 16 blocs de 119 jours).
3. Seuil de 20 % : confirmé.

Avant la PBO de la voie C, deux contrôles :
- négatif : 960 configurations, mêmes dates, rendements tirés au hasard (graine 0). Attendu : PBO ≈ 50 %.
- positif : même grille aléatoire, une configuration reçoit un avantage constant (Sharpe annualisé ≈ 1). Attendu : PBO proche de 0.
Si un contrôle ne sort pas comme attendu, arrête-toi avant la voie C.

Écris ces décisions dans le préenregistrement, committe, affiche le hash, puis calcule.

## 3. Réponses de Jonas du 26/10/2026 (mot pour mot) — elles remplacent les contrôles du § 2

1. Contrôle positif : avantage de Sharpe annualisé 3 (√252) ajouté chaque jour à la colonne 0. Réussi si PBO ≤ 10 % sur la graine 0. Calcule aussi, à titre informatif (ne décide rien), la PBO avec un avantage de Sharpe 1, pour documenter la puissance du test.
2. Contrôle négatif : moyenne de la PBO sur 100 graines neuves (1001 à 1100). Réussi si la moyenne est entre 45 % et 55 %. Rapporte aussi la valeur de la graine 0 seule, sans qu'elle décide.
3. Les trois lectures sont confirmées : N(0, 1) indépendants, colonne 0, Sharpe annualisé en √252.

Puis préenregistrement, commit, hash, contrôles, et voie C seulement si les deux contrôles passent. Lance le calcul dans tmux.

## 4. Puissance du test (phrase demandée par Jonas le 26/10, mot pour mot)

« Avec 960 configurations sur 1 904 jours, la meilleure configuration au hasard atteint un Sharpe d'environ 1,65 en apprentissage. Une PBO élevée de la voie C ne prouvera donc pas l'absence d'avantage, seulement que la grille est trop grande pour le détecter. »

## 5. Règles telles que codées (`beta/pbo_voie_c/regles.py`, empreinte au registre)

**CSCV** (`beta/stats/cscv.py`, 16 tests dans `tests/test_cscv.py`, dont une comparaison avec un recalcul naïf) :
- matrice T × N, T = 1 904 jours coupés en 16 blocs **contigus** de 119 jours, dans l'ordre du temps ;
- les C(16, 8) = 12 870 combinaisons de 8 blocs servent d'apprentissage (IS), les 8 autres de test (OOS) ;
- Sharpe = moyenne / écart-type (ddof = 1) × √252, sans taux sans risque ;
- n* = la configuration au meilleur Sharpe IS ; w = rang OOS de n* / (N + 1), rang croissant (1 = pire) ; λ = ln(w / (1 − w)) ;
- PBO = part des combinaisons où λ ≤ 0 ;
- égalité de Sharpe IS : la première colonne dans l'ordre de la grille ; égalité OOS : rang moyen ;
- un écart-type nul ou non fini arrête le calcul (aucun chiffre).

**Contrôles**, calculés **avant** toute lecture des données de la voie C :
- grilles de 1 904 × 960 rendements N(0, 1) indépendants, `numpy.random.default_rng(graine).standard_normal((1904, 960))` ;
- **positif** : graine 0, colonne 0 + 3 / √252 chaque jour. **Réussi si PBO ≤ 10 %.** Informatif : même grille, colonne 0 + 1 / √252 ;
- **négatif** : graines 1001 à 1100 incluses (100 grilles), sans avantage. **Réussi si la moyenne des 100 PBO est comprise entre 45 % et 55 %, bornes incluses.** Rapporté : la graine 0 seule, sans avantage ;
- un contrôle raté : arrêt, la grille de la voie C n'est pas calculée, aucun verdict.

**Données de la voie C** :
- les rendements quotidiens **nets** de chaque configuration, produits par `voie_c_optim.evaluer()` lui-même (moteur `derouler_bande`, 5 bps, funding), sans rien recopier : le script remplace `derouler_bande` par une enveloppe qui garde sa sortie, configuration par configuration, puis jette les statistiques qu'`evaluer` calcule ;
- le moteur part du premier jour commun de la grille, qui doit être le 12/06/2021 ; l'évaluation garde le 20/06/2021 → 05/09/2026, qui doit faire 1 904 jours. Sinon, arrêt.

**Dédoublonnage** :
- option b : les configurations qui ne diffèrent que par la cible forment un groupe. La grille doit compter 5 760 configurations et 960 groupes de 6 cibles ; on garde la cible 20 %, qui est dans la grille (`CIBLES = (0,15 ; 0,20 ; 0,25 ; 0,30 ; 0,35 ; 0,45)`) ;
- puis, parmi les 960 représentants, ceux dont les 1 904 rendements quotidiens sont **identiques bit à bit** sont des doublons : on garde le premier dans l'ordre de la grille (`itertools.product` de `voie_c_optim`). Deux séries identiques ont le même Sharpe partout, le choix ne change donc aucun rang ;
- le rapport donne : 5 760 avant, 960 groupes, le nombre de doublons exacts retirés (avec leur liste), et le nombre après.

**Verdict mécanique** : PBO < 20 % → « la voie C reste candidate » ; PBO ≥ 20 % → « la voie C est marquée surajustée », ligne ajoutée dans `DECISIONS.md` après le rapport.

**Rapport** (`pbo_voie_c/RAPPORT_PBO.md` et `RESUME_DISCORD.md`, écrits par `beta/pbo_voie_c/rapport.py`) :
- empreintes du code (commit), des règles, de ce texte et de la matrice de la voie C ;
- chaque contrôle avec sa PBO et son issue ;
- pour la voie C : configurations avant et après, PBO, distribution de w et de λ (quantiles et déciles), Sharpe IS et OOS de n*, configurations le plus souvent choisies comme n*, verdict ;
- compteurs avant et après (inchangés).

## 6. Ce qui était déjà connu au moment de ce préenregistrement

- La grille de la voie C a été mesurée le 03/10 sur le train (5 760 configurations, Sharpe net train : médiane et maximum imprimés par `voie_c_optim`) et son OOS 2024-07-01 → 2026-09-05 a été imprimé pour la config retenue et la référence. Le hold-out du 01/01/2025 au 05/09/2026 est donc **déjà vu** : cette PBO est un diagnostic de surajustement de la grille, **pas une validation hors échantillon**.
- La PBO de cette grille n'a jamais été calculée ; aucun rendement de la grille n'a été relu depuis le 03/10.
- La simulation de conception du 25/10 (`/root/rapports/2026-10-25_pbo-voie-c-conception/`), graines 1 à 600 seulement, sans aucune donnée de la voie C : contrôle négatif, moyenne 49,1 % sur 600 graines ; contrôle positif, PBO médiane 0,0 % avec un avantage de Sharpe 3 (98 % des 50 graines ≤ 10 %) et 43,4 % avec un avantage de Sharpe 1. C'est sur cette base que Jonas a fixé les contrôles du § 3. Les graines 0 et 1001 à 1100 n'ont jamais été tirées.
