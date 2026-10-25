/* BETA — onglet Test invest (TI1, Jonas 20/10). Les 5 votes du socle VC dans leur usage invest :
   un panier tenu en buy and hold, expose a E selon le score, juge sur la SURVIE aux grandes
   baisses. Rien ne se calcule ici (decision D3) : l'onglet relit ce que scripts/test_invest.py a
   mesure ; une configuration absente s'affiche avec la commande qui la calcule.
   Les utilitaires d'app.js (preparer, axes, couleur, vide, tuile, nb, pct) ne servent qu'a
   l'execution : app.js est charge apres ce fichier. */

const INVEST = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { vue: null, run: null, periode: "principale", charge: false };

  const VOTES = ["momentum_btc", "taux_reel_10a", "inflation_anticipee_10a", "nasdaq",
                 "fear_greed"];
  const NOMS = { momentum_btc: "momentum BTC 126 j", taux_reel_10a: "taux réel 10 ans (DFII10)",
                 inflation_anticipee_10a: "inflation anticipée (T10YIE)",
                 nasdaq: "Nasdaq (couplage + cassure)", fear_greed: "Fear & Greed",
                 complet: "socle complet" };
  const VERDICTS = { reel: ["effet considéré comme réel", "good"],
                     "non concluant": ["non concluant", "warning"],
                     hasard: ["indistinguable du hasard", "muted"] };

  const echapper = (t) => String(t ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const manque = (v) => v === null || v === undefined || Number.isNaN(v);
  const pc = (v, d = 1) => manque(v) ? "—" : (100 * v).toFixed(d) + " %";
  const n2 = (v, d = 3) => manque(v) ? "—" : Number(v).toFixed(d);
  const nomSignal = (s) => NOMS[s] || (s.startsWith("sans_") ? "sans " + (NOMS[s.slice(5)] || s.slice(5)) : s);

  function verdictHtml(v) {
    if (!v) return '<span class="muet">pas de test</span>';
    const [libelle, ton] = VERDICTS[v] || [v, "muted"];
    return `<span class="verdict-${ton}">${libelle}</span>`;
  }

  function table(entetes, lignes) {
    if (!lignes.length) return '<p class="vide">Aucune donnée.</p>';
    const th = entetes.map((e) => `<th>${e}</th>`).join("");
    const tr = lignes.map((l) => "<tr>" + l.map((c) =>
      (typeof c === "object" && c !== null) ? `<td class="${c.classe || ""}">${c.html}</td>`
                                            : `<td>${c}</td>`).join("") + "</tr>").join("");
    return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  /* ---------- graphiques --------------------------------------------------------------- */

  // Base 100 en echelle log : sur six ans, le panier fait x10 puis /7 ; en lineaire, les annees
  // basses ne se lisent plus.
  function courbesLog(canvas, dates, series) {
    const { ctx, large, haut } = preparer(canvas);
    if (dates.length < 2) return vide(ctx, large, haut, "Pas de série.");
    const marge = { gauche: 52, droite: 12, haut: 14, bas: 22 };
    const logs = series.flatMap((s) => s.v.map((x) => Math.log(100 * x)));
    const lMin = Math.min(...logs), lMax = Math.max(...logs);
    const ecart = (lMax - lMin) * 0.05 || 0.1;
    const yMin = lMin - ecart, yMax = lMax + ecart;
    const x = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (dates.length - 1);
    const y = (l) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - l) / (yMax - yMin);
    ctx.font = "11px system-ui, sans-serif";
    ctx.lineWidth = 1;
    for (let k = -6; k <= 8; k++) {                  // graduations 100 x 2^k
      const valeur = 100 * Math.pow(2, k), l = Math.log(valeur);
      if (l < yMin || l > yMax) continue;
      ctx.strokeStyle = couleur(k === 0 ? "--axis" : "--grid");
      ctx.beginPath();
      ctx.moveTo(marge.gauche, y(l) + 0.5);
      ctx.lineTo(large - marge.droite, y(l) + 0.5);
      ctx.stroke();
      ctx.fillStyle = couleur("--text-muted");
      ctx.textAlign = "right";
      ctx.fillText(valeur >= 10 ? valeur.toFixed(0) : valeur.toFixed(1), marge.gauche - 6, y(l) + 4);
    }
    for (const s of series) {
      ctx.strokeStyle = s.couleur;
      ctx.lineWidth = s.epais ? 2.2 : 1.3;
      ctx.setLineDash(s.pointille ? [5, 4] : []);
      ctx.beginPath();
      s.v.forEach((v, i) => (i ? ctx.lineTo(x(i), y(Math.log(100 * v)))
                                : ctx.moveTo(x(i), y(Math.log(100 * v)))));
      ctx.stroke();
    }
    ctx.setLineDash([]);
    bornes(ctx, dates, marge, large, haut);
  }

  function bornes(ctx, dates, marge, large, haut) {
    ctx.fillStyle = couleur("--text-muted");
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(dates[0], marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(dates[dates.length - 1], large - marge.droite, haut - 6);
  }

  function drawdowns(canvas, dates, series, episodes) {
    const { ctx, large, haut } = preparer(canvas);
    if (dates.length < 2) return vide(ctx, large, haut, "Pas de série.");
    const marge = { gauche: 52, droite: 12, haut: 14, bas: 22 };
    const yMin = Math.min(...series.flatMap((s) => s.v), -0.05) * 1.05, yMax = 0.02;
    const x = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (dates.length - 1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin);
    // Les episodes de grande baisse du panier (B1), du pic au retour (ou a la fin des donnees).
    ctx.fillStyle = couleur("--status-critical") + "22";
    for (const ep of episodes) {
      const fin = ep.fin === null ? dates.length - 1 : ep.fin;
      ctx.fillRect(x(ep.pic), marge.haut, Math.max(1, x(fin) - x(ep.pic)),
                   haut - marge.haut - marge.bas);
    }
    axes(ctx, large, haut, marge, 100 * yMin, 100 * yMax, y(0));
    for (const s of series) {
      ctx.strokeStyle = s.couleur;
      ctx.lineWidth = s.epais ? 1.8 : 1.2;
      ctx.beginPath();
      s.v.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
      ctx.stroke();
    }
    bornes(ctx, dates, marge, large, haut);
  }

  function exposition(canvas, dates, e, eNeutre) {
    const { ctx, large, haut } = preparer(canvas);
    if (!e.length) return vide(ctx, large, haut, "Pas d'exposition.");
    const marge = { gauche: 52, droite: 12, haut: 10, bas: 22 };
    const yMax = Math.max(1, ...e);
    const x = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / e.length;
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / yMax;
    axes(ctx, large, haut, marge, 0, 100 * yMax, null);
    ctx.fillStyle = couleur("--accent") + "55";
    ctx.strokeStyle = couleur("--accent");
    ctx.beginPath();
    ctx.moveTo(x(0), y(0));
    e.forEach((v, i) => { ctx.lineTo(x(i), y(v)); ctx.lineTo(x(i + 1), y(v)); });
    ctx.lineTo(x(e.length), y(0));
    ctx.closePath();
    ctx.fill();
    ctx.setLineDash([4, 4]);
    ctx.strokeStyle = couleur("--text-muted");
    ctx.beginPath();
    ctx.moveTo(marge.gauche, y(eNeutre));
    ctx.lineTo(large - marge.droite, y(eNeutre));
    ctx.stroke();
    ctx.setLineDash([]);
    bornes(ctx, [dates[1], dates[dates.length - 1]], marge, large, haut);
  }

  function histoNull(canvas, valeurs, observe, p) {
    const { ctx, large, haut } = preparer(canvas);
    const v = (valeurs || []).filter((x) => !manque(x));
    if (!v.length || manque(observe)) return vide(ctx, large, haut,
      "Pas de test de permutation pour cette configuration.");
    const marge = { gauche: 40, droite: 12, haut: 18, bas: 22 };
    const min = Math.min(...v, observe), max = Math.max(...v, observe);
    const nCases = 30, pas = (max - min) / nCases || 1;
    const cases = new Array(nCases).fill(0);
    v.forEach((x) => { cases[Math.min(nCases - 1, Math.floor((x - min) / pas))] += 1; });
    const hMax = Math.max(...cases);
    const largeur = (large - marge.gauche - marge.droite) / nCases;
    axes(ctx, large, haut, marge, 0, hMax, null);
    ctx.fillStyle = couleur("--series-neutre");
    cases.forEach((c, i) => {
      const h = (haut - marge.haut - marge.bas) * c / (hMax || 1);
      ctx.fillRect(marge.gauche + i * largeur + 1, haut - marge.bas - h, Math.max(1, largeur - 2), h);
    });
    const xo = marge.gauche + (observe - min) / (max - min || 1) * (large - marge.gauche - marge.droite);
    ctx.strokeStyle = couleur("--accent");
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(xo, marge.haut - 4);
    ctx.lineTo(xo, haut - marge.bas);
    ctx.stroke();
    ctx.fillStyle = couleur("--text-secondary");
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = xo > large / 2 ? "right" : "left";
    ctx.fillText(`observé ${n2(observe)} · p = ${n2(p)}`, xo + (xo > large / 2 ? -6 : 6), marge.haut + 4);
    ctx.textAlign = "left";
    ctx.fillStyle = couleur("--text-muted");
    ctx.fillText("Ulcer " + n2(min), marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(n2(max), large - marge.droite, haut - 6);
  }

  function legende(id, series) {
    $$(id).innerHTML = '<ul class="legende">' + series.map((s) =>
      `<li><span class="pastille" style="background:${s.couleur}"></span>${echapper(s.nom)}`
      + (s.pointille ? " (pointillé)" : "") + "</li>").join("") + "</ul>";
  }

  /* ---------- en-tete, selection ---------------------------------------------------------- */

  function rendreEntete() {
    const c = etat.vue.campagne;
    const p = c && c.periodes[etat.periode];
    const lignes = c ? Object.entries(c.periodes).map(([nom, x]) => [
      `<strong>${nom}</strong>`, `${x.debut} → ${x.fin}`, entier(x.n_jours),
      { html: `${x.n_episodes}${x.puissance_faible ? " — puissance faible" : ""}`,
        classe: x.puissance_faible ? "neg" : "" },
      entier(x.changements_regime)]) : [];
    $$("#invest-entete").innerHTML = `
      <h2>Test invest — les votes du socle VC dans leur usage invest</h2>
      <p class="sous">Préenregistré (${etat.vue.experience}, 20/10) avant toute mesure.
        Exposition E décidée à la clôture et appliquée le lendemain sur un panier des 6 paires
        tenu en buy and hold ; métrique principale : l'Ulcer Index (plus bas = meilleur).
        Règle D4 appliquée mécaniquement : il faut battre les deux nulls (p retenue = la plus
        grande) ; p &lt; 0,05 réel, 0,05 ≤ p &lt; 0,20 non concluant, au-delà hasard.</p>
      <div class="avertir">
        <p><strong>Rien ici n'est hors échantillon</strong> : la période principale inclut le
          hold-out (2025-2026, déjà consommé pour l'allocation quotidienne le 13/10) et ces votes
          ont déjà été regardés sur ces fenêtres. Ce test peut éliminer un vote, pas en valider un.</p>
        <p>Votes DFII10 et Nasdaq pris à leur date de publication FRED (D1) ; trou du Fear &amp;
          Greed du 26/10/2024 comblé par la règle de péremption du socle (D6). Sharpe en
          racine de 365 : non comparable aux mesures VC (racine de 252).</p>
      </div>
      <div class="kpis" style="margin-top:12px">
        ${(etat.vue.compteurs || []).map((k) =>
          tuile(entier(k.valeur), echapper(k.nom), "warning", k.portee)).join("")}
      </div>
      ${c ? `<div class="kpis" style="margin-top:12px">
        ${tuile(entier(c.compteur), "Test invest 1 – compteur au 20/10/2026", "warning",
                "compteur après la campagne")}
        ${tuile(entier(c.runs.length), "mesures de la campagne")}
        ${tuile(p ? entier(p.n_episodes) : "—", `épisodes ≥ 20 % (${etat.periode})`,
                p && p.puissance_faible ? "critical" : "")}
      </div>
      <div class="tableau-wrap" style="margin-top:12px">${table(
        ["période", "fenêtre", "jours", "épisodes ≥ 20 %", "changements de régime (socle)"],
        lignes)}</div>` : '<p class="vide">Campagne pas encore lancée.</p>'}`;
  }

  // Les controles sont dans le HTML (ids verifies par les tests) ; on ne fait que les remplir.
  function initSelection() {
    $$("#invest-periode").innerHTML = Object.keys(etat.vue.periodes).map((p) =>
      `<option value="${p}">${p}</option>`).join("");
    $$("#invest-votes").insertAdjacentHTML("beforeend", VOTES.map((v) =>
      `<label class="chk"><input type="checkbox" value="${v}" checked> ${NOMS[v]}</label>`).join(""));
    $$("#invest-afficher").addEventListener("click", chercher);
    $$("#invest-periode").addEventListener("change", chercher);
  }

  function rendreSelection() {
    const cfg = etat.run ? etat.run.config : null;
    $$("#invest-periode").value = etat.periode;
    if (!cfg) return;
    document.querySelectorAll(".invest-votes input").forEach((i) => {
      i.checked = cfg.indicateurs.includes(i.value);
    });
    $$("#invest-mapping").value = cfg.mapping.nom;
    $$("#invest-theta").value = cfg.theta_episode;
    $$("#invest-cout-pb").value = cfg.kappa_pb;
    $$("#invest-b").value = cfg.b;
    $$("#invest-graine").value = cfg.graine;
  }

  function choix() {
    return {
      periode: $$("#invest-periode").value,
      indicateurs: [...document.querySelectorAll(".invest-votes input:checked")].map((i) => i.value),
      mapping: $$("#invest-mapping").value,
      theta: Number($$("#invest-theta").value), kappa: Number($$("#invest-cout-pb").value),
      b: Number($$("#invest-b").value), graine: Number($$("#invest-graine").value),
    };
  }

  function chercher() {
    const c = choix();
    etat.periode = c.periode;
    rendreEntete();
    rendreCampagne();
    const trouve = etat.vue.runs.find((r) => r.periode === c.periode && r.mapping === c.mapping
      && r.pit === "publication" && r.indicateurs.length === c.indicateurs.length
      && c.indicateurs.every((v) => r.indicateurs.includes(v))
      && Math.abs(r.theta_episode - c.theta) < 1e-9 && Math.abs(r.kappa_pb - c.kappa) < 1e-9
      && r.b === c.b && r.graine === c.graine);
    if (trouve) return montrer(trouve.run_id).then(rendreSelection);
    $$("#invest-detail").hidden = true;
    const commande = etat.vue.commande.replace("{periode}", c.periode)
      .replace("{indicateurs}", c.indicateurs.join(",") || "momentum_btc")
      .replace("{mapping}", c.mapping).replace("{theta}", c.theta).replace("{kappa}", c.kappa)
      .replace("{b}", c.b).replace("{graine}", c.graine);
    $$("#invest-message").innerHTML = `<span class="neg">Configuration pas encore calculée.</span>
      Le dashboard du VPS reste en lecture seule (D3) ; elle se calcule en ligne de commande, et
      compte un essai de plus au compteur :<br><code class="invest-commande">${echapper(commande)}</code>`;
  }

  async function montrer(runId) {
    $$("#invest-message").textContent = "chargement…";
    try {
      etat.run = await fetch("/api/invest/run?id=" + runId).then((r) => r.json());
    } catch (exc) {
      $$("#invest-message").textContent = "serveur injoignable : " + exc.message;
      return;
    }
    if (etat.run.erreur) {
      $$("#invest-message").textContent = etat.run.erreur;
      return;
    }
    $$("#invest-message").textContent = `${etat.run.libelle} · ${etat.run.periode.nom} · run ${runId}`
      + ` · ${etat.run.statut === "campagne" ? "mesure préenregistrée (TI1)" : "exploratoire (hors campagne)"}`;
    $$("#invest-detail").hidden = false;
    rendreRun();
  }

  /* ---------- un run -------------------------------------------------------------------- */

  function rendreRun() {
    const r = etat.run;
    if (!r) return;
    const m = r.metriques, s = r.series, st = m.strategie;
    const tonVerdict = r.verdict ? (VERDICTS[r.verdict] || [0, ""])[1] : "muted";
    $$("#invest-resume").innerHTML = `
      <h2>${echapper(r.libelle)} — ${r.periode.nom} (${r.periode.debut} → ${r.periode.fin})</h2>
      <div class="kpis">
        ${tuile(n2(st.ulcer), "Ulcer", "", "panier " + n2(m.panier.ulcer))}
        ${tuile(pc(st.mdd), "MDD", "", "panier " + pc(m.panier.mdd))}
        ${tuile(pc(st.protection), "protection agrégée", "", `${r.periode.n_episodes} épisode(s)`)}
        ${tuile(n2(st.calmar, 2), "Calmar")}
        ${tuile(pc(st.cagr), "CAGR", "", "panier " + pc(m.panier.cagr))}
        ${tuile(n2(st.sharpe, 2), "Sharpe (√365)", "", "DSR " + n2(st.dsr, 2) + " · N " + (st.n_essais || "—"))}
        ${tuile(n2(st.expo_moyenne, 2), "exposition moyenne", "", `${st.changements_expo} changements`)}
        ${tuile(r.verdict ? (VERDICTS[r.verdict] || [r.verdict])[0] : "pas de test", "verdict D4", tonVerdict,
                r.nulls ? "p retenue " + n2(r.nulls.p_retenue) : "")}
      </div>
      <div class="atelier-boutons" style="margin-top:10px">
        <button class="btn" data-export="run-md">Exporter (Markdown)</button>
        <button class="btn" data-export="run-csv">Exporter (CSV)</button>
      </div>`;
    const couleurs = { strategie: couleur("--accent"), panier: couleur("--series-neutre"),
                       btc: couleur("--actif-btc") };
    const series = [
      { nom: "stratégie", v: s.v_s, couleur: couleurs.strategie, epais: true },
      { nom: "panier (buy and hold)", v: s.v_b, couleur: couleurs.panier, pointille: true },
      { nom: "BTC (buy and hold)", v: s.v_btc, couleur: couleurs.btc },
    ];
    courbesLog($$("#invest-courbes"), s.dates, series);
    legende("#invest-courbes-legende", series);
    const dds = [{ nom: "stratégie", v: s.dd_s, couleur: couleurs.strategie, epais: true },
                 { nom: "panier", v: s.dd_b, couleur: couleurs.panier }];
    drawdowns($$("#invest-dd"), s.dates, dds, r.survie.episodes);
    legende("#invest-dd-legende", dds.concat([{ nom: "épisode de grande baisse du panier",
      couleur: couleur("--status-critical") + "55" }]));
    exposition($$("#invest-expo"), s.dates, s.e, r.config.mapping.e_neutre);
    const nl = r.nulls;
    histoNull($$("#invest-null-circ"), nl && nl.circulaire.ulcer, nl && nl.observe.ulcer,
              nl && nl.p.circulaire.ulcer);
    histoNull($$("#invest-null-seg"), nl && nl.segments.ulcer, nl && nl.observe.ulcer,
              nl && nl.p.segments.ulcer);
    rendreTablesRun();
  }

  function rendreTablesRun() {
    const r = etat.run, m = r.metriques;
    const ligne = (nom, x) => [nom, n2(x.ulcer), pc(x.mdd), entier(x.duree_sous_eau_max_j),
      n2(x.calmar, 2), pc(x.cagr), pc(x.vol), n2(x.sharpe, 2), pc(x.protection),
      n2(x.expo_moyenne, 2)];
    $$("#invest-metriques").innerHTML = table(["", "Ulcer", "MDD", "sous l'eau (j)", "Calmar",
      "CAGR", "vol", "Sharpe", "protection", "expo"], [
      ligne("<strong>stratégie</strong>", m.strategie),
      ligne(`témoin (E constante ${n2(m.temoin.expo_moyenne, 2)})`, m.temoin),
      ligne("panier (buy and hold)", { ...m.panier, expo_moyenne: 1 }),
      ligne("BTC (buy and hold)", { ...m.btc, expo_moyenne: 1 })]);
    $$("#invest-episodes").innerHTML = table(["pic", "creux", "fin", "panier", "stratégie",
      "protection", "retard (j)", "part déjà subie", "rebond raté", "retour"],
      r.survie.episodes.map((e) => [e.date_pic, e.date_creux, e.date_fin || "pas rattrapé",
        pc(e.perte_b), pc(e.perte_s),
        { html: pc(e.protection), classe: e.protection >= 0 ? "pos" : "neg" },
        manque(e.retard_j) ? "pas de réaction" : e.retard_j, pc(e.part_subie), pc(e.rebond_rate),
        echapper(e.retour)]));
    const nl = r.nulls;
    $$("#invest-pvalues").innerHTML = nl ? table(["métrique", "observé", "p circulaire",
      "p segments"], [["Ulcer (principale)", "ulcer"], ["|MDD|", "mdd_abs"],
      ["protection", "prot"], ["Calmar", "calmar"]].map(([nom, cle]) => [nom, n2(nl.observe[cle]),
        n2(nl.p.circulaire[cle]), n2(nl.p.segments[cle])]))
      + `<p class="sous" style="margin-top:8px">p retenue (Ulcer, la plus grande des deux) :
        <strong>${n2(nl.p_retenue)}</strong> → ${verdictHtml(r.verdict)} · B = ${nl.b},
        graine ${nl.graine}, décalage ≥ ${nl.m_j} j.</p>`
      : '<p class="vide">Pas de test de permutation pour cette configuration (préenregistrés :'
        + " socle complet et chaque vote seul).</p>";
    const f = r.survie.faux_signaux, c = r.survie.captures;
    $$("#invest-cout").innerHTML = `
      <div class="kpis">
        ${tuile(`${f.n_faux} / ${f.n_evalues}`, "faux signaux", "", `${f.n_non_evaluables} non évaluable(s)`)}
        ${tuile(pc(f.cout_cumule), "coût cumulé des faux signaux")}
        ${tuile(n2(c.haussiere, 2), "capture haussière", "", `${c.n_hausse} semaines`)}
        ${tuile(n2(c.baissiere, 2), "capture baissière", "", `${c.n_baisse} semaines`)}
      </div>
      <p class="sous" style="margin-top:10px">Faux signal : passage en défensif sans baisse du panier
        d'au moins ${pc(r.config.theta_f, 0)} dans les ${r.config.horizon_j} jours ; coût =
        (E avant − E défensive) × rendement du panier pendant la période défensive. Profil
        recherché : capture haussière élevée, baissière nettement plus faible.</p>`;
  }

  /* ---------- la campagne : C1, C2, C3, PIT -------------------------------------------- */

  function rendreCampagne() {
    const c = etat.vue.campagne;
    if (!c) {
      for (const id of ["#invest-c1", "#invest-c2", "#invest-kappa", "#invest-pit"])
        $$(id).innerHTML = '<p class="vide">Campagne pas encore lancée.</p>';
      return;
    }
    const p = c.periodes[etat.periode], syn = p.synthese;
    $$("#invest-c1").innerHTML = table(["signal", "Ulcer", "MDD", "protection", "expo",
      "p circulaire", "p segments", "p retenue", "q BH (informatif)", "verdict D4"],
      syn.c1.map((l) => [`<a href="#invest" data-run="${l.run_id}">${echapper(nomSignal(l.signal))}</a>`,
        n2(l.ulcer), pc(l.mdd), pc(l.protection), n2(l.expo_moyenne, 2), n2(l.p_circulaire),
        n2(l.p_segments), `<strong>${n2(l.p_retenue)}</strong>`, n2(l.q_bh), verdictHtml(l.verdict)]))
      + `<p class="sous" style="margin-top:8px">Socle complet en paliers (veille = 0,7), sans test :
        Ulcer ${n2(syn.socle_paliers.ulcer)}, MDD ${pc(syn.socle_paliers.mdd)}, protection
        ${pc(syn.socle_paliers.protection)}.</p>`;
    $$("#invest-c2").innerHTML = table(["vote retiré", "Δ Ulcer", "Δ MDD", "Δ protection",
      "Δ CAGR", "lecture"], VOTES.map((v) => {
      const x = syn.c2[v];
      return [echapper(NOMS[v]), n2(x.delta.ulcer), pc(x.delta.mdd), pc(x.delta.protection),
        pc(x.delta.cagr), x.lecture.startsWith("contribue") ? { html: "contribue", classe: "pos" }
          : { html: "inutile ou nuisible", classe: "neg" }];
    })) + `<p class="sous" style="margin-top:8px">Δ = M(socle complet) − M(sans ce vote). Si le
      retirer n'abîme ni l'Ulcer, ni le MDD, ni la protection, il est inutile ou nuisible.</p>`;
    rendreKappa(syn.c3);
    const d = c.diagnostic_pit[etat.periode];
    $$("#invest-pit").innerHTML = d ? table(["vote", "jours différents", "par jour de la semaine"],
      VOTES.map((v) => [echapper(NOMS[v]), entier(d.votes[v].jours),
        Object.entries(d.votes[v].par_jour).map(([j, n]) => `${j} ${n}`).join(" · ") || "—"]))
      + `<p class="sous" style="margin-top:8px">Décalage fixe de 2 jours (socle VC) contre
        calendrier de publication FRED, sur ${entier(d.jours)} jours : l'état du régime diffère
        ${entier(d.etat.jours)} jours. Les backtests VC2-VC5 utilisent le décalage fixe.</p>` : "";
  }

  function rendreKappa(c3) {
    const cellule = (k) => {
      if (manque(k)) return '<td class="muet">—</td>';
      const fond = k >= 0 ? couleur("--accent") : couleur("--status-critical");
      const alpha = Math.round(Math.min(1, Math.abs(k)) * 200).toString(16).padStart(2, "0");
      return `<td class="kappa" style="background:${fond}${alpha}">${n2(k, 2)}</td>`;
    };
    const court = { momentum_btc: "momentum", taux_reel_10a: "DFII10",
                    inflation_anticipee_10a: "T10YIE", nasdaq: "Nasdaq", fear_greed: "F&G" };
    $$("#invest-kappa").innerHTML = `<div class="tableau-wrap"><table><thead><tr><th></th>
      ${VOTES.map((v) => `<th>${court[v]}</th>`).join("")}</tr></thead><tbody>
      ${VOTES.map((a) => `<tr><th>${court[a]}</th>${VOTES.map((b) => cellule(c3.kappa[a][b])).join("")}</tr>`).join("")}
      </tbody></table></div>
      <p class="sous" style="margin-top:8px">Kappa de Cohen sur ${etat.periode} : l'accord au-delà
        du hasard. Élevé = les deux votes comptent presque double dans le score. Spearman :
        ${VOTES.flatMap((a, i) => VOTES.slice(i + 1).map((b) =>
          `${court[a]}/${court[b]} ${n2(c3.spearman[a][b], 2)}`)).join(" · ")}.</p>`;
  }

  function rendreListe() {
    $$("#invest-runs").innerHTML = table(["run", "statut", "période", "configuration", "κ",
      "θ", "B", "Ulcer", "verdict"], etat.vue.runs.map((r) => [
      `<a href="#invest" data-run="${r.run_id}">${r.run_id}</a>`, r.statut, r.periode,
      echapper(r.libelle), r.kappa_pb, r.theta_episode, r.b, n2(r.ulcer), verdictHtml(r.verdict)]));
  }

  /* ---------- export : Markdown ou CSV, avec tous les parametres ------------------------- */

  function telecharger(nom, type, contenu) {
    const lien = document.createElement("a");
    lien.href = URL.createObjectURL(new Blob([contenu], { type }));
    lien.download = nom;
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
  }

  function exporterRun(format) {
    const r = etat.run, st = r.metriques.strategie;
    const nom = `test-invest_${r.periode.nom}_${r.signal}_${r.config.mapping.nom}_${r.run_id}`;
    const params = JSON.stringify(r.config, null, 1);
    if (format === "csv") {
      const lignes = [["cle", "valeur"], ["run_id", r.run_id], ["statut", r.statut],
        ["donnees", r.donnees.empreinte], ["compteur", r.compteur], ["code", r.code],
        ...Object.entries(r.config).map(([k, v]) => ["config." + k, JSON.stringify(v)]),
        ...Object.entries(st).map(([k, v]) => ["strategie." + k, v]),
        ["verdict", r.verdict], ["p_retenue", r.nulls ? r.nulls.p_retenue : ""],
        [], ["date", "V_strategie", "V_panier", "V_btc", "DD_strategie", "DD_panier", "E_en_vigueur"],
        ...r.series.dates.map((d, i) => [d, r.series.v_s[i], r.series.v_b[i], r.series.v_btc[i],
          r.series.dd_s[i], r.series.dd_b[i], i ? r.series.e[i - 1] : ""])];
      return telecharger(nom + ".csv", "text/csv", lignes.map((l) => l.join(";")).join("\n"));
    }
    const md = [`# Test invest — ${r.libelle} — ${r.periode.nom}`, "",
      `Run \`${r.run_id}\` (${r.statut}) · données \`${r.donnees.empreinte}\` (PIT ${r.donnees.pit},`
      + ` fin ${r.donnees.fin}) · compteur ${r.compteur} · code ${r.code} · ${r.calcule_le}`, "",
      `Période ${r.periode.debut} → ${r.periode.fin} : ${r.periode.n_jours} jours,`
      + ` ${r.periode.n_episodes} épisode(s) ≥ ${pc(r.config.theta_episode, 0)}`
      + `${r.periode.puissance_faible ? " (**moins de 3 : puissance faible**)" : ""},`
      + ` ${r.periode.changements_regime} changements de régime.`, "",
      `**Verdict D4** : ${r.verdict ? VERDICTS[r.verdict][0] : "pas de test"}`
      + (r.nulls ? ` (p retenue ${n2(r.nulls.p_retenue)} ; circulaire ${n2(r.nulls.p.circulaire.ulcer)},`
        + ` segments ${n2(r.nulls.p.segments.ulcer)})` : ""), "",
      "| | Ulcer | MDD | Calmar | CAGR | Sharpe | protection | expo |", "|---|---|---|---|---|---|---|---|",
      ...[["stratégie", st], ["témoin", r.metriques.temoin], ["panier", r.metriques.panier],
          ["BTC", r.metriques.btc]].map(([n, x]) => `| ${n} | ${n2(x.ulcer)} | ${pc(x.mdd)} |`
          + ` ${n2(x.calmar, 2)} | ${pc(x.cagr)} | ${n2(x.sharpe, 2)} | ${pc(x.protection)} |`
          + ` ${n2(x.expo_moyenne, 2)} |`), "",
      "## Épisodes", "", "| pic | creux | fin | panier | stratégie | protection | retard (j) | part subie | rebond raté |",
      "|---|---|---|---|---|---|---|---|---|",
      ...r.survie.episodes.map((e) => `| ${e.date_pic} | ${e.date_creux} | ${e.date_fin || "—"} |`
        + ` ${pc(e.perte_b)} | ${pc(e.perte_s)} | ${pc(e.protection)} | ${e.retard_j ?? "—"} |`
        + ` ${pc(e.part_subie)} | ${pc(e.rebond_rate)} |`), "",
      "## Paramètres", "", "```json", params, "```", ""].join("\n");
    telecharger(nom + ".md", "text/markdown", md);
  }

  function exporterCampagne(format) {
    const c = etat.vue.campagne;
    if (!c) return;
    const p = c.periodes[etat.periode], syn = p.synthese;
    const nom = `test-invest_campagne-TI1_${etat.periode}`;
    if (format === "csv") {
      const tete = ["signal", "ulcer", "mdd", "protection", "expo_moyenne", "p_circulaire",
                    "p_segments", "p_retenue", "q_bh", "verdict", "run_id"];
      return telecharger(nom + ".csv", "text/csv", [tete.join(";")].concat(
        syn.c1.map((l) => tete.map((k) => l[k] ?? "").join(";"))).join("\n"));
    }
    const md = [`# Test invest — campagne TI1 — ${etat.periode}`, "",
      `${p.debut} → ${p.fin} : ${p.n_jours} jours, ${p.n_episodes} épisode(s) ≥ 20 %`
      + `${p.puissance_faible ? " (**puissance faible**)" : ""}. Compteur ${c.compteur} ·`
      + ` données \`${c.donnees.empreinte}\` (PIT ${c.donnees.pit}) · code ${c.code}.`, "",
      "| signal | Ulcer | MDD | protection | p circ. | p seg. | p retenue | q BH | verdict D4 |",
      "|---|---|---|---|---|---|---|---|---|",
      ...syn.c1.map((l) => `| ${nomSignal(l.signal)} | ${n2(l.ulcer)} | ${pc(l.mdd)} |`
        + ` ${pc(l.protection)} | ${n2(l.p_circulaire)} | ${n2(l.p_segments)} | ${n2(l.p_retenue)} |`
        + ` ${n2(l.q_bh)} | ${l.verdict ? VERDICTS[l.verdict][0] : "—"} |`), "",
      "## Ablation (C2)", "", "| vote retiré | Δ Ulcer | Δ MDD | Δ protection | lecture |", "|---|---|---|---|---|",
      ...VOTES.map((v) => `| ${NOMS[v]} | ${n2(syn.c2[v].delta.ulcer)} | ${pc(syn.c2[v].delta.mdd)} |`
        + ` ${pc(syn.c2[v].delta.protection)} | ${syn.c2[v].lecture} |`), ""].join("\n");
    telecharger(nom + ".md", "text/markdown", md);
  }

  /* ---------- cycle de vie ---------------------------------------------------------------- */

  async function charger() {
    try {
      etat.vue = await fetch("/api/invest").then((r) => r.json());
    } catch (exc) {
      $$("#invest-entete").innerHTML = `<p class="erreur">serveur injoignable : ${echapper(exc.message)}</p>`;
      return;
    }
    if (etat.vue.erreur) {
      $$("#invest-entete").innerHTML = `<p class="erreur">${echapper(etat.vue.erreur)}</p>`;
      return;
    }
    etat.charge = true;
    initSelection();
    rendreEntete();
    rendreCampagne();
    rendreListe();
    const socle = etat.vue.runs.find((r) => r.periode === etat.periode && r.signal === "complet"
                                            && r.mapping === "socle" && r.statut === "campagne");
    if (socle) await montrer(socle.run_id);
    rendreSelection();
  }

  document.addEventListener("click", (ev) => {
    const lien = ev.target.closest("[data-run]");
    if (lien && lien.closest("#onglet-invest")) {
      ev.preventDefault();
      montrer(lien.dataset.run).then(rendreSelection);
      return;
    }
    const exp = ev.target.closest("[data-export]");
    if (exp && exp.closest("#onglet-invest")) {
      const [quoi, format] = exp.dataset.export.split("-");
      if (quoi === "run") exporterRun(format); else exporterCampagne(format);
    }
  });

  return {
    afficher: () => (etat.charge ? (rendreRun(), rendreCampagne()) : charger()),
    aDesDonnees: () => etat.charge,
  };
})();
