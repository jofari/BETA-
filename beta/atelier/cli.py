"""`python beta.py atelier ...` — les quatre gestes de l'atelier, en ligne de commande.

    atelier nouveau <module> --hypothese R7    ecrit un squelette pret a remplir
    atelier valider <module>                   passe une candidate existante au sas
    atelier local "<regle>" --module r7_x ...  la fait ecrire par un modele local
    atelier modeles                            quels serveurs locaux repondent

L'affichage est volontairement bavard sur les REFUS et avare sur le reste : le seul moment
ou l'atelier a quelque chose d'utile a dire, c'est quand il refuse. Une candidate qui passe
n'apprend rien — elle est juste eligible a etre mesuree, ce qui est le debut du travail,
pas la fin.
"""

from __future__ import annotations

import logging

from beta import config
from beta.atelier import depot, gabarit, local

log = logging.getLogger("beta.atelier.cli")

RAPPEL = ("une candidate qui passe l'atelier n'est pas une candidate qui marche : elle est "
          "eligible a etre MESUREE.\nProchaine etape : "
          "`python beta.py cribler --candidates {module}`")


def _afficher(rapport: dict) -> None:
    """Le rapport de validation, en clair. Les refus d'abord, ils sont l'information."""
    etat = "PASSE" if rapport.get("ok") else "REFUSE"
    print(f"\n{rapport.get('module')} : {etat}")
    for refus in rapport.get("refus") or []:
        print(f"  REFUS    {refus}")
    for reserve in rapport.get("reserves") or []:
        print(f"  reserve  {reserve}")
    mesures = rapport.get("mesures") or {}
    if mesures:
        print("  " + "  ".join(f"{cle}={valeur}" for cle, valeur in mesures.items()))


def cmd_nouveau(args) -> int:
    code = gabarit.ecrire(args.module, args.hypothese, nom=args.nom)
    cible = depot.chemin(args.module)
    if cible.exists() and not args.ecraser:
        print(f"{cible} existe deja — `--ecraser` pour le remplacer")
        return 1
    try:
        depot.verifier_nom(args.module)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(code, encoding="utf-8")
    except (depot.DepotError, OSError) as exc:
        print(f"ecriture impossible : {exc}")
        return 1

    print(f"squelette ecrit : {cible}")
    print("Il ne signale RIEN pour l'instant : l'epreuve le refusera tant que la regle "
          "n'est pas ecrite.\nC'est voulu — un squelette qui passe est un squelette qu'on "
          "mesure par distraction.")
    for reserve in depot.reserves_de_protocole(code):
        print(f"  reserve  {reserve}")
    print(f"\nQuand la regle est ecrite : `python beta.py atelier valider {args.module}`")
    return 0


def cmd_valider(args) -> int:
    cible = depot.chemin(args.module)
    if not cible.exists():
        print(f"{cible} introuvable. `python beta.py candidates` pour l'inventaire.")
        return 1
    try:
        code = cible.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"lecture impossible : {exc}")
        return 1
    rapport = depot.valider(code, args.module)
    _afficher(rapport)
    if rapport["ok"]:
        print("\n" + RAPPEL.format(module=args.module))
    return 0 if rapport["ok"] else 1


def cmd_local(args) -> int:
    print(f"generation de '{args.module}' par un modele local "
          f"({args.backend}{'/' + args.modele if args.modele else ''}), "
          f"{args.essais} essai(s) au plus.")
    print("Un 7B met une a trois minutes par essai sur ce poste.\n")
    try:
        rapport = local.ecrire_candidate(
            args.hypothese_en_clair, args.module, args.hypothese,
            backend=args.backend, modele=args.modele, essais=args.essais)
    except local.LocalError as exc:
        print(f"modele local indisponible :\n{exc}")
        return 1

    print(f"modele : {rapport['backend']} / {rapport['modele']} — "
          f"{len(rapport['tentatives'])} tentative(s)")
    for tentative in rapport["tentatives"]:
        marque = "PASSE" if tentative["ok"] else "refuse"
        print(f"  essai {tentative['essai']} : {marque}")
        for refus in tentative.get("refus") or []:
            print(f"      {refus}")

    if not rapport["ok"]:
        print("\nAucune version acceptable. Le code du dernier essai n'est PAS depose.")
        print("Relancer avec `--essais 5`, ou reformuler la regle en une seule idee.")
        if rapport.get("code"):
            brouillon = config.DATA / f"brouillon_{args.module}.py"
            try:
                brouillon.parent.mkdir(parents=True, exist_ok=True)
                brouillon.write_text(rapport["code"], encoding="utf-8")
                print(f"Dernier brouillon conserve pour relecture : {brouillon}")
            except OSError:
                pass                       # un brouillon perdu n'est pas une panne
        return 1

    try:
        pose = depot.deposer(rapport["code"], args.module, ecraser=args.ecraser)
    except depot.DepotError as exc:
        print(f"\ndepot refuse : {exc}")
        return 1
    _afficher(pose)
    print(f"\ndepose : {pose['chemin']}")
    print("RELIS-LE. Un modele local ecrit une hypothese, jamais un edge — et le sas "
          "attrape des erreurs, pas un adversaire.")
    print("\n" + RAPPEL.format(module=args.module))
    return 0


def cmd_modeles(_args) -> int:
    for serveur in local.disponibles():
        if serveur["disponible"]:
            print(f"{serveur['backend']:<10} {serveur['base']:<26} "
                  f"{len(serveur['modeles'])} modele(s) : {', '.join(serveur['modeles'])}")
        else:
            print(f"{serveur['backend']:<10} {serveur['base']:<26} injoignable "
                  f"({serveur['detail'][:70]})")
    print("\nOllama    : `ollama serve` puis `ollama pull qwen2.5:7b`")
    print("LM Studio : onglet Developer, `Start Server` (port 1234)")
    return 0


COMMANDES = {"nouveau": cmd_nouveau, "valider": cmd_valider, "local": cmd_local,
             "modeles": cmd_modeles}


def executer(args) -> int:
    oublies = depot.nettoyer_essais()
    if oublies:
        log.info("%d essai(s) oublie(s) par un plantage precedent, retire(s)", oublies)
    return COMMANDES[args.sous_commande](args)
