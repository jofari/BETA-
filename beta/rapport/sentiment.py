"""Onglet « Sentiment » : relit ce que le pipeline DS2 a ecrit (sentiment FinBERT des news).

DS2 est le projet de Jonas (depot `jofari/DS2`) : il classe chaque news de DS1 avec FinBERT,
detecte les actifs cites et ecrit `ds2.clasifications` ; la vue `ds2.v_score_jour` donne son
score par actif et par jour. Ici, RIEN n'est classe ni recalcule a la place de DS2 : on compte
ce qui est en base et on relit sa vue, en lecture seule.

Ce que l'onglet n'est PAS : un signal. Aucun test preregistre ne lie ce sentiment aux prix ;
l'interface le dit en tete de page (invariant n° 4 : rien ne se mesure sans preenregistrement).

Connexion : un fichier `KEY=VALUE` hors depot (defaut `/root/.config/beta/ds2.env`, ou la
variable `BETA_DS2_ENV`), avec les cles libpq habituelles (PGHOST, PGPORT, PGDATABASE, PGUSER,
PGPASSWORD). Le role ne doit avoir que SELECT sur le schema `ds2` et sur `public.news`.
Sans ce fichier, ou sans psycopg, l'onglet dit « DS2 non branche » au lieu d'echouer.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re

log = logging.getLogger("beta.rapport.sentiment")

FICHIER_ENV_DEFAUT = pathlib.Path("/root/.config/beta/ds2.env")
CLES_ADMISES = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "PGSSLMODE")
NOM_ACTIF = re.compile(r"^[A-Za-z0-9_]{1,24}$")
NOM_VERSION = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
FENETRES = {"24h": 1, "7j": 7, "30j": 30}
JOURS_SERIE = 60
ARTICLES_MAX = 40


class NonBranche(Exception):
    """DS2 n'est pas joignable : on le dit dans l'onglet, sans trace d'erreur."""


def fichier_env() -> pathlib.Path:
    return pathlib.Path(os.environ.get("BETA_DS2_ENV") or FICHIER_ENV_DEFAUT)


def lire_env(chemin: pathlib.Path) -> dict:
    """Lit un fichier KEY=VALUE ; ignore les commentaires et toute cle hors libpq."""
    params = {}
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        cle = cle.strip()
        if cle in CLES_ADMISES:
            params[cle] = valeur.strip().strip('"').strip("'")
    return params


def connecter():
    chemin = fichier_env()
    if not chemin.exists():
        raise NonBranche(f"fichier de connexion absent ({chemin})")
    try:
        import psycopg
    except ImportError as exc:                       # pragma: no cover - depend du venv
        raise NonBranche("psycopg n'est pas installe dans le venv de BETA") from exc
    p = lire_env(chemin)
    try:
        return psycopg.connect(
            host=p.get("PGHOST"), port=p.get("PGPORT"), dbname=p.get("PGDATABASE"),
            user=p.get("PGUSER"), password=p.get("PGPASSWORD"),
            sslmode=p.get("PGSSLMODE", "prefer"), connect_timeout=3,
            application_name="beta-web-sentiment",
            options="-c default_transaction_read_only=on -c statement_timeout=15000",
        )
    except psycopg.OperationalError as exc:
        raise NonBranche(f"base DS2 injoignable : {str(exc).strip().splitlines()[0]}") from exc


# ---------- requetes (lecture seule) -----------------------------------------------------------

SQL_VERSIONS = """
    SELECT version_modele, max(modele) AS modele, count(*) AS lignes,
           count(DISTINCT article_id) AS articles, max(date_class) AS derniere_classification
    FROM ds2.clasifications GROUP BY version_modele ORDER BY max(date_class) DESC
"""

SQL_ECHECS = """
    SELECT raison, count(*) AS n FROM ds2.echecs WHERE version_modele = %(v)s
    GROUP BY raison ORDER BY raison
"""

SQL_NEWS = """
    SELECT count(*) AS articles, min(ts_recu) AS premier, max(ts_recu) AS dernier
    FROM public.news
"""

