"""Le sas : ce qu'on lit du code d'une candidate AVANT de l'importer.

Un controle statique, sur l'arbre syntaxique, sans jamais executer une ligne. Il est
volontairement place avant l'epreuve dynamique (`epreuve.py`) : importer un fichier, c'est
deja l'executer, et il vaut mieux refuser un `import subprocess` en le LISANT qu'apres.

Ce que le sas cherche, dans l'ordre d'importance :

1. **Les dependances interdites.** Une candidate importe pandas, numpy et le contrat. Rien
   d'autre. En particulier pas `beta.lake` : une candidate qui charge sa propre serie n'est
   plus une fonction du DataFrame qu'on lui donne, et le moteur ne controle plus ce qu'elle
   voit. C'est du look-ahead par construction.
2. **Les deux motifs de look-ahead que tout le monde ecrit.** `shift(-1)` et `center=True`.
   Ils ne sont pas les seuls — c'est l'epreuve de causalite qui couvre le reste — mais ce
   sont ceux qu'un modele local produit spontanement, et les refuser ici donne un message
   d'erreur comprehensible plutot qu'un « les signaux different a la ligne 8412 ».
3. **Le contrat de fichier.** Une fonction `creer()` au niveau du module, et aucun effet de
   bord a l'import : un fichier de candidate se lit, il ne fait rien.

**Ce que le sas n'est pas** : un bac a sable. Il attrape des erreurs, pas un adversaire —
qui peut ecrire dans `beta/candidates/` peut deja executer ce qu'il veut sur cette machine.
Confondre les deux serait la facon la plus rapide de se faire avoir.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("beta.atelier.sas")

# Ce qu'une candidate a le droit d'importer. Liste courte a dessein : chaque ajout est une
# facon de plus, pour une candidate, de voir autre chose que le DataFrame qu'on lui passe.
IMPORTS_AUTORISES = frozenset({
    "__future__", "pandas", "numpy", "math", "dataclasses", "typing", "collections",
    "beta.moteur.contrats",
})

# Modules explicitement nommes dans le refus, parce que leur presence dit CE QUI ne va pas.
IMPORTS_EXPLIQUES = {
    "beta.lake": "une candidate recoit ses donnees, elle ne va jamais les chercher — "
                 "charger sa propre serie, c'est du look-ahead par construction",
    "beta.protocole": "une candidate ne touche pas au registre d'experiences",
    "beta.moteur.pipeline": "une candidate ne connait pas le moteur, seulement le contrat",
    "os": "une candidate ne lit pas le disque",
    "sys": "une candidate ne lit pas le disque",
    "pathlib": "une candidate ne lit pas le disque",
    "subprocess": "une candidate ne lance pas de processus",
    "socket": "une candidate ne parle pas au reseau",
    "urllib": "une candidate ne parle pas au reseau",
    "requests": "une candidate ne parle pas au reseau",
    "random": "une candidate doit etre une fonction PURE : meme df, memes signaux "
              "(utiliser numpy.random.default_rng avec une graine si l'alea est voulu)",
    "datetime": "l'horloge n'a rien a faire dans une candidate : elle rendrait des signaux "
                "differents selon le jour ou on la mesure",
    "time": "l'horloge n'a rien a faire dans une candidate",
}

# Noms dont l'appel ouvre une porte qu'une candidate n'a aucune raison d'ouvrir.
APPELS_INTERDITS = frozenset({
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars",
})

# Attributs par lesquels on sort du bac a sable qu'on croyait avoir. Refuses parce que leur
# presence dans une candidate n'a aucune lecture innocente.
ATTRIBUTS_INTERDITS = frozenset({
    "__globals__", "__builtins__", "__subclasses__", "__class__", "__mro__", "__code__",
    "__dict__", "__getattribute__", "__import__", "__loader__", "__spec__",
})

# Methodes pandas qui remontent le temps. `bfill` recopie une valeur future vers le passe :
# aucun reglage ne la rend causale.
METHODES_INTERDITES = {
    "bfill": "recopie une valeur future dans le passe",
    "backfill": "recopie une valeur future dans le passe",
}
METHODES_SOUS_RESERVE = {
    "interpolate": "interpole par defaut avec les points suivants",
}

FABRIQUE = "creer"
SIGNAUX = "signaux"


@dataclass
class Rapport:
    """Ce que le sas a vu. `refus` interdit le depot ; `reserves` ne fait que le signaler."""

    module: str
    refus: list[str] = field(default_factory=list)
    reserves: list[str] = field(default_factory=list)
    mesures: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.refus

    def texte(self) -> str:
        lignes = [f"sas {self.module} : {'PASSE' if self.ok else 'REFUSE'}"]
        lignes += [f"  refus    {r}" for r in self.refus]
        lignes += [f"  reserve  {r}" for r in self.reserves]
        for cle, valeur in self.mesures.items():
            lignes.append(f"  {cle} = {valeur}")
        return "\n".join(lignes)

    def dict(self) -> dict:
        return {"module": self.module, "ok": self.ok, "refus": self.refus,
                "reserves": self.reserves, "mesures": self.mesures}


def _racine_module(nom: str) -> str:
    """`pandas.tseries.offsets` -> `pandas`, mais `beta.lake.lecture` -> `beta.lake`.

    Les sous-paquets de `beta` se jugent a deux niveaux : `beta.moteur.contrats` est permis
    quand `beta.moteur.pipeline` ne l'est pas, et les confondre reviendrait a tout ouvrir.
    """
    morceaux = nom.split(".")
    if morceaux[0] == "beta":
        return ".".join(morceaux[:3]) if len(morceaux) >= 3 else ".".join(morceaux[:2])
    return morceaux[0]


def _juger_import(nom: str, rapport: Rapport) -> None:
    racine = _racine_module(nom)
    if racine in IMPORTS_AUTORISES:
        return
    # `beta.moteur.contrats` est autorise ; `beta.moteur` tout court ne l'est pas, sinon
    # `from beta.moteur import pipeline` passerait par la porte de derriere.
    for prefixe, motif in IMPORTS_EXPLIQUES.items():
        if racine == prefixe or nom == prefixe or nom.startswith(prefixe + "."):
            rapport.refus.append(f"import de `{nom}` : {motif}")
            return
    rapport.refus.append(
        f"import de `{nom}` hors liste blanche ({', '.join(sorted(IMPORTS_AUTORISES))})")


def _decalage_negatif(appel: ast.Call) -> bool:
    """`shift(-1)`, `shift(periods=-2)` : le motif de look-ahead le plus repandu."""
    arguments = list(appel.args) + [mot.value for mot in appel.keywords
                                    if mot.arg in ("periods", "freq")]
    for argument in arguments:
        if isinstance(argument, ast.UnaryOp) and isinstance(argument.op, ast.USub):
            return True
        if isinstance(argument, ast.Constant) and isinstance(argument.value, int) \
                and argument.value < 0:
            return True
    return False


def _juger_appel(appel: ast.Call, rapport: Rapport) -> None:
    if isinstance(appel.func, ast.Name) and appel.func.id in APPELS_INTERDITS:
        rapport.refus.append(f"appel a `{appel.func.id}()` : une candidate calcule, "
                             "elle n'ouvre rien")
        return
    if not isinstance(appel.func, ast.Attribute):
        return
    methode = appel.func.attr
    if methode == "shift" and _decalage_negatif(appel):
        rapport.refus.append("`shift()` avec un decalage NEGATIF : c'est lire le futur")
    if methode in METHODES_INTERDITES:
        rapport.refus.append(f"`{methode}()` : {METHODES_INTERDITES[methode]}")
    if methode in METHODES_SOUS_RESERVE:
        rapport.reserves.append(f"`{methode}()` : {METHODES_SOUS_RESERVE[methode]} "
                                "- l'epreuve de causalite tranchera")
    for mot in appel.keywords:
        if mot.arg == "center" and isinstance(mot.value, ast.Constant) and mot.value.value:
            rapport.refus.append("`center=True` : une fenetre centree deborde sur le futur")
        if mot.arg == "method" and isinstance(mot.value, ast.Constant) \
                and str(mot.value.value) in METHODES_INTERDITES:
            rapport.refus.append(f"`method='{mot.value.value}'` : "
                                 f"{METHODES_INTERDITES[str(mot.value.value)]}")


def _juger_indice(noeud: ast.Subscript, rapport: Rapport) -> None:
    """`serie[-1]`, `df.iloc[-1]` : une valeur de FIN de serie appliquee a toutes les lignes.

    Sous reserve et non refuse : l'ecriture est legitime dans une fonction auxiliaire qui
    ne rend qu'un scalaire, et illegitime dans le corps de `signaux`. Le sas ne sait pas
    faire la difference ; l'epreuve de causalite, elle, la fait.
    """
    indice = noeud.slice
    negatif = (
        (isinstance(indice, ast.UnaryOp) and isinstance(indice.op, ast.USub))
        or (isinstance(indice, ast.Constant) and isinstance(indice.value, int)
            and indice.value < 0))
    if negatif:
        rapport.reserves.append(
            f"indice negatif ligne {noeud.lineno} : prend une valeur de fin de serie — "
            "l'epreuve de causalite tranchera")


def _juger_niveau_module(arbre: ast.Module, rapport: Rapport) -> None:
    """A l'import, un fichier de candidate ne doit RIEN faire d'autre que se definir."""
    for noeud in arbre.body:
        if isinstance(noeud, (ast.Import, ast.ImportFrom, ast.FunctionDef,
                              ast.AsyncFunctionDef, ast.ClassDef, ast.Assign,
                              ast.AnnAssign, ast.Pass)):
            continue
        if isinstance(noeud, ast.Expr) and isinstance(noeud.value, ast.Constant):
            continue                                       # docstring, ou chaine libre
        if isinstance(noeud, ast.If) and _est_garde_main(noeud):
            continue
        rapport.refus.append(
            f"instruction executee a l'import, ligne {noeud.lineno} "
            f"({type(noeud).__name__}) : un fichier de candidate se lit, il n'agit pas")


def _est_garde_main(noeud: ast.If) -> bool:
    test = noeud.test
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
            and test.left.id == "__name__")


def controler(code: str, module: str = "?") -> Rapport:
    """Le sas complet. Ne leve jamais : un refus est une donnee, pas une exception."""
    rapport = Rapport(module=module)

    if len(code.strip()) < 40:
        rapport.refus.append("fichier quasi vide — rien a controler")
        return rapport
    try:
        arbre = ast.parse(code)
    except SyntaxError as exc:
        rapport.refus.append(f"Python invalide, ligne {exc.lineno} : {exc.msg}")
        return rapport

    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            for alias in noeud.names:
                _juger_import(alias.name, rapport)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:                                # `from . import x`
                rapport.refus.append("import relatif : une candidate est isolee, elle "
                                     "n'a pas de voisin")
            elif noeud.module:
                _juger_import(noeud.module, rapport)
        elif isinstance(noeud, ast.Call):
            _juger_appel(noeud, rapport)
        elif isinstance(noeud, ast.Attribute) and noeud.attr in ATTRIBUTS_INTERDITS:
            rapport.refus.append(f"acces a `{noeud.attr}` : aucune lecture innocente")
        elif isinstance(noeud, ast.Subscript):
            _juger_indice(noeud, rapport)
        elif isinstance(noeud, (ast.Global, ast.Nonlocal)):
            rapport.refus.append("`global`/`nonlocal` : une candidate garde un etat entre "
                                 "deux appels, donc elle n'est plus une fonction pure")

    _juger_niveau_module(arbre, rapport)

    fonctions = {n.name for n in arbre.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if FABRIQUE not in fonctions:
        rapport.refus.append(f"pas de `{FABRIQUE}()` au niveau du module : le registre "
                             "decouvre les candidates par cette fonction, et rien d'autre")
    if SIGNAUX not in fonctions:
        rapport.reserves.append(f"pas de fonction `{SIGNAUX}()` nommee : lisible quand "
                                "meme, mais l'empreinte de code sera celle d'un lambda")

    rapport.mesures = {"lignes": len(code.splitlines()), "fonctions": len(fonctions)}
    return rapport


def hypothese_du_code(code: str) -> str:
    """L'id d'experience declare dans `creer()`, lu sans importer le fichier.

    Sert a prevenir tot qu'une candidate vise une hypothese qui n'est pas preenregistree.
    Ce n'est PAS un verrou — le verrou materiel est dans `contrats.Run`, qui refusera de
    mesurer. C'est un avertissement, au moment ou il coute le moins cher a entendre.
    """
    motif = r"hypothese\s*=\s*[\"']([A-Za-z0-9_\-]+)[\"']"
    trouve = re.search(motif, code)
    return trouve.group(1) if trouve else ""
