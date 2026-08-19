"""Les mesures des hypotheses R1-R6. Une par module, aucune sans preenregistrement.

Ces modules ne sont pas des candidates : ils ne produisent pas de signaux, ils repondent a
une question posee sur des donnees DEJA existantes. R1 et R6 sont les deux moins cheres du
lot — elles se mesurent sans ecrire une seule strategie, sur les 79 trades et les 3 151
evaluations importes d'ARIT.

Chacune appelle `protocole.exiger()` avant de calculer quoi que ce soit, et clot son
experience au registre avec le verdict obtenu, y compris — surtout — quand il est
INDECIDABLE.
"""