# Un article cite par plusieurs actifs a une ligne par actif, avec le MEME sentiment. Par
# actif, chaque ligne compte ; par marche, un article ne compte qu'une fois (DISTINCT).
SQL_GROUPES = """
    WITH c AS (
        SELECT c.{cle} AS groupe, c.classe_actif, c.article_id, c.sentiment, n.ts_recu
        FROM ds2.clasifications c JOIN public.news n ON n.id = c.article_id
        WHERE c.version_modele = %(v)s
    )
    SELECT groupe, max(classe_actif) AS classe_actif,
           count(DISTINCT article_id) AS total,
           max(ts_recu) AS dernier_article,
           {colonnes}
    FROM c GROUP BY groupe
"""

SQL_SCORE = """
    SELECT {cle} AS groupe, {colonnes}
    FROM ds2.v_score_jour WHERE version_modele = %(v)s GROUP BY {cle}
"""

SQL_SERIE = """
    WITH c AS (
        SELECT c.{cle} AS groupe, c.article_id, c.sentiment,
               date_trunc('day', n.ts_recu AT TIME ZONE 'UTC') AS jour
        FROM ds2.clasifications c JOIN public.news n ON n.id = c.article_id
        WHERE c.version_modele = %(v)s AND c.{cle} = %(g)s
          AND n.ts_recu >= now() - make_interval(days => %(j)s)
    )
    SELECT jour::date AS jour,
           count(DISTINCT article_id) FILTER (WHERE sentiment = 'bullish') AS haussiers,
           count(DISTINCT article_id) FILTER (WHERE sentiment = 'bearish') AS baissiers,
           count(DISTINCT article_id) FILTER (WHERE sentiment = 'neutral') AS neutres
    FROM c GROUP BY jour ORDER BY jour
"""

SQL_SCORE_SERIE = """
    SELECT (jour AT TIME ZONE 'UTC')::date AS jour, sum(score) AS score
    FROM ds2.v_score_jour
    WHERE version_modele = %(v)s AND {cle} = %(g)s
      AND jour >= now() - make_interval(days => %(j)s)
    GROUP BY 1 ORDER BY 1
"""

SQL_ARTICLES = """
    SELECT n.ts_recu, n.source, n.titre, n.url, c.sentiment, c.proba, c.texte_utilise,
           (SELECT string_agg(c2.actif, ' ' ORDER BY c2.actif) FROM ds2.clasifications c2
             WHERE c2.article_id = c.article_id AND c2.version_modele = c.version_modele) AS actifs
    FROM ds2.clasifications c JOIN public.news n ON n.id = c.article_id
    WHERE c.version_modele = %(v)s AND c.{cle} = %(g)s
    ORDER BY n.ts_recu DESC LIMIT %(n)s
"""


def _colonnes_comptes() -> str:
    morceaux = []
    for nom, jours in FENETRES.items():
        borne = f"ts_recu >= now() - interval '{jours} days'"
        morceaux.append(f"count(DISTINCT article_id) FILTER (WHERE {borne}) AS n_{nom}")
        for sens, etiquette in (("bullish", "haussiers"), ("bearish", "baissiers"),
                                ("neutral", "neutres")):
            morceaux.append(f"count(DISTINCT article_id) FILTER (WHERE {borne} AND "
                            f"sentiment = '{sens}') AS {etiquette}_{nom}")
    return ",\n           ".join(morceaux)


def _colonnes_score() -> str:
    return ", ".join(f"sum(score) FILTER (WHERE jour >= now() - interval '{j} days') AS score_{nom}"
                     for nom, j in FENETRES.items())


def _param(params: dict, cle: str, defaut=None):
    """`parse_qs` rend des listes : on prend la premiere valeur."""
    v = params.get(cle, defaut)
    if isinstance(v, list):
        v = v[0] if v else defaut
    return v


def _cle(par: str) -> str:
    if par not in ("actif", "marche"):
        raise ValueError("`par` vaut actif ou marche")
    return "actif" if par == "actif" else "classe_actif"


def _lignes(curs, sql: str, params: dict) -> list[dict]:
    curs.execute(sql, params)
    noms = [d.name for d in curs.description]
    return [dict(zip(noms, ligne)) for ligne in curs.fetchall()]


