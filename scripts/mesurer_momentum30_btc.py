"""Mesure MOMENTUM30_BTC et la clot au registre - verdict et rapport par le programme.

    /root/venvs/arit/bin/python scripts/mesurer_momentum30_btc.py

Refuse de tourner si le texte du preenregistrement ou le moteur a change depuis le gel, ou si
l'experience est deja close. Ecrit data/momentum30_btc/resultats.json,
rapports/MOMENTUM30_BTC/RAPPORT.md et RESUME_DISCORD.md. Aucun chiffre n'est tape a la main.
"""
from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import subprocess
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from beta.invest import moteur as invest_moteur          # noqa: E402
from beta.lake import lecture                            # noqa: E402
from beta.momentum30_btc import moteur                   # noqa: E402
from beta.protocole import experiences, holdout          # noqa: E402

log = logging.getLogger("beta.mesurer_momentum30_btc")
SPEC = RACINE / "MOMENTUM30_BTC" / "PREENREGISTREMENT.md"
CODE = RACINE / "beta" / "momentum30_btc" / "moteur.py"
SORTIE = RACINE / "data" / "momentum30_btc"
RAPPORTS = RACINE / "rapports" / moteur.ID_EXPERIENCE
ID = moteur.ID_EXPERIENCE


def empreinte_fichier(chemin: pathlib.Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()[:16]


def empreinte_tableau(x) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(x, dtype=float)).tobytes()).hexdigest()[:16]


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=RACINE, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:          # noqa: BLE001
        return "inconnu"


def verifier_gel(pre: dict) -> None:
    attendu = pre.get("empreintes") or {}
    reel = {"spec": empreinte_fichier(SPEC), "code": empreinte_fichier(CODE)}
    if attendu != reel:
        raise SystemExit(f"GEL ROMPU : empreintes au registre {attendu}, fichiers {reel} - "
                         "rien n'est mesure")


def charger() -> dict:
    fin = holdout.borner_train(None)
    df = lecture.load("BTC", "1d", fin=fin)
    df["date"] = pd.to_datetime(df["date"], utc=True)
    close = df["close"].to_numpy(dtype=float)
    jours_tous = pd.DatetimeIndex(df["date"])
    e_tous = moteur.exposition(close, moteur.LOOKBACK)
    r_tous = moteur.rendements_bruts(close)
    debut = moteur.LOOKBACK + 1                     # premier jour avec une exposition decidee
    jours = jours_tous[debut:]
    e, r_b = e_tous[debut:], r_tous[debut:]
    funding = lecture.funding("BTC")
    phi = moteur.funding_journalier(funding, jours)
    dff = lecture.macro_globales()["fedfunds"]
    rf = invest_moteur.rf_quotidien(dff, jours)
    return {"df": df, "close": close, "jours": jours, "e": e, "r_b": r_b, "phi": phi, "rf": rf,
            "funding": funding, "dff": dff, "debut": debut,
            "donnees": {"bougies_1d": int(len(df)), "premiere_bougie": str(jours_tous[0].date()),
                        "derniere_bougie": str(jours_tous[-1].date()),
                        "premier_rendement": str(jours[0].date()), "dernier_rendement": str(jours[-1].date()),
                        "n_jours": int(len(jours)), "reglements_funding": int(len(funding)),
                        "sha256_close": empreinte_tableau(close),
                        "sha256_funding": empreinte_tableau(phi),
                        "sha256_dff": empreinte_tableau(rf)}}


def controles(d: dict) -> list[dict]:
    """Tests de coherence sur les vraies series, avant toute lecture des metriques."""
    out = []
    z = np.zeros(len(d["r_b"]))
    h = moteur.hold(d["r_b"], z, z)
    ratio = d["close"][-1] / d["close"][d["debut"] - 1] - 1.0
    out.append({"controle": "hold sans cout = ratio des clotures", "ok": bool(abs(h["rendement_total"] - ratio) < 1e-9),
                "detail": f"{h['rendement_total']:.10f} contre {ratio:.10f}"})
    s0 = moteur._sharpe(d["e"], d["r_b"], d["phi"], d["rf"], moteur.KAPPA_PB)
    s1 = moteur._sharpe(np.roll(d["e"], 0), d["r_b"], d["phi"], d["rf"], moteur.KAPPA_PB)
    out.append({"controle": "decalage circulaire de 0 jour = observe", "ok": bool(s0 == s1), "detail": f"{s0:.10f} = {s1:.10f}"})
    ok = True
    for coupe in (400, 1000, len(d["close"]) - 1):
        a = moteur.exposition(d["close"][:coupe], moteur.LOOKBACK)[d["debut"]:]
        b = moteur.exposition(d["close"], moteur.LOOKBACK)[d["debut"]:coupe]
        ok &= np.array_equal(a, b)
    out.append({"controle": "causalite : exposition(prefixe) = prefixe(exposition), 3 coupures", "ok": bool(ok), "detail": "coupures 400, 1000, N-1"})
    out.append({"controle": "aucun NaN dans E, R_B, phi, rf", "ok": not any(np.isnan(d[k]).any() for k in ("e", "r_b", "phi", "rf")), "detail": ""})
    f = d["funding"].copy()
    f["date"] = pd.to_datetime(f["date"], utc=True)
    par_jour = f.groupby((f["date"] - pd.Timedelta(microseconds=1)).dt.floor("D")).size().reindex(d["jours"]).fillna(0)
    hors = par_jour[par_jour != 3]
    out.append({"controle": "3 reglements de funding par jour", "ok": bool(len(hors) == 0),
                "detail": f"{len(hors)} jour(s) hors norme" + (f" : {[str(x.date()) for x in hors.index[:5]]}" if len(hors) else "")})
    return out


