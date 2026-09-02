"use strict";

/*
 * PINCABOS_LOBBY_AV_BROWSER_GUARD_V1
 *
 * The cabinet Chromium instance is the media endpoint. This guard is loaded
 * only in the dedicated Lobby A/V profile and never on pincabos.cc.
 *
 * Chromium rejects a BUNDLE answer when the same payload type is described
 * with different fmtp parameters in different media sections. The observed
 * failure on the cabinet is VP8/PT 96 with x-google-start-bitrate present in
 * one section and absent in another. The hint is optional, so remove only
 * that hint before Chromium validates the SDP.
 */
(() => {
  const marker = "[PinCabOS Lobby A/V]";

  function normalizeSdp(sdp) {
    if (typeof sdp !== "string" || !sdp.includes("x-google-start-bitrate")) {
      return sdp;
    }

    return sdp.replace(
      /^a=fmtp:(\d+)\s+([^\r\n]*)$/gm,
      (line, payloadType, rawParameters) => {
        const parameters = String(rawParameters)
          .split(";")
          .map((value) => value.trim())
          .filter(Boolean)
          .filter(
            (value) =>
              !/^x-google-start-bitrate\s*=/i.test(value),
          );

        if (!parameters.length) {
          return "";
        }
        return `a=fmtp:${payloadType} ${parameters.join(";")}`;
      },
    );
  }

  function wrapDescription(description) {
    if (!description || typeof description.sdp !== "string") {
      return description;
    }

    const sdp = normalizeSdp(description.sdp);
    if (sdp === description.sdp) {
      return description;
    }

    console.info(`${marker} SDP VP8 normalisé pour BUNDLE Chromium.`);
    return { type: description.type, sdp };
  }

  if (window.RTCPeerConnection) {
    const pc = window.RTCPeerConnection.prototype;

    const nativeSetRemoteDescription = pc.setRemoteDescription;
    pc.setRemoteDescription = function (description) {
      return nativeSetRemoteDescription.call(this, wrapDescription(description));
    };

    const nativeSetLocalDescription = pc.setLocalDescription;
    pc.setLocalDescription = function (description) {
      return nativeSetLocalDescription.call(this, wrapDescription(description));
    };
  }

  /*
   * Keep the real cabinet webcam lightweight. Preserve deviceId/facingMode
   * chosen by LiveKit, but cap capture to 640x360 @ 15 fps.
   */
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    const nativeGetUserMedia =
      navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);

    navigator.mediaDevices.getUserMedia = function (constraints) {
      if (!constraints || !constraints.video) {
        return nativeGetUserMedia(constraints);
      }

      const requested =
        typeof constraints.video === "object" && constraints.video
          ? { ...constraints.video }
          : {};

      const guarded = {
        ...constraints,
        video: {
          ...requested,
          width: { ideal: 640, max: 640 },
          height: { ideal: 360, max: 360 },
          frameRate: { ideal: 15, max: 15 },
        },
      };

      return nativeGetUserMedia(guarded);
    };
  }

  /*
   * The B2S JPEG is only a local preview, never the camera. While a real
   * A/V call is connected it is frozen, and while idle it is throttled to
   * one request every two seconds even though the legacy page timer runs
   * more often.
   */
  const imageSrc = Object.getOwnPropertyDescriptor(
    HTMLImageElement.prototype,
    "src",
  );
  let lastB2sPreview = 0;

  if (imageSrc && imageSrc.set && imageSrc.get) {
    Object.defineProperty(HTMLImageElement.prototype, "src", {
      configurable: imageSrc.configurable,
      enumerable: imageSrc.enumerable,
      get: imageSrc.get,
      set(value) {
        const text = String(value || "");
        if (
          this.id === "b2s" &&
          text.includes("/pincabos-link/api/lobby/b2s-preview")
        ) {
          const hangup = document.getElementById("hangup");
          const callConnected = Boolean(hangup && !hangup.disabled);
          const now = Date.now();

          if (callConnected || now - lastB2sPreview < 2000) {
            return;
          }
          lastB2sPreview = now;
        }

        imageSrc.set.call(this, value);
      },
    });
  }
})();
