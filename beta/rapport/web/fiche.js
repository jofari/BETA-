/* La fiche d'une candidate : tout ce que la batterie a trouve, sur un ecran.
 *
 * Une regle de lecture gouverne toute la mise en page : ce qui TUE une candidate est en
 * haut, ce qui la flatte est en bas. Le verdict et les portes echouees precedent la courbe
 * d'equity, parce qu'une belle courbe lue en premier eteint tout esprit critique pour le
 * reste de la page — c'est la panne cognitive que ce banc d'essai existe pour eviter.
 *
 * Deuxieme regle : rien n'est comble. Une porte non executee s'affiche « non executee »,
 * jamais un tiret qui se confondrait avec un zero.
 */

const FICHE = (() => {
  const etatFiche = { liste: [], courant: null, donnees: null };

  const q = (sel) => document.querySelector(sel);
  const n2 = (v) => (v === null || v === undefined || Number.isNaN(v))
    ? "—" : Number(v).toFixed(2);
  const n4 = (v) => (v === null || v === undefined || Number.isNaN(v))
    ? "—" : Number(v).toFixed(4);
  const pc = (v) => (v === null || v === undefined || Number.isNaN(v))
    ? "—" : (Number(v) * 100).toFixed(1) + " %";
  const ent = (v) => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("fr-FR");
  const jour = (s) => s ? String(s).slice(0, 10) : "—";

  const TONS = { confirmee: "good", infirmee: "critical", indecidable: "warn" };
  const ETIQUETTE_PORTE = {
    S1_benjamini_hochberg: "S1 · Benjamini-Hochberg",
    S2_sharpe_degonfle: "S2 · Sharpe dégonflé",
    S3_bootstrap: "S3 · bootstrap par blocs",
    S4_monte_carlo: "S4 · Monte-Carlo",
    S5_synthetique: "S5 · chemins synthétiques",
    S6_walk_forward: "S6 · walk-forward purgé",
    S7_reality_check: "S7 · reality check",
    S8_buy_and_hold: "S8 · buy-and-hold",
    S9_diversification: "S9 · diversification",
  };

  /* ---------- dessin ------------------------------------------------------------------- */

  const CSS = getComputedStyle(document.documentElement);
  const couleur = (nom) => CSS.getPropertyValue(nom).trim();

  function toile(canvas) {
    const ratio = window.devicePixelRatio || 1;
    const large = canvas.clientWidth || 600;
    const haut = canvas.clientHeight || 200;
    canvas.width = large * ratio;
    canvas.height = haut * ratio;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, large, haut);
    ctx.font = "11px system-ui, sans-serif";
    return { ctx, large, haut };
  }

  function rien(ctx, large, haut, message) {
    ctx.fillStyle = couleur("--text-muted");
    ctx.textAlign = "center";
    ctx.fillText(message, large / 2, haut / 2);
  }

  function grille(ctx, large, haut, marge, yMin, yMax) {
    ctx.strokeStyle = couleur("--grid");
    ctx.fillStyle = couleur("--text-muted");
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = marge.haut + (haut - marge.haut - marge.bas) * i / 4;
      const valeur = yMax - (yMax - yMin) * i / 4;
      ctx.beginPath();
      ctx.moveTo(marge.gauche, y + 0.5);
      ctx.lineTo(large - marge.droite, y + 0.5);
      ctx.stroke();
      ctx.textAlign = "right";
      ctx.fillText(Math.abs(valeur) >= 1000 ? (valeur / 1000).toFixed(0) + "k"
        : valeur.toFixed(1), marge.gauche - 6, y + 4);
    }
  }

  function serie(ctx, valeurs, x, y, teinte, epaisseur = 2) {
    ctx.beginPath();
    valeurs.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    ctx.strokeStyle = teinte;
    ctx.lineWidth = epaisseur;
    ctx.stroke();
  }

  /** Equity de la candidate contre buy-and-hold, ramenes tous deux a une base 100.
   *  Les superposer est le seul moyen de voir ce que la courbe seule cache toujours :
   *  qu'une hausse de 40 % pendant que le marche en fait 300 est une perte relative. */
  function equityContreHold(canvas, donnees) {
    const { ctx, large, haut } = toile(canvas);
    const courbe = donnees.courbe.equity || [];
    if (courbe.length < 2) return rien(ctx, large, haut, "Pas assez de trades.");
    const base = courbe[0] || 1;
    const moi = courbe.map((v) => v / base * 100);
    const holdBrut = (donnees.hold.courbe.valeur || []);
    const hold = holdBrut.map((v) => v * 100);

    const marge = { gauche: 52, droite: 12, haut: 14, bas: 24 };
    const toutes = moi.concat(hold.length ? hold : []);
    const yMax = Math.max(...toutes, 110);
    const yMin = Math.min(...toutes, 90);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin || 1);
    grille(ctx, large, haut, marge, yMin, yMax);

    if (hold.length > 1) {
      const xh = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (hold.length - 1);
      serie(ctx, hold, xh, y, couleur("--text-muted"), 1.5);
    }
    const xm = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (moi.length - 1);
    const fin = moi[moi.length - 1];
    serie(ctx, moi, xm, y, fin >= 100 ? couleur("--status-good") : couleur("--status-critical"));

    ctx.fillStyle = couleur("--text-muted");
    ctx.textAlign = "left";
    ctx.fillText(jour(donnees.courbe.ts[0]), marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(jour(donnees.courbe.ts[donnees.courbe.ts.length - 1]), large - marge.droite, haut - 6);
    ctx.textAlign = "left";
    ctx.fillStyle = couleur("--status-good");
    ctx.fillText("— candidate", marge.gauche + 4, marge.haut + 12);
    ctx.fillStyle = couleur("--text-muted");
    ctx.fillText("— buy-and-hold", marge.gauche + 90, marge.haut + 12);
  }

  /** Le cone Monte-Carlo : toutes les trajectoires compatibles avec les memes trades. */
  function cone(canvas, mc) {
    const { ctx, large, haut } = toile(canvas);
    const p5 = mc.cone.p5 || [], p50 = mc.cone.p50 || [], p95 = mc.cone.p95 || [];
    if (p50.length < 2) return rien(ctx, large, haut, "Monte-Carlo non calculé.");
    const marge = { gauche: 52, droite: 12, haut: 14, bas: 24 };
    const yMax = Math.max(...p95, ...p50);
    const yMin = Math.min(...p5, ...p50);
    const x = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (p50.length - 1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin || 1);
    grille(ctx, large, haut, marge, yMin, yMax);

    ctx.beginPath();
    p95.forEach((v, i) => (i ? ctx.lineTo(x(i), y(v)) : ctx.moveTo(x(i), y(v))));
    for (let i = p5.length - 1; i >= 0; i--) ctx.lineTo(x(i), y(p5[i]));
    ctx.closePath();
    ctx.fillStyle = couleur("--accent") + "22";
    ctx.fill();
    serie(ctx, p50, x, y, couleur("--accent"), 1.5);
    ctx.fillStyle = couleur("--text-muted");
    ctx.textAlign = "left";
    ctx.fillText("p5 – p95 sur 10 000 ordres de trades possibles", marge.gauche + 4, marge.haut + 12);
  }

  /** Histogramme generique a partir de {bords, effectifs}, avec un repere sur la valeur reelle. */
  function barres(canvas, histo, reel = null, unite = "") {
    const { ctx, large, haut } = toile(canvas);
    const eff = histo && histo.effectifs || [];
    if (!eff.length) return rien(ctx, large, haut, "Distribution non calculée.");
    const marge = { gauche: 46, droite: 12, haut: 14, bas: 24 };
    const hMax = Math.max(...eff);
    const largeurCase = (large - marge.gauche - marge.droite) / eff.length;
    grille(ctx, large, haut, marge, 0, hMax);
    const min = histo.bords[0], max = histo.bords[histo.bords.length - 1];
    eff.forEach((compte, i) => {
      const centre = (histo.bords[i] + histo.bords[i + 1]) / 2;
      const h = (haut - marge.haut - marge.bas) * compte / (hMax || 1);
      ctx.fillStyle = centre >= 0 ? couleur("--status-good") : couleur("--status-critical");
      ctx.fillRect(marge.gauche + i * largeurCase + 1, haut - marge.bas - h,
        Math.max(1, largeurCase - 2), h);
    });
    if (reel !== null && reel !== undefined && Number.isFinite(reel)) {
      const xr = marge.gauche + (reel - min) / (max - min || 1) * (large - marge.gauche - marge.droite);
      ctx.strokeStyle = couleur("--axis");
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(xr, marge.haut);
      ctx.lineTo(xr, haut - marge.bas);
      ctx.stroke();
      ctx.fillStyle = couleur("--text-primary");
      ctx.textAlign = xr > large / 2 ? "right" : "left";
      ctx.fillText("observé " + n2(reel) + unite, xr + (xr > large / 2 ? -6 : 6), marge.haut + 12);
    }
    ctx.fillStyle = couleur("--text-muted");
    ctx.textAlign = "left";
    ctx.fillText(n2(min) + unite, marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(n2(max) + unite, large - marge.droite, haut - 6);
  }

  /** Barres verticales signees : P&L par annee, IS/OOS par pli. */
  function colonnes(canvas, libelles, series) {
    const { ctx, large, haut } = toile(canvas);
    if (!libelles.length) return rien(ctx, large, haut, "Rien à ventiler.");
    const marge = { gauche: 46, droite: 12, haut: 14, bas: 26 };
    const toutes = series.flatMap((s) => s.valeurs.filter((v) => Number.isFinite(v)));
    const yMax = Math.max(...toutes, 0.1), yMin = Math.min(...toutes, -0.1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin || 1);
    grille(ctx, large, haut, marge, yMin, yMax);
    const zone = (large - marge.gauche - marge.droite) / libelles.length;
    const largeurBarre = Math.max(3, (zone - 6) / series.length);

    ctx.strokeStyle = couleur("--axis");
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(marge.gauche, y(0));
    ctx.lineTo(large - marge.droite, y(0));
    ctx.stroke();

    libelles.forEach((libelle, i) => {
      series.forEach((s, j) => {
        const v = s.valeurs[i];
        if (!Number.isFinite(v)) return;
        const x = marge.gauche + i * zone + 3 + j * largeurBarre;
        ctx.fillStyle = s.teinte || (v >= 0 ? couleur("--status-good") : couleur("--status-critical"));
        ctx.fillRect(x, Math.min(y(v), y(0)), largeurBarre - 1, Math.abs(y(v) - y(0)));
      });
      ctx.fillStyle = couleur("--text-muted");
      ctx.textAlign = "center";
      ctx.fillText(libelle, marge.gauche + i * zone + zone / 2, haut - 8);
    });
  }

  /* ---------- rendu -------------------------------------------------------------------- */

  function porteHtml(nom, passe) {
    const etiquette = ETIQUETTE_PORTE[nom] || nom;
    if (passe === true) return `<li class="porte ok">✓ ${etiquette}</li>`;
    if (passe === false) return `<li class="porte ko">✕ ${etiquette}</li>`;
    return `<li class="porte na">· ${etiquette} <em>non exécutée</em></li>`;
  }

  function enTete(d) {
    const v = d.verdict;
    const m = v.metriques || {};
    const ton = TONS[v.issue] || "";
    const ident = identiteDe(d.explication);
    // Un titre reconstitue du nom de fichier se signale. La regle « rien n'est comble »
    // vaut pour les libelles autant que pour les chiffres : un titre plausible mais
    // fabrique serait pire que l'identifiant brut qu'il remplace.
    const reconstitue = ident.source === "aucune"
      ? ' <span class="badge" title="Cette candidate ne déclare pas de titre : '
        + 'ce libellé est reconstitué du nom de fichier.">titre reconstitué</span>' : "";
    return `
      <div class="verdict-bandeau" data-tone="${ton}">
        <div>
          <h2>${echapper(ident.titre)} <span class="badge">${v.experience}</span></h2>
          <p class="sous"><code>${echapper(ident.module)}</code>${reconstitue}
             · run ${v.run_id} · ${v.timeframe} · ${(v.paires || []).join(" ")}
             · split ${v.split} · essai cumulé n° ${v.n_essais_cumules}</p>
        </div>
        <div class="verdict-issue" data-tone="${ton}">${(v.issue || "").toUpperCase()}</div>
      </div>
      <div class="kpis-fiche">
        ${tuileF(ent(m.n), "trades")}
        ${tuileF(n4(m.r_moyen), "R moyen", m.r_moyen >= 0 ? "good" : "critical")}
        ${tuileF(n4(m.mde_r), "MDE", "warn", "plus petit effet détectable")}
        ${tuileF(pc(m.win_rate), "win rate")}
        ${tuileF(n2(m.profit_factor), "profit factor")}
        ${tuileF(n2(d.sharpe_degonfle.sharpe), "Sharpe")}
        ${tuileF(n2(d.sharpe_degonfle.sharpe_seuil), "Sharpe du hasard",
          "warn", `attendu du max de ${d.sharpe_degonfle.n_essais || "?"} essais`)}
        ${tuileF(n2(d.hold.ecarts.ecart_rendement_pct), "écart au hold (pts)",
          d.hold.ecarts.passe ? "good" : "critical")}
      </div>
      <ul class="portes">
        ${Object.entries(v.portes || {}).map(([nom, passe]) => porteHtml(nom, passe)).join("")}
      </ul>
      ${(v.reserves || []).length
        ? `<div class="reserves"><h3>Réserves</h3><ul>${
          v.reserves.map((r) => `<li>${echapper(r)}</li>`).join("")}</ul></div>` : ""}`;
  }

  /** L'identite d'un run, quelle que soit l'ancienneté du verdict qui la porte.
   *  Le serveur la resout deja ; ce repli couvre le cas d'une reponse tronquee, jamais
   *  celui d'une candidate sans titre — ca, c'est `source: "aucune"` et ca se dit. */
  function identiteDe(source) {
    const i = (source || {}).identite || {};
    return { titre: i.titre || i.module || "—", module: i.module || "—",
             description: i.description || "", source: i.source || "aucune" };
  }

  function tuileF(valeur, libelle, ton = "", note = "") {
    return `<div class="kpi" data-tone="${ton}">
      <span class="kpi-value">${valeur}</span>
      <span class="kpi-label">${libelle}</span>
      ${note ? `<span class="kpi-note">${note}</span>` : ""}
    </div>`;
  }

  function echapper(texte) {
    const div = document.createElement("div");
    div.textContent = String(texte);
    return div.innerHTML;
  }

  function tableauSimple(lignes, colonnes) {
    if (!lignes || !lignes.length) return '<p class="vide">—</p>';
    const th = colonnes.map((c) => `<th>${c}</th>`).join("");
    const tr = lignes.map((l) => `<tr>${colonnes.map((c) => {
      const v = l[c];
      const texte = typeof v === "number" ? (Number.isInteger(v) ? ent(v) : n4(v))
        : echapper(v === null || v === undefined ? "—" : v);
      const classe = typeof v === "number" && !Number.isInteger(v)
        ? (v >= 0 ? "pos" : "neg") : "";
      return `<td class="${classe}">${texte}</td>`;
    }).join("")}</tr>`).join("");
    return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  /* ---------- « cette stratégie, elle fait quoi ? » ------------------------------------ */

  /** L'horizon en bougies ne se lit pas. Le meme nombre en jours, si : 96 bougies 4h, ce
   *  sont 16 jours de detention maximale, et c'est ce chiffre-la qui dit si la barriere de
   *  temps mord ou non. Rend "" si le timeframe n'est pas interpretable — jamais un faux. */
  function enJours(bougies, timeframe) {
    const t = /^(\d+)([mhd])$/.exec(String(timeframe || ""));
    if (!t || !Number.isFinite(bougies)) return "";
    const heures = { m: 1 / 60, h: 1, d: 24 }[t[2]] * Number(t[1]) * Number(bougies);
    return heures < 48 ? ` (${n2(heures)} h)` : ` (${n2(heures / 24)} jours)`;
  }

  function listeDefinitions(paires) {
    const lignes = paires.filter(([, v]) => v !== null && v !== undefined && v !== "");
    if (!lignes.length) return '<p class="vide">—</p>';
    return `<dl class="explique-dl">${lignes.map(([cle, valeur]) =>
      `<dt>${echapper(cle)}</dt><dd>${valeur}</dd>`).join("")}</dl>`;
  }

  /** La carte qui repond avant toutes les autres. Trois etages, dans cet ordre :
   *  ce que la regle DECIDE, ce qu'on en ATTENDAIT, comment le trade SORT.
   *
   *  Le troisieme etage n'est pas un detail de mise en page. Les sorties n'appartiennent
   *  pas a la candidate — la triple barriere est imposee par le Run — et elles expliquent
   *  une grande part du R. Les omettre laisserait croire que la regle d'entree explique
   *  tout le resultat, ce qui est la lecture fausse la plus facile a faire ici. */
  function explicationHtml(d) {
    const e = d.explication || {};
    const ident = identiteDe(e);
    const ex = e.execution || {};
    const pre = e.preenregistrement || {};
    const decision = pre.regle_de_decision || {};
    const params = Object.entries(e.parametres || {});

    const regle = ident.description
      ? `<p class="explique-phrase">${echapper(ident.description)}</p>`
      : `<p class="vide">Cette candidate ne décrit pas sa règle. Le code ci-dessous est
         alors la seule source — et c'est un défaut à corriger dans le fichier.</p>`;

    const hypothese = pre.hypothese
      ? `<p class="explique-phrase">${echapper(pre.hypothese)}</p>
         ${listeDefinitions([
           ["Métrique primaire", echapper(pre.metrique_primaire || "—")],
           ["Confirmée si", echapper(decision.confirmee || "—")],
           ["Infirmée si", echapper(decision.infirmee || "—")],
           ["Indécidable si", echapper(decision.indecidable || "—")],
           ["Déjà connu avant", echapper(pre.deja_connu || "—")],
         ])}`
      : `<p class="vide">Préenregistrement « ${echapper(d.verdict.experience)} » introuvable
         dans <code>EXPERIMENTS.jsonl</code>.</p>`;

    return `
      <h2>Ce que la stratégie fait, concrètement</h2>
      <p class="sous">Le code dit ce que la règle calcule ; le préenregistrement dit ce
        qu'on en attendait ; la barrière dit comment le trade se termine. Aucun des trois
        ne suffit seul à comprendre un R moyen.</p>

      <div class="explique">
        <section>
          <h3>La règle d'entrée</h3>
          ${regle}
          ${params.length ? listeDefinitions(params.map(([c, v]) =>
            [c, `<code>${echapper(v)}</code>`])) : ""}
        </section>

        <section>
          <h3>L'hypothèse préenregistrée · ${echapper(d.verdict.experience)}</h3>
          ${hypothese}
        </section>

        <section>
          <h3>La sortie, imposée par le moteur</h3>
          <p class="sous">Triple barrière identique pour toutes les candidates : c'est ce
            qui rend deux règles d'entrée comparables entre elles.</p>
          ${listeDefinitions([
            ["Stop", `${n2(ex.stop_atr)} × ATR`],
            ["Take-profit", `${n2(ex.take_profit_r)} R`],
            ["Horizon maximal", `${ent(ex.horizon_bougies)} bougies${
              enJours(ex.horizon_bougies, ex.timeframe)}`],
            ["Coût aller-retour", `${n2(ex.cout_aller_retour_pct)} %`],
            ["Univers", echapper((ex.paires || []).join(" · ") || "—")],
            ["Unité de temps", echapper(ex.timeframe || "—")],
            ["Empreinte du code", `<code>${echapper(ex.empreinte || "—")}</code>`],
          ])}
        </section>
      </div>

      ${e.code
        ? `<details class="explique-code"><summary>Le code exécuté —
             <code>${echapper(ident.module)}.py</code></summary>
           <pre>${echapper(e.code)}</pre></details>`
        : `<p class="vide">Le fichier <code>${echapper(ident.module)}.py</code> n'existe
           plus. Le verdict reste valable : c'est l'empreinte du code, pas le fichier, qui
           identifie ce qui a été mesuré.</p>`}`;
  }

  function rendreDetail() {
    const d = etatFiche.donnees;
    if (!d) return;
    q("#fiche-entete").innerHTML = enTete(d);
    q("#fiche-explication").innerHTML = explicationHtml(d);

    const mc = d.monte_carlo;
    q("#fiche-mc-chiffres").innerHTML = `
      ${tuileF(pc(mc.p_perte), "P(finir en perte)", mc.p_perte > 0.1 ? "critical" : "good")}
      ${tuileF(pc(mc.p_drawdown), `P(drawdown > ${n2(mc.seuil_dd_pct)} %)`,
        mc.p_drawdown > 0.1 ? "critical" : "good")}
      ${tuileF(n2(mc.drawdown_max_reel_pct) + " %", "drawdown observé")}
      ${tuileF(n2(mc.centile_drawdown_reel) + "e", "centile du drawdown observé", "warn",
        "bas = la chronologie réelle a été chanceuse")}`;

    const wf = d.walk_forward;
    q("#fiche-wf-chiffres").innerHTML = `
      ${tuileF(n2(wf.efficacite), "efficacité OOS/IS", wf.efficacite >= 0.5 ? "good" : "critical")}
      ${tuileF(ent(wf.cpcv.n_combinaisons), "chemins CPCV")}
      ${tuileF(pc(wf.cpcv.part_chemins_perdants), "chemins perdants",
        wf.cpcv.part_chemins_perdants > 0.35 ? "critical" : "good")}
      ${tuileF(n4(wf.cpcv.oos_median), "R médian hors échantillon")}`;

    const syn = d.synthetique || {};
    q("#fiche-syn-chiffres").innerHTML = `
      ${tuileF(n2(syn.centile) + "e", "centile parmi les marchés synthétiques",
        syn.passe ? "good" : "critical")}
      ${tuileF(ent(syn.n_chemins), "chemins rejoués")}
      ${tuileF(n2(syn.synthetique_median), "R total médian sur du bruit")}
      ${tuileF(n2(syn.observe), "R total observé")}`;

    q("#fiche-bootstrap").innerHTML = tableauSimple(
      (d.bootstrap || []).map((b) => ({
        "bloc ℓ": b.ell_demande, observé: b.observe, "IC bas": b.ic_bas,
        "IC haut": b.ic_haut, "p": b.p_value,
      })), ["bloc ℓ", "observé", "IC bas", "IC haut", "p"]);

    q("#fiche-annees").innerHTML = tableauSimple(d.par_annee,
      ["annee", "n", "r_total", "r_moyen", "win_rate"]);
    q("#fiche-sens").innerHTML = tableauSimple(d.par_sens,
      ["sens", "n", "r_moyen", "mde_r", "win_rate", "profit_factor"]);
    q("#fiche-paires").innerHTML = tableauSimple(d.par_paire,
      ["paire", "n", "r_moyen", "mde_r", "win_rate"]);
    q("#fiche-raisons").innerHTML = tableauSimple(d.par_raison,
      ["raison_sortie", "n", "r_moyen", "win_rate"]);

    redessiner();
  }

  function redessiner() {
    const d = etatFiche.donnees;
    if (!d) return;
    equityContreHold(q("#fiche-equity"), d);
    cone(q("#fiche-cone"), d.monte_carlo);
    barres(q("#fiche-dd"), histoDepuisPercentiles(d.monte_carlo.drawdown_max),
      d.monte_carlo.drawdown_max_reel_pct, " %");
    barres(q("#fiche-distribution"), d.distribution_r, null, " R");
    barres(q("#fiche-cpcv"), d.walk_forward.cpcv_histogramme, null, " R");
    colonnes(q("#fiche-annees-graph"), d.par_annee.map((a) => String(a.annee)),
      [{ valeurs: d.par_annee.map((a) => a.r_total) }]);
    const plis = d.walk_forward.plis || [];
    colonnes(q("#fiche-wf-graph"), plis.map((p) => "pli " + p.pli), [
      { valeurs: plis.map((p) => p.is), teinte: couleur("--text-muted") },
      { valeurs: plis.map((p) => p.oos) },
    ]);
  }

  /** Les percentiles du drawdown suffisent a en dessiner la forme : on n'a pas besoin
   *  des 10 000 tirages pour montrer ou tombe le drawdown observe. */
  function histoDepuisPercentiles(percentiles) {
    const valeurs = Object.values(percentiles || {}).filter(Number.isFinite);
    if (valeurs.length < 2) return { bords: [], effectifs: [] };
    valeurs.sort((a, b) => a - b);
    const bords = valeurs.slice();
    const effectifs = valeurs.slice(0, -1).map(() => 1);
    return { bords, effectifs };
  }

  /* ---------- liste et actions ---------------------------------------------------------- */

  function rendreListe() {
    const cible = q("#fiche-liste");
    if (!etatFiche.liste.length) {
      cible.innerHTML = `<p class="vide">Aucun run enregistré. Lancer une candidate :
        <code>beta.moteur.pipeline.executer(...)</code>.</p>`;
      return;
    }
    cible.innerHTML = etatFiche.liste.map((r) => `
      <button class="run-item ${r.run_id === etatFiche.courant ? "is-active" : ""}"
              data-run="${r.run_id}">
        <span class="run-nom">${echapper(identiteDe({ identite: r.identite }).titre)}</span>
        <span class="run-meta"><code>${echapper(r.candidate)}</code></span>
        <span class="run-meta">${r.experience} · ${r.timeframe} · ${ent(r.n)} trades</span>
        <span class="run-issue" data-tone="${TONS[r.issue] || ""}">${r.issue}</span>
      </button>`).join("");
    cible.querySelectorAll(".run-item").forEach((b) =>
      b.addEventListener("click", () => ouvrir(b.dataset.run)));
  }

  async function ouvrir(runId) {
    etatFiche.courant = runId;
    rendreListe();
    q("#fiche-detail").hidden = false;
    try {
      etatFiche.donnees = await fetch("/api/run?id=" + encodeURIComponent(runId))
        .then((r) => r.json());
    } catch (exc) {
      q("#fiche-entete").innerHTML = `<p class="erreur">${echapper(exc.message)}</p>`;
      return;
    }
    if (etatFiche.donnees.erreur) {
      q("#fiche-entete").innerHTML = `<p class="erreur">${echapper(etatFiche.donnees.erreur)}</p>`;
      return;
    }
    rendreDetail();
  }

  async function agir(action) {
    if (!etatFiche.courant) return;
    const info = q("#fiche-action-message");
    info.textContent = "…";
    try {
      const reponse = await fetch("/api/action", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, run_id: etatFiche.courant }),
      }).then((r) => r.json());
      info.textContent = reponse.erreur ? "✕ " + reponse.erreur : "✓ " + reponse.message;
    } catch (exc) {
      info.textContent = "✕ " + exc.message;
    }
  }

  async function charger() {
    try {
      const donnees = await fetch("/api/runs").then((r) => r.json());
      etatFiche.liste = donnees.runs || [];
    } catch (exc) {
      etatFiche.liste = [];
    }
    rendreListe();
    if (!etatFiche.courant && etatFiche.liste.length) ouvrir(etatFiche.liste[0].run_id);
  }

  document.addEventListener("click", (ev) => {
    const bouton = ev.target.closest("[data-action-run]");
    if (bouton) agir(bouton.dataset.actionRun);
  });

  return { charger, redessiner, aDesDonnees: () => Boolean(etatFiche.donnees) };
})();
