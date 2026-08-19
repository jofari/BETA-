"""L'atelier : ecrire une candidate, a la main ou avec un modele local, sans mentir.

Le probleme que l'atelier resout n'est pas « comment produire du code de strategie » — un
modele de 7 milliards de parametres en produit dix par minute. C'est **comment empecher que
ce code, ecrit vite, entre dans le banc en emportant du look-ahead avec lui**.

Un banc d'essai qui accepte des candidates ecrites a la chaine devient une usine a faux
gagnants d'autant plus efficace qu'il est rapide. L'atelier abaisse donc le cout d'ECRIRE
une candidate, jamais le seuil pour en CONFIRMER une :

    gabarit / modele local  ->  sas (statique, sans importer)  ->  epreuve (sous-processus)
                            ->  beta/candidates/  ->  protocole inchange (preenregistrement,
                                compteur d'essais, batterie S1-S9)

Trois idees portees par le code plutot que par la discipline :

1. **Une candidate ne va JAMAIS chercher ses donnees.** Elle recoit un DataFrame. Le sas
   refuse tout import de `beta.lake` : une candidate qui charge sa propre serie fabrique du
   look-ahead par construction, et aucun test statistique ne le rattrape ensuite.
2. **La causalite se mesure, elle ne se relit pas.** `signaux(df[:t])` doit rendre
   exactement `signaux(df)[:t]`. Ce test attrape tout ce qui regarde le futur — y compris
   les formes qu'aucune liste de motifs interdits ne prevoit.
3. **Le sas n'est pas un bac a sable.** Qui peut ecrire dans `beta/candidates/` peut deja
   executer du code sur cette machine. Le sas attrape des ERREURS, pas un adversaire. Le
   croire etanche serait la facon la plus rapide de se faire avoir : on relit le code
   depose, toujours, y compris celui qu'un modele vient d'ecrire.
"""
