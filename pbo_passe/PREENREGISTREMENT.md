# PBO du passé (PBOR) — préenregistrement

> Préenregistré le 26/10/2026, **avant tout calcul de PBO** sur les lots et les variantes ci-dessous. Diagnostic : **aucun essai ajouté au compteur, aucun verdict modifié**. Ce texte reprend mot pour mot la demande de Jonas du 26/10/2026 et ses réponses du soir, puis les règles telles que codées.

---

## 1. Demande de Jonas (26/10/2026, 10:13 UTC, mot pour mot)

« intègre le pbo de facon systematique et lance le dans ta sesiosn tmux »

## 2. Réponses de Jonas (26/10/2026 au soir) : options choisies, avec le texte qu'il avait sous les yeux

1. **« Porte obligatoire »** : « S10 devient la 10e porte. Une candidate n'est confirmée que si elle passe aussi S10. Si la PBO ne peut pas se calculer (historique trop court, candidate sans aucun trade sur une moitié), S10 compte « non exécutée » : la candidate reste indécidable, comme pour les 9 autres portes. Côté invest, tout préenregistrement qui choisit un réglage parmi plusieurs inclut la même PBO. »
2. **« PBO < 20 % »** : « Le seuil que tu as fixé pour la voie C le 25/10. »
3. **« Recalculer le passé »** : « PBO des 3 lots de trading de septembre (à partir des courbes déjà enregistrées, sans relancer de backtest) et des variantes de la voie C du 22/09. Préenregistré avant calcul comme PBOC, compteur inchangé, rapport seul : aucun verdict déjà rendu n'est modifié. »
4. Période des variantes de la voie C du 22/09 — **« Comme PBOC »** : « Du premier jour où les 6 variantes existent jusqu'au 05/09/2026, fin de la fenêtre de PBOC. Contient l'OOS et une partie du hold-out, déjà vus : diagnostic, pas validation. Les jours les plus anciens sont retirés pour avoir 16 blocs égaux. »
5. Lots de trading — question posée : « le rendement quotidien d'une candidate est la somme des R des trades clôturés ce jour-là (0 les jours sans clôture). Je ne prends pas la variation en % de l'equity : elle est à risque fixe, sans composition, et passe sous zéro chez les candidates très perdantes (R10 disjonction : −234 R), où un % n'a plus de sens. Sur quelle période ? » — **« Clôtures du lot »** : « Du premier au dernier jour où une candidate du lot clôture un trade. Les jours les plus anciens sont retirés pour avoir 16 blocs égaux, comme PBOC. »

La porte S10 est branchée dans la batterie au commit `3428cb8` (`DECISIONS.md` § 2026-10-26).

## 3. Règles telles que codées (`beta/pbo_passe/regles.py`, empreinte au registre)

