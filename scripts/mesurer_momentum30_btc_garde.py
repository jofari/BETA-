"""Mesure MOMENTUM30_BTC_GARDE et la clot au registre - verdict et rapport par le programme.

    ARIT_HOME=/root/ARIT2.0 /root/venvs/beta/bin/python scripts/mesurer_momentum30_btc_garde.py

Refuse de tourner si le texte du preenregistrement, le moteur de la garde ou le moteur de base
a change depuis le gel, ou si l'experience est deja close. Ecrit
data/momentum30_btc_garde/resultats.json, rapports/MOMENTUM30_BTC_GARDE/RAPPORT.md et
RESUME_DISCORD.md. Aucun chiffre n'est tape a la main.

Le chargement et les controles de coherence sont ceux de MOMENTUM30_BTC
(`scripts/mesurer_momentum30_btc.py`), importes tels quels.
"""
from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import sys
from datetime import UTC, datetime

import numpy as np
import pandas as pd

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "scripts"))

import mesurer_momentum30_btc as m30                      # noqa: E402
from beta.momentum30_btc import moteur as base            # noqa: E402
from beta.momentum30_btc_garde import moteur              # noqa: E402
from beta.protocole import experiences                    # noqa: E402

log = logging.getLogger("beta.mesurer_momentum30_btc_garde")
SPEC = RACINE / "MOMENTUM30_BTC_GARDE" / "PREENREGISTREMENT.md"
CODE = RACINE / "beta" / "momentum30_btc_garde" / "moteur.py"
CODE_BASE = RACINE / "beta" / "momentum30_btc" / "moteur.py"
SORTIE = RACINE / "data" / "momentum30_btc_garde"
ID = moteur.ID_EXPERIENCE
RAPPORTS = RACINE / "rapports" / ID
_pct, _n, _ligne = m30._pct, m30._n, m30._ligne


def verifier_gel(pre: dict) -> None:
    reel = {"spec": m30.empreinte_fichier(SPEC), "code": m30.empreinte_fichier(CODE),
            "code_base": m30.empreinte_fichier(CODE_BASE)}
    if (pre.get("empreintes") or {}) != reel:
        raise SystemExit(f"GEL ROMPU : registre {pre.get('empreintes')}, fichiers {reel} - rien n'est mesure")


def expo_garde(close: np.ndarray, debut: int, seuil: float) -> tuple[np.ndarray, np.ndarray]:
    e, g = moteur.exposition(close, moteur.LOOKBACK, seuil)
    return e[debut:], g[debut:]


def controles_garde(d: dict, e: np.ndarray, g: np.ndarray) -> list[dict]:
    out = m30.controles(d)
    ok = True
    for coupe in (400, 1000, len(d["close"]) - 1):
        a, _ = moteur.exposition(d["close"][:coupe])
        b, _ = moteur.exposition(d["close"])
        ok &= np.array_equal(a[d["debut"]:], b[d["debut"]:coupe], equal_nan=True)
    out.append({"controle": "causalite de la garde : exposition(prefixe) = prefixe(exposition), 3 coupures",
                "ok": bool(ok), "detail": "coupures 400, 1000, N-1"})
    e0 = d["e"]
    out.append({"controle": "garde : n'ajoute jamais d'exposition au momentum (e_garde <= e_base)",
                "ok": bool((e <= e0).all()), "detail": ""})
    out.append({"controle": "garde : coupe = base - garde, jour par jour",
                "ok": bool(np.array_equal(g, e0 - e)), "detail": ""})
    out.append({"controle": "aucun NaN dans l'exposition gardee", "ok": not np.isnan(e).any(), "detail": ""})
    return out


def declenchements(jours: pd.DatetimeIndex, g: np.ndarray) -> list[dict]:
    debut = np.flatnonzero(np.diff(np.concatenate([[0.0], g])) == 1.0)
    fin = np.flatnonzero(np.diff(np.concatenate([g, [0.0]])) == -1.0)
    return [{"premier_jour_coupe": str(jours[a].date()), "dernier_jour_coupe": str(jours[b].date()),
             "jours": int(b - a + 1)} for a, b in zip(debut, fin)]


