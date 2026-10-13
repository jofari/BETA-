# Mission : cohérence de la batterie + réexécution des stratégies avec les nouveaux coûts

Contexte immédiat — le moteur `beta/moteur/espace_r.py` a DÉJÀ été modifié (non commité) :
il paie maintenant trois coûts par trade, tous convertis en R via `entree / risque` :
frais+slippage (forfaitaires), **spread** (estimateur Corwin-Schultz, demi à l'entrée +
demi à la sortie), et **funding** (cumulé sur la durée de détention, signé par le sens).
`Run` porte `spread=True` et `funding=True` par défaut, et `Run.id` intègre les coûts.
Les tests sont verts. Pars de cet état, NE REVIENS PAS en arrière.

Tu travailles sur le VPS Linux. Venv : `/root/venvs/arit/bin/python`. Tests :
`cd /root/BETA- && /root/venvs/arit/bin/python -m pytest -q`. Réponds en français,
docstrings/code SANS accents. Lis CLAUDE.md. Ne commit pas, ne push pas.

## Phase 1 — la batterie doit payer les MÊMES coûts que la candidate (CODE)

Une candidate paie désormais le funding et le spread. Si les références contre lesquelles
on la juge ne les paient pas, deux portes de la batterie deviennent biaisées :

1. **S8 (buy-and-hold)** — `beta/stats/reference.py`, fonction `hold()`. Le hold est un
   LONG équipondéré, jamais rebalancé. Un long perpétuel tenu des années paie un funding
   réel. Il doit donc payer :
   - le **funding** cumulé sur toute sa durée de détention, signé long (sens +1 : un
     funding positif est un coût, un négatif un revenu), à partir de la colonne
     `funding_rate` jointe par le pipeline (absente pour les indices => funding nul, sans
     erreur) ;
   - le **spread** (avec le même estimateur `espace_r.spread_corwin_schultz`, ou son
     équivalent) payé une fois en plus du `cout_aller_retour_pct` existant.
   Le total vient en déduction du rendement, comme le `cout_aller_retour_pct` actuel. La
   signature et les appelants de `hold()` (qui reçoit `cout_aller_retour_pct`) : conserve la
   compatibilité, ajoute les paramètres nécessaires (type, spread/funding), et propage les
   valeurs depuis `batterie.evaluer` / `pipeline.executer` (`run.spread`, `run.funding`).

2. **S4 (témoin synthétique)** — `beta/moteur/pipeline.py`, `_resultats_synthetiques`, et
   `beta/stats/synthetique.py` `_reconstruire_ohlcv`. Les marchés aléatoires « phase » sont
   reconstruits en OHLCV nu et ne portent PAS `funding_rate` (déjà noté dans un docstring).
   Pour l'équité, fais en sorte que le témoin paie aussi le funding : soit recopie la
   colonne `funding_rate` de la série mère dans les chemins synthétiques (même index), soit
   — si la reconstruction rend cela incohérent — dis-le clairement et je trancherai. Le
   spread, lui, est déjà calculé sur les mèches du témoin (aucune action).

Ajoute des tests couvrant : le hold paie un funding positif (rendement inférieur à un hold
sans funding), le hold d'un indice (sans colonne funding) ne change pas de rendement, et le
témoin synthétique paie le funding. Vérifie que TOUTE la suite reste verte.

## Phase 2 — réexécuter toutes les stratégies déjà mesurées (EXÉCUTION, pas de nouveau code)

Le but : re-mesurer chaque stratégie AVEC les nouveaux coûts, en journalisant normalement.
Le compteur d'essais monte — c'est voulu et validé (doctrine A1 : un run = +1). N'essaie pas
de l'éviter.

Stratégies à réexécuter :
- les 11 candidates de `beta/candidates/` : r2_mean_reversion (R2), r4_fear_greed_contrarian
  (R4), r9_funding_contrarian (R9), r10_conjonction + r10_disjonction (R10),
  r11_credit_contrarian (R11), auto_r7_01 + auto_r7_03 (R7),
  liquidity_ny_stop_050 + _100 + _150 (R8) ;
- les recherches R1 (trailing) et R6 (news_window) qui vivent dans `beta/recherche/` et se
  mesurent via `scripts/mesurer.py`.

Contraintes de paramètres (à VÉRIFIER dans les préenregistrements de `EXPERIMENTS.jsonl` et
les docstrings avant de lancer, et à me rapporter) :
- timeframe : **5m pour R8** (liquidity_ny_stop_*), **4h pour toutes les autres** ;
- paires : les 6 crypto (BTC, ETH, SOL, BNB, LINK, XRP) ;
- split : train uniquement, JAMAIS hold-out ;
- stop_atr 2.0, take_profit_r 2.0, horizon 96 (les défauts), sauf si un préenregistrement
  impose autre chose.

Procédé :
- candidates en 4h : un seul `beta.py cribler` sur le lot 4h (pour que S7/S9 comparent le
  lot ensemble) ;
- candidates en 5m (R8) : un `beta.py cribler` séparé en `--timeframe 5m` ;
- R1/R6 : réévalue si `scripts/mesurer.py` les re-mesure proprement avec les nouveaux coûts.
  Si oui, relance-le ; si non (script figé), ne bricole rien et rapporte-le précisément.

Avant d'exécuter la moindre commande de réexécution qui journalise, rapporte-moi la MATRICE
exacte que tu t'apprêtes à lancer (candidate → hypothèse → timeframe → paires → horizon →
commande), puis exécute dans la foulée — je veux la trace, pas un vote bloquant.

## Livrable final

Résume en français, concis :
1. Phase 1 : ce qui a changé dans reference.py / pipeline.py / synthetique.py, et les
   valeurs par défaut retenues ; résultat de `pytest`.
2. Phase 2 : la matrice réellement lancée, les commandes exécutées, et pour chaque
   hypothèse : ancien verdict → nouveau verdict (avec le compteur avant/après).
3. Toute décision prise seul (temps d'exécution, candidate illisible, R1/R6 non
   re-mesurable, etc.) que je dois connaître.