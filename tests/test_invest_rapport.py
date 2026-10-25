"""Test invest — la vue de l'onglet : relit data/test_invest/, ne calcule rien (D3)."""

import html
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from beta.invest import campagne
from beta.protocole import experiences
from beta.rapport import invest, serveur

WEB = pathlib.Path(serveur.__file__).resolve().parent / "web"


def _run(rid="0123456789ab", periode="principale", verdict="hasard"):
    return {"run_id": rid, "statut": "campagne", "calcule_le": "2026-10-20T17:00:00+00:00",
            "libelle": "socle complet · socle", "signal": "complet", "verdict": verdict,
            "config": {"periode": periode, "indicateurs": ["momentum_btc"], "kappa_pb": 10.0,
                       "theta_episode": 0.2, "b": 1000, "graine": 0, "pit": "publication",
                       "nulls": True, "mapping": {"nom": "socle"}},
            "periode": {"nom": periode, "n_jours": 10, "n_episodes": 1},
            "metriques": {"strategie": {"ulcer": 0.2, "mdd": -0.3, "protection": 0.1,
                                        "expo_moyenne": 0.7}},
            "nulls": {"p_retenue": 0.4}, "series": {"v_s": [1.0] * 11}}


@pytest.fixture
def dossier(tmp_path, monkeypatch):
    d = tmp_path / "test_invest"
    monkeypatch.setattr(campagne, "DOSSIER", d)
    return d


def test_vue_sans_rien_de_calcule(dossier):
    v = invest.vue()
    assert v["runs"] == [] and v["campagne"] is None
    assert "scripts/test_invest.py" in v["commande"]


def test_vue_liste_les_runs_sans_leurs_series_et_la_campagne(dossier):
    dossier.mkdir()
    (dossier / "0123456789ab.json").write_text(json.dumps(_run()), encoding="utf-8")
    (dossier / "campagne_TI1.json").write_text(json.dumps({"experience": "TI1"}),
                                               encoding="utf-8")
    v = invest.vue()
    assert v["campagne"] == {"experience": "TI1"}
    (r,) = v["runs"]
    assert r["run_id"] == "0123456789ab" and r["mapping"] == "socle"
    assert r["periode"] == "principale" and r["indicateurs"] == ["momentum_btc"]
    assert r["ulcer"] == 0.2 and r["p_retenue"] == 0.4 and "series" not in r


@pytest.mark.parametrize("mauvais", ["../etc", "0123456789AB", "abc", "campagne_TI1"])
def test_un_identifiant_de_run_invalide_est_refuse(dossier, mauvais):
    with pytest.raises(ValueError):
        invest.run({"id": [mauvais]})


def test_run_introuvable_puis_trouve(dossier):
    with pytest.raises(FileNotFoundError):
        invest.run({"id": ["0123456789ab"]})
    dossier.mkdir()
    (dossier / "0123456789ab.json").write_text(json.dumps(_run()), encoding="utf-8")
    assert invest.run({"id": ["0123456789ab"]})["series"]["v_s"][0] == 1.0


def test_les_routes_de_l_onglet_sont_des_get():
    assert {"/api/invest", "/api/invest/run"} <= set(serveur.ROUTES)


def test_la_liste_ne_relit_un_run_que_s_il_a_change(dossier, monkeypatch):
    dossier.mkdir()
    chemin = dossier / "0123456789ab.json"
    chemin.write_text(json.dumps(_run()), encoding="utf-8")
    lectures = []
    vrai = invest._lire
    monkeypatch.setattr(invest, "_lire", lambda c: lectures.append(c.name) or vrai(c))
    invest.vue()
    invest.vue()
    assert lectures == ["0123456789ab.json"]
    chemin.write_text(json.dumps(_run(verdict="reel")), encoding="utf-8")
    import os
    os.utime(chemin, ns=(1, 2_000_000_000_000_000_000))
    assert invest.vue()["runs"][0]["verdict"] == "reel" and len(lectures) == 2


# --- Les deux compteurs du back-end dans l'onglet (Jonas, 25/10) -----------------------------

@pytest.fixture
def registre(tmp_path, monkeypatch):
    """Un registre isole aux valeurs connues : trading 30 + 1 en attente = 31 ; invest 2 mesures
    (le diagnostic D1 ne compte pas) = 2 ; total 33."""
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "EXPERIMENTS.jsonl")
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    experiences.preenregistrer("T1", "h", "m", {"ok": "x"})
    experiences.preenregistrer("I1", "h", "m", {"ok": "x"}, famille_compteur="invest")
    experiences.preenregistrer("D1", "h", "m", {"ok": "x"}, famille_compteur="invest",
                               diagnostic=True)
    experiences.enregistrer_run("r1", "I1", "c", "e")
    experiences.enregistrer_run("r2", "I1", "c", "e")


