"""Les candidates : une hypothese par fichier, chacune exposant `creer() -> Candidate`.

Aucune ne connait le moteur, aucune n'en importe quoi que ce soit hors `contrats`. Elles
sont decouvertes par `beta.moteur.registre`, jamais listees a la main : ajouter un fichier
ici suffit a le faire entrer dans le criblage.

Un fichier de ce dossier est du code JETABLE. Il n'a pas a etre beau, il doit etre juste et
isole — une candidate fausse ne doit pouvoir salir que son propre verdict.
"""
