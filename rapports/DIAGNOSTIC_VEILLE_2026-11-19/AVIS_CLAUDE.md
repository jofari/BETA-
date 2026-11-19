## Avis de Claude — ce n'est PAS le programme

**Ce que je lis dans les chiffres du programme**

- **La veille est un défaut déjà présent dans le backtest, pas une malchance du forward.** En backtest, la veille de VC3 n'a vendu que 7 jours sur 777. Le moteur haussier voulait en moyenne *plus* d'exposition que celle tenue (écart −0,19). La règle « réduire seulement si le moteur veut moins » ne se déclenche donc presque jamais.
- **Tout dépend du régime d'où l'on vient.** Une veille qui suit un baissier garde une exposition faible : en 2022, l'exposition moyenne était de 0,06 et VC3 a perdu −2,35 % pendant que BTC perdait −29,14 %. C'est ce qui a rendu le backtest flatteur. Une veille qui suit un haussier fige une exposition forte. C'est le cas de 08/2023, 07-08/2024 et du 31/10 au 17/11/2026, qui arrive au 2e rang des pires baisses de BTC en veille sur 112 épisodes. En 2024, VC3 a perdu −10,10 % en veille quand BTC gagnait +10,17 %.
- **VC5 est la plus touchée** : avec une exposition de 0,94 à 1,00 en veille, elle suit BTC pendant toute la baisse.

**Pistes pour réduire l'exposition au risque** (notées gratuitement dans `IDEES.jsonl`, aucune n'est mesurée)

- I17 — **Veille dégressive** : en veille, l'exposition baisse chaque jour, ou elle est plafonnée (par exemple à un tiers), au lieu d'être figée.
- I18 — **Garde de drawdown sur l'équité**, indépendante des votes : sous X % du plus haut, on revient à une petite poche.
- I19 — **Moteur plus réactif** : volatilité sur une fenêtre courte ou une moyenne exponentielle, et/ou une cible de 15 %.
- I20 — **BTC seul**, comme tu l'envisages : on enlève les alts, qui ont baissé plus que BTC (équipondéré −26,35 % contre −21,00 %). Cette piste rejoint MOMENTUM30_BTC (exploration confirmée le 10/11, MDD −47 % contre −79 % pour le hold).

**Ce que je recommande** : ne pas retoucher VC3, VC4 ni VC5 (ce serait régler après avoir vu le résultat). Préparer plutôt **une seule nouvelle voie préenregistrée en BTC seul**. Elle combinerait le momentum 30 jours de MOMENTUM30_BTC avec une veille dégressive ou une garde de drawdown, choisie d'avance, sans balayage de réglages. Cela coûte un essai au compteur. Les voies actuelles continuent leur dry-run jusqu'à son terme, comme prévu.
