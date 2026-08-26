/* PINCABOS_SMART_IMPORT_REAL_QUEUE_V1 */
(function () {
  "use strict";

  function initializeSmartImportQueue() {
    var finalInput =
      document.getElementById("pcoSmartImportPackages");

    var expectedInput =
      document.getElementById("pcoSmartImportExpectedCount");

    var addButton =
      document.getElementById("pcoSmartImportAddFiles");

    var clearButton =
      document.getElementById("pcoSmartImportClearFiles");

    var countLabel =
      document.getElementById("pcoSmartImportFileCount");

    var list =
      document.getElementById("pcoSmartImportFileList");

    var message =
      document.getElementById("pcoSmartImportQueueMessage");

    if (
      !finalInput ||
      !expectedInput ||
      !addButton ||
      !clearButton ||
      !countLabel ||
      !list ||
      !message
    ) {
      return;
    }

    if (finalInput.dataset.queueReady === "1") {
      return;
    }

    if (typeof DataTransfer === "undefined") {
      message.hidden = false;
      message.dataset.kind = "error";
      message.textContent =
        "Ce navigateur ne permet pas de conserver plusieurs sélections.";
      return;
    }

    finalInput.dataset.queueReady = "1";

    var form = finalInput.closest("form");
    var queue = [];

    /* PINCABOS_SMART_IMPORT_CLIENT_MTIME_V1 */
    var modifiedTimesInput = null;

    if (form) {
      modifiedTimesInput =
        form.querySelector(
          'input[name="file_mtimes_json"]'
        );

      if (!modifiedTimesInput) {
        modifiedTimesInput =
          document.createElement("input");

        modifiedTimesInput.type = "hidden";
        modifiedTimesInput.name =
          "file_mtimes_json";

        form.appendChild(
          modifiedTimesInput
        );
      }
    }

    var submitButton = form
      ? form.querySelector(
          'button[type="submit"], input[type="submit"]'
        )
      : null;

    var originalSubmitLabel = "";

    if (submitButton) {
      originalSubmitLabel =
        submitButton.tagName === "INPUT"
          ? submitButton.value
          : submitButton.textContent.trim();
    }

    function fileKey(file) {
      return [
        file.name,
        String(file.size),
        String(file.lastModified || 0)
      ].join("\u0001");
    }

    function extensionOf(name) {
      var lower = name.toLowerCase();

      if (lower.endsWith(".directb2s")) {
        return "B2S";
      }

      var position = name.lastIndexOf(".");

      if (
        position <= 0 ||
        position === name.length - 1
      ) {
        return "FILE";
      }

      return name.slice(position + 1).toUpperCase();
    }

    function formatBytes(bytes) {
      if (!Number.isFinite(bytes) || bytes <= 0) {
        return "0 octet";
      }

      var units = ["octets", "Ko", "Mo", "Go", "To"];

      var index = Math.min(
        Math.floor(Math.log(bytes) / Math.log(1024)),
        units.length - 1
      );

      var value = bytes / Math.pow(1024, index);

      var decimals =
        index === 0 || value >= 100
          ? 0
          : value >= 10
            ? 1
            : 2;

      return (
        value.toFixed(decimals) +
        " " +
        units[index]
      );
    }

    function showMessage(text, kind) {
      message.textContent = text;
      message.dataset.kind = kind || "info";
      message.hidden = !text;
    }

    function synchronizeFinalInput() {
      var transfer = new DataTransfer();

      queue.forEach(function (file) {
        transfer.items.add(file);
      });

      finalInput.files = transfer.files;
      expectedInput.value = String(queue.length);

      if (modifiedTimesInput) {
        modifiedTimesInput.value =
          JSON.stringify(
            queue.map(function (file) {
              return Number(
                file.lastModified || 0
              );
            })
          );
      }
    }

    function updateSubmitButton() {
      if (!submitButton) {
        return;
      }

      var label =
        queue.length === 0
          ? originalSubmitLabel
          : "Analyser " +
            queue.length +
            (queue.length === 1
              ? " fichier"
              : " fichiers");

      if (submitButton.tagName === "INPUT") {
        submitButton.value = label;
      } else {
        submitButton.textContent = label;
      }
    }

    function removeFile(key) {
      queue = queue.filter(function (file) {
        return fileKey(file) !== key;
      });

      synchronizeFinalInput();
      render();

      showMessage(
        "Fichier retiré de la sélection.",
        "info"
      );
    }

    function createFileRow(file) {
      var row = document.createElement("div");
      row.className = "pco-smart-import-file-row";

      var type = document.createElement("span");
      type.className = "pco-smart-import-file-type";
      type.textContent = extensionOf(file.name);

      var info = document.createElement("div");
      info.className = "pco-smart-import-file-info";

      var name = document.createElement("strong");
      name.textContent = file.name;
      name.title = file.name;

      var metadata = document.createElement("small");
      metadata.textContent =
        formatBytes(file.size) +
        (file.type ? " · " + file.type : "");

      info.appendChild(name);
      info.appendChild(metadata);

      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "pco-smart-import-file-remove";
      remove.textContent = "Retirer";

      remove.setAttribute(
        "aria-label",
        "Retirer " + file.name
      );

      remove.addEventListener("click", function () {
        removeFile(fileKey(file));
      });

      row.appendChild(type);
      row.appendChild(info);
      row.appendChild(remove);

      return row;
    }

    function render() {
      list.replaceChildren();

      countLabel.textContent =
        queue.length +
        (queue.length === 1
          ? " fichier"
          : " fichiers");

      clearButton.disabled = queue.length === 0;

      addButton.textContent =
        queue.length === 0
          ? "📂 Parcourir / Ajouter des fichiers"
          : "📂 Ajouter d’autres fichiers";

      updateSubmitButton();

      if (queue.length === 0) {
        var empty = document.createElement("div");
        empty.className = "pco-smart-import-queue-empty";
        empty.textContent =
          "Aucun fichier sélectionné.";

        list.appendChild(empty);
        return;
      }

      var fragment = document.createDocumentFragment();

      queue.forEach(function (file) {
        fragment.appendChild(createFileRow(file));
      });

      list.appendChild(fragment);
    }

    function addFiles(files) {
      var existingKeys = new Set(
        queue.map(function (file) {
          return fileKey(file);
        })
      );

      var added = 0;
      var duplicates = 0;

      Array.from(files || []).forEach(function (file) {
        var key = fileKey(file);

        if (existingKeys.has(key)) {
          duplicates += 1;
          return;
        }

        existingKeys.add(key);
        queue.push(file);
        added += 1;
      });

      synchronizeFinalInput();
      render();

      if (added > 0) {
        var text =
          added +
          (added === 1
            ? " fichier ajouté. "
            : " fichiers ajoutés. ");

        text +=
          queue.length +
          (queue.length === 1
            ? " fichier reste affiché dans la carte."
            : " fichiers restent affichés dans la carte.");

        if (duplicates > 0) {
          text +=
            " " +
            duplicates +
            (duplicates === 1
              ? " doublon ignoré."
              : " doublons ignorés.");
        }

        showMessage(text, "success");
        return;
      }

      if (duplicates > 0) {
        showMessage(
          duplicates === 1
            ? "Ce fichier était déjà dans la liste."
            : "Ces fichiers étaient déjà dans la liste.",
          "info"
        );
      }
    }

    function openPicker() {
      var picker = document.createElement("input");

      picker.type = "file";
      picker.multiple = true;
      picker.hidden = true;
      picker.tabIndex = -1;

      document.body.appendChild(picker);

      picker.addEventListener(
        "change",
        function () {
          addFiles(picker.files);
          picker.remove();
        },
        { once: true }
      );

      picker.addEventListener(
        "cancel",
        function () {
          picker.remove();
        },
        { once: true }
      );

      picker.click();
    }

    addButton.addEventListener(
      "click",
      openPicker
    );

    clearButton.addEventListener(
      "click",
      function () {
        queue = [];

        synchronizeFinalInput();
        render();

        showMessage(
          "La liste complète a été vidée.",
          "info"
        );
      }
    );

    if (form) {
      form.addEventListener(
        "submit",
        function (event) {
          synchronizeFinalInput();

          if (queue.length === 0) {
            event.preventDefault();

            showMessage(
              "Ajoutez au moins un fichier avant l’analyse.",
              "error"
            );

            return;
          }

          if (finalInput.files.length !== queue.length) {
            event.preventDefault();

            showMessage(
              "Le nombre de fichiers attachés ne correspond pas " +
              "au nombre affiché.",
              "error"
            );

            return;
          }

          showMessage(
            queue.length +
            (queue.length === 1
              ? " fichier est envoyé à Smart Import."
              : " fichiers sont envoyés à Smart Import."),
            "success"
          );
        },
        true
      );
    }

    synchronizeFinalInput();
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initializeSmartImportQueue,
      { once: true }
    );
  } else {
    initializeSmartImportQueue();
  }
})();