def mesurer(d: dict, e: np.ndarray, g: np.ndarray, n_essais: int) -> dict:
    r_b, phi, rf, jours = d["r_b"], d["phi"], d["rf"], d["jours"]
    strat = moteur.evaluer(e, r_b, phi, rf, n_essais=n_essais)
    ref = moteur.hold(r_b, phi, rf, n_essais=n_essais)
    sans = base.evaluer(d["e"], r_b, phi, rf, n_essais=n_essais)
    temoin = moteur.temoin_constant(e, r_b, phi, rf)
    cond = moteur.conditions(strat, ref, sans)
    nl = moteur.nulls_sharpe(e, r_b, phi, rf)
    issue = moteur.verdict(cond, nl["p_retenue"])
    r_s = moteur.rendement_net(e, r_b, phi, rf)["r"]
    r_0 = base.rendement_net(d["e"], r_b, phi, rf)["r"]
    annees = moteur.par_annee(jours, r_s, r_b, e)
    annees["sans_garde"] = pd.Series(r_0, index=jours).groupby(jours.year).apply(lambda x: float(np.prod(1 + x) - 1))
    rob = {}
    for s in (0.15, 0.25):
        e_s, _ = expo_garde(d["close"], d["debut"], s)
        rob[f"seuil_{int(s * 100)}"] = moteur.evaluer(e_s, r_b, phi, rf)
    z = np.zeros(len(e))
    rob["comptant"] = moteur.evaluer(e, r_b, z, rf)
    rob["comptant_sans_garde"] = base.evaluer(d["e"], r_b, z, rf)
    rob["hold_comptant"] = moteur.hold(r_b, z, rf)
    rob["frais_12pb"] = moteur.evaluer(e, r_b, phi, rf, kappa_pb=12.0)
    sous = {}
    for nom, (a, b) in {"2019-10-09 -> 2022-12-31": ("2019-10-09", "2022-12-31"),
                        "2023-01-01 -> 2024-12-31": ("2023-01-01", "2024-12-31")}.items():
        m = (jours >= pd.Timestamp(a, tz="UTC")) & (jours <= pd.Timestamp(b, tz="UTC"))
        sous[nom] = {"garde": moteur.evaluer(e[m], r_b[m], phi[m], rf[m]),
                     "sans_garde": base.evaluer(d["e"][m], r_b[m], phi[m], rf[m]),
                     "hold": moteur.hold(r_b[m], phi[m], rf[m])}
    return {"strategie": strat, "hold": ref, "sans_garde": sans, "temoin": temoin, "conditions": cond,
            "nulls": nl, "issue": issue, "declenchements": declenchements(jours, g),
            "jours_coupes": int(g.sum()),
            "par_annee": annees.reset_index().rename(columns={"date": "annee", "index": "annee"}).to_dict("records"),
            "robustesse": rob, "sous_periodes": sous}