**Méthode** : celle de la porte S10, `beta.stats.pbo.calculer` (CSCV de `beta.stats.cscv`, le code de PBOC) :
- matrice jours × configurations, les jours les plus **anciens** retirés pour que T soit un multiple de S = 16, blocs **contigus** ;
- les C(16, 8) = 12 870 combinaisons de 8 blocs servent d'apprentissage (IS), les 8 autres de test (OOS) ;
- Sharpe = moyenne / écart-type (ddof = 1) × √252, sans taux sans risque ; n* = meilleur Sharpe IS ; w = rang OOS de n* / (N + 1) ; PBO = part des combinaisons où w ≤ 1/2 ;
- doublons exacts (rendements identiques bit à bit) : on garde le premier dans l'ordre des colonnes ;
- **incalculable** (moins d'un jour par bloc, moins de 2 configurations distinctes, écart-type nul sur une moitié) : aucun chiffre, lecture « S10 non exécutée » ;
- **lecture** : PBO < 20 % → « la porte S10 aurait été franchie » ; PBO ≥ 20 % → « la porte S10 aurait échoué ».

**Les 3 lots de `cribler()` de septembre** (les seuls lots enregistrés dont le reality check S7 a tourné ; chacun vérifié par l'univers de son S7) :

| Lot | Lancé le | N figé | Candidates (run) |
|---|---|---|---|
| L1 | 08/09/2026 | 45 | r10_conjonction (`c8a374a40a87`), r10_disjonction (`274eb02a15ee`) |
| L2 | 19/09/2026 | 57 | liquidity_ny_stop_050 (`36ed58e66266`), _100 (`96d03113b579`), _150 (`52423a324274`) |
| L3 | 19/09/2026 | 62 | auto_r7_01 (`2ce411b82067`), auto_r7_03 (`f57f95588500`), mean_reversion_z (`7eb7f9c2cb17`), r10_conjonction (`f76121140b7c`), r10_disjonction (`21acf3928232`), r11_credit_contrarian (`b3b0374c238e`), r4_fear_greed_contrarian (`f2217235b2ed`), r9_funding_contrarian (`58a1b966537e`) |

- Données : `data/runs/<run>/trades.parquet` tel qu'enregistré (la séquence de trades dont la courbe d'equity du run est tirée), **empreintes SHA-256 figées** dans `regles.EMPREINTES_TRADES`, relevées le 26/10 avant tout calcul. Un fichier différent arrête la campagne.
- Contrôle de chaque run : `verdict.json` doit porter la même candidate, la même date de lancement et le même N, et l'univers de S7 (`batterie.json`) doit avoir la taille du lot. Sinon, arrêt.
- Rendement quotidien : somme des R des trades clôturés chaque jour UTC, 0 sans clôture ; période : du premier au dernier jour de clôture du lot ; colonnes dans l'ordre des noms.

**Les 6 variantes de la voie C du 22/09** : `vt 25 % / 45 % / 70 %` × fenêtre de vol `30 j / 60 j`, rééquilibrage quotidien, levier borné [0,33 ; 2], 5 bps, funding — les variantes parmi lesquelles `voie_c_voltarget.main()` choisit sur le Sharpe net du train (jusqu'au 30/06/2024). Ces briques viennent des scripts du 22-24/09 archivés dans `archives/arit_funding/`, repris dans `voie_c_voltarget.py` le 25/09 (`f674686`, `DECISIONS.md` § 2026-10-25).
- Code : `voie_c_voltarget.preparer(fin="2026-09-05")` puis `variantes_selection()`. Ces deux fonctions sont extraites de `main()` le 26/10, qui les appelle désormais lui-même. La sortie imprimée de `main()` est **identique à l'octet près** avant et après l'extraction (22 917 octets, SHA-256 `0eda4915269b12a4`), comparée par le programme sans être lue.
- Rendement : `r_net` quotidien ; période : du premier jour où les 6 variantes existent (le `depart` de `main()`) au 05/09/2026, rien n'étant lu au-delà ; doit finir exactement le 05/09/2026, sinon arrêt.
- Rapportée sans rien décider : la variante retenue par la règle de `main()` (meilleur Sharpe net du train, la première en cas d'égalité), recalculée par le programme sur ces mêmes rendements.

**Rapport** (`pbo_passe/RAPPORT_PBO.md` et `RESUME_DISCORD.md`, écrits par `beta/pbo_passe/rapport.py`) : empreintes du code, des règles, de ce texte et de chaque matrice ; pour chaque lot, les candidates, leur run, leur verdict rendu (inchangé), leur nombre de trades et la meilleure selon S7 ; pour chaque lot et pour la voie C : période, jours retirés, jours par bloc, configurations avant et après doublons, PBO, quantiles de w, part des combinaisons où chaque configuration est n*, lecture S10 ; compteurs avant et après (inchangés). Aucune interprétation au-delà de la lecture.

**Statut** : diagnostic (`diagnostic=True`), journalisé en famille trading (sans effet sur aucun compteur). Aucune ligne `DECISIONS.md` n'est prévue, quel que soit le résultat.

## 4. Lectures nécessaires pour le coder (signalées, pas décidées par Jonas)

- « À partir des courbes déjà enregistrées » : les courbes d'equity enregistrées sont tirées des trades enregistrés (`trades.parquet`), et la réponse 5 définit le rendement quotidien par les R clôturés. On lit donc les trades, pas `equity.parquet`.
- Aucun contrôle positif ou négatif propre à PBOR : ils n'ont pas été demandés. Le code CSCV est inchangé depuis PBOC (`beta/stats/cscv.py`), dont les contrôles ont réussi le 26/10 sur des grilles de 960 configurations.
- Avec 2 configurations (L1), w ne prend que deux valeurs : la PBO est la part des 12 870 découpages où la meilleure en apprentissage est la moins bonne hors échantillon.

## 5. Ce qui était déjà connu au moment de ce préenregistrement

- Les 13 runs des 3 lots sont déjà jugés : **tous infirmés**. Selon S7, la meilleure est r10_disjonction dans L1, liquidity_ny_stop_150 dans L2 et auto_r7_03 dans L3. Une porte ne peut que dégrader un résultat : aucun de ces verdicts ne peut changer, et aucun ne sera modifié.
- PBOC (26/10) : PBO de la grille de 5 760 configurations de la voie C = 9,9 %.
- La sélection du 22/09 a été imprimée par les scripts de l'époque ; l'OOS et le hold-out jusqu'au 05/09/2026 sont déjà vus.
- Aucune PBO de ces lots ni de ces variantes n'a jamais été calculée. Aucun rendement de ces lots ni de ces variantes n'a été relu pour préparer ce texte (seules les empreintes des fichiers ont été calculées).
