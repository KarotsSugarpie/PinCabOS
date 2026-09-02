"use strict";

/*
 * PINCABOS_LOBBY_AV_BROWSER_GUARD_V3
 *
 * Cabinet-only WebRTC guard for the dedicated PinCabOS Lobby A/V Chromium.
 *
 * V3 keeps the SDP protections from V2 and adds an explicit local camera
 * preview sourced from the exact MediaStream returned to LiveKit. The local
 * tile therefore does not depend on a published/subscribed WebRTC track in
 * order to show the cabinet operator their own camera.
 */
(() => {
  const marker = "[PinCabOS Lobby A/V]";
  const guardState = {
    version: "3.0.0",
    normalizedDescriptions: 0,
    generatedLocalDescriptions: 0,
    localPreviewMounts: 0,
  };
  window.__PINCABOS_LOBBY_AV_GUARD__ = guardState;

  function normalizeSdp(sdp) {
    if (
      typeof sdp !== "string" ||
      !/x-google-(?:start|min|max)-bitrate/i.test(sdp)
    ) {
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

  let localPreviewStream = null;
  let localPreviewVideo = null;
  let localPreviewObserver = null;

  function localPreviewTrack() {
    if (!localPreviewStream) {
      return null;
    }
    return localPreviewStream.getVideoTracks()[0] || null;
  }

  function localPreviewActive() {
    const track = localPreviewTrack();
    return Boolean(
      track &&
        track.readyState === "live" &&
        track.enabled !== false &&
        track.muted !== true,
    );
  }

  function clearLocalPreview() {
    if (localPreviewVideo) {
      try {
        localPreviewVideo.pause();
      } catch (_error) {}
      localPreviewVideo.srcObject = null;
      localPreviewVideo.remove();
    }
    localPreviewVideo = null;
    localPreviewStream = null;
  }

  function mountLocalPreview() {
    if (!localPreviewActive()) {
      return;
    }

    const media = document.querySelector("#local .media");
    if (!media) {
      return;
    }

    if (!localPreviewVideo) {
      localPreviewVideo = document.createElement("video");
      localPreviewVideo.dataset.pincabosLocalPreview = "1";
      localPreviewVideo.autoplay = true;
      localPreviewVideo.muted = true;
      localPreviewVideo.playsInline = true;
      localPreviewVideo.setAttribute("aria-label", "Caméra locale PinCabOS");
    }

    if (localPreviewVideo.srcObject !== localPreviewStream) {
      localPreviewVideo.srcObject = localPreviewStream;
    }

    if (
      localPreviewVideo.parentElement !== media ||
      media.childNodes.length !== 1
    ) {
      media.replaceChildren(localPreviewVideo);
      guardState.localPreviewMounts += 1;
    }

    localPreviewVideo.play().catch(() => {});
  }

  function watchLocalPreview() {
    if (localPreviewObserver) {
      return;
    }

    const media = document.querySelector("#local .media");
    if (!media) {
      window.setTimeout(watchLocalPreview, 50);
      return;
    }

    localPreviewObserver = new MutationObserver(() => {
      if (localPreviewActive()) {
        queueMicrotask(mountLocalPreview);
      }
    });
    localPreviewObserver.observe(media, { childList: true, subtree: false });
  }

  function installLocalPreview(stream) {
    const track = stream && stream.getVideoTracks
      ? stream.getVideoTracks()[0]
      : null;
    if (!track) {
      return;
    }

    localPreviewStream = stream;
    track.addEventListener("ended", clearLocalPreview, { once: true });
    track.addEventListener("unmute", mountLocalPreview);
    track.addEventListener("mute", () => {
      window.setTimeout(() => {
        if (!localPreviewActive() && localPreviewVideo) {
          localPreviewVideo.remove();
        }
      }, 0);
    });

    watchLocalPreview();
    mountLocalPreview();
    window.setTimeout(mountLocalPreview, 100);
    window.setTimeout(mountLocalPreview, 500);
  }

  /*
   * Keep the real cabinet webcam lightweight and use that exact capture as
   * the local preview. No second camera capture is opened.
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

      return nativeGetUserMedia(guarded).then((stream) => {
        installLocalPreview(stream);
        return stream;
      });
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
