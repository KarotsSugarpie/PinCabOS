(function () {
  "use strict";

  if (window.__pcoExplorerBundleLoaderV1) return;
  window.__pcoExplorerBundleLoaderV1 = true;

  function load(src, done) {
    var script = document.createElement("script");
    script.src = src;
    script.async = false;
    script.onload = function () { if (done) done(); };
    script.onerror = function () {
      console.error("PinCabOS Explorer: impossible de charger " + src);
    };
    document.head.appendChild(script);
  }

  load("/static/pincabos-explorer-table-test-core-v1.js?v=1", function () {
    load("/static/pincabos-explorer-analysis-report-v1.js?v=1");
  });
})();
