"""Onglet Sentiment (DS2, 28/11) : ce qui se teste sans base vivante.

Aucune connexion reelle : la base DS2 est une source vivante (regle du 25/10). On teste la
lecture du fichier de connexion, les gardes sur les parametres, le solde net et le repli
« DS2 non branche ».
"""

from __future__ import annotations

import pytest

from beta.rapport import sentiment


def test_lire_env_garde_les_seules_cles_libpq(tmp_path):
    f = tmp_path / "ds2.env"
    f.write_text("# commentaire\nPGHOST=127.0.0.1\nPGPORT=5433\nPGPASSWORD='secret'\n"
                 "AUTRE=x\nligne sans egal\n\nPGDATABASE=\"ds2\"\n", encoding="utf-8")
    assert sentiment.lire_env(f) == {"PGHOST": "127.0.0.1", "PGPORT": "5433",
                                     "PGPASSWORD": "secret", "PGDATABASE": "ds2"}


def test_sans_fichier_de_connexion_l_onglet_dit_non_branche(tmp_path, monkeypatch):
    monkeypatch.setenv("BETA_DS2_ENV", str(tmp_path / "absent.env"))
    vue = sentiment.vue({})
    assert vue["branche"] is False
    assert "absent.env" in vue["message"]
    assert sentiment.detail({"groupe": ["BTC"]})["branche"] is False


def test_base_injoignable_dit_non_branche(tmp_path, monkeypatch):
    pytest.importorskip("psycopg")
    f = tmp_path / "ds2.env"
    # Port 1 : rien n'y ecoute, la connexion echoue tout de suite.
    f.write_text("PGHOST=127.0.0.1\nPGPORT=1\nPGDATABASE=x\nPGUSER=x\nPGPASSWORD=x\n",
                 encoding="utf-8")
    monkeypatch.setenv("BETA_DS2_ENV", str(f))
    vue = sentiment.vue({})
    assert vue["branche"] is False
    assert "injoignable" in vue["message"]


@pytest.mark.parametrize("groupe", ["", "x;drop", "a b", "' or 1=1", "x" * 30])
def test_detail_refuse_un_groupe_invalide(groupe):
    with pytest.raises(ValueError):
        sentiment.detail({"groupe": [groupe]})


def test_detail_refuse_un_par_inconnu():
    with pytest.raises(ValueError):
        sentiment.detail({"par": ["source"], "groupe": ["BTC"]})


def test_param_prend_la_premiere_valeur_de_parse_qs():
    assert sentiment._param({"g": ["BTC", "ETH"]}, "g") == "BTC"
    assert sentiment._param({"g": []}, "g", "def") == "def"
    assert sentiment._param({}, "g", "def") == "def"
    assert sentiment._param({"g": "SOL"}, "g") == "SOL"


def test_solde_net_compte_haussiers_moins_baissiers_sur_les_articles():
    ligne = {"n_24h": 0, "haussiers_24h": 0, "baissiers_24h": 0,
             "n_7j": 10, "haussiers_7j": 6, "baissiers_7j": 1,
             "n_30j": 4, "haussiers_30j": 0, "baissiers_30j": 4}
    sentiment._soldes(ligne)
    assert ligne["solde_24h"] is None              # aucun article : pas de zero invente
    assert ligne["solde_7j"] == pytest.approx(0.5)
    assert ligne["solde_30j"] == pytest.approx(-1.0)


def test_requetes_n_ecrivent_rien():
    """Le module ne contient que des SELECT : un INSERT/UPDATE glisse ici serait une faute."""
    import re
    textes = [v for k, v in vars(sentiment).items() if k.startswith("SQL_")]
    assert textes
    for sql in textes:
        assert not re.search(r"\b(insert|update|delete|drop|alter|create|grant|truncate)\b",
                             sql, flags=re.IGNORECASE), sql
