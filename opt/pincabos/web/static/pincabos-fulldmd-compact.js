/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  const path = window.location.pathname || "";
  const txt = document.body.innerText || "";

  const isFullDmd =
    path.includes("fulldmd") ||
    txt.includes("Calibration FullDMD") ||
    txt.includes("Écran FullDMD");

  if (!isFullDmd) return;

  document.body.classList.add("pincabos-fulldmd-page");

  document.querySelectorAll(".fulldmd-inline-fields, .fulldmd-inline-fields-final").forEach(function (el) {
    el.remove();
  });
});
