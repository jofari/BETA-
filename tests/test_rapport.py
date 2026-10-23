"""Tests du dashboard : serialisation, confinement du statique, coherence HTML/CSS/JS.

Le piege principal ici est la SERIALISATION. Les tables portent des NaN (un trade sans stop
retrouve), des Infinity (un profit factor sans perte) et des Timestamp — dont aucun n'est du
JSON valide. `json.dumps` accepte pourtant NaN et Infinity par defaut et produit un document
que le navigateur REFUSE : la page reste vide, sans erreur cote serveur. D'ou un test qui
verifie non pas que ca serialise, mais que le texte produit est du JSON strict.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

import pandas as pd
import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.rapport import serveur  # noqa: E402

WEB = RACINE / "beta" / "rapport" / "web"


# --- serialisation ---------------------------------------------------------------------

def test_propre_neutralise_ce_que_json_refuse():
    assert serveur._propre(float("nan")) is None
    assert serveur._propre(float("inf")) is None
    assert serveur._propre(float("-inf")) is None
    assert serveur._propre(pd.NaT) is None
    assert serveur._propre(pd.Timestamp("2024-01-01", tz="UTC")).startswith("2024-01-01")
    assert serveur._propre(3) == 3
    assert serveur._propre(True) is True


def test_propre_arrondit_les_flottants():
    assert serveur._propre(1 / 3) == pytest.approx(0.333333)


def test_table_vide():
    assert serveur._table(pd.DataFrame()) == []
    assert serveur._table(None) == []


def test_table_neutralise_les_nan():
    df = pd.DataFrame({"a": [1.0, float("nan")], "b": ["x", None]})
    assert serveur._table(df) == [{"a": 1.0, "b": "x"}, {"a": None, "b": None}]


# Deux routes exigent un parametre. On le leur fournit, ou on saute la route : la tester
# sans son parametre ne verifierait que le message d'erreur, pas la serialisation.
def _params(route: str) -> dict | None:
    if route == "/api/run":
        from beta.rapport import runs
        liste = runs.liste()
        return {"id": [liste[0]["run_id"]]} if liste else None
    if route == "/api/invest/run":
        from beta.rapport import invest
        liste = invest.vue()["runs"]
        return {"id": [liste[0]["run_id"]]} if liste else None
    if route == "/api/candidate":
        from beta.moteur import registre
        modules = sorted(registre.toutes())
        return {"module": [modules[0]]} if modules else None
    return {}


@pytest.mark.parametrize("route", list(serveur.ROUTES))
def test_chaque_route_produit_du_json_strict(route):
    """`json.dumps` accepte NaN par defaut ; le navigateur, non. On teste le texte produit."""
    params = _params(route)
    if params is None:
        pytest.skip(f"{route} demande un objet qui n'existe pas encore")
    texte = json.dumps(serveur.ROUTES[route](params), ensure_ascii=False)
    assert "NaN" not in texte
    assert "Infinity" not in texte
    json.loads(texte, parse_constant=_refuser)      # releverait sur NaN/Infinity


def _refuser(constante):
    raise AssertionError(f"constante non-JSON dans la reponse : {constante}")


# --- coherence des fichiers web ----------------------------------------------------------

def test_chaque_id_utilise_par_le_js_existe_dans_le_html():
    js = "\n".join((WEB / f).read_text(encoding="utf-8")
                    for f in ("app.js", "fiche.js", "invest.js"))
    html = (WEB / "index.html").read_text(encoding="utf-8")
    utilises = set(re.findall(r'[$q]\("#([^"]+)"\)', js))
    declares = set(re.findall(r'id="([^"]+)"', html))
    assert utilises and not (utilises - declares)


def test_aucune_ressource_externe():
    """Zero CDN : la page doit fonctionner hors ligne, comme ALPHA."""
    for fichier in ("index.html", "app.js", "fiche.js", "atelier.js",
                    "comparaison.js", "forward.js", "invest.js", "style.css"):
        contenu = (WEB / fichier).read_text(encoding="utf-8")
        for motif in ("http://", "https://"):
            for occurrence in re.findall(rf"{motif}[^\s\"')]+", contenu):
                # Seules les URL de namespace SVG et les commentaires sont tolerees.
                assert "w3.org" in occurrence, f"{fichier} : ressource externe {occurrence}"


# Les routes POST ne sont pas dans `ROUTES` (qui est la table des GET) : elles sont
# aiguillees dans `do_POST`. Les lister ici est ce qui fait echouer le test quand on ajoute
# un fetch cote client sans la route qui va avec — l'oubli le plus facile du projet.
ROUTES_POST = {"/api/action", "/api/atelier", "/api/idee"}


def test_toutes_les_routes_du_js_existent_cote_serveur():
    lisibles = set(serveur.ROUTES) | set(serveur.ROUTES_SERVEUR) | ROUTES_POST
    for fichier in sorted(WEB.glob("*.js")):
        js = fichier.read_text(encoding="utf-8")
        for route in re.findall(r'fetch\("(/api/[^"?]+)', js):
            assert route in lisibles, f"{fichier.name} appelle {route}, absent du serveur"


def test_chaque_route_post_est_bien_aiguillee():
    """Une route POST declaree ici mais absente de `do_POST` rendrait 404 sans qu'on le voie."""
    import inspect
    source = inspect.getsource(serveur.Handler.do_POST) + inspect.getsource(serveur.Handler)
    for route in ROUTES_POST:
        assert f'"{route}"' in source, f"{route} n'est aiguillee nulle part dans do_POST"


