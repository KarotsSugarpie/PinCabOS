/* PinCabOS-File created by Karots Sugarpie */
document.addEventListener("DOMContentLoaded", function () {
  if (document.querySelector(".pincabos-support-footer-safe")) return;

  function buildFooter(ver) {
    ver = ver || {};
    const qrName = "pcbo_pay_qr_bbb5611b723f953dc3fad1e42e7dbd66fe9fa8d53de4293c.png";

    const footer = document.createElement("div");
    footer.className = "footer pincabos-support-footer-safe";

    footer.innerHTML =
      '<div class="pincabos-release-notes-safe">' +
        '<h2>Notes de version</h2>' +
        '<div class="pincabos-release-grid-safe">' +
          '<p><strong>Nom :</strong> ' + (ver.name || "PinCabOS") + '</p>' +
          '<p><strong>Version :</strong> ' + (ver.version || "Development") + '</p>' +
          '<p><strong>Build :</strong> ' + (ver.build || "dev") + '</p>' +
          '<p><strong>Canal :</strong> ' + (ver.channel || ver.update_channel || "") + '</p>' +
          '<p><strong>Codename :</strong> ' + (ver.codename || "") + '</p>' +
          '<p><strong>Auteur :</strong> ' + (ver.author || "Karots Sugarpie") + '</p>' +
          '<p><strong>Update :</strong> ' + (ver.update_channel || "") + '</p>' +
          '<p><strong>Site :</strong> pincabos.cc</p>' +
        '</div>' +
      '</div>' +

      '<div class="pincabos-footer-banner-safe">' +
        '<img src="/static/branding/TopBanner.png?v=footer" alt="PinCabOS">' +
      '</div>' +

      '<div class="pincabos-support-text-safe">' +
        '<h2>Soutenir PinCabOS</h2>' +
        '<p>Si vous aimez PinCabOS, vous pouvez me le montrer en offrant ce que vous voulez. Merci pour votre soutien.</p>' +
        '<div class="pincabos-paypal-form-safe">' +
          '<form action="https://www.paypal.com/ncp/payment/SE79XX45T2NBG" method="post" target="_blank">' +
            '<input class="pp-SE79XX45T2NBG-safe" type="submit" value="Acheter">' +
            '<img class="pincabos-paypal-cards-safe" src="https://www.paypalobjects.com/images/Debit_Credit_APM.svg" alt="cards">' +
            '<section class="pincabos-paypal-powered-safe">Optimisé par <img src="https://www.paypalobjects.com/paypal-ui/logos/svg/paypal-wordmark-color.svg" alt="paypal"></section>' +
          '</form>' +
        '</div>' +
      '</div>' +

      '<div class="pincabos-support-qr-safe">' +
        '<img src="/static/pincabos-assets/' + qrName + '" alt="QR Code PayPal PinCabOS">' +
        '<div class="pincabos-support-qr-label-safe">QR Code PayPal PinCabOS</div>' +
      '</div>';

    document.body.appendChild(footer);
  }

  fetch("/api/pincabos-version?t=" + Date.now())
    .then(function (r) { return r.ok ? r.json() : {}; })
    .then(function (ver) { buildFooter(ver); })
    .catch(function () { buildFooter({}); });
});
