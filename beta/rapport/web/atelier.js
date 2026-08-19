/* BETA — onglet Atelier. Ecrire une candidate a la main, ou la faire ecrire par un modele
   qui tourne sur cette machine.

   Le client n'envoie jamais de commande : il envoie un NOM DE GESTE pris dans une liste
   blanche cote serveur (gabarit, valider, deposer, generer) et des donnees. Le serveur
   decide de tout le reste — ou le code est ecrit, dans quel sous-processus il est eprouve,
   et s'il a le droit d'entrer dans beta/candidates/.

   La generation est LONGUE par nature (un 7B ecrit une candidate en une a trois minutes, et
   la boucle de reparation recommence). L'interface le dit et desactive ses boutons plutot
   que de laisser croire a une panne. */

const ATELIER = (() => {
  const $$ = (sel) => document.querySelector(sel);
  const etat = { inventaire: null, occupe: false };

  const echapper = (texte) => String(texte ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- rendu ------------------------------------------------------------------ */

  function rendreListe() {
    const d = etat.inventaire;
    const liste = $$("#atelier-liste");
    if (!d || !d.candidates.length) {
      liste.innerHTML = '<p class="vide">Aucune candidate. Partir d\'un squelette.</p>';
      return;
    }
    liste.innerHTML = d.candidates.map((c) => `
      <button class="run-item" data-module="${echapper(c.module)}">
        <span class="run-nom">${echapper(c.nom)}</span>
        <span class="run-meta">${echapper(c.module)} · ${echapper(c.hypothese)} · ${echapper(c.empreinte)}</span>
      </button>`).join("");
  }

  function rendreModeles() {
    const d = etat.inventaire;
    const boite = $$("#atelier-modeles");
    const choix = $$("#atelier-modele");
    if (!d) return;
    boite.innerHTML = d.modeles.map((s) => s.disponible
      ? `<p class="sous"><span class="puce ok">${echapper(s.backend)}</span>
           ${echapper(s.modeles.join(", "))}</p>`
      : `<p class="sous"><span class="puce alerte">${echapper(s.backend)}</span>
           injoignable</p>`).join("");

    const options = ['<option value="">auto — le premier qui répond</option>'];
    d.modeles.filter((s) => s.disponible).forEach((s) => s.modeles.forEach((m) =>
      options.push(`<option value="${echapper(s.backend)}|${echapper(m)}">${echapper(s.backend)} / ${echapper(m)}</option>`)));
    choix.innerHTML = options.join("");
    $$("#atelier-essais").max = d.max_essais;
  }

  function rendreRapport(rapport) {
    const boite = $$("#atelier-rapport");
    if (!rapport) { boite.innerHTML = ""; return; }
    if (rapport.erreur) {
      boite.innerHTML = `<h2>Refus</h2><p class="erreur">${echapper(rapport.erreur)}</p>`;
      return;
    }
    const refus = (rapport.refus || []).map((r) =>
      `<li class="atelier-refus">${echapper(r)}</li>`).join("");
    const reserves = (rapport.reserves || []).map((r) =>
      `<li class="atelier-reserve">${echapper(r)}</li>`).join("");
    const mesures = Object.entries(rapport.mesures || {}).map(([cle, v]) =>
      `<span class="atelier-mesure"><em>${echapper(cle)}</em> ${echapper(v)}</span>`).join("");
    const tentatives = (rapport.tentatives || []).map((t) =>
      `<li>essai ${t.essai} : ${t.ok ? "passé" : "refusé"}${
        (t.refus || []).length ? " — " + echapper(t.refus.join(" | ")) : ""}</li>`).join("");

    boite.innerHTML = `
      <h2>${rapport.ok ? "Passe" : "Refusé"}${rapport.depose ? " · déposé" : ""}</h2>
      <p class="sous">${rapport.ok
        ? "Éligible à être <em>mesurée</em> — ce n'est pas la même chose que « marche ». "
          + "Relis le code : le sas attrape des erreurs, pas un adversaire."
        : "Rien n'a été écrit dans <code>beta/candidates/</code>."}</p>
      ${refus ? `<ul class="atelier-liste-refus">${refus}</ul>` : ""}
      ${reserves ? `<ul class="atelier-liste-refus">${reserves}</ul>` : ""}
      ${mesures ? `<div class="atelier-mesures">${mesures}</div>` : ""}
      ${tentatives ? `<p class="sous" style="margin-top:10px">Tentatives du modèle</p>
                      <ul class="atelier-liste-refus">${tentatives}</ul>` : ""}`;
  }

  /* ---------- echanges avec le serveur ----------------------------------------------- */

  function occuper(occupe, message) {
    etat.occupe = occupe;
    document.querySelectorAll("[data-geste]").forEach((b) => (b.disabled = occupe));
    $$("#atelier-message").textContent = message || "";
  }

  async function charger() {
    try {
      etat.inventaire = await fetch("/api/atelier").then((r) => r.json());
    } catch (exc) {
      $$("#atelier-liste").innerHTML = `<p class="erreur">serveur injoignable : ${echapper(exc.message)}</p>`;
      return;
    }
    rendreListe();
    rendreModeles();
  }

  async function ouvrir(module) {
    const reponse = await fetch("/api/candidate?module=" + encodeURIComponent(module))
      .then((r) => r.json());
    if (reponse.erreur) return rendreRapport(reponse);
    $$("#atelier-code").value = reponse.code;
    $$("#atelier-module").value = module;
    const hypothese = (etat.inventaire.candidates.find((c) => c.module === module) || {}).hypothese;
    if (hypothese) $$("#atelier-hypothese").value = hypothese;
    rendreRapport(null);
    document.querySelectorAll("#atelier-liste .run-item").forEach((b) =>
      b.classList.toggle("is-active", b.dataset.module === module));
  }

  async function geste(nom) {
    if (etat.occupe) return;
    const module = $$("#atelier-module").value.trim();
    if (!module) return rendreRapport({ erreur: "donner un nom de module" });

    const [backend, modele] = ($$("#atelier-modele").value || "|").split("|");
    const charge = {
      geste: nom, module,
      hypothese: $$("#atelier-hypothese").value.trim(),
      intention: $$("#atelier-intention").value.trim(),
      code: $$("#atelier-code").value,
      ecraser: $$("#atelier-ecraser").checked,
      backend: backend || "auto", modele: modele || "",
      essais: Number($$("#atelier-essais").value) || 3,
    };

    const attentes = {
      gabarit: "squelette…", valider: "sas puis épreuve, dans un sous-processus…",
      deposer: "sas, épreuve, puis dépôt…",
      generer: "le modèle local écrit — une à trois minutes par essai, ne pas fermer l'onglet…",
    };
    occuper(true, attentes[nom] || "…");
    let rapport;
    try {
      rapport = await fetch("/api/atelier", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(charge),
      }).then((r) => r.json());
    } catch (exc) {
      rapport = { erreur: "serveur injoignable : " + exc.message };
    } finally {
      occuper(false, "");
    }

    if (rapport.code) $$("#atelier-code").value = rapport.code;
    rendreRapport(rapport);
    if (rapport.depose) charger();
  }

  /* ---------- branchements ------------------------------------------------------------ */

  document.addEventListener("click", (ev) => {
    const bouton = ev.target.closest("[data-geste]");
    if (bouton) return geste(bouton.dataset.geste);
    const item = ev.target.closest("#atelier-liste .run-item");
    if (item) return ouvrir(item.dataset.module);
  });

  return { charger };
})();
