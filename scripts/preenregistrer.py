"""Preenregistre R1 a R6 dans EXPERIMENTS.jsonl. Idempotent : relancer ne reecrit rien.

Ce fichier est le seul endroit du projet ou une hypothese est ECRITE avant d'etre mesuree.
Le lire, c'est savoir ce qu'on cherchait avant d'avoir vu quoi que ce soit — et pouvoir
verifier, dans six mois, qu'aucun seuil n'a bouge entre-temps.

Trois d'entre elles portent une mention `deja_connu` non vide. Ce n'est pas un aveu genant,
c'est l'information la plus importante de la ligne : R1 et R6 viennent de chiffres deja
observes le 18/08, donc leur preenregistrement ne vaut PAS celui d'une hypothese vierge.
Le taire aurait rendu le registre plus flatteur et sans valeur.

    & C:\\Users\\jofar\\venvs\\arit\\Scripts\\python.exe scripts/preenregistrer.py
"""

from __future__ import annotations

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from beta.protocole import experiences          # noqa: E402

log = logging.getLogger("beta.preenregistrer")

# Famille de tests declaree : les six hypotheses forment UNE famille, corrigee ensemble par
# Benjamini-Hochberg. Declarer la taille ici, avant la premiere mesure, est ce qui empeche
# de la reduire plus tard a « celles qui ont marche ».
FAMILLE = 6

HYPOTHESES = [
    {
        "id_exp": "R1",
        "hypothese": "Le trailing stop detruit les shorts : le R moyen d'un short sorti en "
                     "triple barriere fixe est superieur a celui du meme signal sorti avec "
                     "le trailing d'AritV1.",
        "metrique_primaire": "ecart de R moyen (barriere fixe - trailing), shorts seuls",
        "regle_de_decision": {"confirmee": "ecart > 0 ET p <= 0,05 apres BH ET ecart > MDE",
                              "infirmee": "ecart <= 0 ou p > 0,05",
                              "indecidable": "ecart entre 0 et le MDE"},
        "mde_attendu": 1.53,
        "deja_connu": "Signal short brut +0,0637 R contre strategie complete -0,4683 R sur "
                      "la meme periode ; MFE moyen +0,438 R short contre +1,215 R long "
                      "(mesure du 18/08). Le sous-groupe short a ete trouve APRES coup : "
                      "ce preenregistrement ne vaut pas celui d'une hypothese vierge.",
        "issue_attendue": "confirmee",
    },
    {
        "id_exp": "R2",
        "hypothese": "Le retour a la moyenne (z-score du close sur 48 bougies, seuil 2) a "
                     "une esperance en R positive sur l'univers des 6 paires — donc un edge "
                     "structurellement oppose a celui d'AritV1, suiveur de tendance.",
        "metrique_primaire": "R moyen par trade, net de frais et de slippage",
        "regle_de_decision": {"confirmee": "toutes les portes S1-S9 franchies",
                              "infirmee": "une porte executee echoue",
                              "indecidable": "moins de 30 trades ou porte non executee"},
        "mde_attendu": None,
        "deja_connu": "Aucune mesure de mean-reversion n'a ete faite sur ces donnees.",
        "issue_attendue": "indecidable",
    },
    {
        "id_exp": "R3",
        "hypothese": "Le portage (funding des perpetuels) a une esperance positive nette "
                     "de frais, independamment de toute direction de marche.",
        "metrique_primaire": "rendement annualise du portage, net de frais",
        "regle_de_decision": {"confirmee": "rendement net > 0 ET bat le hold ET p <= 0,05",
                              "infirmee": "rendement net <= 0",
                              "indecidable": "donnees de funding indisponibles"},
        "mde_attendu": None,
        "deja_connu": "86 % du profit de MacroFlip venait du portage (source F1). Ce chiffre "
                      "vient d'un autre systeme et d'une autre periode : il motive "
                      "l'hypothese, il ne la soutient pas.",
        "issue_attendue": "indecidable",
        "bloquee_par": "les taux de financement ne sont pas dans le lake (chantier D5)",
    },
    {
        "id_exp": "R4",
        "hypothese": "Les seules variables macro, sans aucune couche technique, suffisent a "
                     "produire une esperance en R positive.",
        "metrique_primaire": "R moyen par trade d'une candidate macro pure",
        "regle_de_decision": {"confirmee": "toutes les portes S1-S9 franchies",
                              "infirmee": "une porte executee echoue",
                              "indecidable": "moins de 30 trades ou features macro absentes"},
        "mde_attendu": None,
        "deja_connu": "Cote ARIT, le veto macro HOSTILE seul n'a jamais ete isole de la "
                      "couche technique — c'est justement ce qui rend la question ouverte.",
        "issue_attendue": "indecidable",
        "bloquee_par": "les features macro ne sont pas dans le lake (chantier D6)",
    },
    {
        "id_exp": "R5",
        "hypothese": "Le spot et le perpetuel de la meme paire ne donnent pas le meme R "
                     "moyen a signal identique — l'ecart, s'il existe, est exploitable.",
        "metrique_primaire": "ecart de R moyen (perp - spot) a signal identique",
        "regle_de_decision": {"confirmee": "ecart != 0, p <= 0,05 apres BH, ecart > MDE",
                              "infirmee": "|ecart| <= MDE",
                              "indecidable": "series spot absentes du lake"},
        "mde_attendu": None,
        "deja_connu": "D1 cote ARIT a ete abandonne parce qu'il mesurait l'alternance "
                      "bull/bear et non un edge. La question est reposee proprement ici, "
                      "avec le hold-out.",
        "issue_attendue": "indecidable",
        "bloquee_par": "les series spot ne sont pas dans le lake (chantier D7)",
    },
    {
        "id_exp": "R6",
        "hypothese": "Les signaux bloques par news_window ont une esperance en R "
                     "indiscernable de celle des signaux acceptes : la porte la plus active "
                     "du systeme ne filtre rien d'utile.",
        "metrique_primaire": "ecart de R moyen (bloques par news_window - acceptes)",
        "regle_de_decision": {"confirmee": "|ecart| <= MDE (la porte ne discrimine pas)",
                              "infirmee": "ecart < 0 ET p <= 0,05 (la porte protege vraiment)",
                              "indecidable": "moins de 30 signaux dans un des deux groupes"},
        "mde_attendu": None,
        "deja_connu": "news_window bloque 91,75 % de tout ce qui est rejete (756 signaux "
                      "sur 824), mesure du 18/08. Le taux de blocage est connu ; ce que "
                      "valent les signaux bloques ne l'est pas.",
        "issue_attendue": "confirmee",
    },
]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    deja = experiences.etat()
    ecrits = 0
    for entree in HYPOTHESES:
        id_exp = entree["id_exp"]
        if id_exp in deja:
            log.info("%s deja preenregistre le %s — laisse tel quel",
                     id_exp, deja[id_exp].get("date"))
            continue
        experiences.preenregistrer(
            id_exp=id_exp, hypothese=entree["hypothese"],
            metrique_primaire=entree["metrique_primaire"],
            regle_de_decision=entree["regle_de_decision"],
            split_autorise="train", issue_attendue=entree["issue_attendue"],
            mde_attendu=entree["mde_attendu"], famille_taille=FAMILLE,
            deja_connu=entree["deja_connu"],
            **{c: v for c, v in entree.items() if c == "bloquee_par"})
        ecrits += 1
    log.info("%d preenregistrement(s) ajoute(s). Compteur cumule : %d essais.",
             ecrits, experiences.compteur())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
