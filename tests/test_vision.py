"""Historique public Binance (10/10) : ce que ces tests protegent.

(1) la liste S3 est suivie page par page ; (2) un .zip dont le sha256 ne correspond pas au
.CHECKSUM n'entre jamais ; (3) les vieux aggTrades sans en-tete se lisent ; (4) l'agregation
a la minute separe bien taker acheteur / vendeur ; (5) un jour non publie est un TROU declare,
pas un silence ; (6) un second passage ne retelecharge rien ; (7) la lecture traverse les mois.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import pathlib
import sys
import zipfile

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta import config  # noqa: E402
from beta.lake import lecture, univers, vision  # noqa: E402

BTC = univers.par_base("BTC")
J0 = dt.date(2024, 1, 31)           # traverse un changement de mois


def _ms(jour: dt.date, secondes: int) -> int:
    return int(dt.datetime(jour.year, jour.month, jour.day,
                           tzinfo=dt.timezone.utc).timestamp() + secondes) * 1000


def _zip(nom: str, texte: str) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr(nom, texte)
    return tampon.getvalue()


def _aggtrades(jour: dt.date, premier_id: int, entete: bool) -> str:
    # minute 0 : achat taker 1 @ 100 puis vente taker 2 @ 99 ; minute 1 : achat 3 @ 101
    lignes = [f"{premier_id},100,1,10,10,{_ms(jour, 5)},false",
              f"{premier_id + 1},99,2,11,12,{_ms(jour, 30)},true",
              f"{premier_id + 2},101,3,13,13,{_ms(jour, 70)},False"]
    tete = ",".join(vision.COLONNES_AGGTRADES) + "\n" if entete else ""
    return tete + "\n".join(lignes) + "\n"


def _liste(cles: list[str], tronquee: bool) -> bytes:
    contenu = "".join(f"<Contents><Key>{c}</Key></Contents>" for c in cles)
    return (f'<?xml version="1.0"?><ListBucketResult xmlns="http://s3.amazonaws.com/doc/'
            f'2006-03-01/"><IsTruncated>{str(tronquee).lower()}</IsTruncated>{contenu}'
            f"</ListBucketResult>").encode()


class FauxBinance:
    """Le serveur : des fichiers par cle, une liste en pages de 2 cles, un journal d'appels."""

    def __init__(self, fichiers: dict[str, bytes], corrompus: set[str] = frozenset()):
        self.fichiers, self.corrompus, self.appels = fichiers, corrompus, []

    def __call__(self, url: str) -> bytes:
        self.appels.append(url)
        if "s3-ap-northeast-1" in url:
            marqueur = url.split("marker=")[1].replace("%2F", "/")
            cles = sorted(k for k in self.fichiers if k > marqueur)
            return _liste(cles[:2], len(cles) > 2)
        cle = url.split("data.binance.vision/")[1]
        if cle.endswith(".CHECKSUM"):
            zip_ = self.fichiers[cle[:-9]]
            sha = "0" * 64 if cle[:-9] in self.corrompus else hashlib.sha256(zip_).hexdigest()
            return f"{sha}  {cle[:-9].rsplit('/', 1)[1]}\n".encode()
        return self.fichiers[cle]


def _cle(jeu: str, jour: dt.date) -> str:
    return f"data/futures/um/daily/{jeu}/BTCUSDT/BTCUSDT-{jeu}-{jour}.zip"


@pytest.fixture
def isole(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "VISION", tmp_path / "vision")
    monkeypatch.setattr(config, "VISION_ETAT", tmp_path / "vision" / "etat.duckdb")
    monkeypatch.setattr(vision, "RETARD_MAX_J", 10**6)
    return tmp_path


def _serveur_aggtrades(jours: list[dt.date], monkeypatch, corrompus=frozenset()):
    fichiers = {}
    for i, jour in enumerate(jours):
        # ids consecutifs d'un jour a l'autre, comme chez Binance ; vieux format sans en-tete
        fichiers[_cle("aggTrades", jour)] = _zip(f"BTCUSDT-aggTrades-{jour}.csv",
                                                 _aggtrades(jour, 1 + 3 * i, entete=i > 0))
    serveur = FauxBinance(fichiers, {_cle("aggTrades", j) for j in corrompus})
    monkeypatch.setattr(vision, "_http", serveur)
    return serveur


def test_liste_suivie_page_par_page(isole, monkeypatch):
    jours = [J0 + dt.timedelta(days=i) for i in range(5)]
    _serveur_aggtrades(jours, monkeypatch)
    assert sorted(vision.lister("aggTrades", "BTC")) == jours


