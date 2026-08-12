/* PinCabOS-File created by Karots Sugarpie */
(function () {
  function textOf(el) {
    return (el && el.textContent ? el.textContent : "").trim();
  }

  function findHeading(text) {
    const headings = Array.from(document.querySelectorAll("h1,h2,h3"));
    return headings.find(h => textOf(h).includes(text));
  }

  function closestCard(el) {
    return el ? el.closest(".card") : null;
  }

  function addHero() {
    // Hero supprimé à la demande: carte inutile.
    return;
  }

  function enhanceImportCard() {
    const card = document.getElementById("pincabos-dof-import-manual-card");
    if (!card) return;

    const h2 = card.querySelector("h2");
    if (h2 && !h2.textContent.includes("ZIP + API")) {
      h2.textContent = "Import DOF Config Tool — ZIP + API";
    }

    const apiNote = Array.from(card.querySelectorAll("p"))
      .find(p => p.textContent.includes("Cloudflare"));
    if (apiNote) {
      apiNote.innerHTML = "Si l’import API retourne <code>403 Forbidden / Cloudflare</code>, utilise l’import ZIP manuel. C’est la méthode la plus fiable.";
    }
  }

  function hideWhatIsThisPageCard() {
    const heading = findHeading("À quoi sert cette page");
    const card = closestCard(heading);

    if (card) {
      card.classList.add("pco-dof-hidden-info-card");
      card.setAttribute("data-hidden-by-pincabos", "dof-info-card");
    }
  }

  function labelSections() {
    const driver = findHeading("État DOF Driver Pack");
    const general = findHeading("DOF — État général");

    [general, driver].forEach(h => {
      const card = closestCard(h);
      if (card) card.classList.add("pco-dof-section-card");
    });
  }

  function boot() {
    document.body.classList.add("pincabos-dof-pro");
    addHero();
    enhanceImportCard();
    hideWhatIsThisPageCard();
    labelSections();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