def test_la_vue_porte_les_deux_compteurs_du_back_end(dossier, registre):
    compteurs = invest.vue()["compteurs"]
    assert compteurs == [
        {"nom": "experiences.compteur_total", "portee": "global", "valeur": 33},
        {"nom": 'experiences.compteur(famille="invest")', "portee": "invest", "valeur": 2}]
    assert compteurs[0]["valeur"] == experiences.compteur_total()
    assert compteurs[1]["valeur"] == experiences.compteur(famille="invest")


VOTES = ["momentum_btc", "taux_reel_10a", "inflation_anticipee_10a", "nasdaq", "fear_greed"]


def _campagne_minimale(compteur: int) -> dict:
    """Ce que l'en-tete et le bloc campagne de l'onglet lisent, rien de plus."""
    zero = {"ulcer": 0.0, "mdd": 0.0, "protection": 0.0, "cagr": 0.0}
    synthese = {"c1": [], "socle_paliers": zero,
                "c2": {v: {"delta": zero, "lecture": "inutile ou nuisible"} for v in VOTES},
                "c3": {"kappa": {a: dict.fromkeys(VOTES) for a in VOTES},
                       "spearman": {a: dict.fromkeys(VOTES) for a in VOTES}}}
    return {"experience": "TI1", "compteur": compteur, "runs": [], "diagnostic_pit": {},
            "periodes": {"principale": {"debut": "2020-09-14", "fin": "2026-10-20",
                                        "n_jours": 10, "n_episodes": 3,
                                        "puissance_faible": False, "changements_regime": 4,
                                        "synthese": synthese}}}


# Execute le vrai invest.js (et les utilitaires d'app.js qu'il appelle, extraits tels quels)
# contre un faux DOM : ce que l'onglet ECRIT dans l'en-tete, a partir de la vue servie.
HARNAIS = r"""
const fs = require("fs"), vm = require("vm");
const [app, onglet, vue] = process.argv.slice(2).map((p) => fs.readFileSync(p, "utf8"));
const elements = {};
const element = (sel) => elements[sel] ??= { innerHTML: "", textContent: "", hidden: false,
  value: "", addEventListener() {}, insertAdjacentHTML(_, h) { this.innerHTML += h; } };
const ctx = { console,
  document: { querySelector: element, querySelectorAll: () => [], addEventListener() {} },
  fetch: (url) => Promise.resolve({ json: () => Promise.resolve(
    url === "/api/invest" ? JSON.parse(vue) : { erreur: "absent du test" }) }) };
vm.createContext(ctx);
const utilitaires = [app.match(/^const entier = .*$/m)[0],
                     app.match(/^function tuile\([\s\S]*?\n\}/m)[0]];
vm.runInContext(utilitaires.join("\n") + "\n" + onglet + "\nglobalThis.INVEST = INVEST;", ctx);
ctx.INVEST.afficher().then(() => process.stdout.write(element("#invest-entete").innerHTML));
"""


def _tuiles_affichees(vue: dict, tmp_path) -> dict[str, int]:
    (tmp_path / "harnais.js").write_text(HARNAIS, encoding="utf-8")
    (tmp_path / "vue.json").write_text(json.dumps(vue), encoding="utf-8")
    sortie = subprocess.run(["node", str(tmp_path / "harnais.js"), str(WEB / "app.js"),
                             str(WEB / "invest.js"), str(tmp_path / "vue.json")],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    tuile = r'<span class="kpi-value">(.*?)</span>\s*<span class="kpi-label">(.*?)</span>'
    paires = re.findall(tuile, sortie)
    return {html.unescape(libelle): int(re.sub(r"\D", "", valeur)) for valeur, libelle in paires
            if re.search(r"\d", valeur)}


@pytest.mark.skipif(shutil.which("node") is None, reason="node absent : rendu de l'onglet non joue")
def test_l_onglet_affiche_les_valeurs_du_back_end(dossier, registre, tmp_path):
    dossier.mkdir()
    (dossier / f"campagne_{campagne.ID_EXP}.json").write_text(
        json.dumps(_campagne_minimale(117)), encoding="utf-8")
    tuiles = _tuiles_affichees(invest.vue(), tmp_path)
    assert tuiles["experiences.compteur_total"] == experiences.compteur_total() == 33
    assert tuiles['experiences.compteur(famille="invest")'] == \
        experiences.compteur(famille="invest") == 2
    assert tuiles["Test invest 1 – compteur au 20/10/2026"] == 117
