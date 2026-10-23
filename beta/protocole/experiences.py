"""Le registre d'experiences : rien ne se mesure sans avoir ete ecrit ici AVANT.

Ce module n'est pas un utilitaire de journalisation. C'est un VERROU, et il est place au
plus bas de la pile a dessein : tout ce qui mesure en depend, donc rien ne peut le
contourner sans que ca se voie dans les imports.

Deux raisons, toutes deux mesurees plutot que supposees :

1. **Sans preenregistrement, un resultat post-hoc est indiscernable d'une hypothese
   confirmee.** On ne peut pas savoir, deux mois plus tard, si le seuil de decision a ete
   choisi avant ou apres avoir vu les chiffres. La p-value ne veut alors plus rien dire.
2. **Sans compteur cumulatif, aucune correction de tests multiples n'est possible.** N doit
   compter TOUS les essais, y compris ceux qu'on n'a jamais rapportes parce qu'ils etaient
   mauvais — c'est le fleau principal. Le compteur de BETA part de **30** : la dette deja
   consommee sur les memes 8,5 ans avant l'ouverture du registre (ARIT, campagnes de
   juillet 2026). Il n'est jamais remis a zero.

   Depuis le 23/10 (Jonas), il y a **deux compteurs**, un par famille d'essais : le
   **trading actif** (les 93 essais d'alors — R1-R12, VC2-VC5 — et la dette de 30) et
   l'**invest** (TI1, T1A : exposition long terme, survie aux krachs). Chaque famille paie
   ses propres essais ; aucun des deux n'est remis a zero.

Format : JSONL append-only. On ne modifie jamais une ligne existante ; on en ajoute une
nouvelle avec le meme `id` et un statut mis a jour, et c'est la derniere qui fait foi.
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import UTC, datetime

from beta import config

log = logging.getLogger("beta.protocole")

REGISTRE = config.RACINE / "EXPERIMENTS.jsonl"

# Le journal des mesures effectivement lancees. A la racine comme le registre :
# `data/` est jetable, et un compteur qu'un nettoyage remet a zero ment.
JOURNAL_RUNS = config.RACINE / "RUNS.jsonl"

# Dette consommee avant l'ouverture du registre : ~40 politiques comparees sur les memes
# 123 episodes cote ARIT (research/pistes_2026-07-31/RAPPORT.md §1.3). Aucune p-value
# calculee sur cette periode n'est interpretable telle quelle.
ESSAIS_INITIAUX = 30

# Les deux familles du compteur (Jonas, 23/10). La dette de 30 est celle du trading actif :
# l'invest n'a herite d'aucun essai anterieur au registre.
FAMILLES = ("trading", "invest")
DETTE_INITIALE = {"trading": ESSAIS_INITIAUX, "invest": 0}

# Le registre n'a eu de champ `famille_compteur` qu'a partir du 23/10. Pour les lignes
# d'avant, le classement est celui de Jonas : TI1 et T1A en invest, tout le reste (ses 93)
# en trading actif.
FAMILLES_HISTORIQUES = {"TI1": "invest", "T1A": "invest"}

CHAMPS_REQUIS = ("id", "hypothese", "metrique_primaire", "regle_de_decision",
                 "split_autorise")

STATUTS = ("preenregistre", "mesure", "clos", "abandonne")


class ProtocoleError(RuntimeError):
    """Preenregistrement absent, incomplet, ou registre illisible."""


def _lignes(chemin: pathlib.Path | None = None) -> list[dict]:
    chemin = chemin or REGISTRE
    if not chemin.exists():
        return []
    entrees = []
    for n, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
        if not ligne.strip():
            continue
        try:
            entrees.append(json.loads(ligne))
        except json.JSONDecodeError as exc:
            raise ProtocoleError(f"{chemin.name} ligne {n} illisible : {exc}") from exc
    return entrees


def etat(chemin: pathlib.Path | None = None) -> dict[str, dict]:
    """L'etat courant de chaque experience : les lignes d'un meme id sont FUSIONNEES.

    La derniere ligne fait foi champ par champ, pas ligne entiere. La difference n'est pas
    theorique : une ligne de cloture ne porte que le verdict, donc l'ecrasement pur ferait
    disparaitre l'hypothese et la regle de decision du dossier. `exiger()` refuserait alors
    de remesurer une experience deja close — c'est-a-dire qu'on ne pourrait plus jamais
    reproduire un resultat publie, ce qui est exactement le contraire du but.
    """
    fusion: dict[str, dict] = {}
    for entree in _lignes(chemin):
        if "id" in entree:
            fusion[entree["id"]] = {**fusion.get(entree["id"], {}), **entree}
    return fusion


def exiger(id_exp: str, chemin: pathlib.Path | None = None) -> dict:
    """Le verrou. Retourne le preenregistrement, ou refuse de laisser mesurer.

    A appeler en PREMIERE ligne de tout code qui produit un chiffre destine a decider
    quelque chose. Ce n'est pas une formalite administrative : c'est ce qui distingue une
    mesure d'une peche aux resultats.
    """
    chemin = chemin or REGISTRE
    entree = etat(chemin).get(id_exp)
    if entree is None:
        raise ProtocoleError(
            f"experience '{id_exp}' non preenregistree dans {chemin}.\n"
            "Ecrire l'hypothese, la metrique primaire et la regle de decision AVANT de "
            "mesurer — sinon le resultat n'est pas interpretable.")
    manquants = [c for c in CHAMPS_REQUIS if not entree.get(c)]
    if manquants:
        raise ProtocoleError(f"preenregistrement '{id_exp}' incomplet : {manquants}")
    return entree


def _verifier_famille(famille: str) -> None:
    if famille not in FAMILLES:
        raise ProtocoleError(f"famille de compteur inconnue : {famille!r} (connues : {FAMILLES})")


def famille_de(id_exp: str | None, chemin: pathlib.Path | None = None, *,
               registre: dict[str, dict] | None = None) -> str:
    """La famille de compteur d'une experience : celle qu'elle declare, sinon l'historique.

    Une mesure dont l'experience est inconnue du registre compte en trading actif : c'est la
    famille qui porte la dette, donc le sens qui durcit au lieu de flatter.
    """
    entree = (etat(chemin) if registre is None else registre).get(id_exp) or {}
    famille = entree.get("famille_compteur") or FAMILLES_HISTORIQUES.get(id_exp, "trading")
    _verifier_famille(famille)
    return famille


def detail_compteur(chemin: pathlib.Path | None = None,
                    chemin_runs: pathlib.Path | None = None, *,
                    famille: str = "trading") -> dict:
    """Le compteur d'une famille, decompose : dette, mesures, hypotheses encore sans mesure."""
    _verifier_famille(famille)
    # Le journal de runs se deduit du registre quand il n'est pas donne : les deux fichiers
    # vivent cote a cote a la racine par construction. Sans cette ligne, un registre isole
    # (un test, une copie de travail) lirait quand meme le journal REEL du depot, et
    # compterait des mesures qui ne correspondent a aucune de ses hypotheses.
    if chemin_runs is None and chemin is not None:
        chemin_runs = chemin.parent / JOURNAL_RUNS.name
    runs = runs_journalises(chemin_runs)
    registre = etat(chemin)

    def de_la_famille(id_exp: str | None) -> bool:
        return famille_de(id_exp, registre=registre) == famille

    mesures = {e["run_id"] for e in runs
               if e.get("run_id") and de_la_famille(e.get("experience"))}
    deja_mesurees = {e.get("experience") for e in runs if e.get("experience")}
    en_attente = {i for i in registre if de_la_famille(i)} - deja_mesurees
    dette = DETTE_INITIALE[famille]
    return {"famille": famille, "dette": dette, "mesures": len(mesures),
            "en_attente": len(en_attente), "total": dette + len(mesures) + len(en_attente)}