def test_agregation_minute_separe_acheteurs_et_vendeurs(isole, monkeypatch):
    _serveur_aggtrades([J0], monkeypatch)
    assert vision.mettre_a_jour(("aggTrades",), (BTC,)) == []
    df = lecture.vision("aggTrades", "BTC")
    assert len(df) == 2 and str(df["date"].dt.tz) == "UTC"
    m0 = df.iloc[0]
    assert (m0.ouverture, m0.haut, m0.bas, m0.cloture) == (100, 100, 99, 99)
    assert (m0.qte_achat, m0.qte_vente, m0.usd_achat, m0.usd_vente) == (1, 2, 100, 198)
    assert (m0.n_agg, m0.n_trades, m0.usd_max_agg) == (2, 3, 198)
    assert df.iloc[1].qte_achat == 3         # « False » majuscule = taker acheteur aussi


def test_checksum_faux_jamais_integre_et_retente(isole, monkeypatch):
    _serveur_aggtrades([J0, J0 + dt.timedelta(days=1)], monkeypatch, corrompus={J0})
    problemes = vision.mettre_a_jour(("aggTrades",), (BTC,))
    assert len(problemes) == 1 and "sha256" in problemes[0]
    assert len(lecture.vision("aggTrades", "BTC")) == 2       # le seul jour sain
    serveur = _serveur_aggtrades([J0, J0 + dt.timedelta(days=1)], monkeypatch)
    assert vision.mettre_a_jour(("aggTrades",), (BTC,)) == []
    assert len(lecture.vision("aggTrades", "BTC")) == 4       # rattrape au passage suivant
    assert sum(_cle("aggTrades", J0) in u for u in serveur.appels) == 2   # zip + CHECKSUM


def test_jour_absent_est_un_trou_declare(isole, monkeypatch):
    jours = [J0 + dt.timedelta(days=i) for i in range(4)]
    serveur = _serveur_aggtrades(jours, monkeypatch)
    del serveur.fichiers[_cle("aggTrades", jours[1])]        # Binance saute un jour
    assert vision.mettre_a_jour(("aggTrades",), (BTC,)) == []
    r = vision.etat().iloc[0]
    assert (r.jours_attendus, r.jours_absents, r.plus_grand_trou_j) == (4, 1, 1)
    assert r.couverture_pct == pytest.approx(75.0) and r.suspect


def test_second_passage_ne_retelecharge_rien(isole, monkeypatch):
    jours = [J0 + dt.timedelta(days=i) for i in range(3)]
    serveur = _serveur_aggtrades(jours, monkeypatch)
    vision.mettre_a_jour(("aggTrades",), (BTC,))
    serveur.appels.clear()
    assert vision.mettre_a_jour(("aggTrades",), (BTC,)) == []
    assert all("s3-ap-northeast-1" in u for u in serveur.appels)
    # un mois par fichier, la lecture les reunit dans l'ordre
    assert sorted(p.name for p in (config.VISION / "aggTrades" / "BTC").iterdir()) == [
        "2024-01.parquet", "2024-02.parquet"]
    assert lecture.vision("aggTrades", "BTC", debut="2024-02-01")["date"].is_monotonic_increasing


def test_bookdepth_pivote_et_couverture_partielle(isole, monkeypatch):
    lignes = ["timestamp,percentage,depth,notional"]
    for s in range(0, 6 * 3600, 30):                     # 6 h sur 24
        t = (dt.datetime(2024, 1, 31) + dt.timedelta(seconds=s)).strftime("%Y-%m-%d %H:%M:%S")
        lignes += [f"{t},-0.2,1,100", f"{t},1,2,200"]
    serveur = FauxBinance({_cle("bookDepth", J0): _zip("x.csv", "\n".join(lignes))})
    monkeypatch.setattr(vision, "_http", serveur)
    assert vision.mettre_a_jour(("bookDepth",), (BTC,)) == []
    df = lecture.vision("bookDepth", "BTC")
    assert list(df.columns) == ["date", "qte_ask_100", "qte_bid_020", "usd_ask_100",
                                "usd_bid_020"]
    assert vision.etat().iloc[0].couverture_pct == pytest.approx(25.0)


def test_metrics_trie_et_sans_symbole(isole, monkeypatch):
    texte = ("create_time,symbol,sum_open_interest\n2024-01-31 00:10:00,BTCUSDT,2\n"
             "2024-01-31 00:05:00,BTCUSDT,1\n")
    monkeypatch.setattr(vision, "_http", FauxBinance({_cle("metrics", J0): _zip("m.csv", texte)}))
    assert vision.mettre_a_jour(("metrics",), (BTC,)) == []
    df = lecture.vision("metrics", "BTC")
    assert list(df.columns) == ["date", "sum_open_interest"]
    assert df["sum_open_interest"].tolist() == [1, 2]


def test_lecture_jeu_absent_dit_quoi_faire(isole):
    with pytest.raises(lecture.DataError, match="scripts/vision.py"):
        lecture.vision("metrics", "BTC")
    with pytest.raises(lecture.DataError, match="jeu inconnu"):
        lecture.vision("klines", "BTC")
