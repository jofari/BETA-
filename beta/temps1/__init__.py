"""Temps 1, etape A (laboratoire, Jonas 21/10) : un detecteur de regime protege-t-il mieux des
grandes baisses qu'une SMA 200, a exposition moyenne egale, sur de longs historiques actions ?

Les actions sont un LABORATOIRE (on ne les trade pas) ; aucune donnee crypto. Le moteur de TI1
est reutilise tel quel (`beta.invest.moteur`, `metriques`, `nulls`) : ce paquet ne fait que lui
fournir des series (calendrier civil comble, cf. `adaptateur`) et des signaux. Chaine pure :
donnees -> detecteurs -> campagne -> rapport. Phase 1 : `temps1/DISCOVERY.md` ;
preenregistrement : `scripts/preenregistrer_t1a.py` ; mesures : `scripts/temps1.py`.
"""