def compteur(chemin: pathlib.Path | None = None,
             chemin_runs: pathlib.Path | None = None, *, famille: str = "trading") -> int:
    """Le nombre d'essais cumules d'une famille, dette initiale comprise. Jamais remis a zero.

    **Deux familles depuis le 23/10 (Jonas)** : `trading` (par defaut, celle qui porte la
    dette de 30 et que la batterie applique aux candidates du moteur) et `invest`. Un essai
    ne compte que dans la famille de son experience (`famille_de`).

    **Arbitrage A1, tranche par Jonas le 2026-08-20 : N porte les MESURES, pas les
    hypotheses.** Jusque-la, N valait 30 + le nombre d'hypotheses preenregistrees. Tant
    qu'il y avait une candidate par hypothese les deux nombres coincidaient ; l'atelier
    casse l'egalite — dix candidates sous R7, c'etait dix tests et un seul point de
    compteur, donc des seuils S1/S2 trop genereux et des verdicts trop flatteurs.

    Un essai est desormais l'un ou l'autre, jamais compte deux fois :

        - une MESURE reellement effectuee (un run distinct de `RUNS.jsonl`) ;
        - une hypothese preenregistree dont aucune mesure n'existe encore — elle a
          consomme un droit de regard, et le compter d'avance est le sens conservateur.

    La formule est monotone : elle ne peut que croitre, et elle vaut **36 le jour du
    changement**, exactement ce que valait l'ancienne. Les trois verdicts du 19/08 ont donc
    ete rendus au bon N — on ne reecrit rien, ce qui etait l'objection principale a (b)
    dans `DECISIONS.md` § A1. Ce qui change commence au premier lot de l'atelier : dix
    candidates sous une meme hypothese comptent desormais pour dix.

    Limite residuelle assumee : une mesure qui ne passe pas par `enregistrer_run` reste
    invisible ici. C'est pourquoi `scripts/mesurer.py` journalise depuis le 20/08 lui aussi.
    """
    return detail_compteur(chemin, chemin_runs, famille=famille)["total"]