def mesurer(d: dict, n_essais: int) -> dict:
    e, r_b, phi, rf, jours = d["e"], d["r_b"], d["phi"], d["rf"], d["jours"]
    strat = moteur.evaluer(e, r_b, phi, rf, n_essais=n_essais)
    ref = moteur.hold(r_b, phi, rf, n_essais=n_essais)
    temoin = moteur.temoin_constant(e, r_b, phi, rf)
    cond = moteur.conditions(strat, ref)
    nl = moteur.nulls_sharpe(e, r_b, phi, rf)
    issue = moteur.verdict(cond, nl["p_retenue"])
    r_s = moteur.rendement_net(e, r_b, phi, rf)["r"]
    annees = moteur.par_annee(jours, r_s, r_b, e)
    # Robustesse, sans effet
    rob = {}
    for L in (14, 60):
        # La fenetre 60 j n'a pas d'exposition avant son propre warm-up : sa periode commence
        # 30 jours plus tard (2019-11-07) ; la fenetre 14 j est lue sur la periode principale.
        k = max(d["debut"], L + 1) - d["debut"]
        e_l = moteur.exposition(d["close"], L)[d["debut"] + k:]
        rob[f"fenetre_{L}"] = {"strategie": moteur.evaluer(e_l, r_b[k:], phi[k:], rf[k:]),
                               "periode": f"{jours[k].date()} -> {jours[-1].date()}"}
    rob["comptant"] = {"strategie": moteur.evaluer(e, r_b, np.zeros(len(e)), rf), "hold": moteur.hold(r_b, np.zeros(len(e)), rf)}
    rob["frais_12pb"] = {"strategie": moteur.evaluer(e, r_b, phi, rf, kappa_pb=12.0)}
    sous = {}
    for nom, (a, b) in {"2019-10-09 -> 2022-12-31": ("2019-10-09", "2022-12-31"), "2023-01-01 -> 2024-12-31": ("2023-01-01", "2024-12-31")}.items():
        m = (jours >= pd.Timestamp(a, tz="UTC")) & (jours <= pd.Timestamp(b, tz="UTC"))
        sous[nom] = {"strategie": moteur.evaluer(e[m], r_b[m], phi[m], rf[m]), "hold": moteur.hold(r_b[m], phi[m], rf[m])}
    return {"strategie": strat, "hold": ref, "temoin": temoin, "conditions": cond, "nulls": nl, "issue": issue,
            "par_annee": annees.reset_index().rename(columns={"index": "annee", "date": "annee"}).to_dict("records"),
            "robustesse": rob, "sous_periodes": sous}


def _pct(x) -> str:
    return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:+.1f} %"


def _n(x, d=2) -> str:
    return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def _ligne(nom: str, m: dict) -> str:
    return (f"{nom:<22}{_pct(m['rendement_total']):>10}{_pct(m['cagr']):>9}{_n(m['sharpe']):>8}"
            f"{_pct(m['mdd']):>9}{_n(m['ulcer'] * 100, 1):>8}{_n(m.get('expo_moyenne'), 2):>7}"
            f"{str(m.get('changements_expo', '')):>6}")


