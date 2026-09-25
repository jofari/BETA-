"""Strategies d'allocation multi-actifs, autonomes du moteur a triple barriere.

Une allocation n'a ni entree ni sortie : elle a un POIDS par actif et par jour. Elle ne
passe donc pas par `moteur.contrats.Run` (qui raisonne en trades) et ne peut pas etre
criblee par S1-S9 telle quelle. Ce qui sort d'ici est une courbe d'equity quotidienne, a
comparer aux references imposees (buy-and-hold, AritV1) par la voie de `stats.comparaison`.
"""
