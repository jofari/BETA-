/* BETA — onglet Forward. Ce que les strategies figees font APRES leur gel, sans retouche :
   les suivis au cours de cloture (SUIVI_*.jsonl) et le paper trading (PAPER_*.jsonl), qui
   execute les memes consignes contre le vrai carnet Binance.

   Le serveur relit les journaux, il ne recalcule rien. Les courbes partent de 100 la veille
   du premier jour suivi ; le rattrapage (journees ecrites apres coup) est en trait fin, le
   live en trait plein : seul le live est un test hors echantillon honnete. */

const FORWARD = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { vue: null };

  const echapper = (t) => String(t ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const manque = (v) => v === null || v === undefined || Number.isNaN(v);
  const pc = (v, d = 2) => manque(v) ? "—" : (v >= 0 ? "+" : "") + (100 * v).toFixed(d) + " %";
  const pb = (v) => manque(v) ? "—" : v.toFixed(1) + " pb";
  const usdt = (v) => manque(v) ? "—" : Number(v).toLocaleString("fr-FR",
    { maximumFractionDigits: 2 }) + " $";
  const poids = (v) => manque(v) ? "—" : (100 * v).toFixed(1) + " %";
  const ton = (v) => manque(v) ? "muet" : (v >= 0 ? "pos" : "neg");

  // Une couleur par voie, la meme dans toutes les vues. BTC reste neutre : c'est le decor.
  const TEINTES = { VOIE_C: "--series-long", VC3: "--accent", VC2: "--status-serious",
                    BTC: "--series-neutre" };
  const teinte = (nom) => couleur(TEINTES[nom] || "--text-muted");
  const VOTES = { momentum_btc: "momentum", taux_reel_10a: "taux réel",
                  inflation_anticipee_10a: "inflation", nasdaq: "Nasdaq", fear_greed: "F&G" };

  const veille = (iso) => new Date(Date.parse(iso + "T00:00:00Z") - 864e5)
    .toISOString().slice(0, 10);

  function table(entetes, lignes) {
    if (!lignes.length) return '<p class="vide">Aucune donnée.</p>';
    const th = entetes.map((e) => `<th>${e}</th>`).join("");
    const tr = lignes.map((l) => "<tr>" + l.map((c) =>
      (typeof c === "object" && c !== null) ? `<td class="${c.classe || ""}">${c.html}</td>`
                                            : `<td>${c}</td>`).join("") + "</tr>").join("");
    return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  /* ---------- graphique multi-courbes, base 100 ------------------------------------------ */

  function courbes(canvas, series, message) {
    const { ctx, large, haut } = preparer(canvas);
    const dates = [...new Set(series.flatMap((s) => s.points.map((p) => p.date)))].sort();
    if (dates.length < 2) return vide(ctx, large, haut, message);
    const marge = { gauche: 46, droite: 12, haut: 14, bas: 22 };
    const valeurs = series.flatMap((s) => s.points.map((p) => p.v));
    const ecart = (Math.max(...valeurs) - Math.min(...valeurs)) * 0.08 || 1;
    const yMin = Math.min(...valeurs) - ecart, yMax = Math.max(...valeurs) + ecart;
    const rang = new Map(dates.map((d, i) => [d, i]));
    const x = (d) => marge.gauche + (large - marge.gauche - marge.droite) * rang.get(d)
      / (dates.length - 1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin);

    axes(ctx, large, haut, marge, yMin, yMax, yMin < 100 && yMax > 100 ? y(100) : null);
    for (const s of series) {
      ctx.strokeStyle = s.couleur;
      ctx.setLineDash(s.pointille ? [5, 4] : []);
      for (let i = 1; i < s.points.length; i++) {
        const a = s.points[i - 1], b = s.points[i];
        ctx.lineWidth = b.plein ? 2.2 : 1.1;
        ctx.globalAlpha = b.plein ? 1 : 0.6;
        ctx.beginPath();
        ctx.moveTo(x(a.date), y(a.v));
        ctx.lineTo(x(b.date), y(b.v));
        ctx.stroke();
      }
    }
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
    ctx.fillStyle = couleur("--text-muted");
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(dates[0], marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(dates[dates.length - 1], large - marge.droite, haut - 6);
  }

  function legende(id, series) {
    $$(id).innerHTML = '<ul class="legende">' + series.map((s) =>
      `<li><span class="pastille" style="background:${s.couleur}"></span>${echapper(s.nom)}`
      + (s.pointille ? " (pointillé)" : "") + "</li>").join("") + "</ul>";
  }

  function seriesSuivi(vue) {
    const series = [];
    let btc = null;
    for (const v of vue.voies) {
      if (!v.suivi) continue;
      const pts = v.suivi.points;
      series.push({ nom: v.titre, couleur: teinte(v.nom), points:
        [{ date: veille(pts[0].date), v: 100, plein: false }].concat(
          pts.map((p) => ({ date: p.date, v: 100 * p.equite, plein: p.live }))) });
      // BTC en spot (prix seul) : la reference de VC3, la plus simple a lire.
      if (v.nom === "VC3" || !btc) {
        btc = [{ date: veille(pts[0].date), v: 100, plein: true }].concat(
          pts.map((p) => ({ date: p.date, v: 100 * p.btc, plein: true })));
      }
    }
    if (btc) series.push({ nom: "BTC (hold)", couleur: teinte("BTC"), points: btc,
                           pointille: true });
    return series;
  }

  function seriesPaper(vue) {
    const series = [];
    for (const v of vue.voies) {
      if (!v.paper) continue;
      const pts = v.paper.points;
      series.push({ nom: v.titre + " — paper", couleur: teinte(v.nom),
                    points: pts.map((p) => ({ date: p.date, v: 100 * p.paper, plein: true })) });
      series.push({ nom: v.titre + " — modèle", couleur: teinte(v.nom), pointille: true,
                    points: pts.map((p) => ({ date: p.date, v: 100 * p.modele, plein: true })) });
    }
    return series;
  }

  /* ---------- cartes par voie ------------------------------------------------------------ */

  function carte(v) {
    const s = v.suivi, p = v.paper;
    const tete = `<div class="voie-tete"><span class="pastille" style="background:${teinte(v.nom)}">
      </span><h2>${echapper(v.titre)}</h2><span class="puce">${echapper(v.instrument)}</span></div>
      <p class="sous">${echapper(v.statut)}</p>`;
    if (!s) return `<div class="carte voie">${tete}<p class="vide">Aucun suivi sur cette machine
      (les timers tournent sur le VPS).</p></div>`;
    const d = s.derniere, c = s.consigne;
    const regime = d.etat ? `<span class="puce regime-${d.etat}">${d.etat}</span>` : "";
    const votes = d.votes ? Object.entries(d.votes).map(([k, x]) =>
      `${VOTES[k] || k} ${x > 0 ? "+" : ""}${x}`).join(" · ") + ` = ${d.somme > 0 ? "+" : ""}${d.somme}`
      : (d.levier ? `levier ${Number(d.levier).toFixed(2)}` : "");
    const live = s.live ? `${s.live.n} j live, ${pc(s.live.net)}, maxDD ${pc(s.live.mdd)}`
                        : "pas encore de journée live";
    const consigne = c ? `${c.date || "demain"} : <strong>${c.trade ? "rééquilibrer" : "ne rien faire"}</strong>`
      + (c.etat ? ` (${c.etat})` : "") : "—";
    const lignes = [
      ["Depuis le " + s.debut, `<span class="${ton(s.tout.net)}">${pc(s.tout.net)}</span>`
        + ` <span class="muet">· BTC ${pc(s.btc)}</span>`],
      ["MaxDD / vol", `${pc(s.tout.mdd)} · ${s.tout.vol === null ? "—" : pc(s.tout.vol, 1)}`],
      ["Live", live],
      ["Régime", regime ? `${regime} <span class="muet">${votes}</span>` : votes || "—"],
      ["Consigne", consigne],
      ["Paper", p ? `<span class="${ton(p.rendement)}">${pc(p.rendement)}</span> sur ${p.n_jours} j`
        + ` <span class="muet">· modèle ${pc(p.modele)}</span>` : "démarre au prochain passage"],
    ];
    return `<div class="carte voie">${tete}<dl class="voie-dl">${lignes.map(([k, x]) =>
      `<dt>${k}</dt><dd>${x}</dd>`).join("")}</dl></div>`;
  }

  /* ---------- tableaux ------------------------------------------------------------------- */

  function tablePositions(vue) {
    const avec = vue.voies.filter((v) => v.suivi);
    const entetes = ["paire"].concat(avec.flatMap((v) =>
      [`${echapper(v.titre)}<br><span class="muet">suivi</span>`,
       `<span class="muet">paper</span>`]));
    const lignes = vue.paires.map((paire) => [paire].concat(avec.flatMap((v) => [
      poids(v.suivi.derniere.positions ? v.suivi.derniere.positions[paire] : null),
      { html: v.paper ? poids(v.paper.poids[paire]) : "—", classe: "muet" }])));
    lignes.push(["brut"].concat(avec.flatMap((v) => {
      const pos = v.suivi.derniere.positions || {};
      const brut = Object.values(pos).reduce((a, x) => a + Math.abs(x), 0);
      const brutPaper = v.paper ? Object.values(v.paper.poids).reduce((a, x) => a + Math.abs(x), 0)
                                : null;
      return [{ html: poids(brut), classe: "fort" }, { html: poids(brutPaper), classe: "muet" }];
    })));
    return table(entetes, lignes);
  }

  function tableExecution(vue) {
    const lignes = vue.voies.filter((v) => v.paper).map((v) => {
      const p = v.paper;
      return [echapper(v.titre), p.n_jours, p.n_ordres, usdt(p.notional),
              pb(p.carnet_pb), pb(p.ouverture_pb), pb(p.modele_pb), usdt(p.frais),
              usdt(p.funding), p.ignores];
    });
    return table(["voie", "jours", "ordres", "notional", "carnet", "ouverture 00:00",
                  "modèle", "frais", "funding", "ignorés"], lignes);
  }

  function tableOrdres(vue) {
    const ordres = vue.voies.filter((v) => v.paper).flatMap((v) =>
      v.paper.ordres.map((o) => ({ voie: v.titre, ...o })))
      .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0)).slice(0, 40);
    return table(["date", "voie", "paire", "sens", "notional", "prix", "carnet",
                  "ouverture 00:00", "modèle"], ordres.map((o) => [
      o.date, echapper(o.voie), o.paire,
      `<span class="puce ${o.sens === "achat" ? "long" : "short"}">${o.sens}</span>`,
      usdt(o.notional), Number(o.prix).toPrecision(6), pb(o.cout_carnet_pb),
      { html: pb(o.ecart_ouverture_pb), classe: o.ecart_ouverture_pb > 0 ? "neg" : "pos" },
      pb(o.slippage_modele_pb)]));
  }

  /* ---------- rendu ------------------------------------------------------------------------ */

  function dessiner() {
    const vue = etat.vue;
    if (!vue || vue.erreur) return;
    const sSuivi = seriesSuivi(vue), sPaper = seriesPaper(vue);
    courbes($$("#forward-suivi"), sSuivi, "Aucun suivi sur cette machine.");
    legende("#forward-suivi-legende", sSuivi);
    courbes($$("#forward-paper"), sPaper,
            "Le paper démarre au prochain passage du timer (01:00 UTC).");
    legende("#forward-paper-legende", sPaper);
  }

  function rendre() {
    const vue = etat.vue;
    if (!vue || vue.erreur) {
      $$("#forward-voies").innerHTML = `<p class="erreur">${echapper(vue ? vue.erreur
        : "pas de données")}</p>`;
      return;
    }
    $$("#forward-voies").innerHTML = vue.voies.map(carte).join("");
    $$("#forward-positions").innerHTML = tablePositions(vue);
    $$("#forward-execution").innerHTML = tableExecution(vue);
    $$("#forward-ordres").innerHTML = tableOrdres(vue);
    $$("#forward-genere").textContent = "relu le " + vue.genere_le.replace("T", " ")
      .replace("+00:00", " UTC");
    dessiner();
  }

  async function charger() {
    try {
      etat.vue = await fetch("/api/forward").then((r) => r.json());
    } catch (exc) {
      etat.vue = { erreur: "serveur injoignable : " + exc.message };
    }
    rendre();
  }

  return { charger, redessiner: dessiner, aDesDonnees: () => !!(etat.vue && !etat.vue.erreur) };
})();