def ecrire_rapports(pre: dict, res: dict, ctrl: list[dict], donnees: dict, cloture: dict, run_id: str) -> None:
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    s, h, t, c, nl = res["strategie"], res["hold"], res["temoin"], res["conditions"], res["nulls"]
    verdict = res["issue"].upper().replace("EE", "ÉE")
    entete = f"{'':<22}{'rendement':>10}{'CAGR':>9}{'Sharpe':>8}{'MDD':>9}{'Ulcer':>8}{'expo':>7}{'basc.':>6}"
    tableau = "\n".join([entete, _ligne("stratégie L30", s), _ligne("hold perpétuel", h), _ligne("témoin expo cste", t)])
    conds = [f"- (a) Sharpe stratégie > hold : {_n(s['sharpe'], 3)} contre {_n(h['sharpe'], 3)} → {'oui' if c['sharpe_superieur'] else 'NON'}",
             f"- (b) CAGR stratégie ≥ hold : {_pct(s['cagr'])} contre {_pct(h['cagr'])} → {'oui' if c['cagr_superieur_ou_egal'] else 'NON'}",
             f"- (c) MDD moins profond : {_pct(s['mdd'])} contre {_pct(h['mdd'])} → {'oui' if c['drawdown_moins_profond'] else 'NON'}",
             f"- nulls (Sharpe, B = {nl['b']}) : p circulaire {_n(nl['circulaire']['p'], 3)} (médiane nulle {_n(nl['circulaire']['mediane'], 2)}, q95 {_n(nl['circulaire']['q95'], 2)}), "
             f"p segments {_n(nl['segments']['p'], 3)} (médiane nulle {_n(nl['segments']['mediane'], 2)}, q95 {_n(nl['segments']['q95'], 2)}) → **p retenue {_n(nl['p_retenue'], 3)}** ({nl['verdict_nulls']})"]
    annees = "\n".join([f"{'année':<8}{'stratégie':>11}{'hold':>10}{'expo':>7}{'basc.':>7}{'jours':>7}"] +
                       [f"{int(a['annee']):<8}{_pct(a['strategie']):>11}{_pct(a['hold']):>10}{a['exposition']:>7.2f}{int(a['bascules']):>7}{int(a['jours']):>7}" for a in res["par_annee"]])
    rob = res["robustesse"]
    robust = "\n".join([entete, _ligne("fenêtre 14 j", rob["fenetre_14"]["strategie"]), _ligne("fenêtre 60 j (dès 11/2019)", rob["fenetre_60"]["strategie"]),
                        _ligne("comptant (φ = 0)", rob["comptant"]["strategie"]), _ligne("hold comptant", rob["comptant"]["hold"]),
                        _ligne("frais 12 pb", rob["frais_12pb"]["strategie"])])
    sous = "\n".join([entete] + [x for nom, v in res["sous_periodes"].items() for x in (_ligne(f"strat {nom[:10]}", v["strategie"]), _ligne(f"hold  {nom[:10]}", v["hold"]))])
    ctrl_txt = "\n".join(f"- {'✅' if x['ok'] else '❌'} {x['controle']}" + (f" — {x['detail']}" if x["detail"] else "") for x in ctrl)
    n_ok = sum(x["ok"] for x in ctrl)
    pastille = "🟢" if n_ok == len(ctrl) else "🔴"
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    titre = "Momentum trente jours sur le BTC (exposition long-only)"
    rapport = f"""# {titre} — rapport du programme — {date}

**Verdict au registre : {ID} {verdict}.** Issue attendue : {pre.get('issue_attendue')} ; conforme : {'oui' if cloture.get('conforme_a_l_issue_attendue') else 'non'}.
État du calcul : {n_ok} contrôles sur {len(ctrl)} passés (pastille = état du calcul, pas jugement du résultat). Code `{commit()}`, run `{run_id}`.

## Préenregistrement (mot pour mot, registre)
- Id `{pre['id']}`, famille {pre['famille_compteur']}, préenregistrée le {pre['date']} (N invest = {pre['n_essais_cumules']}), issue attendue : {pre['issue_attendue']}.
- Hypothèse : {pre['hypothese']}
- Métrique primaire : {pre['metrique_primaire']}
- Règle de décision : confirmée = {pre['regle_de_decision']['confirmee']} ; indécidable = {pre['regle_de_decision']['indecidable']} ; infirmée = {pre['regle_de_decision']['infirmee']}.
- Décidé par : {pre.get('decide_par')}
- Déjà connu : {pre.get('deja_connu')}
- Empreintes gelées : spec `{pre['empreintes']['spec']}`, code `{pre['empreintes']['code']}` (vérifiées avant la mesure).

## Données lues
- BTC perpétuel 1d : {donnees['bougies_1d']} bougies du {donnees['premiere_bougie']} au {donnees['derniere_bougie']} ; rendements du {donnees['premier_rendement']} au {donnees['dernier_rendement']} ({donnees['n_jours']} jours) ; {donnees['reglements_funding']} règlements de funding.
- Empreintes : clôtures `{donnees['sha256_close']}`, funding journalier `{donnees['sha256_funding']}`, DFF `{donnees['sha256_dff']}`.

## Résultat (tous coûts déduits : 6 pb par bascule, funding, cash au DFF)
```
{tableau}
```
Rendement et CAGR en %, Sharpe quotidien net de rf × √365, MDD en %, Ulcer en %, expo = exposition moyenne, basc. = nombre de bascules.
Coûts de la stratégie sur la période : frais {_pct(s['cout_total'])}, funding {_pct(s['funding_total'])} (hold : funding {_pct(h['funding_total'])}). Sharpe déflaté au compteur invest ({s['n_essais']}) : stratégie {_n(s['dsr'], 3)}, hold {_n(h['dsr'], 3)} (informatif).

## Règle de décision, condition par condition
{chr(10).join(conds)}

**→ {verdict}** (`moteur.verdict`).

## Par année civile (sans effet)
```
{annees}
```

## Sous-périodes (sans effet)
```
{sous}
```

## Robustesse (sans effet, aucune variante n'est choisie)
```
{robust}
```

## Contrôles de cohérence
{ctrl_txt}

## Compteur d'essais
- {ID} (invest) : N = {pre['n_essais_cumules']} au préenregistrement ; aujourd'hui : invest {experiences.compteur(famille='invest')}, trading {experiences.compteur(famille='trading')}.

## Fichiers
- `MOMENTUM30_BTC/RECHERCHE.md` (question, littérature, mécanisme, données, prédiction), `MOMENTUM30_BTC/PREENREGISTREMENT.md` (gelé), `beta/momentum30_btc/moteur.py`, `scripts/mesurer_momentum30_btc.py`, `data/momentum30_btc/resultats.json`.
"""
    (RAPPORTS / "RAPPORT.md").write_text(rapport, encoding="utf-8")
    resume = f"""# {pastille} {titre} — rapport du programme — {date}

**Verdict au registre : {ID} {verdict}** (issue attendue : {pre.get('issue_attendue')}). Proposition de Claude du 10/11, relecture de Jonas en attente → exploration, pas preuve.
État du calcul : {n_ok} contrôles sur {len(ctrl)} passés.

## Stratégie contre hold du perpétuel BTC, rendements du {donnees['premier_rendement']} au {donnees['dernier_rendement']}, tous coûts déduits
```
{tableau}
```
{chr(10).join(conds)}

## Par année (sans effet)
```
{annees}
```

## Robustesse (sans effet)
```
{robust}
```

## Compteur
- invest {experiences.compteur(famille='invest')} (N = {pre['n_essais_cumules']} au préenregistrement), trading {experiences.compteur(famille='trading')}

## Fichiers
- `rapports/{ID}/RAPPORT.md` (joint) ; code `{commit()}` ; run {run_id}
"""
    (RAPPORTS / "RESUME_DISCORD.md").write_text(resume, encoding="utf-8")