def _nombre(v):
    return None if v is None else float(v)


def _soldes(ligne: dict) -> dict:
    """Solde net par fenetre = (haussiers - baissiers) / articles. Un simple compte : pas un score."""
    for nom in FENETRES:
        n = ligne.get(f"n_{nom}") or 0
        h, b = ligne.get(f"haussiers_{nom}") or 0, ligne.get(f"baissiers_{nom}") or 0
        ligne[f"solde_{nom}"] = (h - b) / n if n else None
    return ligne


def _groupes(curs, version: str, par: str) -> list[dict]:
    cle = _cle(par)
    lignes = _lignes(curs, SQL_GROUPES.format(cle=cle, colonnes=_colonnes_comptes()),
                     {"v": version})
    scores = {s["groupe"]: s for s in _lignes(
        curs, SQL_SCORE.format(cle=cle, colonnes=_colonnes_score()), {"v": version})}
    for ligne in lignes:
        s = scores.get(ligne["groupe"], {})
        for nom in FENETRES:
            ligne[f"score_{nom}"] = _nombre(s.get(f"score_{nom}"))
        _soldes(ligne)
    lignes.sort(key=lambda l: (-(l["n_7j"] or 0), -(l["total"] or 0), str(l["groupe"])))
    return lignes


def _version(curs, demandee: str | None) -> tuple[str | None, list[dict]]:
    versions = _lignes(curs, SQL_VERSIONS, {})
    if demandee:
        if not NOM_VERSION.match(demandee):
            raise ValueError("version_modele invalide")
        if not any(v["version_modele"] == demandee for v in versions):
            raise ValueError(f"version_modele inconnue : {demandee}")
        return demandee, versions
    return (versions[0]["version_modele"] if versions else None), versions


def vue(params: dict | None = None) -> dict:
    """Etat de DS2 + tableaux par marche et par actif, pour la version de modele demandee."""
    params = params or {}
    try:
        conn = connecter()
    except NonBranche as exc:
        return {"branche": False, "message": str(exc), "fichier_env": str(fichier_env())}
    with conn, conn.cursor() as curs:
        version, versions = _version(curs, _param(params, "version"))
        news = _lignes(curs, SQL_NEWS, {})[0]
        if version is None:
            return {"branche": True, "base": conn.info.dbname, "versions": [], "news": news,
                    "message": "aucune classification en base : le pipeline DS2 n'a pas encore tourne"}
        echecs = _lignes(curs, SQL_ECHECS, {"v": version})
        return {
            "branche": True,
            "base": conn.info.dbname,
            "version": version,
            "versions": versions,
            "news": news,
            "echecs": echecs,
            "fenetres": list(FENETRES),
            "par_marche": _groupes(curs, version, "marche"),
            "par_actif": _groupes(curs, version, "actif"),
        }


def detail(params: dict) -> dict:
    """Serie quotidienne et derniers articles d'un actif ou d'un marche."""
    par = _param(params, "par", "actif")
    cle = _cle(par)
    groupe = _param(params, "groupe") or ""
    if not NOM_ACTIF.match(groupe):
        raise ValueError("parametre `groupe` invalide")
    try:
        conn = connecter()
    except NonBranche as exc:
        return {"branche": False, "message": str(exc)}
    with conn, conn.cursor() as curs:
        version, _ = _version(curs, _param(params, "version"))
        if version is None:
            return {"branche": True, "serie": [], "articles": []}
        p = {"v": version, "g": groupe, "j": JOURS_SERIE, "n": ARTICLES_MAX}
        serie = _lignes(curs, SQL_SERIE.format(cle=cle), p)
        scores = {s["jour"]: _nombre(s["score"])
                  for s in _lignes(curs, SQL_SCORE_SERIE.format(cle=cle), p)}
        for ligne in serie:
            ligne["score"] = scores.get(ligne["jour"])
        articles = _lignes(curs, SQL_ARTICLES.format(cle=cle), p)
        for a in articles:
            a["proba"] = _nombre(a["proba"])
        return {"branche": True, "version": version, "par": par, "groupe": groupe,
                "jours": JOURS_SERIE, "serie": serie, "articles": articles}
