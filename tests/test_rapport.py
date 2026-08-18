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


@pytest.mark.parametrize("route", list(serveur.ROUTES))
def test_chaque_route_produit_du_json_strict(route):
    """`json.dumps` accepte NaN par defaut ; le navigateur, non. On teste le texte produit."""
    texte = json.dumps(serveur.ROUTES[route]({}), ensure_ascii=False)
    assert "NaN" not in texte
    assert "Infinity" not in texte
    json.loads(texte, parse_constant=_refuser)      # releverait sur NaN/Infinity


def _refuser(constante):
    raise AssertionError(f"constante non-JSON dans la reponse : {constante}")


# --- coherence des fichiers web ----------------------------------------------------------

def test_chaque_id_utilise_par_le_js_existe_dans_le_html():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")
    utilises = set(re.findall(r'\$\("#([^"]+)"\)', js))
    declares = set(re.findall(r'id="([^"]+)"', html))
    assert utilises and not (utilises - declares)


def test_aucune_ressource_externe():
    """Zero CDN : la page doit fonctionner hors ligne, comme ALPHA."""
    for fichier in ("index.html", "app.js", "style.css"):
        contenu = (WEB / fichier).read_text(encoding="utf-8")
        for motif in ("http://", "https://"):
            for occurrence in re.findall(rf"{motif}[^\s\"')]+", contenu):
                # Seules les URL de namespace SVG et les commentaires sont tolerees.
                assert "w3.org" in occurrence, f"{fichier} : ressource externe {occurrence}"


def test_les_trois_routes_du_js_existent_cote_serveur():
    js = (WEB / "app.js").read_text(encoding="utf-8")
    for route in re.findall(r'fetch\("(/api/[^"?]+)', js):
        assert route in serveur.ROUTES, f"le JS appelle {route}, absent du serveur"


# --- confinement du statique ---------------------------------------------------------------

def test_le_dossier_web_contient_bien_les_trois_fichiers():
    for nom in ("index.html", "app.js", "style.css"):
        assert (WEB / nom).is_file()


def test_port_distinct_d_alpha():
    """ALPHA occupe 7373 : partager le port ferait echouer le second demarre, en silence."""
    assert serveur.PORT != 7373