def _propre(x):
    if isinstance(x, dict):
        return {k: _propre(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_propre(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    return x


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    etat = experiences.etat().get(ID, {})
    if not etat:
        log.error("%s n'est pas preenregistree", ID)
        return 1
    if etat.get("statut") == "clos":
        log.error("%s deja close : on ne remesure pas sous le meme id", ID)
        return 1
    pre = experiences.exiger(ID)
    verifier_gel(pre)
    d = charger()
    ctrl = controles(d)
    if not all(x["ok"] for x in ctrl):
        log.error("controle(s) en echec : %s - rien n'est mesure", [x for x in ctrl if not x["ok"]])
        return 1
    run_id = hashlib.sha256(f"{ID}|{pre['empreintes']}|{d['donnees']['sha256_close']}|{d['donnees']['sha256_funding']}".encode()).hexdigest()[:12]
    experiences.enregistrer_run(run_id, ID, "momentum30_btc:L30", pre["empreintes"]["code"], issue="essai journalise avant calcul")
    n_essais = experiences.compteur(famille="invest")
    res = mesurer(d, n_essais)
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "resultats.json").write_text(json.dumps(_propre({"run": run_id, "donnees": d["donnees"], "controles": ctrl, **res}),
                                                      ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    s, h, nl = res["strategie"], res["hold"], res["nulls"]
    resultat = (f"strategie : Sharpe {s['sharpe']:.4f}, CAGR {s['cagr']:.4f}, MDD {s['mdd']:.4f} ; hold : Sharpe {h['sharpe']:.4f}, "
                f"CAGR {h['cagr']:.4f}, MDD {h['mdd']:.4f} ; conditions {res['conditions']} ; p circulaire {nl['circulaire']['p']:.4f}, "
                f"p segments {nl['segments']['p']:.4f}, p retenue {nl['p_retenue']:.4f} ({nl['verdict_nulls']})")
    cloture = experiences.clore(ID, res["issue"], resultat, runs=[run_id], donnees=d["donnees"], controles=ctrl,
                                conditions=res["conditions"], nulls={k: v for k, v in nl.items()})
    experiences.enregistrer_run(run_id, ID, "momentum30_btc:L30", pre["empreintes"]["code"], issue=res["issue"])
    ecrire_rapports(pre, res, ctrl, d["donnees"], cloture, run_id)
    print(f"\n{ID} : {res['issue'].upper()}")
    print((RAPPORTS / "RESUME_DISCORD.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
