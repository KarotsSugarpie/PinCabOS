/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  const hasActiveTask =
    document.body.dataset.taskActive === "1" ||
    document.querySelector("[data-task-active='1']");

  if (hasActiveTask) return;

  const ids = [
    "progressLog",
    "updateLog",
    "taskLog",
    "jobLog",
    "progressText",
    "progressStatus",
    "progressPercent"
  ];

  ids.forEach(function (id) {
    const el = document.getElementById(id);
    if (!el) return;

    if (id.toLowerCase().includes("percent")) {
      el.textContent = "0%";
    } else if (id.toLowerCase().includes("status")) {
      el.textContent = "En attente";
    } else {
      el.textContent = "";
    }
  });

  document.querySelectorAll("progress").forEach(function (el) {
    el.value = 0;
  });

  document.querySelectorAll(".progress-bar, .progress-fill, .bar-fill").forEach(function (el) {
    el.style.width = "0%";
    el.textContent = "0%";
  });

  document.querySelectorAll(".progress-log, .task-log, .update-log, pre.log").forEach(function (el) {
    el.textContent = "";
  });

  document.querySelectorAll(".card").forEach(function (card) {
    if (!card.textContent.includes("Progression")) return;

    card.innerHTML = card.innerHTML
      .replace(/Statut\s*:\s*complete/gi, "Statut : En attente")
      .replace(/Mises à jour terminée avec succès\./gi, "")
      .replace(/100%/g, "0%");
  });
});
