"""Preenregistrement de MOMENTUM30_BTC_GARDE - momentum trente jours sur le BTC avec garde de baisse.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/preenregistrer_momentum30_btc_garde.py

Ecrit la ligne au registre (famille invest, un essai) avec les empreintes du texte du
preenregistrement, du moteur de la garde et du moteur de base qu'il reprend :
`scripts/mesurer_momentum30_btc_garde.py` refuse de tourner si l'une a change.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.momentum30_btc_garde import moteur    # noqa: E402
from beta.protocole import experiences          # noqa: E402

SPEC = RACINE / "MOMENTUM30_BTC_GARDE" / "PREENREGISTREMENT.md"
CODE = RACINE / "beta" / "momentum30_btc_garde" / "moteur.py"
CODE_BASE = RACINE / "beta" / "momentum30_btc" / "moteur.py"


def empreinte(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


REGLE = {
    "confirmee": "(a) Sharpe_garde > Sharpe_hold ET (b) CAGR_garde >= CAGR_hold ET (c) MDD_garde moins "
                 "profond que MDD_hold ET (d) MDD_garde moins profond que MDD du momentum sans garde ET "
                 "(e) Sharpe_garde >= Sharpe du momentum sans garde, ET p retenue des deux nulls "
                 "(decalage circulaire, melange des segments ; Sharpe ; B = 1000 ; p = la plus grande) < 0,05",
    "indecidable": "les cinq conditions vraies ET 0,05 <= p retenue < 0,20, ou p incalculable",
    "infirmee": "une des cinq conditions fausse, ou p retenue >= 0,20",
    "verdict_par_le_programme": "scripts/mesurer_momentum30_btc_garde.py applique moteur.verdict et "
                                "clot l'experience lui-meme",
    "suite_si_confirmee": "aucun passage au reel ; relecture de Jonas (sinon exploration), puis paper BTC "
                          "et/ou ouverture unique du hold-out, decision de Jonas",
}

if __name__ == "__main__":
    e = experiences.preenregistrer(
        moteur.ID_EXPERIENCE,
        "Sur le perpetuel BTC/USDT Binance en quotidien, l'exposition du momentum trente jours de "
        "MOMENTUM30_BTC coupee par une garde de baisse de 20 % (sortie quand la cloture tombe 20 % "
        "sous le plus haut de l'episode investi, retour seulement au signal neuf suivant) bat le "
        "buy-and-hold du meme perpetuel sur les rendements du 09/10/2019 au 31/12/2024, tous couts "
        "deduits, en Sharpe, en CAGR et en drawdown maximal, a un drawdown maximal moins profond que "
        "le meme momentum sans garde et un Sharpe au moins egal au sien, et son placement dans le "
        "temps bat les deux nulls du test invest (p retenue < 0,05).",
        "Sharpe quotidien net de rf x racine(365), CAGR base 365 et MDD de la strategie contre ceux du "
        "hold du perpetuel BTC et du momentum trente jours sans garde (meme periode, memes couts) ; "
        "p retenue des nulls sur le Sharpe (beta.invest.nulls, B = 1000, graine 0)",
        REGLE,
        split_autorise="train",
        issue_attendue="infirmee",
        famille_taille=1,
        famille_compteur="invest",
        n_configurations=1,
        deja_connu=(
            "MOMENTUM30_BTC mesuree le 10/11 sur EXACTEMENT cette periode : CONFIRMEE, Sharpe 1,16 / "
            "CAGR +55 % / MDD -47 % contre hold 0,80 / +38 % / -79 %, p retenue 0,027 ; tableaux par "
            "annee et sous-periodes lus ; drawdowns episode par episode NON calcules, le seuil de 20 % "
            "n'en vient pas (budget -25 % des voies C moins 5 points d'ecart d'une journee). Diagnostic "
            "de la veille des voies C du 19/11. Connaissance generale de l'histoire du BTC (mars 2020, "
            "mai 2021, 2022), nommee. Litterature verifiee le 19/11 : Kaminski-Lo 2014 (contre sauf "
            "inertie), Han-Zhou-Zhu 2014 (pour, avant frais, actions). Aucun chiffre de cette strategie "
            "ni de ses variantes calcule avant le gel. EXPLORATION : periode deja vue par MOMENTUM30_BTC."),
        decide_par="Claude, 2026-11-19, a la demande de Jonas (« je te lance un backtest de cette theorie, "
                   "entre-la dans BETA en candidate invest ») ; hypothese, regles et seuil = proposition de "
                   "Claude ; nuit entre gel et lancement sautee ; relecture de Jonas en attente",
        derive_de="MOMENTUM30_BTC (10/11/2026) ; I18 et I20 (19/11/2026) ; diagnostic de la veille du 19/11",
        regles={"actif": "BTC perpetuel Binance, lake 1d", "lookback_jours": moteur.LOOKBACK,
                "seuil_garde": moteur.SEUIL_GARDE,
                "periode_rendements": "2019-10-09 -> 2024-12-31 (1910 jours), train seulement",
                "frais_pb_par_cote": moteur.KAPPA_PB, "funding": "reel, paye par tout le long",
                "cash": "DFF du dernier jour <= D-1", "nulls": "circulaire + segments, B=1000, graine 0",
                "spec": str(SPEC.relative_to(RACINE)), "code": str(CODE.relative_to(RACINE)),
                "code_base": str(CODE_BASE.relative_to(RACINE))},
        empreintes={"spec": empreinte(SPEC), "code": empreinte(CODE), "code_base": empreinte(CODE_BASE)},
    )
    print(f"{e['id']} preenregistree (famille {e['famille_compteur']}) - essai cumule n deg "
          f"{e['n_essais_cumules']} ; empreintes {e['empreintes']}")
    print(f"compteur invest : {experiences.compteur(famille='invest')}")
