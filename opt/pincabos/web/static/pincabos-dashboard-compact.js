/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  const txt = document.body.innerText || "";

  const looksLikeDashboard =
    txt.includes("Hostname :") &&
    txt.includes("Utilisation") &&
    txt.includes("Chemins essentiels");

  if (!looksLikeDashboard) return;

  document.body.classList.add("dashboard-compact");

  document.querySelectorAll(".card").forEach(function (card) {
    const t = card.innerText || "";

    if (
      t.includes("Chemins essentiels") ||
      t.includes("Disques") ||
      t.includes("GPU / Drivers") ||
      t.includes("OpenGL / Mesa") ||
      t.includes("Vulkan") ||
      t.includes("Services")
    ) {
      card.classList.add("dashboard-scroll");
    }
  });
});
