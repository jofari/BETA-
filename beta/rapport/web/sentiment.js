/* BETA — onglet Sentiment (DS2, 28/11). Relit ce que le pipeline DS2 de Jonas a ecrit :
   sentiment FinBERT des news de DS1, par actif et par marche. Rien n'est classe ni recalcule
   ici ; le serveur compte ce qui est en base et relit la vue ds2.v_score_jour.
   Ce n'est PAS un signal : aucun test preregistre ne lie ce sentiment aux prix.
   Les utilitaires d'app.js (preparer, couleur, vide) ne servent qu'a l'execution : app.js est
   charge apres ce fichier. */

const SENTIMENT = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { vue: null, fenetre: "7j", choix: null, detail: null, charge: false };

  const MARCHES = { crypto: "Crypto", forex: "Forex", indice: "Indices",
                    matieres_premieres: "Matières premières", macro: "Macro (banques centrales)" };
  const FENETRES = { "24h": "24 heures", "7j": "7 jours", "30j": "30 jours" };
  const RAISONS = { aucun_actif: "aucun actif détecté", texte_vide: "texte vide",
                    erreur_modele: "erreur du modèle" };
  const SENS = { bullish: ["haussier", "pos"], bearish: ["baissier", "neg"],
                 neutral: ["neutre", "muet"] };

  const echapper = (t) => String(t ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const manque = (v) => v === null || v === undefined || Number.isNaN(v);
  const ent = (v) => manque(v) ? "—" : Number(v).toLocaleString("fr-FR");
  const solde = (v) => manque(v) ? "—" : (v >= 0 ? "+" : "") + (100 * v).toFixed(0) + " %";
  const score = (v) => manque(v) ? "—" : (v >= 0 ? "+" : "") + Number(v).toLocaleString("fr-FR",
    { maximumFractionDigits: 1 });
  const ton = (v) => manque(v) || v === 0 ? "muet" : (v > 0 ? "pos" : "neg");
  const quand = (s) => s ? String(s).replace("T", " ").slice(0, 16) + " UTC" : "—";
  const nomMarche = (m) => MARCHES[m] || m || "—";

  async function lire(url) {
    const r = await fetch(url);
    const j = await r.json();
    if (!r.ok || j.erreur) throw new Error(j.erreur || r.statusText);
    return j;
  }

  /* ---------- en-tete ------------------------------------------------------------------ */

  function rendreEntete() {
    const v = etat.vue;
    const el = $$("#sentiment-entete");
    if (!v.branche) {
      el.innerHTML = `<h2>DS2 non branché</h2>
        <p class="sous">${echapper(v.message)}. L'onglet lit la base de DS2 avec le fichier
        <code>${echapper(v.fichier_env || "")}</code> (rôle en lecture seule).</p>`;
      return false;
    }
    if (!v.version) {
      el.innerHTML = `<h2>DS2 branché, aucune classification</h2>
        <p class="sous">${echapper(v.message || "")}</p>`;
      return false;
    }
    const ver = v.versions.find((x) => x.version_modele === v.version) || {};
    const echecs = (v.echecs || []).map((e) =>
      `${ent(e.n)} ${RAISONS[e.raison] || echapper(e.raison)}`).join(" · ") || "aucun";
    const traites = (ver.articles || 0) + (v.echecs || []).reduce((s, e) => s + e.n, 0);
    const options = v.versions.map((x) => `<option ${x.version_modele === v.version ? "selected" : ""}>
      ${echapper(x.version_modele)}</option>`).join("");
    el.innerHTML = `
      <div class="verdict-bandeau" data-tone="warn">
        <div class="verdict-issue" data-tone="warn">Description des news, pas un signal</div>
        <p class="sous" style="margin:6px 0 0">Aucun test préenregistré ne relie ce sentiment
          aux prix. Les chiffres ci-dessous comptent ce que le pipeline DS2 a écrit ; ils ne disent
          pas qu'un actif va monter ou baisser.</p>
      </div>
      <div class="sentiment-etat">
        <span>base <b>${echapper(v.base)}</b></span>
        <label>version du modèle <select id="sentiment-version">${options}</select></label>
        <span>modèle <b>${echapper(ver.modele || "—")}</b></span>
        <span><b>${ent(ver.articles)}</b> articles classés sur <b>${ent(traites)}</b> traités
          (${ent(v.news.articles)} news dans DS1)</span>
        <span>échecs : ${echecs}</span>
        <span>dernière classification : ${quand(ver.derniere_classification)}</span>
        <span>dernière news : ${quand(v.news.dernier)}</span>
      </div>`;
    el.querySelector("select").addEventListener("change", (e) => charger(e.target.value));
    return true;
  }

  /* ---------- tableaux par marche et par actif ---------------------------------------- */

  function barre(l, f) {
    const n = l["n_" + f] || 0;
    if (!n) return '<span class="muet">—</span>';
    const h = 100 * (l["haussiers_" + f] || 0) / n, b = 100 * (l["baissiers_" + f] || 0) / n;
    return `<span class="sentiment-barre" title="haussiers ${h.toFixed(0)} %, baissiers ${b.toFixed(0)} %, neutres ${(100 - h - b).toFixed(0)} %">
      <i class="h" style="width:${h}%"></i><i class="n" style="width:${100 - h - b}%"></i><i class="b" style="width:${b}%"></i></span>`;
  }

  function tableGroupes(lignes, par) {
    if (!lignes.length) return '<p class="vide">Aucune donnée.</p>';
    const f = etat.fenetre;
    const th = [par === "actif" ? "actif" : "marché", ...(par === "actif" ? ["marché"] : []),
      "articles 24 h", "articles 7 j", "articles 30 j",
      `répartition (${FENETRES[f]})`, `haussiers`, `baissiers`, `neutres`,
      `solde net`, `score DS2`, "total", "dernier article"];
    const tr = lignes.map((l) => {
      const actif = etat.choix && etat.choix.par === par && etat.choix.groupe === l.groupe;
      return `<tr class="cliquable ${actif ? "choisi" : ""}" data-par="${par}" data-groupe="${echapper(l.groupe)}">
        <td><b>${echapper(par === "actif" ? l.groupe : nomMarche(l.groupe))}</b></td>
        ${par === "actif" ? `<td>${echapper(nomMarche(l.classe_actif))}</td>` : ""}
        <td>${ent(l.n_24h)}</td><td>${ent(l.n_7j)}</td><td>${ent(l.n_30j)}</td>
        <td>${barre(l, f)}</td>
        <td>${ent(l["haussiers_" + f])}</td><td>${ent(l["baissiers_" + f])}</td>
        <td>${ent(l["neutres_" + f])}</td>
        <td class="${ton(l["solde_" + f])}">${solde(l["solde_" + f])}</td>
        <td class="${ton(l["score_" + f])}">${score(l["score_" + f])}</td>
        <td>${ent(l.total)}</td><td class="muet">${quand(l.dernier_article)}</td></tr>`;
    }).join("");
    return `<table><thead><tr>${th.map((t) => `<th>${t}</th>`).join("")}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  function rendreTables() {
    const v = etat.vue;
    $$("#sentiment-marches").innerHTML = tableGroupes(v.par_marche, "marche");
    $$("#sentiment-actifs").innerHTML = tableGroupes(v.par_actif, "actif");
    document.querySelectorAll("#onglet-sentiment tr.cliquable").forEach((tr) =>
      tr.addEventListener("click", () => choisir(tr.dataset.par, tr.dataset.groupe)));
  }

  /* ---------- detail : barres quotidiennes + derniers articles ------------------------ */

  // Une barre par jour : haussiers vers le haut, baissiers vers le bas, neutres en gris
  // au-dessus des haussiers. Jours sans article = rien (pas de zero invente).
  function barresJour(canvas, serie, jours) {
    const { ctx, large, haut } = preparer(canvas);
    if (!serie.length) return vide(ctx, large, haut, "Aucun article classé sur la période.");
    const marge = { gauche: 40, droite: 10, haut: 12, bas: 24 };
    const fin = new Date(); fin.setUTCHours(0, 0, 0, 0);
    const debut = new Date(fin.getTime() - (jours - 1) * 86400000);
    const idx = (j) => Math.round((new Date(j + "T00:00:00Z") - debut) / 86400000);
    const hautMax = Math.max(1, ...serie.map((s) => s.haussiers + s.neutres));
    const basMax = Math.max(1, ...serie.map((s) => s.baissiers));
    const plage = hautMax + basMax;
    const zone = haut - marge.haut - marge.bas;
    const y0 = marge.haut + zone * hautMax / plage;
    const pas = (large - marge.gauche - marge.droite) / jours;
    const l = Math.max(1, pas * 0.75);
    const yv = (v) => zone * v / plage;
    ctx.strokeStyle = couleur("--axis"); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(marge.gauche, y0 + 0.5); ctx.lineTo(large - marge.droite, y0 + 0.5); ctx.stroke();
    ctx.fillStyle = couleur("--text-muted"); ctx.font = "11px system-ui, sans-serif"; ctx.textAlign = "right";
    ctx.fillText(String(hautMax), marge.gauche - 6, marge.haut + 8);
    ctx.fillText("0", marge.gauche - 6, y0 + 4);
    ctx.fillText("−" + basMax, marge.gauche - 6, haut - marge.bas);
    for (const s of serie) {
      const i = idx(String(s.jour).slice(0, 10));
      if (i < 0 || i >= jours) continue;
      const x = marge.gauche + i * pas + (pas - l) / 2;
      ctx.fillStyle = couleur("--status-good");
      ctx.fillRect(x, y0 - yv(s.haussiers), l, yv(s.haussiers));
      ctx.fillStyle = couleur("--series-neutre");
      ctx.fillRect(x, y0 - yv(s.haussiers + s.neutres), l, yv(s.neutres));
      ctx.fillStyle = couleur("--status-critical");
      ctx.fillRect(x, y0, l, yv(s.baissiers));
    }
    ctx.fillStyle = couleur("--text-muted"); ctx.textAlign = "center";
    for (let i = 0; i < jours; i += 10) {
      const d = new Date(debut.getTime() + i * 86400000).toISOString().slice(5, 10);
      ctx.fillText(d.slice(3) + "/" + d.slice(0, 2), marge.gauche + i * pas + pas / 2, haut - 6);
    }
  }

  function rendreDetail() {
    const d = etat.detail;
    const zone = $$("#sentiment-detail");
    if (!d) { zone.hidden = true; return; }
    zone.hidden = false;
    const nom = d.par === "actif" ? d.groupe : nomMarche(d.groupe);
    $$("#sentiment-detail-titre").textContent = `${nom} — articles par jour (${d.jours} derniers jours, UTC)`;
    barresJour($$("#sentiment-barres"), d.serie, d.jours);
    const lignes = d.articles.map((a) => {
      const [lib, cls] = SENS[a.sentiment] || [a.sentiment, ""];
      const titre = a.url ? `<a href="${echapper(a.url)}" target="_blank" rel="noopener noreferrer">${echapper(a.titre)}</a>`
                          : echapper(a.titre);
      return `<tr><td class="muet">${quand(a.ts_recu)}</td><td>${echapper(a.source)}</td>
        <td class="${cls}">${lib}</td><td>${manque(a.proba) ? "—" : (100 * a.proba).toFixed(0) + " %"}</td>
        <td>${echapper(a.actifs || "")}</td><td class="muet">${echapper(a.texte_utilise)}</td>
        <td class="sentiment-titre">${titre}</td></tr>`;
    }).join("");
    $$("#sentiment-articles").innerHTML = lignes
      ? `<table><thead><tr><th>reçu</th><th>source</th><th>sentiment</th><th>proba</th><th>actifs</th>
         <th>texte lu</th><th>titre</th></tr></thead><tbody>${lignes}</tbody></table>`
      : '<p class="vide">Aucun article.</p>';
  }

  async function choisir(par, groupe) {
    etat.choix = { par, groupe };
    rendreTables();
    try {
      const v = encodeURIComponent(etat.vue.version || "");
      etat.detail = await lire(`/api/sentiment/detail?par=${par}&groupe=${encodeURIComponent(groupe)}&version=${v}`);
    } catch (exc) {
      etat.detail = null;
      $$("#sentiment-message").textContent = "Erreur : " + exc.message;
    }
    rendreDetail();
  }

  /* ---------- chargement --------------------------------------------------------------- */

  async function charger(version) {
    $$("#sentiment-message").textContent = "Chargement…";
    try {
      etat.vue = await lire("/api/sentiment" + (version ? "?version=" + encodeURIComponent(version) : ""));
      $$("#sentiment-message").textContent = "";
    } catch (exc) {
      $$("#sentiment-message").textContent = "Erreur : " + exc.message;
      return;
    }
    const ok = rendreEntete();
    $$("#sentiment-corps").hidden = !ok;
    if (!ok) return;
    rendreTables();
    if (etat.choix) await choisir(etat.choix.par, etat.choix.groupe);
    else if (etat.vue.par_actif.length) await choisir("actif", etat.vue.par_actif[0].groupe);
  }

  document.querySelectorAll("#sentiment-fenetres button").forEach((b) =>
    b.addEventListener("click", () => {
      etat.fenetre = b.dataset.fenetre;
      document.querySelectorAll("#sentiment-fenetres button").forEach((x) =>
        x.classList.toggle("is-active", x === b));
      if (etat.vue && etat.vue.version) rendreTables();
    }));
  $$("#sentiment-recharger").addEventListener("click", () => charger(etat.vue && etat.vue.version));

  return {
    afficher() {                        // a la premiere ouverture seulement
      if (!etat.charge) { etat.charge = true; charger(); }
      else if (etat.detail) rendreDetail();      // canvas masque = largeur nulle : on redessine
    },
  };
})();