def compteur_total(chemin: pathlib.Path | None = None,
                   chemin_runs: pathlib.Path | None = None) -> int:
    """La somme des deux familles — pour l'affichage, jamais pour juger une candidate."""
    return sum(compteur(chemin, chemin_runs, famille=f) for f in FAMILLES)


def n_essais_pour(id_exp: str, chemin: pathlib.Path | None = None) -> int:
    """Le N qui juge une experience : le compteur de SA famille."""
    return compteur(chemin, famille=famille_de(id_exp, chemin))


def enregistrer_run(run_id: str, id_experience: str, candidate: str, empreinte: str,
                    issue: str = "", chemin: pathlib.Path | None = None) -> None:
    """Journalise une mesure REELLEMENT effectuee. Append-only, hors de `data/`.

    Pourquoi ce journal existe depuis le 19/08, alors que `compteur()` semblait suffire :
    le compteur compte les HYPOTHESES preenregistrees, pas les mesures. Tant qu'il y avait
    une candidate par hypothese, les deux nombres etaient egaux. L'atelier casse cette
    egalite — dix candidates sous la meme hypothese R7, c'est dix tests et un seul point de
    compteur. L'ecart est exactement la quantite de p-hacking qu'un banc rapide rend
    possible sans qu'elle se voie.

    Depuis l'arbitrage A1 (20/08), ce journal ne mesure plus l'ecart : il **porte N**.
    Chaque ligne ecrite ici durcit S1 et S2 pour toutes les candidates suivantes. C'est le
    prix d'une mesure, et c'est ce qui permet de lancer l'atelier en serie sans que la
    batterie perde son sens.

    Il vit a la RACINE, pas dans `data/` : `data/` est jetable (invariant n° 7), et un
    compteur qu'un nettoyage remet a zero est un compteur qui ment.
    """
    chemin = chemin or JOURNAL_RUNS
    entree = {"run_id": run_id, "experience": id_experience, "candidate": candidate,
              "empreinte": empreinte, "issue": issue,
              "date": datetime.now(UTC).isoformat()}
    try:
        _ajouter(entree, chemin)
    except ProtocoleError as exc:
        # Un journal qui ne s'ecrit pas ne doit pas faire perdre une mesure qui, elle, a
        # tourne. On le dit fort, on ne tue pas le run.
        log.warning("run %s non journalise : %s", run_id, exc)