# --- confinement du statique ---------------------------------------------------------------

def test_le_dossier_web_contient_bien_les_trois_fichiers():
    for nom in ("index.html", "app.js", "style.css"):
        assert (WEB / nom).is_file()


def test_port_distinct_d_alpha():
    """ALPHA occupe 7373 : partager le port ferait echouer le second demarre, en silence."""
    assert serveur.PORT != 7373


# --- efficacite OOS/IS et ruine (bugs du 15/10) -------------------------------------------

from beta.rapport import runs as vue_runs  # noqa: E402
from beta.stats import montecarlo  # noqa: E402
from beta.stats.batterie import SEUIL_EFFICACITE_WF  # noqa: E402


def _ancre(is_, oos):
    return {"is_moyen": is_, "oos_moyen": oos,
            "efficacite": oos / is_ if is_ else float("nan")}


def test_efficacite_is_negatif_donne_na_et_pas_un_ratio():
    # IS = -0,10 et OOS = -0,15 : le ratio brut vaut 1,5 et passerait pour excellent.
    e = vue_runs._efficacite(_ancre(-0.10, -0.15))
    assert e["valeur"] is None
    assert e["ton"] == "muted"


@pytest.mark.parametrize("is_", [0.0, -0.01, float("nan")])
def test_efficacite_na_des_que_is_n_est_pas_positif(is_):
    e = vue_runs._efficacite({"is_moyen": is_, "oos_moyen": 0.05, "efficacite": 3.0})
    assert e["valeur"] is None and e["ton"] == "muted"


def test_efficacite_oos_negatif_avec_is_positif_est_rouge():
    e = vue_runs._efficacite(_ancre(0.10, -0.02))
    assert e["valeur"] == pytest.approx(-0.2)
    assert e["ton"] == "critical"


def test_efficacite_verte_seulement_au_dessus_du_seuil_de_la_config():
    assert vue_runs._efficacite(_ancre(0.10, 0.10 * SEUIL_EFFICACITE_WF))["ton"] == "good"
    assert vue_runs._efficacite(_ancre(0.10, 0.10 * SEUIL_EFFICACITE_WF * 0.99))["ton"] \
        == "critical"
    assert vue_runs._efficacite(_ancre(0.10, 0.08))["seuil"] == SEUIL_EFFICACITE_WF


