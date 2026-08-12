/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  const lang = document.querySelector(".top-language-widget");
  const brandLeft = document.querySelector(".brand-left");
  const headerLogo = document.querySelector(".brand-left img.logo, .brand-left img[src*='pincabos-logo']");
  const nav = document.querySelector(".nav");

  // 1. Déplacer la langue à la place du logo dans l'entête.
  if (lang && brandLeft) {
    brandLeft.innerHTML = "";
    brandLeft.appendChild(lang);
    brandLeft.classList.add("brand-language-slot");
  }

  // 2. Supprimer tout logo restant dans l'entête.
  if (headerLogo && headerLogo.parentNode) {
    headerLogo.remove();
  }

  document.querySelectorAll(".brand-title, .brand-subtitle, .pincabos-header-subtitle").forEach(function (el) {
    el.remove();
  });

  // 3. Corriger le highlight Dashboard / Tableau de bord.
  if (window.location.pathname === "/" || window.location.pathname === "") {
    document.querySelectorAll(".pincabos-nav a").forEach(function (a) {
      if (a.getAttribute("href") === "/") {
        a.classList.remove("secondary");
        a.classList.add("active");
      } else {
        a.classList.remove("active");
        if (!a.classList.contains("secondary")) {
          a.classList.add("secondary");
        }
      }
    });
  }

  // 4. Ajouter le logo dans la carte Système du dashboard.
  const pageText = document.body.innerText || "";
  const isDashboard = pageText.includes("Hostname :") && pageText.includes("Utilisation") && pageText.includes("Chemins essentiels");

  if (isDashboard) {
    const systemCard = Array.from(document.querySelectorAll(".card")).find(function (card) {
      const t = card.innerText || "";
      return t.includes("Système") && t.includes("Hostname :") && t.includes("IP :");
    });

    if (systemCard && !systemCard.querySelector(".dashboard-system-logo")) {
      const logo = document.createElement("img");
      logo.src = "/static/pincabos-logo.png";
      logo.alt = "PinCabOS Logo";
      logo.className = "dashboard-system-logo";

      const content = document.createElement("div");
      content.className = "dashboard-system-text";

      while (systemCard.firstChild) {
        content.appendChild(systemCard.firstChild);
      }

      systemCard.classList.add("dashboard-system-card");
      systemCard.appendChild(logo);
      systemCard.appendChild(content);
    }
  }
});
