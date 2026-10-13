/* BETA — onglet Forward. Ce que les strategies figees font APRES leur gel, sans retouche :
   les suivis au cours de cloture (SUIVI_*.jsonl) et le paper trading (PAPER_*.jsonl), qui
   execute les memes consignes contre le vrai carnet Binance.

   Le serveur relit les journaux, il ne recalcule rien. Les courbes partent de 100 la veille
   du premier jour suivi ; le rattrapage (journees ecrites apres coup) est en trait fin, le
   live en trait plein : seul le live est un test hors echantillon honnete. */

const FORWARD = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { vue: null, direct: null };

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
  const TEINTES = { VOIE_C: "--series-long", VC3: "--accent", VC5: "--serie-vc5",
                    VC4: "--serie-vc4", VC2: "--status-serious", BTC: "--series-neutre" };
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

  /* Le paper en direct : une courbe par voie, en temps reel (les passages quotidiens, puis
     un point par minute), rendement depuis le premier jour. Rien d'autre sur ce graphique. */
  function courbesDirect(canvas, direct) {
    const { ctx, large, haut } = preparer(canvas);
    const series = Object.entries((direct && direct.voies) || {}).map(([nom, x]) => ({
      nom, points: x.points.map((p) => ({ t: Date.parse(p.t), v: 100 * p.r })) }));
    const tous = series.flatMap((s) => s.points);
    if (tous.length < 2) return vide(ctx, large, haut,
      "Le paper en direct démarre avec le premier relevé (chaque minute).");
    const marge = { gauche: 46, droite: 12, haut: 14, bas: 22 };
    const tMin = Math.min(...tous.map((p) => p.t)), tMax = Math.max(...tous.map((p) => p.t));
    const vs = tous.map((p) => p.v).concat([0]);
    const ecart = (Math.max(...vs) - Math.min(...vs)) * 0.08 || 1;
    const yMin = Math.min(...vs) - ecart, yMax = Math.max(...vs) + ecart;
    const x = (t) => marge.gauche + (large - marge.gauche - marge.droite) * (t - tMin)
      / ((tMax - tMin) || 1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin);
    // Axe en % : 0 = le capital de depart (10 000 $).
    axes(ctx, large, haut, marge, yMin, yMax, y(0));
    ctx.lineWidth = 2;
    for (const s of series) {
      ctx.strokeStyle = teinte(s.nom);
      ctx.beginPath();
      s.points.forEach((p, i) => (i ? ctx.lineTo : ctx.moveTo).call(ctx, x(p.t), y(p.v)));
      ctx.stroke();
    }
    ctx.fillStyle = couleur("--text-muted");
    ctx.font = "11px system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(heureUtc(new Date(tMin).toISOString()), marge.gauche, haut - 6);
    ctx.textAlign = "right";
    ctx.fillText(heureUtc(new Date(tMax).toISOString()), large - marge.droite, haut - 6);
  }

  function legendeDirect(vue) {
    $$("#forward-paper-legende").innerHTML = '<ul class="legende">' + vue.voies
      .filter((v) => etat.direct && etat.direct.voies && etat.direct.voies[v.nom])
      .map((v) => `<li><span class="pastille" style="background:${teinte(v.nom)}"></span>`
        + echapper(v.titre) + "</li>").join("") + "</ul>";
  }

  /* ---------- cartes par voie ------------------------------------------------------------ */

  // La position d'AUJOURD'HUI : celle de la consigne (decidee a 00:00 UTC, executee par le
  // paper vers 01:00). La derniere ligne du suivi porte celle d'HIER : comparer le paper a
  // celle-la melange deux journees des qu'il y a eu un reequilibrage (piege du 10/10).
  const positionDuJour = (s) => (s.consigne && (s.consigne.position || s.consigne.cible))
    || s.derniere.positions || null;
  const brutDe = (pos) => pos ? Object.values(pos).reduce((a, x) => a + Math.abs(x), 0) : null;

  function carte(v) {
    const s = v.suivi, p = v.paper;
    const tete = `<div class="voie-tete"><span class="pastille" style="background:${teinte(v.nom)}">
      </span><h2>${echapper(v.titre)}</h2><span class="puce">${echapper(v.instrument)}</span></div>
      <p class="sous">${echapper(v.statut)}</p>`;
    if (!s) return `<div class="carte voie">${tete}<p class="vide">Aucun suivi sur cette machine
      (les timers tournent sur le VPS).</p></div>`;
    const d = s.derniere, c = s.consigne;
    // Le regime affiche est celui de la CONSIGNE DU JOUR (meme source que le panneau Indicateurs),
    // pas celui de la derniere journee close : les deux ne coincidaient pas (+2 / +3 le 13/10).
    const r = c && c.votes ? c : d;
    const indic = (c && c.indicateurs && c.indicateurs.votes) || {};
    const regime = r.etat ? `<span class="puce regime-${r.etat}">${r.etat}</span>` : "";
    const votes = r.votes ? Object.entries(r.votes).map(([k, x]) =>
      `${VOTES[k] || k} ${x > 0 ? "+" : ""}${x}`
      + (r === c && indic[k] && indic[k].perimee ? " (donnée périmée → 0)" : "")).join(" · ")
      + ` = <strong>${r.somme > 0 ? "+" : ""}${r.somme}</strong>`
      + (r === c && d.somme !== undefined && d.somme !== c.somme
        ? ` <span class="muet">(veille ${d.somme > 0 ? "+" : ""}${d.somme})</span>` : "")
      : (d.levier ? `multiplicateur vol-cible ${Number(d.levier).toFixed(2)}`
        + ' <span class="muet">(pas un effet de levier)</span>' : "");
    const live = s.live ? `${s.live.n} j live, ${pc(s.live.net)}, maxDD ${pc(s.live.mdd)}`
                        : "pas encore de journée live";
    // « aucun ordre » ne veut PAS dire « ne rien detenir » : la position est gardee telle quelle.
    const consigne = c ? `${c.date || "demain"} : <strong>${c.trade ? "rééquilibrer"
      : "garder les positions"}</strong>` + (c.trade ? "" : ' <span class="muet">(aucun ordre)</span>')
      + (c.etat ? ` (${c.etat})` : "") : "—";
    const investi = brutDe(positionDuJour(s));
    const exposition = investi === null ? "—" : `<strong>${poids(investi)}</strong> investi`
      + ` <span class="muet">· ${poids(Math.max(0, 1 - investi))} non investi (cash)</span>`;
    const alloc = p && p.allocation;
    const brute = alloc ? alloc.exposition_brute : investi;
    const levier = manque(brute) ? "—" : (alloc ? alloc.effet_levier : brute > 1 + 1e-6)
      ? `<span class="puce levier-oui">oui ×${brute.toFixed(2)}</span>`
      : `<span class="puce levier-non">non</span> <span class="muet">· exposé à ${poids(brute)}`
        + " du capital</span>";
    const lignes = [
      ["Depuis le " + s.debut, `<span class="${ton(s.tout.net)}">${pc(s.tout.net)}</span>`
        + ` <span class="muet">· BTC ${pc(s.btc)}</span>`],
      ["MaxDD / vol", `${pc(s.tout.mdd)} · ${s.tout.vol === null ? "—" : pc(s.tout.vol, 1)}`],
      ["Live", live],
      [r === c ? `Régime du ${String(c.date).slice(0, 10)}` : "Régime", regime ? `${regime} <span class="muet">${votes}</span>` : votes || "—"],
      ["Exposition", exposition],
      ["Effet de levier", levier],
      ["Consigne", consigne],
      ["Paper", paperDirect(v.nom, p)],
    ];
    return `<div class="carte voie">${tete}<dl class="voie-dl">${lignes.map(([k, x]) =>
      `<dt>${k}</dt><dd>${x}</dd>`).join("")}</dl></div>`;
  }

  /* LE chiffre paper : le compte valorise a la derniere minute relevee, funding regle inclus. */
  function paperDirect(nom, p) {
    const x = etat.direct && etat.direct.voies && etat.direct.voies[nom];
    if (!x) return p ? "relevé en cours…" : "démarre au prochain passage";
    return `<strong class="${ton(x.rendement)}">${pc(x.rendement)}</strong>`
      + ` <span class="muet">· ${usdt(x.equite)} · ${heureUtc(x.t).slice(11)}</span>`;
  }

  function heureUtc(iso) {
    return iso ? iso.slice(0, 16).replace("T", " ") + " UTC" : "—";
  }

  /* ---------- allocation du compte paper et effet de levier ------------------------------ */

  const ACTIFS = ["BTC", "ETH", "SOL", "BNB", "LINK", "XRP"];
  const teinteActif = (p) => couleur("--actif-" + p.toLowerCase()) || couleur("--text-muted");

  function barreAllocation(a) {
    // Largeur totale = max(100 %, exposition brute) : du levier deborderait du capital.
    const echelle = Math.max(1, a.exposition_brute || 0);
    const segments = a.actifs.filter((x) => Math.abs(x.poids) > 5e-4).map((x) =>
      `<span class="segment${x.poids < 0 ? " short" : ""}" title="${x.paire} ${part(x.poids)}"
        style="width:${(100 * Math.abs(x.poids) / echelle).toFixed(3)}%;
        background:${teinteActif(x.paire)}"></span>`);
    if (a.part_cash > 5e-4) {
      segments.push(`<span class="segment cash" title="cash ${part(a.part_cash)}"
        style="width:${(100 * a.part_cash / echelle).toFixed(3)}%"></span>`);
    }
    return `<div class="barre-alloc">${segments.join("")}</div>`;
  }

  function legendeAllocation(a) {
    const actifs = a.actifs.filter((x) => Math.abs(x.poids) > 5e-4).map((x) =>
      `<li><span class="pastille" style="background:${teinteActif(x.paire)}"></span>${x.paire}`
      + ` <strong>${part(x.poids)}</strong>${x.poids < 0 ? " (short)" : ""}</li>`);
    actifs.push(`<li><span class="pastille cash"></span>${a.part_cash < 0 ? "emprunt" : "cash"}`
      + ` <strong>${part(Math.abs(a.part_cash))}</strong></li>`);
    return `<ul class="legende">${actifs.join("")}</ul>`;
  }

  function detailAllocation(a) {
    const lignes = a.actifs.map((x) => [x.paire, nombre(x.quantite, x.quantite < 1 ? 4 : 2),
      nombre(x.prix, x.prix < 10 ? 4 : 2) + " $", nombre(x.valeur, 0) + " $", part(x.poids)]);
    lignes.push([a.part_cash < 0 ? "emprunt (cash négatif)" : "cash", "", "",
                 nombre(a.cash, 0) + " $", part(a.part_cash)]);
    lignes.push([{ html: "<strong>équité</strong>" }, "", "", { html: `<strong>${nombre(a.equite, 0)}
      $</strong>` }, "100,0 %"]);
    return table(["actif", "quantité", "prix (milieu)", "valeur", "% du capital"], lignes);
  }

  function ligneAllocation(v) {
    const a = v.paper && v.paper.allocation;
    if (!a) return "";
    const badge = a.effet_levier
      ? `<span class="puce levier-oui">effet de levier : OUI ×${a.exposition_brute.toFixed(2)}</span>`
      : '<span class="puce levier-non">effet de levier : non</span>';
    const net = Math.abs(a.exposition_brute - a.exposition_nette) > 1e-4
      ? ` · nette ${part(a.exposition_nette)}` : "";
    return `<div class="alloc-voie">
      <div class="alloc-tete"><span class="pastille" style="background:${teinte(v.nom)}"></span>
        <strong>${echapper(v.titre)}</strong> <span class="muet">${echapper(v.instrument)} ·
        ${nombre(a.equite, 0)} $ · exposé à ${part(a.exposition_brute)}${net}</span>${badge}</div>
      ${barreAllocation(a)}${legendeAllocation(a)}
      <details class="alloc-detail"><summary>quantités, prix et valeurs (paper du ${a.date},
        exécuté ${(a.execute_le || "").slice(11, 16)} UTC)</summary>${detailAllocation(a)}</details>
    </div>`;
  }

  function panneauAllocation(vue) {
    const blocs = vue.voies.map(ligneAllocation).filter(Boolean);
    return blocs.length ? blocs.join("")
      : '<p class="vide">Aucun compte paper sur cette machine (le paper tourne sur le VPS).</p>';
  }

  /* ---------- indicateurs : ce que la strategie a lu pour decider ------------------------ */

  const nombre = (v, d = 2) => manque(v) ? "—" : Number(v).toLocaleString("fr-FR",
    { minimumFractionDigits: d, maximumFractionDigits: d });
  const signe = (x) => x > 0 ? "+" + x : x < 0 ? "−" + (-x) : "0";
  const pcfr = (v, d = 1) => manque(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "")
    + nombre(100 * Math.abs(v), d) + " %";
  const part = (v, d = 1) => manque(v) ? "—" : nombre(100 * v, d) + " %";
  const puceVote = (x) => `<span class="puce ${x > 0 ? "ok" : x < 0 ? "alerte" : ""}">${signe(x)}</span>`;
  const pt = (v) => manque(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + nombre(Math.abs(v), 2) + " pt";
  const fraicheur = (v) => v.perimee
    ? `<span class="neg">périmée (${nombre(v.age_h, 0)} h &gt; ${v.params.perime_h} h) → 0</span>` : "";

  function ligneVote(nom, v) {
    const p = v.params || {};
    if (nom === "momentum_btc") {
      return ["Momentum BTC " + p.fenetre_j + " j", v.lu,
              `clôture ${nombre(v.valeur, 0)} $`,
              `${p.fenetre_j} j plus tôt (${v.date_reference}) : ${nombre(v.reference, 0)} $ → `
              + `<strong>${pcfr(v.variation)}</strong>`,
              `+1 si BTC est plus haut qu'il y a ${p.fenetre_j} j, −1 s'il est plus bas`];
    }
    if (nom === "nasdaq") {
      const couple = { COUPLE: "couplé", DECOUPLE: "découplé", TRANSITION: "en transition" };
      return ["Nasdaq-100", v.lu, nombre(v.valeur, 0),
              `plus bas des ${p.cassure_obs} séances précédentes ${nombre(v.plus_bas, 0)} → `
              + `<strong>${v.cassure ? "cassure" : "pas de cassure"}</strong> · corrélation BTC `
              + `${p.rho_court} j ${nombre(v.rho_court, 2)} / ${p.rho_long} j ${nombre(v.rho_long, 2)}`
              + ` → <strong>${couple[v.couplage] || "—"}</strong> ${fraicheur(v)}`,
              `−1 seulement si BTC est couplé (${p.rho_court} j ≥ ${nombre(p.arme_si, 1)} et `
              + `${p.rho_long} j ≥ ${nombre(p.confirme_long_si, 1)}) ET le Nasdaq casse son plus bas `
              + `${p.cassure_obs} séances ; jamais +1`];
    }
    if (nom === "fear_greed") {
      return ["Fear & Greed", v.lu, nombre(v.valeur, 0), fraicheur(v) || "—",
              `&lt; ${p.bas} → −1 ; ≥ ${p.haut} → +1 ; entre les deux → 0`];
    }
    const titres = { taux_reel_10a: "Taux réel 10 ans US (DFII10)",
                     inflation_anticipee_10a: "Inflation anticipée 10 ans (T10YIE)" };
    const hausse = p.signe_hausse > 0 ? "+1" : "−1", baisse = p.signe_hausse > 0 ? "−1" : "+1";
    return [titres[nom] || nom, v.lu, nombre(v.valeur, 2) + " %",
            `${p.fenetre_obs} séances plus tôt (${v.date_reference}) : ${nombre(v.reference, 2)} % → `
            + `<strong>${pt(v.variation)}</strong> ${fraicheur(v)}`,
            `hausse ≥ ${nombre(p.seuil_pt, 2)} pt → ${hausse} ; baisse ≥ ${nombre(p.seuil_pt, 2)} pt `
            + `→ ${baisse} ; sinon 0`];
  }

  function decision(ind, c) {
    const ex = ind.execution;
    if (!ex) return "";
    const ecart = `écart à la cible ${nombre(100 * ex.ecart, 1)} pts, bande ${nombre(100 * ex.bande, 0)} pts`;
    if (ind.etat === "haussier") {
      return `Investi voulu <strong>${part(ex.brut_voulu)}</strong> · tenu ${part(ex.brut_tenu)}`
        + ` · ${ecart} → <strong>${c.trade ? "rééquilibrer vers le voulu"
        : "garder les positions (sous la bande, aucun ordre)"}</strong>`;
    }
    if (ind.etat === "veille") {
      return `Veille : aucun ajout. Investi tenu ${part(ex.brut_tenu)}, voulu du moteur `
        + `${part(ex.brut_voulu)} → <strong>${c.trade ? "réduire au prorata"
        : "garder les positions"}</strong> <span class="muet">(réduction seulement si le tenu `
        + `dépasse le voulu de plus de ${nombre(100 * ex.bande, 0)} pts)</span>`;
    }
    return `Baissier : poche BTC ≤ 25 % du plus haut de l'équité, alts −50 % au signal puis `
      + `sortie de chaque alt dont le momentum 126 j est négatif → <strong>${c.trade
      ? "ordres de réduction" : "garder les positions"}</strong>`;
  }

  /* L'allocation en quatre etapes. Les chiffres et les controles viennent du serveur
     (forward.pas_a_pas), qui refait chaque etape et la compare au journal : ici, on affiche. */
  function pasAPas(pp) {
    const h = pp.params, e1 = pp.etape1, e2 = pp.etape2, e3 = pp.etape3, e4 = pp.etape4;
    const ko = (n) => pp.controles.filter((c) => c.etape === n && !c.ok);
    const verdict = (n) => ko(n).length
      ? `<p class="erreur">Ne se recoupe pas avec le journal : ${ko(n).map((c) =>
          echapper(c.libelle)).join(", ")}. L'explication ne décrit pas ce que la chaîne a fait.</p>`
      : `<p class="muet">✓ recalculé et identique au journal (${pp.controles.filter((c) =>
          c.etape === n).length} contrôle(s))</p>`;
    const tete = pp.verifie
      ? `<p class="sous">Chaque étape est refaite par le serveur à partir de l'étape précédente et
          comparée à ce que la chaîne a journalisé : <strong>${pp.controles.length} contrôles, tous
          identiques</strong>. Valeurs lues le ${pp.lu} (veille de la consigne).</p>`
      : `<p class="erreur">${pp.controles.filter((c) => !c.ok).length} contrôle(s) en échec :
          ne pas se fier à cette explication, voir journalctl -u beta-suivi-*.</p>`;
    const t1 = table(["paire", `vol ${h.fenetre_vol_jambes} j`, "1 / vol", "poids de base",
                      `momentum ${h.fenetre_mom} j`, "jambe tendance", "poids final"],
      e1.paires.map((x) => [x.paire, part(x.vol, 0), nombre(x.inverse, 2), part(x.base),
        { html: pcfr(x.momentum), classe: x.momentum >= 0 ? "pos" : "neg" },
        x.tendance_active ? part(x.tendance) : '<span class="neg">0 (en baisse)</span>',
        { html: part(x.composite), classe: "fort" }])
        .concat([["total", "", "", "100,0 %", "", "", { html: part(e1.somme_composite), classe: "fort" }]]));
    const t3 = table(["paire", "poids final", `voulu = poids × ${nombre(e2.en_vigueur, 2)}`
                      + (e3.echelle < 1 ? ` × ${nombre(e3.echelle, 3)} (plafond)` : "")],
      e1.paires.map((x) => [x.paire, part(x.composite), { html: part(x.voulu), classe: "fort" }])
        .concat([["total", part(e1.somme_composite), { html: part(e3.brut_voulu), classe: "fort" }]]));
    const garde = e2.change ? "le calcul s'est écarté de plus du seuil : le levier <strong>change</strong>"
      : `écart ${nombre(e2.ecart, 2)} ≤ seuil ${nombre(h.seuil_levier, 2)} : on <strong>garde</strong> l'ancien`;
    return `<h3>Comment l'allocation est calculée</h3>${tete}
      <h4>1. Poids de chaque paire</h4>
      <p class="sous">Moitié <strong>base</strong> : chaque paire pèse l'inverse de sa volatilité
        ${h.fenetre_vol_jambes} j, ramené à 100 % (une paire calme pèse plus). Moitié
        <strong>tendance</strong> : le même poids, seulement si la paire a monté sur ${h.fenetre_mom} j ;
        sinon 0, et cette part reste en cash (pas redistribuée). Poids final = ½ base + ½ tendance.</p>
      ${t1}${verdict(1)}
      <h4>2. Taille totale (« levier » du moteur)</h4>
      <p class="sous">Cible de vol ${part(e2.cible_vol, 0)} ÷ vol du portefeuille ${h.fenetre} j
        ${part(e2.sigma)} = ${nombre(e2.brut, 2)}, borné ${nombre(h.lmin, 2)}–${nombre(h.lmax, 1)}
        → <strong>${nombre(e2.calcule, 2)}</strong>. En vigueur : <strong>${nombre(e2.en_vigueur, 2)}</strong>
        (${garde}). Ce n'est pas un emprunt : c'est la part du capital investie.</p>${verdict(2)}
      <h4>3. Position voulue</h4>
      <p class="sous">Poids final × ${nombre(e2.en_vigueur, 2)}`
        + (e3.plafond !== null && e3.plafond !== undefined ? `, ramené à ${part(e3.plafond, 0)} investi au plus (spot, sans emprunt)` : "")
        + `. Le reste est du cash.</p>${t3}${verdict(3)}
      <h4>4. Rééquilibrer ou non</h4>
      <p class="sous">Règle (${echapper(pp.etat)}) : ${echapper(e4.regle)}. Tenu ${part(e4.brut_tenu)}
        investi, voulu ${part(e3.brut_voulu)} ; somme des écarts par paire ${part(e4.ecart)},
        bande ${part(e4.bande, 0)} → <strong>${e4.trade ? "rééquilibrer vers le voulu"
        : "garder les positions (aucun ordre)"}</strong>. Investi après décision :
        <strong>${part(e4.brut_final)}</strong>, cash ${part(1 - e4.brut_final)}.</p>${verdict(4)}`;
  }

  function blocIndicateurs(v, ouvert) {
    const c = v.suivi && v.suivi.consigne, ind = c && c.indicateurs;
    if (!ind) return "";
    const s = ind.seuils;
    const alerte = ind.coherent ? "" : '<p class="erreur">Indicateurs incohérents avec la chaîne '
      + "de calcul : ne pas s'y fier (voir journalctl -u beta-suivi-*).</p>";
    const votes = table(["indicateur", "lu le", "valeur", "comparaison", "règle", "vote"],
      Object.entries(ind.votes).map(([nom, x]) => ligneVote(nom, x).concat([puceVote(x.vote)])));
    const moteur = v.pas_a_pas ? pasAPas(v.pas_a_pas) : "";
    return `<details class="indicateurs" ${ouvert ? "open" : ""}>
      <summary><span class="pastille" style="background:${teinte(v.nom)}"></span>
        ${echapper(v.titre)} — consigne du ${ind.date} :
        <span class="puce regime-${ind.etat}">${ind.etat}</span>
        somme des votes <strong>${signe(ind.somme)}</strong>
        <span class="muet">(haussier ≥ ${signe(s.haussier)}, baissier ≤ ${signe(s.baissier)})</span></summary>
      ${alerte}${votes}
      <p class="indic-decision">${decision(ind, c)}</p>
      ${moteur}
    </details>`;
  }

  function panneauIndicateurs(vue) {
    const blocs = vue.voies.filter((v) => v.suivi && v.suivi.consigne
                                          && v.suivi.consigne.indicateurs);
    if (!blocs.length) {
      return '<p class="vide">Les indicateurs sont journalisés avec chaque consigne depuis le '
        + "10/10 : ils apparaissent au prochain passage du suivi (00:45-00:50 UTC).</p>";
    }
    // Le put/call ratio des options (DS1) est du CONTEXTE : aucune strategie ne le lit. Il vit
    // dans le dashboard VPS, a cote des autres donnees DS1 ; on y mene d'un clic.
    const vps = document.querySelector("#lien-vps");
    const contexte = vps && !vps.hidden && vps.href ? `<p class="sous">Contexte, non utilisé
      pour décider : <a href="${vps.href.replace(/#.*$/, "")}#options" target="_blank"
      rel="noopener">put/call ratio des options BTC/ETH (onglet Options du dashboard VPS ↗)</a></p>`
      : "";
    return blocs.map((v, i) => blocIndicateurs(v, i === 0)).join("") + contexte;
  }

  /* ---------- tableaux ------------------------------------------------------------------- */

  function tablePositions(vue) {
    const avec = vue.voies.filter((v) => v.suivi);
    const entetes = ["paire"].concat(avec.flatMap((v) =>
      [`${echapper(v.titre)}<br><span class="muet">consigne${v.suivi.consigne
        && v.suivi.consigne.date ? " du " + v.suivi.consigne.date.slice(5) : ""}</span>`,
       `<span class="muet">paper</span>`]));
    const lignes = vue.paires.map((paire) => [paire].concat(avec.flatMap((v) => {
      const pos = positionDuJour(v.suivi);
      return [poids(pos ? pos[paire] : null),
              { html: v.paper ? poids(v.paper.poids[paire]) : "—", classe: "muet" }];
    })));
    // Exposition brute = somme des |poids| = la part INVESTIE ; le reste est du cash (spot) ou
    // de la marge libre (perpetuels).
    const bruts = avec.map((v) => [brutDe(positionDuJour(v.suivi)) || 0,
                                   v.paper ? brutDe(v.paper.poids) : null]);
    lignes.push(["investi (brut)"].concat(bruts.flatMap(([s, p]) =>
      [{ html: poids(s), classe: "fort" }, { html: poids(p), classe: "muet" }])));
    lignes.push(["non investi (cash)"].concat(bruts.flatMap(([s, p]) =>
      [poids(Math.max(0, 1 - s)), { html: p === null ? "—" : poids(Math.max(0, 1 - p)),
                                    classe: "muet" }])));
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
    const sSuivi = seriesSuivi(vue);
    courbes($$("#forward-suivi"), sSuivi, "Aucun suivi sur cette machine.");
    legende("#forward-suivi-legende", sSuivi);
    courbesDirect($$("#forward-paper"), etat.direct);
    legendeDirect(vue);
  }

  function rendre() {
    const vue = etat.vue;
    if (!vue || vue.erreur) {
      $$("#forward-voies").innerHTML = `<p class="erreur">${echapper(vue ? vue.erreur
        : "pas de données")}</p>`;
      return;
    }
    $$("#forward-voies").innerHTML = vue.voies.map(carte).join("");
    $$("#forward-allocation").innerHTML = panneauAllocation(vue);
    $$("#forward-indicateurs").innerHTML = panneauIndicateurs(vue);
    $$("#forward-positions").innerHTML = tablePositions(vue);
    $$("#forward-execution").innerHTML = tableExecution(vue);
    $$("#forward-ordres").innerHTML = tableOrdres(vue);
    $$("#forward-genere").textContent = "Journaux relus le " + heureUtc(vue.genere_le)
      + " · ordres : chaque jour 01:00 UTC, VC4 aux ouvertures de Londres et New York (semaine)";
    dessiner();
  }

  async function chargerDirect() {
    try {
      etat.direct = await fetch("/api/forward/direct").then((r) => r.json());
    } catch (exc) {
      etat.direct = null;
    }
  }

  async function charger() {
    try {
      etat.vue = await fetch("/api/forward").then((r) => r.json());
    } catch (exc) {
      etat.vue = { erreur: "serveur injoignable : " + exc.message };
    }
    await chargerDirect();
    rendre();
  }

  // Chaque minute : le paper seul (cartes + graphique), sans relire le reste.
  async function direct() {
    await chargerDirect();
    if (etat.vue && !etat.vue.erreur) rendre();
  }

  return { charger, direct, redessiner: dessiner, aDesDonnees: () => !!(etat.vue && !etat.vue.erreur) };
})();