def _equity_qui_passe_sous_zero():
    ts = pd.date_range("2024-01-01", periods=6, freq="D", tz="UTC")
    courbe = pd.Series([100_000.0, 110_000.0, 40_000.0, -10_000.0, -50_000.0, 5_000.0])
    sommet = courbe.cummax()
    return pd.DataFrame({"ts": ts, "equity": courbe,
                         "drawdown_pct": (courbe / sommet - 1.0) * 100.0})


def test_equity_sous_zero_donne_dd_moins_100_et_date_de_ruine():
    equity = _equity_qui_passe_sous_zero()
    assert equity["drawdown_pct"].min() < -100.0          # le moteur, lui, va au-dela
    courbe = vue_runs._courbe(equity)
    assert min(courbe["drawdown_pct"]) == -100.0
    assert courbe["ruine"]["date"] == "2024-01-04"
    assert courbe["ruine"]["indice"] == 3
    assert vue_runs._dd_affiche(-231.4) == -100.0
    assert vue_runs._dd_affiche(-56.8) == -56.8


def test_pas_de_ruine_si_l_equity_reste_positive():
    equity = _equity_qui_passe_sous_zero().iloc[:3]
    assert vue_runs._courbe(equity)["ruine"] is None


def test_le_point_de_ruine_survit_a_l_echantillonnage():
    # 2 000 points, ruine au point 1 000 : l'echantillon a 600 points peut l'enjamber.
    n = 2_000
    ts = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    valeurs = [1_000.0 - i for i in range(n)]               # touche 0 au point 1 000
    courbe = pd.Series(valeurs)
    equity = pd.DataFrame({"ts": ts, "equity": courbe,
                           "drawdown_pct": (courbe / courbe.cummax() - 1.0) * 100.0})
    ruine = vue_runs._courbe(equity)["ruine"]
    assert ruine["ts"] == ts[1_000].isoformat()
    echantillon = vue_runs._courbe(equity)["ts"]
    assert echantillon[ruine["indice"]] >= ruine["ts"] > echantillon[ruine["indice"] - 1]


def test_une_ruine_apres_le_dernier_point_garde_ne_fait_pas_tomber_la_fiche():
    # 10 000 points, ruine au tout dernier : l'echantillon a 600 points s'arrete avant.
    n = 10_000
    ts = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    courbe = pd.Series([1_000.0] * (n - 1) + [-1.0])
    equity = pd.DataFrame({"ts": ts, "equity": courbe,
                           "drawdown_pct": (courbe / courbe.cummax() - 1.0) * 100.0})
    vue = vue_runs._courbe(equity)
    assert vue["ruine"]["ts"] == ts[-1].isoformat()
    assert vue["ruine"]["indice"] == len(vue["ts"]) - 1


def test_monte_carlo_compte_la_ruine_a_part_sans_toucher_au_reste():
    r = [-30.0, -30.0, -30.0, -30.0, 5.0, 5.0]             # 1 % de risque : -120 % au pire
    res = montecarlo.simuler(r, "permutation", n_tirages=200)
    assert res["p_ruine"] == 1.0                            # la perte totale depasse 100 %
    sain = montecarlo.simuler([1.0, -0.5, 1.0, -0.5], "remise", n_tirages=200)
    assert sain["p_ruine"] == 0.0
    # Le drawdown du moteur n'est pas plafonne : seul l'affichage l'est.
    assert res["drawdown_max_reel_pct"] < -100.0


def test_le_dashboard_recoit_les_deux_compteurs(tmp_path, monkeypatch):
    from beta.protocole import experiences
    monkeypatch.setattr(experiences, "REGISTRE", tmp_path / "exp.jsonl")
    monkeypatch.setattr(experiences, "JOURNAL_RUNS", tmp_path / "RUNS.jsonl")
    experiences.preenregistrer("I1", "h", "m", {"ok": "x"}, famille_compteur="invest")
    d = serveur.donnees_protocole()
    assert d["compteurs"] == {"trading": 30, "invest": 1}
    assert d["compteur"] == 30                 # la tuile historique reste celle du trading actif
