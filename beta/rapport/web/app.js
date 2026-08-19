/* BETA — dashboard. Vanilla, zero dependance, zero CDN : le serveur ne sert que web/.
   Les graphiques sont dessines au canvas plutot qu'avec une librairie — deux courbes ne
   justifient pas 300 ko de dependance, et le canvas rend le meme resultat hors ligne. */

const $ = (sel) => document.querySelector(sel);
const etat = { strategie: null, lake: null, protocole: null, onglet: "strategie" };

const CSS = getComputedStyle(document.documentElement);
const couleur = (nom) => CSS.getPropertyValue(nom).trim();

/* ---------- formatage ---------------------------------------------------------------- */

const nb = (v, d = 4) => (v === null || v === undefined || Number.isNaN(v))
  ? "—" : Number(v).toLocaleString("fr-FR", { minimumFractionDigits: d, maximumFractionDigits: d });
const signe = (v, d = 4) => (v === null || v === undefined || Number.isNaN(v))
  ? "—" : (v >= 0 ? "+" : "") + nb(v, d);
const pct = (v) => (v === null || v === undefined || Number.isNaN(v))
  ? "—" : (100 * v).toFixed(1) + " %";
const entier = (v) => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("fr-FR");
const date = (s) => s ? String(s).slice(0, 10) : "—";

/* ---------- tableaux ------------------------------------------------------------------ */

// Chaque colonne declare son rendu : sans ca, on retombe vite sur des `if (cle === ...)`
// disperses dans le code d'affichage.
const COLONNES = {
  n: ["n", entier], n_avec_r: ["avec R", entier],
  r_moyen: ["R moyen", (v) => signe(v)], r_median: ["R médian", (v) => signe(v)],
  r_total: ["R total", (v) => signe(v, 2)], mde_r: ["MDE", (v) => signe(v)],
  r_sigma: ["σ(R)", (v) => nb(v, 3)],
  rendement_total_pct: ["rendement", (v) => signe(v, 2) + " %"],
  rendement_moyen_pct: ["rdt moyen", (v) => signe(v, 3) + " %"],
  win_rate: ["win rate", pct], profit_factor: ["PF", (v) => nb(v, 3)],
  mfe_r_moyen: ["MFE", (v) => signe(v, 3)], mae_r_moyen: ["MAE", (v) => signe(v, 3)],
  duree_h_mediane: ["durée méd. (h)", (v) => nb(v, 1)],
  part_pct: ["part", (v) => nb(v, 2) + " %"],
  n_bougies: ["bougies", entier], couverture_pct: ["couverture", (v) => nb(v, 2) + " %"],
  bougies_manquantes: ["manquantes", entier],
  plus_grand_trou_h: ["+ grand trou (h)", (v) => nb(v, 1)],
  debut: ["début", date], fin: ["fin", date], maj: ["màj", date],
};

const NEGATIF_EST_MAUVAIS = new Set(["r_moyen", "r_median", "r_total",
  "rendement_total_pct", "rendement_moyen_pct"]);

function tableau(lignes, colonnes) {
  if (!lignes || !lignes.length) return '<p class="vide">Aucune donnée.</p>';
  const cles = colonnes || Object.keys(lignes[0]);
  const th = cles.map((c) => `<th>${(COLONNES[c] || [c])[0]}</th>`).join("");
  const tr = lignes.map((ligne) => "<tr>" + cles.map((c) => {
    const brut = ligne[c];
    const rendu = COLONNES[c] ? COLONNES[c][1](brut) : cellule(c, brut);
    let classe = "";
    if (NEGATIF_EST_MAUVAIS.has(c) && typeof brut === "number") classe = brut >= 0 ? "pos" : "neg";
    if (brut === null || brut === undefined) classe = "muet";
    return `<td class="${classe}">${rendu}</td>`;
  }).join("") + "</tr>").join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}

