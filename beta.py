"""BETA — point d'entree unique en ligne de commande.

    python beta.py serve         le dashboard (et le navigateur qui s'ouvre)
    python beta.py lake          construit/actualise le lake OHLCV
    python beta.py strategie     importe les donnees de strategie depuis ARIT
    python beta.py etat          l'etat du lake, dans le terminal
    python beta.py doctor        ce qui est en place et ce qui manque

    python beta.py candidates    l'inventaire du registre de candidates
    python beta.py cribler       passe des candidates a la batterie S1-S9
    python beta.py comparer      compare les strategies deja mesurees entre elles
    python beta.py idee ...      la boite a idees (noter est gratuit)
    python beta.py atelier ...   ecrire une candidate, a la main ou avec un modele local
    python beta.py mcp           le serveur MCP stdio (lance par le client, pas a la main)

Doctrine et invariants : CLAUDE.md.
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import subprocess
import sys

RACINE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RACINE))


def preparer_console() -> None:
    """La console Windows est en cp1252 : sans ca, un accent tue le script sur un print."""
    for flux in (sys.stdout, sys.stderr):
        if hasattr(flux, "reconfigure"):
            flux.reconfigure(encoding="utf-8", errors="replace")


def preparer_logs(bavard: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if bavard else logging.INFO,
                        format="%(levelname)-7s %(name)-22s %(message)s")


def _script(nom: str, *args: str) -> int:
    """Delegue a un script de `scripts/`, dans le MEME interpreteur.

    Passer par `sys.executable` plutot que par `python` : le venv n'est pas forcement actif
    dans le shell qui lance BETA, et un mauvais interpreteur donnerait un « module
    introuvable » incomprehensible.
    """
    return subprocess.call([sys.executable, str(RACINE / "scripts" / nom), *args])


def cmd_serve(args) -> int:
    from beta.rapport import serveur
    return serveur.servir(hote=args.host, port=args.port, ouvrir=not args.no_browser)


def cmd_lake(args) -> int:
    extra = []
    if args.sans_telechargement:
        extra.append("--sans-telechargement")
    if args.purge:
        extra.append("--purge")
    return _script("build_lake.py", *extra)


def cmd_strategie(args) -> int:
    return _script("import_strategie.py", *(["--holdout"] if args.holdout else []))


def cmd_etat(_args) -> int:
    return _script("build_lake.py", "--etat")


def cmd_mcp(_args) -> int:
    """Le serveur MCP stdio. Normalement lance par le client, jamais tape a la main.

    L'exposer ici quand meme donne un point de lancement unique : la configuration MCP
    d'un client pointe sur `-m beta.mcp.serveur`, mais un humain qui veut verifier que le
    serveur demarre n'a pas a connaitre ce detail. Pour l'eprouver vraiment :
    `python scripts/epreuve_mcp.py`.
    """
    from beta.mcp import serveur
    return serveur.servir()


def cmd_candidates(_args) -> int:
    from beta.moteur import registre

    inventaire = registre.inventaire()
    if not inventaire:
        print("Aucune candidate. `python beta.py atelier nouveau <module> --hypothese R7`")
        return 0
    print(f"{'module':<28} {'hypothese':<10} {'empreinte':<12} nom")
    for ligne in inventaire:
        print(f"{ligne['module']:<28} {ligne['hypothese']:<10} "
              f"{ligne['empreinte']:<12} {ligne['nom']}")
    print(f"\n{len(inventaire)} candidate(s). Chacune mesuree AUGMENTE le compteur d'essais,")
    print("donc durcit le seuil de toutes les autres. C'est voulu.")
    return 0


def cmd_cribler(args) -> int:
    """Passe un lot de candidates a la batterie, puis S7 et S9 sur le lot ENTIER.

    Pourquoi le lot plutot que la candidate : les deux portes qui comparent les candidates
    entre elles n'ont aucun sens une par une. Cribler dix candidates dix fois de suite en
    solo donnerait dix resultats flatteurs et faux — chacune se croirait seule au monde.
    """
    from beta.lake import univers
    from beta.moteur import pipeline, registre
    from beta.protocole import experiences

    disponibles = registre.toutes()
    if args.candidates:
        demandes = [c.strip() for c in args.candidates.split(",") if c.strip()]
        inconnues = [c for c in demandes if c not in disponibles]
        if inconnues:
            print(f"candidate(s) inconnue(s) : {', '.join(inconnues)}")
            print(f"connues : {', '.join(sorted(disponibles)) or 'aucune'}")
            return 1
        lot = {nom: disponibles[nom] for nom in demandes}
    else:
        lot = disponibles
    if not lot:
        print("aucune candidate a cribler")
        return 1

    paires = tuple(p.strip().upper() for p in args.paires.split(",") if p.strip()) \
        if args.paires else tuple(p.base for p in univers.PAIRES)

    print(f"criblage de {len(lot)} candidate(s) sur {', '.join(paires)} en {args.timeframe}")
    print(f"compteur d'essais AVANT : {experiences.compteur()}")
    if args.split != "train":
        print("\n*** SPLIT HOLD-OUT DEMANDE. Le regarder, c'est le bruler. ***\n")

    verdicts = pipeline.cribler(lot, paires=paires, timeframe=args.timeframe,
                                split=args.split, take_profit_r=args.take_profit_r,
                                stop_atr=args.stop_atr,
                                horizon_bougies=args.horizon)
    if not verdicts:
        print("aucun verdict rendu — voir les erreurs ci-dessus")
        return 1

    print(f"\n{'candidate':<24} {'issue':<12} {'n':>6} {'R moyen':>9} {'MDE':>8}  "
          "portes echouees")
    for nom, verdict in sorted(verdicts.items()):
        m = verdict.metriques
        echouees = ", ".join(verdict.portes_echouees) or "-"
        print(f"{nom:<24} {verdict.issue:<12} {m.get('n', 0):>6} "
              f"{m.get('r_moyen', float('nan')):>9.4f} {m.get('mde_r', float('nan')):>8.4f}"
              f"  {echouees}")
    print("\ndetail : data/runs/<run_id>/  ·  dashboard : onglet Candidates")
    print("un chiffre de criblage se lit en R par trade, JAMAIS en rendement de "
          "portefeuille.")
    cmd_comparer(args)
    # Une candidate infirmee n'est pas un echec de la commande : c'est son resultat normal,
    # et de loin le plus frequent. Seule l'absence de verdict en est un (traitee plus haut).
    return 0


def cmd_comparer(args) -> int:
    """Le banc COMPARATIF : ce qu'on ne peut pas savoir en regardant une candidate a la fois.

    Il relit `data/runs/`, il ne relance rien. Deux strategies mesurees a trois semaines
    d'ecart doivent pouvoir se comparer sans qu'on ait a les remesurer ensemble — sinon la
    comparaison ne se fait jamais.
    """
    from beta.rapport import comparaison as lecture
    from beta.stats import comparaison as stats_comparaison

    split = getattr(args, "split", "train")
    lot, classement = lecture.classement_du_lot(split)
    if not lot["n"]:
        print(f"\naucun run en '{split}' — `python beta.py cribler` d'abord")
        return 1
    print("\n=== comparaison ===")
    print(stats_comparaison.texte(classement))
    return 0


def cmd_atelier(args) -> int:
    from beta.atelier import cli
    return cli.executer(args)


def cmd_idee(args) -> int:
    """La boite a idees. Noter est gratuit ; promouvoir avance le compteur d'essais.

    C'est toute la raison d'etre de la commande : sans etage gratuit, une idee de passage
    n'a nulle part ou aller — preenregistrer chacune couterait un cran de compteur, donc on
    n'en note aucune, donc on les perd.
    """
    from beta.protocole import idees

    try:
        if args.geste == "note":
            idee = idees.ajouter(args.texte, source=args.source, pourquoi=args.pourquoi)
            print(f"{idee['id']} notee. Le compteur d'essais n'a PAS bouge "
                  f"({idees.experiences.compteur()}).")
            print(f"La promouvoir : `python beta.py idee promouvoir {idee['id']} "
                  "--experience R7 ...`")
            return 0

        if args.geste == "liste":
            trouvees = idees.lister(args.etat)
            if not trouvees:
                print("aucune idee. `python beta.py idee note \"...\"`")
                return 0
            for idee in trouvees:
                marque = {"nouvelle": " ", "promue": "+", "ecartee": "-"}.get(
                    idee.get("etat"), "?")
                suffixe = ""
                if idee.get("etat") == "promue":
                    suffixe = f"   -> {idee.get('id_experience')}"
                elif idee.get("etat") == "ecartee":
                    suffixe = f"   ecartee : {idee.get('motif', '')[:60]}"
                print(f"{marque} {idee['id']:<5} {idee.get('date', '')}  "
                      f"{idee.get('texte', '')[:88]}{suffixe}")
            resume = idees.resume()
            print(f"\n{resume['n']} idee(s) : {resume['nouvelle']} nouvelle(s), "
                  f"{resume['promue']} promue(s), {resume['ecartee']} ecartee(s). "
                  f"Compteur d'essais : {resume['compteur_essais']}.")
            return 0

        if args.geste == "ecarter":
            idees.ecarter(args.id, args.motif)
            print(f"{args.id} ecartee — elle reste au fichier, avec son motif.")
            return 0

        regle = {"confirmee": args.confirmee, "infirmee": args.infirmee,
                 "indecidable": args.indecidable}
        promue = idees.promouvoir(
            args.id, args.experience, args.hypothese, args.metrique, regle,
            mde_attendu=args.mde, famille_taille=args.famille,
            deja_connu=args.deja_connu, issue_attendue=args.issue_attendue)
        print(f"{args.id} promue en {args.experience}.")
        print(f"Compteur d'essais : {promue['compteur_avant']} -> "
              f"{promue['compteur_apres']}. Le seuil de TOUTES les autres vient de durcir.")
        return 0
    except idees.IdeeError as exc:
        print(f"refus : {exc}")
        return 1
    except idees.experiences.ProtocoleError as exc:
        print(f"preenregistrement refuse : {exc}\nL'idee reste `nouvelle`.")
        return 1


def cmd_doctor(_args) -> int:
    from beta import config
    from beta.lake import catalogue, strategie
    from beta.protocole import experiences, holdout

    print(f"racine        {RACINE}")
    print(f"donnees       {config.DATA}")
    print(f"ARIT (lecture) {config.ARIT}"
          f"{'' if config.ARIT.exists() else '   <- INTROUVABLE'}")
    print(f"hold-out      scelle au {holdout.DEBUT.date()}")
    print(f"essais cumules {experiences.compteur()} "
          f"(dont {experiences.ESSAIS_INITIAUX} de dette initiale)")

    # Deux nombres, pas un. Le compteur porte les HYPOTHESES ; le journal porte les MESURES.
    # Tant qu'il y a une candidate par hypothese ils coincident ; des que l'atelier en
    # produit plusieurs sous la meme hypothese, l'ecart est la quantite de tests que la
    # correction de tests multiples ignore. Cf. DECISIONS.md § A1.
    mesures = experiences.compteur_runs()
    hypotheses = experiences.compteur() - experiences.ESSAIS_INITIAUX
    print(f"runs mesures  {mesures} pour {hypotheses} hypothese(s) declaree(s)"
          + ("   <- ECART : N sous-estime les tests reellement faits"
             if mesures > hypotheses else ""))

    etat = catalogue.etat()
    if etat.empty:
        print("lake OHLCV    VIDE — lancer `python beta.py lake`")
    else:
        suspectes = int(etat["suspect"].sum())
        print(f"lake OHLCV    {len(etat)} series · {etat['paire'].nunique()} paires · "
              f"{int(etat['n_bougies'].sum()):,} bougies · {suspectes} suspecte(s)"
              .replace(",", " "))
        print(f"              borne commune : {str(etat['fin'].min())[:10]} "
              "(limite d'un run multi-paires)")

    manquantes = []
    for table in strategie.TABLES:
        chemin = strategie.chemin_table(table)
        if chemin.exists():
            try:
                print(f"{table:13s} {len(strategie.lire(table)):6d} lignes")
            except strategie.StrategieError as exc:
                print(f"{table:13s} ILLISIBLE : {exc}")
        else:
            manquantes.append(table)
    if manquantes:
        print(f"strategie     {', '.join(manquantes)} absente(s) — "
              "lancer `python beta.py strategie`")
    return 0


def parseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="beta", description=__doc__.splitlines()[0])
    p.add_argument("-v", "--verbose", action="store_true")
    subs = p.add_subparsers(dest="commande", required=True)

    from beta.rapport.serveur import HOTE, PORT
    serve = subs.add_parser("serve", help="dashboard web")
    serve.add_argument("--host", default=HOTE)
    serve.add_argument("--port", type=int, default=PORT)
    serve.add_argument("--no-browser", action="store_true")
    serve.set_defaults(fonction=cmd_serve)

    lake = subs.add_parser("lake", help="construit ou actualise le lake OHLCV")
    lake.add_argument("--sans-telechargement", action="store_true")
    lake.add_argument("--purge", action="store_true")
    lake.set_defaults(fonction=cmd_lake)

    strat = subs.add_parser("strategie", help="importe les donnees de strategie d'ARIT")
    strat.add_argument("--holdout", action="store_true",
                       help="inclut le hold-out dans le resume (EXCLU par defaut)")
    strat.set_defaults(fonction=cmd_strategie)

    subs.add_parser("etat", help="l'etat du lake").set_defaults(fonction=cmd_etat)
    subs.add_parser("doctor", help="ce qui est en place et ce qui manque"
                    ).set_defaults(fonction=cmd_doctor)
    subs.add_parser("mcp", help="serveur MCP stdio (lance par le client MCP)"
                    ).set_defaults(fonction=cmd_mcp)
    subs.add_parser("candidates", help="inventaire du registre de candidates"
                    ).set_defaults(fonction=cmd_candidates)

    comparer = subs.add_parser("comparer", help="compare les strategies deja mesurees "
                                                "entre elles, sans rien relancer")
    comparer.add_argument("--split", default="train", choices=["train", "holdout"])
    comparer.set_defaults(fonction=cmd_comparer)

    from beta.moteur.contrats import Run
    from beta.protocole import holdout
    defauts = Run.__dataclass_fields__
    cribler = subs.add_parser("cribler", help="passe des candidates a la batterie S1-S9")
    cribler.add_argument("--candidates", default="",
                         help="modules separes par des virgules (defaut : toutes)")
    cribler.add_argument("--paires", default="",
                         help="BTC,ETH,... (defaut : l'univers entier)")
    cribler.add_argument("--timeframe", default="4h")
    cribler.add_argument("--split", default=holdout.TRAIN,
                         choices=[holdout.TRAIN, holdout.HOLDOUT],
                         help="le hold-out n'est ouvert qu'aux experiences qui l'autorisent")
    cribler.add_argument("--take-profit-r", type=float,
                         default=defauts["take_profit_r"].default)
    cribler.add_argument("--stop-atr", type=float, default=defauts["stop_atr"].default)
    cribler.add_argument("--horizon", type=int,
                         default=defauts["horizon_bougies"].default)
    cribler.set_defaults(fonction=cmd_cribler)

    atelier = subs.add_parser("atelier", help="ecrire une candidate, a la main ou "
                                             "avec un modele local")
    ateliers = atelier.add_subparsers(dest="sous_commande", required=True)

    nouveau = ateliers.add_parser("nouveau", help="ecrit un squelette pret a remplir")
    nouveau.add_argument("module", help="nom de fichier sans .py, ex: r7_breakout")
    nouveau.add_argument("--hypothese", required=True, help="id preenregistre, ex: R7")
    nouveau.add_argument("--nom", default="", help="nom de la candidate (defaut : module)")
    nouveau.add_argument("--ecraser", action="store_true")

    valider = ateliers.add_parser("valider", help="passe une candidate existante au sas")
    valider.add_argument("module")

    local = ateliers.add_parser("local", help="fait ecrire la candidate par un modele local")
    local.add_argument("hypothese_en_clair",
                       help="la regle voulue, en une ou deux phrases")
    local.add_argument("--module", required=True, help="nom de fichier sans .py")
    local.add_argument("--hypothese", required=True, help="id preenregistre, ex: R7")
    local.add_argument("--backend", default="auto",
                       choices=["auto", "ollama", "lmstudio"])
    local.add_argument("--modele", default="", help="defaut : le premier modele servi")
    local.add_argument("--essais", type=int, default=3,
                       help="tentatives de reparation apres un refus du sas")
    local.add_argument("--ecraser", action="store_true")

    ateliers.add_parser("modeles", help="quels serveurs locaux repondent, et avec quoi")
    atelier.set_defaults(fonction=cmd_atelier)

    idee = subs.add_parser("idee", help="la boite a idees : noter est gratuit, "
                                        "promouvoir avance le compteur d'essais")
    gestes = idee.add_subparsers(dest="geste", required=True)

    note = gestes.add_parser("note", help="note une idee, sans forme imposee et sans cout")
    note.add_argument("texte")
    note.add_argument("--source", default="", help="d'ou elle vient (vidéo, mesure, lecture)")
    note.add_argument("--pourquoi", default="", help="ce qui te fait y croire aujourd'hui")

    liste = gestes.add_parser("liste", help="les idees notees")
    liste.add_argument("--etat", default="", choices=["", "nouvelle", "promue", "ecartee"])

    ecarter = gestes.add_parser("ecarter", help="ecarte une idee, sans l'effacer")
    ecarter.add_argument("id")
    ecarter.add_argument("motif")

    # Promouvoir demande tout ce qui manque a une idee pour devenir mesurable. La friction
    # est le point : c'est le seul geste du fichier qui coute un cran de compteur.
    promo = gestes.add_parser("promouvoir",
                              help="transforme une idee en experience preenregistree")
    promo.add_argument("id")
    promo.add_argument("--experience", required=True, help="id court, ex: R7")
    promo.add_argument("--hypothese", required=True, help="la phrase FALSIFIABLE")
    promo.add_argument("--metrique", required=True, help="la metrique primaire, une seule")
    promo.add_argument("--confirmee", required=True, help="ce qui vaut confirmee")
    promo.add_argument("--infirmee", required=True, help="ce qui vaut infirmee")
    promo.add_argument("--indecidable", default="tout le reste")
    promo.add_argument("--mde", type=float, default=None, help="MDE attendu")
    promo.add_argument("--famille", type=int, default=None,
                       help="taille de la famille de tests, declaree AVANT")
    promo.add_argument("--issue-attendue", default="", dest="issue_attendue")
    promo.add_argument("--deja-connu", default="", dest="deja_connu",
                       help="ce qui a DEJA ete regarde sur ces donnees — ne pas le remplir "
                            "rend le preenregistrement sans valeur")
    idee.set_defaults(fonction=cmd_idee)
    return p


def main() -> int:
    preparer_console()
    args = parseur().parse_args()
    preparer_logs(args.verbose)
    return args.fonction(args)


if __name__ == "__main__":
    sys.exit(main())
