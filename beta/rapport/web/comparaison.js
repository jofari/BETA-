/* BETA — onglet Comparaison. Plusieurs strategies mises en regard, pas une fiche a la fois.

   Ce que cet onglet montre et qu'aucun autre ne peut montrer : le classement, la matrice de
   correlation, la p-value du MEILLEUR du lot (S7), et l'ecart contre AritV1 — la strategie
   qui tourne, qui est la reference qui decide vraiment, a cote du buy-and-hold.

   Les courbes sont en base 100 et dans la meme convention de sizing pour toutes : sans ca,
   l'ecart mesurerait la convention avant de mesurer la strategie. */

const COMPARAISON = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { vue: null };

  const echapper = (t) => String(t ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Palette des courbes. AritV1 garde toujours la meme couleur et le pointille : c'est la
  // reference, elle ne doit pas changer d'aspect quand on ajoute une candidate.
  const TEINTES = ["--accent", "--series-long", "--series-short", "--status-warning",
                   "--status-serious"];
  const teinte = (i) => couleur(TEINTES[i % TEINTES.length]);
  const EST_ARIT = (nom) => nom.startsWith("AritV1");

  /* ---------- classement -------------------------------------------------------------- */

  const COLONNES = [
    ["rang", "#", (v) => v],
    ["candidate", "candidate", echapper],
    ["issue", "issue", (v) => `<span class="puce ${v === "confirmee" ? "ok" : "alerte"}">${echapper(v)}</span>`],
    ["n", "n", entier],
    ["r_moyen", "R moyen", (v) => signe(v)],
    ["mde_r", "MDE", (v) => signe(v)],
    ["win_rate", "win rate", pct],
    ["portes_echouees", "portes ✗", entier],
    ["portes_non_executees", "non exéc.", entier],
    ["vs_arit_ecart_rendement_pct", "vs AritV1 (rdt)", (v) => signe(v, 1) + " pts"],
    ["vs_arit_ecart_sharpe", "vs AritV1 (Sharpe)", (v) => signe(v, 2)],
    ["vs_arit_correlation", "corr. AritV1", (v) => nb(v, 3)],
  ];

  function rendreTableau() {
    const lignes = etat.vue.tableau;
    const cible = $$("#comparaison-tableau");
    if (!lignes.length) { cible.innerHTML = '<p class="vide">Aucun run.</p>'; return; }
    const presentes = COLONNES.filter(([cle]) => cle in lignes[0]);
    const th = presentes.map(([, titre]) => `<th>${titre}</th>`).join("");
    const tr = lignes.map((l) => "<tr>" + presentes.map(([cle, , rendu]) => {
      const brut = l[cle];
      const classe = (brut === null || brut === undefined) ? "muet"
        : (cle.startsWith("vs_arit_ecart") || cle === "r_moyen")
          ? (brut >= 0 ? "pos" : "neg") : "";
      return `<td class="${classe}">${brut === null || brut === undefined ? "—" : rendu(brut)}</td>`;
    }).join("") + "</tr>").join("");
    cible.innerHTML = `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
  }

  /* ---------- courbes superposees ------------------------------------------------------ */

  function rendreCourbes() {
    const canvas = $$("#comparaison-courbes");
    const { ctx, large, haut } = preparer(canvas);
    const noms = Object.keys(etat.vue.courbes).filter((n) => etat.vue.courbes[n].length > 1);
    if (!noms.length) return vide(ctx, large, haut, "Aucune courbe à superposer.");

    const marge = { gauche: 52, droite: 12, haut: 14, bas: 26 };
    const points = noms.map((n) => etat.vue.courbes[n]);
    const temps = points.flat().map((p) => Date.parse(p.ts));
    const tMin = Math.min(...temps), tMax = Math.max(...temps);
    const valeurs = points.flat().map((p) => p.valeur);
    const yMax = Math.max(...valeurs, 105), yMin = Math.min(...valeurs, 95);

    const x = (ts) => marge.gauche + (large - marge.gauche - marge.droite)
      * (Date.parse(ts) - tMin) / (tMax - tMin || 1);
    const y = (v) => marge.haut + (haut - marge.haut - marge.bas)
      * (yMax - v) / (yMax - yMin || 1);

    axes(ctx, large, haut, marge, yMin, yMax, y(100));

    noms.forEach((nom, i) => {
      ctx.strokeStyle = EST_ARIT(nom) ? couleur("--text-muted") : teinte(i);
      ctx.lineWidth = EST_ARIT(nom) ? 1.6 : 2;
      ctx.setLineDash(EST_ARIT(nom) ? [5, 4] : []);
      ctx.beginPath();
      etat.vue.courbes[nom].forEach((p, j) =>
        j ? ctx.lineTo(x(p.ts), y(p.valeur)) : ctx.moveTo(x(p.ts), y(p.valeur)));
      ctx.stroke();
    });
    ctx.setLineDash([]);

    $$("#comparaison-legende").innerHTML = noms.map((nom, i) =>
      `<span class="comp-legende"><i style="background:${
        EST_ARIT(nom) ? couleur("--text-muted") : teinte(i)}"></i>${echapper(nom)}</span>`
    ).join("");
  }

  /* ---------- matrice et S7 ------------------------------------------------------------ */

  function rendreMatrice() {
    const m = etat.vue.matrice;
    const cible = $$("#comparaison-matrice");
    if (!m.noms.length) {
      cible.innerHTML = '<p class="vide">Il faut au moins deux candidates dont les courbes '
        + 'se recouvrent pour qu\'une corrélation existe.</p>';
      return;
    }
    const th = m.noms.map((n) => `<th>${echapper(n)}</th>`).join("");
    const tr = m.valeurs.map((ligne, i) => `<tr><th>${echapper(m.noms[i])}</th>` +
      ligne.map((v, j) => {
        if (v === null) return '<td class="muet">—</td>';
        const fort = i !== j && Math.abs(v) >= 0.70;
        return `<td class="${fort ? "neg" : ""}">${nb(v, 2)}</td>`;
      }).join("") + "</tr>").join("");
    cible.innerHTML = `<table><thead><tr><th></th>${th}</tr></thead><tbody>${tr}</tbody></table>`;

    const doublons = etat.vue.redondances;
    if (doublons.length) {
      cible.innerHTML += doublons.map((d) =>
        `<p class="erreur">${echapper(d.a)} et ${echapper(d.b)} corrélées à ${nb(d.correlation, 2)}
         — elles n'en font qu'une.</p>`).join("");
    }
  }

  function rendreS7() {
    const rc = etat.vue.reality_check;
    const cible = $$("#comparaison-s7");
    if (rc.p_value === null || rc.p_value === undefined) {
      cible.innerHTML = `<p class="vide">Non exécutable : ${entier(rc.n_candidates)} candidate(s).
        Il en faut au moins deux — le maximum d'un ensemble à un élément est cet élément.</p>`;
      return;
    }
    const passe = rc.p_value <= 0.05;
    cible.innerHTML = `
      <div class="kpis">
        ${tuile(nb(rc.p_value, 4), "p-value du maximum", passe ? "good" : "critical")}
        ${tuile(entier(rc.n_candidates), "candidates dans l'univers")}
        ${tuile(echapper(rc.meilleure || "—"), "meilleure du lot", "muted")}
      </div>
      <p class="sous" style="margin-top:12px">H₀ : aucune candidate ne bat la référence.
        ${passe ? "p ≤ 0,05 — le meilleur du lot n'est pas explicable par le seul choix du meilleur."
                : "p > 0,05 — <strong>le meilleur du lot est explicable par le hasard du choix</strong>."}</p>`;
  }

  /* ---------- entete et reserves -------------------------------------------------------- */

  function rendreEntete() {
    const v = etat.vue;
    $$("#comparaison-entete").innerHTML = `
      <h2>Comparer des stratégies entre elles</h2>
      <div class="kpis">
        ${tuile(entier(v.n), "stratégies comparées", v.n < 2 ? "warning" : "good")}
        ${tuile(v.arit_present ? "oui" : "non", "AritV1 en référence",
                v.arit_present ? "good" : "warning")}
        ${tuile(echapper(v.split || "train"), "split", "muted")}
      </div>
      <p class="sous" style="margin-top:12px">Un seul run par candidate, le plus récent :
        deux runs de la même stratégie ne sont pas deux stratégies, et les compter deux fois
        gonflerait l'univers du reality check avec une copie de lui-même.</p>`;

    $$("#comparaison-reserves").innerHTML = v.reserves.length
      ? `<h2>Ce que cette comparaison ne dit pas</h2><ul class="atelier-liste-refus">${
          v.reserves.map((r) => `<li class="atelier-reserve">${echapper(r)}</li>`).join("")}</ul>`
      : "";
  }

  /* ---------- chargement ---------------------------------------------------------------- */

  async function charger() {
    const holdout = $$("#holdout").checked ? "?holdout=1" : "";
    try {
      etat.vue = await fetch("/api/comparaison" + holdout).then((r) => r.json());
    } catch (exc) {
      $$("#comparaison-entete").innerHTML =
        `<p class="erreur">serveur injoignable : ${echapper(exc.message)}</p>`;
      return;
    }
    rendreEntete();
    rendreTableau();
    rendreMatrice();
    rendreS7();
    rendreCourbes();
  }

  return { charger, redessiner: () => etat.vue && rendreCourbes(),
           aDesDonnees: () => Boolean(etat.vue) };
})();