function cellule(cle, valeur) {
  if (valeur === null || valeur === undefined) return "—";
  if (cle === "suspect") {
    return valeur ? '<span class="puce alerte">suspecte</span>'
                  : '<span class="puce ok">complète</span>';
  }
  if (cle === "sens") return `<span class="puce ${valeur}">${valeur}</span>`;
  if (typeof valeur === "number") return nb(valeur, 4);
  return String(valeur);
}

/* ---------- graphiques ---------------------------------------------------------------- */

function preparer(canvas) {
  // Sans mise a l'echelle par devicePixelRatio, tout est flou sur un ecran HiDPI.
  const ratio = window.devicePixelRatio || 1;
  const large = canvas.clientWidth || 600;
  const haut = canvas.clientHeight || 260;
  canvas.width = large * ratio;
  canvas.height = haut * ratio;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, large, haut);
  return { ctx, large, haut };
}

function axes(ctx, large, haut, marge, yMin, yMax, zero) {
  ctx.strokeStyle = couleur("--grid");
  ctx.fillStyle = couleur("--text-muted");
  ctx.font = "11px system-ui, sans-serif";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = marge.haut + (haut - marge.haut - marge.bas) * i / 4;
    const valeur = yMax - (yMax - yMin) * i / 4;
    ctx.beginPath();
    ctx.moveTo(marge.gauche, y + 0.5);
    ctx.lineTo(large - marge.droite, y + 0.5);
    ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(valeur.toFixed(1), marge.gauche - 6, y + 4);
  }
  if (zero !== null) {                      // le zero merite un trait plus marque
    ctx.strokeStyle = couleur("--axis");
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(marge.gauche, zero);
    ctx.lineTo(large - marge.droite, zero);
    ctx.stroke();
  }
}

function courbeEquity(canvas, points) {
  const { ctx, large, haut } = preparer(canvas);
  if (!points || points.length < 2) return vide(ctx, large, haut, "Pas assez de trades.");
  const marge = { gauche: 46, droite: 12, haut: 14, bas: 22 };
  const ys = points.map((p) => p.r_cumule);
  const yMax = Math.max(...ys, 0.5);
  const yMin = Math.min(...ys, -0.5);
  const x = (i) => marge.gauche + (large - marge.gauche - marge.droite) * i / (points.length - 1);
  const y = (v) => marge.haut + (haut - marge.haut - marge.bas) * (yMax - v) / (yMax - yMin || 1);

  axes(ctx, large, haut, marge, yMin, yMax, y(0));

  // Aire sous la courbe, teintee selon le signe final : le sens du resultat doit se lire
  // avant meme d'avoir regarde l'axe.
  const fin = ys[ys.length - 1];
  const teinte = fin >= 0 ? couleur("--status-good") : couleur("--status-critical");
  ctx.beginPath();
  ctx.moveTo(x(0), y(0));
  points.forEach((p, i) => ctx.lineTo(x(i), y(p.r_cumule)));
  ctx.lineTo(x(points.length - 1), y(0));
  ctx.closePath();
  ctx.fillStyle = teinte + "22";
  ctx.fill();

  ctx.beginPath();
  points.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.r_cumule)) : ctx.moveTo(x(i), y(p.r_cumule))));
  ctx.strokeStyle = teinte;
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = couleur("--text-muted");
  ctx.textAlign = "left";
  ctx.fillText(date(points[0].ts), marge.gauche, haut - 6);
  ctx.textAlign = "right";
  ctx.fillText(date(points[points.length - 1].ts), large - marge.droite, haut - 6);
}