def runs_journalises(chemin: pathlib.Path | None = None) -> list[dict]:
    return _lignes(chemin or JOURNAL_RUNS)


def compteur_runs(chemin: pathlib.Path | None = None) -> int:
    """Le nombre de mesures distinctes reellement effectuees. A comparer a `compteur()`."""
    return len({e["run_id"] for e in runs_journalises(chemin) if e.get("run_id")})


def marquer_mesuree(id_exp: str, run_id: str, issue: str,
                    chemin: pathlib.Path | None = None) -> dict | None:
    """T10 — dit au registre qu'une mesure a eu lieu, sans CLORE l'experience.

    Le statut `mesure` existait dans `STATUTS` depuis l'ouverture du registre et rien ne le
    posait jamais : `pipeline` ecrivait son verdict dans `data/runs/` et `RUNS.jsonl`, donc
    `EXPERIMENTS.jsonl` continuait d'annoncer `preenregistre` une hypothese deja mesuree.
    R2 l'a montre le 19/08 — infirmee, et toujours affichee comme en attente.

    Pourquoi `mesure` et non `clos` : une hypothese se clot quand on decide qu'elle est
    finie, pas quand un run tourne. Sous une meme hypothese, l'atelier en mesure dix ; clore
    a la premiere interdirait les neuf autres, ou obligerait a rouvrir a chaque fois. La
    cloture reste un geste explicite (`clore()`), pris en fin de lot.

    Ne fait jamais echouer le run appelant : une mesure qui a tourne ne doit pas etre
    perdue parce que son registre est en lecture seule.
    """
    chemin = chemin or REGISTRE
    try:
        origine = exiger(id_exp, chemin)
    except ProtocoleError as exc:
        log.warning("'%s' non marquee mesuree : %s", id_exp, exc)
        return None
    if origine.get("statut") in ("clos", "abandonne"):
        return None
    entree = {"id": id_exp, "date": datetime.now(UTC).date().isoformat(),
              "statut": "mesure", "dernier_run": run_id, "derniere_issue": issue,
              "n_essais_cumules": n_essais_pour(id_exp, chemin)}
    try:
        _ajouter(entree, chemin)
    except ProtocoleError as exc:
        log.warning("'%s' non marquee mesuree : %s", id_exp, exc)
        return None
    return entree


