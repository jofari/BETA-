"""Preenregistrement de MOMENTUM30_BTC - momentum trente jours sur le BTC, exposition long-only.

    /root/venvs/arit/bin/python scripts/preenregistrer_momentum30_btc.py

Ecrit la ligne au registre (famille invest, un essai) avec les empreintes du texte du
preenregistrement et du moteur : `scripts/mesurer_momentum30_btc.py` refuse de tourner si
l'une a change.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.momentum30_btc import moteur    # noqa: E402
from beta.protocole import experiences    # noqa: E402

SPEC = RACINE / "MOMENTUM30_BTC" / "PREENREGISTREMENT.md"
CODE = RACINE / "beta" / "momentum30_btc" / "moteur.py"


def empreinte(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


REGLE = {
    "confirmee": "Sharpe_strategie > Sharpe_hold ET CAGR_strategie >= CAGR_hold ET MDD_strategie "
                 "moins profond que MDD_hold, ET p retenue des deux nulls (decalage circulaire, "
                 "melange des segments ; Sharpe ; B = 1000 ; p = la plus grande) < 0,05",
    "indecidable": "les trois conditions vraies ET 0,05 <= p retenue < 0,20, ou p incalculable",
    "infirmee": "une des trois conditions fausse, ou p retenue >= 0,20",
    "verdict_par_le_programme": "scripts/mesurer_momentum30_btc.py applique moteur.verdict et "
                                "clot l'experience lui-meme",
    "suite_si_confirmee": "aucun passage au reel ; paper BTC et/ou ouverture unique du hold-out, "
                          "decision de Jonas ; sans relecture de Jonas = exploration",
}

if __name__ == "__main__":
    e = experiences.preenregistrer(
        moteur.ID_EXPERIENCE,
        "Sur le perpetuel BTC/USDT Binance en quotidien, une exposition long-only valant 1 quand "
        "close(t)/close(t-30)-1 > 0 et 0 sinon, decidee a la cloture du jour t et appliquee au "
        "rendement du jour t+1, bat le buy-and-hold du meme perpetuel sur les rendements du "
        "09/10/2019 au 31/12/2024, tous couts deduits (6 pb par bascule, funding paye par tout "
        "le long, cash au DFF), en Sharpe ET en CAGR, avec un drawdown maximal moins profond, et "
        "son placement dans le temps bat les deux nulls du test invest (p retenue < 0,05).",
        "Sharpe quotidien net de rf x racine(365), CAGR base 365 et MDD de la strategie contre "
        "ceux du hold du perpetuel BTC (meme periode, meme funding) ; p retenue des nulls sur "
        "le Sharpe (beta.invest.nulls, B = 1000, graine 0)",
        REGLE,
        split_autorise="train",
        issue_attendue="infirmee",
        famille_taille=1,
        famille_compteur="invest",
        n_configurations=1,
        deja_connu=(
            "ARIT 05/09/2026 (research/pertinence_donnees_2026-09-05) : long-only quotidien, signe "
            "du rendement sur L jours, 5 pb par bascule, SANS funding, 2019-09 -> 2026-09 (hold-out "
            "de BETA inclus) : Sharpe BTC L14 1,01 / L30 1,00 / L60 0,88 contre 0,55 pour le hold ; "
            "train < 2023 1,03, 2023+ 0,98. L = 30 fixe AVANT ce test par l'idee I16 (11/09). "
            "BETA invest : TI1 momentum BTC 126 j seul = hasard ; T1J/T1F MOM126 et SMA200 sur BTC "
            "non solides ; VC3/VC5 confirmees avec momentum 126 j parmi 5 votes en allocation. "
            "BETA trading : 9 hypotheses contrariennes infirmees, aucune continuation mesuree. "
            "Litterature verifiee le 10/11 : Moskowitz-Ooi-Pedersen 2012 (pour), Liu-Tsyvinski "
            "2021 (pour), Grobys-Sapkota 2019 (contre). Regarde avant le gel sans rendement "
            "calcule : couverture des series, dates, moyenne du funding du train (0,0134 %/8 h). "
            "Aucun chiffre de la strategie, du hold ni du temoin calcule avant le gel."),
        decide_par="Claude, 2026-11-10, a la demande de Jonas (« theorise et teste une strategie "
                   "rentable sur le BTC ») ; hypothese et regles = proposition de Claude, relecture "
                   "de Jonas en attente ; nuit entre gel et lancement sautee a sa demande",
        derive_de="I16 (11/09/2026) ; ARIT research 05/09/2026",
        regles={"actif": "BTC perpetuel Binance, lake 1d", "lookback_jours": 30,
                "periode_rendements": "2019-10-09 -> 2024-12-31 (1910 jours), train seulement",
                "frais_pb_par_cote": 6.0, "funding": "reel, paye par tout le long, 3 reglements/jour",
                "cash": "DFF du dernier jour <= D-1", "nulls": "circulaire + segments, B=1000, graine 0",
                "spec": str(SPEC.relative_to(RACINE)), "code": str(CODE.relative_to(RACINE))},
        empreintes={"spec": empreinte(SPEC), "code": empreinte(CODE)},
    )
    print(f"{e['id']} preenregistree (famille {e['famille_compteur']}) - essai cumule n deg "
          f"{e['n_essais_cumules']} ; empreintes spec {e['empreintes']['spec']} code "
          f"{e['empreintes']['code']}")
    print(f"compteur invest : {experiences.compteur(famille='invest')}")