def ecrire_rapports(pre: dict, res: dict, ctrl: list[dict], donnees: dict, cloture: dict, run_id: str) -> None:
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    s, h, z, t, c, nl = (res["strategie"], res["hold"], res["sans_garde"], res["temoin"],
                         res["conditions"], res["nulls"])
    verdict = res["issue"].upper().replace("EE", "ÉE")
    entete = f"{'':<22}{'rendement':>10}{'CAGR':>9}{'Sharpe':>8}{'MDD':>9}{'Ulcer':>8}{'expo':>7}{'basc.':>6}"
    tableau = "\n".join([entete, _ligne("garde 20 %", s), _ligne("momentum sans garde", z),
                         _ligne("hold perpétuel", h), _ligne("témoin expo cste", t)])
    oui = lambda b: "oui" if b else "NON"  # noqa: E731
    conds = [f"- (a) Sharpe garde > hold : {_n(s['sharpe'], 3)} contre {_n(h['sharpe'], 3)} → {oui(c['sharpe_superieur'])}",
             f"- (b) CAGR garde ≥ hold : {_pct(s['cagr'])} contre {_pct(h['cagr'])} → {oui(c['cagr_superieur_ou_egal'])}",
             f"- (c) MDD garde moins profond que hold : {_pct(s['mdd'])} contre {_pct(h['mdd'])} → {oui(c['drawdown_moins_profond'])}",
             f"- (d) MDD garde moins profond que sans garde : {_pct(s['mdd'])} contre {_pct(z['mdd'])} → {oui(c['drawdown_moins_profond_que_sans_garde'])}",
             f"- (e) Sharpe garde ≥ sans garde : {_n(s['sharpe'], 3)} contre {_n(z['sharpe'], 3)} → {oui(c['sharpe_au_moins_egal_sans_garde'])}",
             f"- nulls (Sharpe, B = {nl['b']}) : p circulaire {_n(nl['circulaire']['p'], 3)}, p segments "
             f"{_n(nl['segments']['p'], 3)} → **p retenue {_n(nl['p_retenue'], 3)}** ({nl['verdict_nulls']})"]
    decl = res["declenchements"]
    decl_txt = "\n".join(f"- coupé du {x['premier_jour_coupe']} au {x['dernier_jour_coupe']} ({x['jours']} j)" for x in decl) or "- aucun"
    annees = "\n".join([f"{'année':<8}{'garde':>10}{'sans g.':>10}{'hold':>10}{'expo':>7}{'basc.':>7}"] +
                       [f"{int(a['annee']):<8}{_pct(a['strategie']):>10}{_pct(a['sans_garde']):>10}{_pct(a['hold']):>10}"
                        f"{a['exposition']:>7.2f}{int(a['bascules']):>7}" for a in res["par_annee"]])
    rob = res["robustesse"]
    robust = "\n".join([entete, _ligne("seuil 15 %", rob["seuil_15"]), _ligne("seuil 25 %", rob["seuil_25"]),
                        _ligne("comptant garde", rob["comptant"]), _ligne("comptant sans garde", rob["comptant_sans_garde"]),
                        _ligne("hold comptant", rob["hold_comptant"]), _ligne("frais 12 pb", rob["frais_12pb"])])
    sous = "\n".join([entete] + [x for nom, v in res["sous_periodes"].items() for x in (
        _ligne(f"garde {nom[:10]}", v["garde"]), _ligne(f"sans  {nom[:10]}", v["sans_garde"]), _ligne(f"hold  {nom[:10]}", v["hold"]))])
    ctrl_txt = "\n".join(f"- {'✅' if x['ok'] else '❌'} {x['controle']}" + (f" — {x['detail']}" if x["detail"] else "") for x in ctrl)
    n_ok = sum(x["ok"] for x in ctrl)
    pastille = "🟢" if n_ok == len(ctrl) else "🔴"
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    titre = "Momentum trente jours sur le BTC avec garde de baisse"
    rapport = f"""# {titre} — rapport du programme — {date}

**Verdict au registre : {ID} {verdict}.** Issue attendue : {pre.get('issue_attendue')} ; conforme : {'oui' if cloture.get('conforme_a_l_issue_attendue') else 'non'}.
**Exploration, pas recherche** : période déjà vue par MOMENTUM30_BTC, hypothèse de Claude, relecture de Jonas en attente.
État du calcul : {n_ok} contrôles sur {len(ctrl)} passés (pastille = état du calcul, pas jugement du résultat). Code `{m30.commit()}`, run `{run_id}`.

## Préenregistrement (mot pour mot, registre)
- Id `{pre['id']}`, famille {pre['famille_compteur']}, préenregistrée le {pre['date']} (N invest = {pre['n_essais_cumules']}), issue attendue : {pre['issue_attendue']}.
- Hypothèse : {pre['hypothese']}
- Règle de décision : confirmée = {pre['regle_de_decision']['confirmee']} ; indécidable = {pre['regle_de_decision']['indecidable']} ; infirmée = {pre['regle_de_decision']['infirmee']}.
- Décidé par : {pre.get('decide_par')}
- Déjà connu : {pre.get('deja_connu')}
- Empreintes gelées : {pre['empreintes']} (vérifiées avant la mesure).

## Données lues
- BTC perpétuel 1d : {donnees['bougies_1d']} bougies du {donnees['premiere_bougie']} au {donnees['derniere_bougie']} ; rendements du {donnees['premier_rendement']} au {donnees['dernier_rendement']} ({donnees['n_jours']} jours) ; {donnees['reglements_funding']} règlements de funding.
- Empreintes : clôtures `{donnees['sha256_close']}`, funding journalier `{donnees['sha256_funding']}`, DFF `{donnees['sha256_dff']}`.

## Résultat (tous coûts déduits : 6 pb par bascule, funding, cash au DFF)
```
{tableau}
```
Sharpe quotidien net de rf × √365 ; MDD et Ulcer en % ; expo = exposition moyenne ; basc. = bascules.
Garde : {len(decl)} déclenchement(s), {res['jours_coupes']} jours coupés. Coûts : frais {_pct(s['cout_total'])}, funding {_pct(s['funding_total'])}. Sharpe déflaté au compteur invest ({s['n_essais']}) : {_n(s['dsr'], 3)} (informatif).

## Règle de décision, condition par condition
{chr(10).join(conds)}

**→ {verdict}** (`moteur.verdict`).

## Déclenchements de la garde
{decl_txt}

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
- `MOMENTUM30_BTC_GARDE/PREENREGISTREMENT.md` (gelé), `beta/momentum30_btc_garde/moteur.py`, `scripts/mesurer_momentum30_btc_garde.py`, `data/momentum30_btc_garde/resultats.json`.
"""
    (RAPPORTS / "RAPPORT.md").write_text(rapport, encoding="utf-8")
    resume = f"""# {pastille} {titre} — rapport du programme — {date}

**Verdict au registre : {ID} {verdict}** (issue attendue : {pre.get('issue_attendue')}). Exploration, pas preuve : période déjà vue par MOMENTUM30_BTC, relecture de Jonas en attente.
État du calcul : {n_ok} contrôles sur {len(ctrl)} passés.

## Rendements du {donnees['premier_rendement']} au {donnees['dernier_rendement']}, tous coûts déduits
```
{tableau}
```
{chr(10).join(conds)}

Garde : {len(decl)} déclenchement(s), {res['jours_coupes']} jours coupés.

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
- `rapports/{ID}/RAPPORT.md` (joint) ; code `{m30.commit()}` ; run {run_id}
"""
    (RAPPORTS / "RESUME_DISCORD.md").write_text(resume, encoding="utf-8")


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
    d = m30.charger()
    e, g = expo_garde(d["close"], d["debut"], moteur.SEUIL_GARDE)
    ctrl = controles_garde(d, e, g)
    if not all(x["ok"] for x in ctrl):
        log.error("controle(s) en echec : %s - rien n'est mesure", [x for x in ctrl if not x["ok"]])
        return 1
    run_id = hashlib.sha256(f"{ID}|{pre['empreintes']}|{d['donnees']['sha256_close']}|"
                            f"{d['donnees']['sha256_funding']}".encode()).hexdigest()[:12]
    experiences.enregistrer_run(run_id, ID, "momentum30_btc_garde:L30:G20", pre["empreintes"]["code"],
                                issue="essai journalise avant calcul")
    n_essais = experiences.compteur(famille="invest")
    res = mesurer(d, e, g, n_essais)
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "resultats.json").write_text(json.dumps(m30._propre({"run": run_id, "donnees": d["donnees"],
                                                                   "controles": ctrl, **res}),
                                                      ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    s, h, z, nl = res["strategie"], res["hold"], res["sans_garde"], res["nulls"]
    resultat = (f"garde : Sharpe {s['sharpe']:.4f}, CAGR {s['cagr']:.4f}, MDD {s['mdd']:.4f} ; sans garde : Sharpe "
                f"{z['sharpe']:.4f}, CAGR {z['cagr']:.4f}, MDD {z['mdd']:.4f} ; hold : Sharpe {h['sharpe']:.4f}, "
                f"CAGR {h['cagr']:.4f}, MDD {h['mdd']:.4f} ; conditions {res['conditions']} ; p retenue "
                f"{nl['p_retenue']:.4f} ({nl['verdict_nulls']})")
    cloture = experiences.clore(ID, res["issue"], resultat, runs=[run_id], donnees=d["donnees"], controles=ctrl,
                                conditions=res["conditions"], nulls=dict(nl))
    experiences.enregistrer_run(run_id, ID, "momentum30_btc_garde:L30:G20", pre["empreintes"]["code"], issue=res["issue"])
    ecrire_rapports(pre, res, ctrl, d["donnees"], cloture, run_id)
    print(f"\n{ID} : {res['issue'].upper()}")
    print((RAPPORTS / "RESUME_DISCORD.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