def preenregistrer(id_exp: str, hypothese: str, metrique_primaire: str,
                   regle_de_decision: dict, *, split_autorise: str = "train",
                   issue_attendue: str = "", mde_attendu: float | None = None,
                   famille_taille: int | None = None, deja_connu: str = "",
                   famille_compteur: str = "trading",
                   chemin: pathlib.Path | None = None, **extra) -> dict:
    """Ajoute une experience au registre. Refuse d'ecraser un id deja preenregistre.

    `deja_connu` n'est pas decoratif : c'est la ou l'on ecrit ce qu'on avait DEJA regarde au
    moment de preenregistrer. Un preenregistrement redige apres avoir vu les resultats et
    qui ne le dit pas est pire que pas de preenregistrement du tout.

    `famille_compteur` dit quel compteur l'essai fait monter : `trading` par defaut, `invest`
    pour un test d'exposition long terme (TI1, T1A). Il est ecrit dans la ligne, toujours.
    """
    _verifier_famille(famille_compteur)
    chemin = chemin or REGISTRE
    existant = etat(chemin).get(id_exp)
    if existant and existant.get("statut") == "preenregistre":
        raise ProtocoleError(f"'{id_exp}' est deja preenregistre — ne pas le reecrire. "
                             "Pour le clore, utiliser clore().")
    entree = {"id": id_exp, "date": datetime.now(UTC).date().isoformat(),
              "statut": "preenregistre", "hypothese": hypothese,
              "metrique_primaire": metrique_primaire,
              "regle_de_decision": regle_de_decision, "split_autorise": split_autorise,
              "issue_attendue": issue_attendue, "mde_attendu": mde_attendu,
              "famille_taille": famille_taille, "deja_connu": deja_connu,
              "famille_compteur": famille_compteur,
              "n_essais_cumules": (compteur(chemin, famille=famille_compteur)
                                   + (0 if existant else 1)), **extra}
    _ajouter(entree, chemin)
    log.info("experience '%s' preenregistree (%s, essai cumule n° %s)",
             id_exp, famille_compteur, entree["n_essais_cumules"])
    return entree


def amender(id_exp: str, raison: str, chemin: pathlib.Path | None = None,
            **champs) -> dict:
    """Modifie un preenregistrement AVANT mesure, en laissant la trace du changement.

    Un preenregistrement qu'on ne peut pas amender est un preenregistrement qu'on
    contourne : quand la donnee necessaire manque, la tentation est d'ecrire un protocole
    different et de ne rien dire. On prefere donc un amendement DATE, MOTIVE, et conserve a
    cote de l'original — la ligne d'origine reste dans le fichier, et la comparaison des
    deux est justement ce qui permet de juger si l'amendement etait de bonne foi.

    Refuse d'amender une experience deja close : a ce moment-la, ce n'est plus un
    amendement, c'est une reecriture du resultat.
    """
    chemin = chemin or REGISTRE
    dernier = etat(chemin).get(id_exp)
    # `mesure` fait partie de la liste depuis le 20/08 : le statut n'etait pose par rien
    # avant `marquer_mesuree()`, donc amender apres une mesure passait sans que le registre
    # puisse le savoir. C'est exactement ce que cette fonction dit ne pas vouloir permettre.
    if dernier and dernier.get("statut") in ("mesure", "clos", "abandonne"):
        raise ProtocoleError(f"'{id_exp}' est {dernier['statut']} : on n'amende pas "
                             "un preenregistrement apres avoir vu le resultat")
    origine = exiger(id_exp, chemin)
    entree = {**origine, **champs, "id": id_exp,
              "date": datetime.now(UTC).date().isoformat(), "statut": "preenregistre",
              "amendement": raison,
              "amende_depuis": origine.get("date")}
    _ajouter(entree, chemin)
    log.info("experience '%s' amendee : %s", id_exp, raison)
    return entree


def clore(id_exp: str, verdict: str, resultat: str, *, statut: str = "clos",
          chemin: pathlib.Path | None = None, **extra) -> dict:
    """Ferme une experience. Le preenregistrement d'origine reste dans le fichier."""
    chemin = chemin or REGISTRE
    if statut not in STATUTS:
        raise ProtocoleError(f"statut inconnu : {statut} (connus : {STATUTS})")
    origine = exiger(id_exp, chemin)
    entree = {"id": id_exp, "date": datetime.now(UTC).date().isoformat(), "statut": statut,
              "verdict": verdict, "resultat": resultat,
              "conforme_a_l_issue_attendue": verdict == origine.get("issue_attendue"),
              "n_essais_cumules": origine.get("n_essais_cumules"), **extra}
    _ajouter(entree, chemin)
    log.info("experience '%s' close : %s", id_exp, verdict)
    return entree


def _ajouter(entree: dict, chemin: pathlib.Path) -> None:
    try:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise ProtocoleError(f"ecriture du registre impossible : {exc}") from exc
