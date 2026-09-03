"use strict";

/*
 * PINCABOS_LOBBY_AV_BROWSER_GUARD_V4
 *
 * Cabinet-only WebRTC guard for the dedicated PinCabOS Lobby A/V Chromium.
 *
 * V4 keeps the SDP protections and local camera preview from V3, while
 * persisting the full-screen transparent PNG frame overlay used on the
 * cabinet Backglass. The local preview uses the exact MediaStream returned
 * to LiveKit; no second camera capture is opened.
 */
(() => {
  const marker = "[PinCabOS Lobby A/V]";
  const guardState = {
    version: "4.0.0",
    normalizedDescriptions: 0,
    generatedLocalDescriptions: 0,
    localPreviewMounts: 0,
    frameOverlayMounts: 0,
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
   * Legacy protection: if an older Lobby A/V page still tries to refresh the
   * Backglass screenshot, throttle it and freeze it while a call is active.
   * Newer pages use /b2s-state and no longer mirror the complete Backglass.
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

  /* PINCABOS_LOBBY_AV_FRAME_V1 */
  let frameOverlayImage = null;
  let frameOverlayTimer = null;

  function buildFramePng() {
    const width = Math.max(window.innerWidth || 0, 1);
    const height = Math.max(window.innerHeight || 0, 1);
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(width * dpr));
    canvas.height = Math.max(1, Math.round(height * dpr));

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return "";
    }

    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const inset = 10;
    const inner = 24;

    ctx.shadowColor = "rgba(255, 120, 0, 0.85)";
    ctx.shadowBlur = 28;
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(255, 130, 20, 0.98)";
    ctx.strokeRect(inset, inset, width - inset * 2, height - inset * 2);

    ctx.shadowBlur = 0;
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(255, 205, 120, 0.95)";
    ctx.strokeRect(inner, inner, width - inner * 2, height - inner * 2);

    const accent = 90;
    const gap = 18;
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(255, 120, 0, 0.95)";

    const lines = [
      [inset + gap, inset + gap, inset + gap + accent, inset + gap],
      [inset + gap, inset + gap, inset + gap, inset + gap + accent],
      [width - inset - gap, inset + gap, width - inset - gap - accent, inset + gap],
      [width - inset - gap, inset + gap, width - inset - gap, inset + gap + accent],
      [inset + gap, height - inset - gap, inset + gap + accent, height - inset - gap],
      [inset + gap, height - inset - gap, inset + gap, height - inset - gap - accent],
      [width - inset - gap, height - inset - gap, width - inset - gap - accent, height - inset - gap],
      [width - inset - gap, height - inset - gap, width - inset - gap, height - inset - gap - accent],
    ];

    for (const [x1, y1, x2, y2] of lines) {
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }

    return canvas.toDataURL("image/png");
  }

  function mountFrameOverlay() {
    if (!document.body) {
      window.setTimeout(mountFrameOverlay, 50);
      return;
    }

    if (!frameOverlayImage) {
      frameOverlayImage = document.createElement("img");
      frameOverlayImage.dataset.pincabosFrameOverlay = "1";
      frameOverlayImage.alt = "";
      Object.assign(frameOverlayImage.style, {
        position: "fixed",
        inset: "0",
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: "2147483647",
        objectFit: "fill",
        opacity: "1",
      });
      document.body.appendChild(frameOverlayImage);
      guardState.frameOverlayMounts += 1;
    } else if (!frameOverlayImage.isConnected) {
      document.body.appendChild(frameOverlayImage);
      guardState.frameOverlayMounts += 1;
    }

    const png = buildFramePng();
    if (png) {
      frameOverlayImage.src = png;
    }
  }

  function scheduleFrameOverlayRefresh() {
    if (frameOverlayTimer) {
      window.clearTimeout(frameOverlayTimer);
    }
    frameOverlayTimer = window.setTimeout(mountFrameOverlay, 60);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountFrameOverlay, { once: true });
  } else {
    mountFrameOverlay();
  }

  window.addEventListener("resize", scheduleFrameOverlayRefresh, { passive: true });
  window.setTimeout(mountFrameOverlay, 150);
  window.setTimeout(mountFrameOverlay, 600);
})();
