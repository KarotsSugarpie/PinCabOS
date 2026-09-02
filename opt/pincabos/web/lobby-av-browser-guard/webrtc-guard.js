"use strict";

/*
 * PINCABOS_LOBBY_AV_BROWSER_GUARD_V2
 *
 * The cabinet Chromium instance is the media endpoint. This guard is loaded
 * only in the dedicated Lobby A/V profile and never on pincabos.cc.
 *
 * Chromium rejects a BUNDLE description when the same payload type is
 * described with different fmtp parameters in different media sections.
 * The cabinet reproduced this with VP8/PT 96 and x-google-start-bitrate.
 * Those x-google bitrate fields are optional encoder hints, so remove them
 * before Chromium validates local or remote SDP.
 *
 * Important: LiveKit may call setLocalDescription() with no argument. In that
 * mode Chromium generates the offer/answer internally, which bypassed the V1
 * wrapper. V2 mirrors the browser's automatic offer/answer choice, normalizes
 * the generated SDP, and then calls the native setLocalDescription().
 */
(() => {
  const marker = "[PinCabOS Lobby A/V]";
  const guardState = {
    version: "2.0.0",
    normalizedDescriptions: 0,
    generatedLocalDescriptions: 0,
  };
  window.__PINCABOS_LOBBY_AV_GUARD__ = guardState;

  function normalizeSdp(sdp) {
    if (typeof sdp !== "string" || !/x-google-(?:start|min|max)-bitrate/i.test(sdp)) {
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
              !/^x-google-(?:start|min|max)-bitrate\s*=/i.test(value),
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

    guardState.normalizedDescriptions += 1;
    console.info(`${marker} SDP normalisé pour BUNDLE Chromium.`);
    return { type: description.type, sdp };
  }

  const patchedPrototypes = new WeakSet();

  function installPeerConnectionGuard(PeerConnection) {
    if (!PeerConnection || !PeerConnection.prototype) {
      return;
    }

    const pc = PeerConnection.prototype;
    if (patchedPrototypes.has(pc)) {
      return;
    }
    patchedPrototypes.add(pc);

    const nativeCreateOffer = pc.createOffer;
    const nativeCreateAnswer = pc.createAnswer;
    const nativeSetRemoteDescription = pc.setRemoteDescription;
    const nativeSetLocalDescription = pc.setLocalDescription;

    if (
      typeof nativeCreateOffer !== "function" ||
      typeof nativeCreateAnswer !== "function" ||
      typeof nativeSetRemoteDescription !== "function" ||
      typeof nativeSetLocalDescription !== "function"
    ) {
      return;
    }

    pc.createOffer = function (options) {
      return nativeCreateOffer.call(this, options).then(wrapDescription);
    };

    pc.createAnswer = function (options) {
      return nativeCreateAnswer.call(this, options).then(wrapDescription);
    };

    pc.setRemoteDescription = function (description) {
      return nativeSetRemoteDescription.call(this, wrapDescription(description));
    };

    pc.setLocalDescription = function (description) {
      if (description !== undefined && description !== null) {
        return nativeSetLocalDescription.call(this, wrapDescription(description));
      }

      /*
       * Browser/WebRTC automatic mode:
       * - have-remote-offer / have-local-pranswer => generate an answer
       * - otherwise => generate an offer
       *
       * Generate explicitly so the SDP can be normalized before native SLD.
       */
      const shouldAnswer =
        this.signalingState === "have-remote-offer" ||
        this.signalingState === "have-local-pranswer";
      const generator = shouldAnswer ? nativeCreateAnswer : nativeCreateOffer;

      guardState.generatedLocalDescriptions += 1;
      return generator
        .call(this)
        .then(wrapDescription)
        .then((generated) => nativeSetLocalDescription.call(this, generated));
    };
  }

  installPeerConnectionGuard(window.RTCPeerConnection);
  if (
    window.webkitRTCPeerConnection &&
    window.webkitRTCPeerConnection !== window.RTCPeerConnection
  ) {
    installPeerConnectionGuard(window.webkitRTCPeerConnection);
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