function histogramme(canvas, valeurs) {
  const { ctx, large, haut } = preparer(canvas);
  if (!valeurs || !valeurs.length) return vide(ctx, large, haut, "Aucun R disponible.");
  const marge = { gauche: 46, droite: 12, haut: 14, bas: 22 };
  const min = Math.min(...valeurs), max = Math.max(...valeurs);
  const nCases = Math.min(24, Math.max(6, Math.round(Math.sqrt(valeurs.length) * 2)));
  const pas = (max - min) / nCases || 1;
  const cases = new Array(nCases).fill(0);
  valeurs.forEach((v) => {
    const i = Math.min(nCases - 1, Math.floor((v - min) / pas));
    cases[i] += 1;
  });
  const hMax = Math.max(...cases);
  const largeurCase = (large - marge.gauche - marge.droite) / nCases;

  axes(ctx, large, haut, marge, 0, hMax, null);

  cases.forEach((compte, i) => {
    const centre = min + pas * (i + 0.5);
    const h = (haut - marge.haut - marge.bas) * compte / (hMax || 1);
    ctx.fillStyle = centre >= 0 ? couleur("--status-good") : couleur("--status-critical");
    ctx.fillRect(marge.gauche + i * largeurCase + 1, haut - marge.bas - h,
                 Math.max(1, largeurCase - 2), h);
  });

  const xZero = marge.gauche + (0 - min) / (max - min || 1) * (large - marge.gauche - marge.droite);
  if (min < 0 && max > 0) {
    ctx.strokeStyle = couleur("--axis");
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(xZero, marge.haut);
    ctx.lineTo(xZero, haut - marge.bas);
    ctx.stroke();
  }
  ctx.fillStyle = couleur("--text-muted");
  ctx.textAlign = "left";
  ctx.fillText(min.toFixed(2) + " R", marge.gauche, haut - 6);
  ctx.textAlign = "right";
  ctx.fillText(max.toFixed(2) + " R", large - marge.droite, haut - 6);
}

function vide(ctx, large, haut, message) {
  ctx.fillStyle = couleur("--text-muted");
  ctx.font = "12px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(message, large / 2, haut / 2);
}

/* ---------- rendu ---------------------------------------------------------------------- */

function tuile(valeur, libelle, ton = "", note = "") {
  return `<div class="kpi" data-tone="${ton}">
    <span class="kpi-value">${valeur}</span>
    <span class="kpi-label">${libelle}</span>
    ${note ? `<span class="kpi-note">${note}</span>` : ""}
  </div>`;
}

function rendreStrategie() {
  const d = etat.strategie;
  if (!d || d.erreur) {
    $("#kpis").innerHTML = "";
    $("#carte-verdict").innerHTML =
      `<p class="erreur">${d ? d.erreur : "chargement impossible"}</p>
       <p class="sous">Lancer <code>scripts/import_strategie.py</code> pour remplir le lake.</p>`;
    return;
  }
  const r = d.resume;
  const sousLeSeuil = Math.abs(r.r_moyen) < r.mde_r;

  $("#kpis").innerHTML = [
    tuile(entier(r.n), "trades", "", r.n_avec_r !== r.n ? `${r.n_avec_r} avec R` : ""),
    tuile(signe(r.r_moyen), "R moyen", r.r_moyen >= 0 ? "good" : "critical"),
    tuile(signe(r.mde_r), "MDE", "muted", "seuil de détection"),
    tuile(signe(r.rendement_total_pct, 2) + " %", "rendement",
          r.rendement_total_pct >= 0 ? "good" : "critical"),
    tuile(pct(r.win_rate), "win rate"),
    tuile(nb(r.profit_factor, 3), "profit factor",
          r.profit_factor >= 1 ? "good" : "critical"),
  ].join("");

  $("#carte-verdict").innerHTML = `
    <h2>Ce que l'échantillon permet de dire</h2>
    ${sousLeSeuil ? `<p class="avertir"><strong>|R moyen| = ${nb(Math.abs(r.r_moyen))}
      est SOUS le MDE (${nb(r.mde_r)})</strong> : sur ${entier(r.n_avec_r)} trades, ce
      résultat est indiscernable de zéro. Ni bon, ni mauvais — <em>non mesurable</em>.
      Aucune décision ne devrait s'appuyer dessus.</p>`
      : `<p class="avertir"><strong>|R moyen| dépasse le MDE.</strong> L'écart est
      détectable à cette taille d'échantillon — ce qui ne dispense ni d'une correction de
      tests multiples, ni d'une confirmation hors échantillon.</p>`}
    <div class="tableau-wrap">${tableau([r], ["n", "n_avec_r", "r_moyen", "r_median",
      "r_sigma", "r_total", "mde_r", "rendement_total_pct", "win_rate", "profit_factor",
      "mfe_r_moyen", "mae_r_moyen", "duree_h_mediane"])}</div>`;

  const colonnes = ["n", "r_moyen", "mde_r", "r_total", "rendement_total_pct",
                    "win_rate", "profit_factor"];
  $("#par-sens").innerHTML = tableau(d.par_sens, ["sens", ...colonnes]);
  $("#par-paire").innerHTML = tableau(d.par_paire, ["paire", ...colonnes]);
  $("#par-strategie").innerHTML = tableau(d.par_strategie, ["strategie", ...colonnes]);
  $("#raisons-sortie").innerHTML = tableau(d.raisons_sortie, ["raison_sortie", ...colonnes]);
  $("#raisons-rejet").innerHTML = tableau(d.raisons_rejet);

  $("#portee").innerHTML = d.portee.startsWith("train")
    ? `portée : train seulement — hold-out scellé au ${d.holdout_debut}`
    : `portée : <strong>HOLD-OUT INCLUS</strong> — ces chiffres ne peuvent plus servir à choisir`;

  courbeEquity($("#equity"), d.equity);
  histogramme($("#distribution"), d.distribution_r);
}

function rendreLake() {
  const d = etat.lake;
  if (!d || !d.series.length) {
    $("#carte-lake").innerHTML = '<p class="vide">Lake vide — lancer scripts/build_lake.py.</p>';
    $("#series").innerHTML = "";
    return;
  }
  const r = d.resume;
  $("#carte-lake").innerHTML = `
    <h2>Le lake</h2>
    <div class="kpis">
      ${tuile(entier(r.paires), "paires")}
      ${tuile(entier(r.series), "séries")}
      ${tuile(entier(r.bougies), "bougies")}
      ${tuile(entier(r.suspectes), "suspectes", r.suspectes ? "critical" : "good")}
      ${tuile(date(r.fin_commune), "borne commune", "muted", "limite d'un run multi-paires")}
    </div>
    <p class="sous" style="margin-top:12px">Couverture ${date(r.debut)} → ${date(r.fin)}.
      Un backtest multi-paires s'arrête à la <em>borne commune</em>, pas à la date la plus
      récente.</p>`;
  $("#series").innerHTML = tableau(d.series, ["paire", "timeframe", "n_bougies", "debut",
    "fin", "couverture_pct", "bougies_manquantes", "plus_grand_trou_h", "suspect", "source"]);
}

function rendreProtocole() {
  const d = etat.protocole;
  if (!d || d.erreur) {
    $("#carte-protocole").innerHTML = `<p class="erreur">${d ? d.erreur : "—"}</p>`;
    return;
  }
  $("#carte-protocole").innerHTML = `
    <h2>Protocole expérimental</h2>
    <div class="kpis">
      ${tuile(entier(d.compteur), "essais cumulés", "warning",
              `dont ${d.dette_initiale} de dette initiale`)}
      ${tuile(entier(d.experiences.length), "expériences déclarées")}
    </div>
    <p class="sous" style="margin-top:12px">Le compteur n'est jamais remis à zéro : il doit
      compter <em>tous</em> les essais, y compris ceux qu'on n'a jamais rapportés. C'est la
      seule base honnête d'une correction de tests multiples.</p>`;
  $("#experiences").innerHTML = d.experiences.length
    ? tableau(d.experiences, ["id", "statut", "date", "verdict", "hypothese"])
    : '<p class="vide">Aucune expérience déclarée. Rien ne se mesure avant.</p>';
}

/* ---------- boite a idees ---------------------------------------------------------------- */

// Noter une idee est GRATUIT : le compteur d'essais ne bouge pas. Il ne bouge qu'a la
// promotion en experience preenregistree, qui se fait en ligne de commande — la friction est
// voulue, c'est le seul geste qui durcit le seuil de toutes les hypotheses.
async function chargerIdees() {
  let d;
  try {
    d = await fetch("/api/idees").then((r) => r.json());
  } catch (exc) {
    $("#idees").innerHTML = `<p class="erreur">${exc.message}</p>`;
    return;
  }
  $("#idees").innerHTML = d.idees.length
    ? tableau(d.idees.map((i) => ({
        id: i.id, date: i.date, etat: i.etat, texte: i.texte,
        suite: i.id_experience || i.motif || "",
      })), ["id", "date", "etat", "texte", "suite"])
    : '<p class="vide">Aucune idée notée. La boîte est gratuite : rien ne coûte tant qu'on ne promeut pas.</p>';
  $("#idee-message").textContent =
    `${d.resume.nouvelle} nouvelle(s) · compteur d'essais : ${d.resume.compteur_essais} (inchangé)`;
}

document.addEventListener("submit", async (ev) => {
  if (ev.target.id !== "idee-form") return;
  ev.preventDefault();
  const texte = $("#idee-texte").value.trim();
  if (texte.length < 10) {
    $("#idee-message").textContent = "une idée de moins de dix caractères ne se relira pas";
    return;
  }
  $("#idee-message").textContent = "…";
  const reponse = await fetch("/api/idee", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texte, source: $("#idee-source").value.trim() }),
  }).then((r) => r.json()).catch((exc) => ({ erreur: exc.message }));
  if (reponse.erreur) {
    $("#idee-message").textContent = "refus : " + reponse.erreur;
    return;
  }
  $("#idee-texte").value = "";
  $("#idee-source").value = "";
  chargerIdees();
});

/* ---------- chargement ------------------------------------------------------------------ */

async function charger() {
  const bouton = $("#rafraichir");
  bouton.disabled = true;
  const holdout = $("#holdout").checked ? "?holdout=1" : "";
  try {
    const [strategie, lake, protocole] = await Promise.all([
      fetch("/api/strategie" + holdout).then((r) => r.json()),
      fetch("/api/lake").then((r) => r.json()),
      fetch("/api/protocole").then((r) => r.json()),
    ]);
    Object.assign(etat, { strategie, lake, protocole });
  } catch (exc) {
    etat.strategie = { erreur: "serveur injoignable : " + exc.message };
  } finally {
    bouton.disabled = false;
  }
  rendreStrategie();
  rendreLake();
  rendreProtocole();
  FICHE.charger();
  ATELIER.charger();
  COMPARAISON.charger();
  chargerIdees();
}

function ongletActif(nom) {
  etat.onglet = nom;
  document.querySelectorAll(".tab").forEach((t) =>
    t.classList.toggle("is-active", t.dataset.onglet === nom));
  ["strategie", "candidates", "comparaison", "atelier", "lake", "protocole"].forEach((o) =>
    ($("#onglet-" + o).hidden = o !== nom));
  // Un canvas d'onglet masque a une largeur nulle : la fiche se redessine a l'affichage.
  if (nom === "candidates" && FICHE.aDesDonnees()) FICHE.redessiner();
  if (nom === "comparaison" && COMPARAISON.aDesDonnees()) COMPARAISON.redessiner();
  if (nom === "strategie" && etat.strategie && !etat.strategie.erreur) {
    // Le canvas d'un onglet masque a une largeur nulle : on redessine a l'affichage.
    courbeEquity($("#equity"), etat.strategie.equity);
    histogramme($("#distribution"), etat.strategie.distribution_r);
  }
}

document.querySelectorAll(".tab").forEach((t) =>
  t.addEventListener("click", () => ongletActif(t.dataset.onglet)));
$("#rafraichir").addEventListener("click", charger);
$("#holdout").addEventListener("change", charger);
window.addEventListener("resize", () => ongletActif(etat.onglet));

charger();
