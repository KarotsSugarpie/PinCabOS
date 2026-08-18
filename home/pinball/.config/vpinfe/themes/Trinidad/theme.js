let windowName = "";
let currentTableIndex = 0;
let renderedWheelCenterIndex = null;
let vpinPlayRatingToken = 0;
let attractIdleTimer = null;
let attractAdvanceTimer = null;
let attractModeActive = false;
let attractSuspended = false;
let wheelMode = "tables";
let collectionEntries = [];
let currentCollectionIndex = 0;

const ATTRACT_IDLE_MS = 60000;
const ATTRACT_STEP_MS = 7000;

const vpin = new VPinFECore();
vpin.init();
window.vpin = vpin;

vpin.ready.then(async () => {
    console.log("VPinFECore is fully initialized");
    windowName = await vpin.call("get_my_window_name");
    document.body.classList.add(`window-${windowName}`);

    const themeConfig = await vpin.call("get_theme_config") || {};
    const startInCollectionSelection = Boolean(themeConfig?.startCollectionSelection);

    if (windowName === "table") {
        vpin.enableCoreAudio(true);
        vpin.setAudioOptions({
            maxVolume: 0.8,
            fadeDuration: 350,
            loop: true
        });
    }

    applyMenuRotation();
    if (windowName === "table") {
        vpin.registerInputHandler(handleInput);
        setupAttractMode();
        markUserActivity();
    }

    if (windowName === "table" && startInCollectionSelection) {
        await enterCollectionMode();
        if (!isCollectionMode()) {
            setImage();
        }
    } else {
        setImage();
    }
});

function ensureMenuOverlayContainer() {
    const overlayRoot = document.getElementById("overlay-root");
    if (!overlayRoot) {
        return null;
    }

    let container = document.getElementById("menu-overlay-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "menu-overlay-container";
        overlayRoot.appendChild(container);
    }

    Array.from(overlayRoot.children).forEach((child) => {
        if (child !== container) {
            container.appendChild(child);
        }
    });

    if (!overlayRoot._menuObserver) {
        const observer = new MutationObserver(() => {
            Array.from(overlayRoot.children).forEach((child) => {
                if (child !== container) {
                    container.appendChild(child);
                }
            });
        });
        observer.observe(overlayRoot, { childList: true });
        overlayRoot._menuObserver = observer;
    }

    return container;
}

function applyMenuRotation() {
    const rotation = Number(vpin.tableRotation) || 0;
    const normalizedRotation = ((rotation % 360) + 360) % 360;
    const menuRotation =
        normalizedRotation === 90 ? 90 :
        normalizedRotation === 180 ? 90 :
        normalizedRotation === 270 ? 270 :
        -90;
    const root = document.documentElement;
    root.style.setProperty("--menu-rotation", "0deg");

    const contentSwapAxes = Math.abs(rotation) === 90 || Math.abs(rotation) === 270;
    const menuSwapAxes = Math.abs(menuRotation) === 90 || Math.abs(menuRotation) === 270;
    root.style.setProperty("--menu-width", menuSwapAxes ? "84vh" : "84vw");
    root.style.setProperty("--menu-height", menuSwapAxes ? "84vw" : "84vh");
    root.style.setProperty("--collection-menu-width", menuSwapAxes ? "50vh" : "50vw");
    root.style.setProperty("--collection-menu-height", menuSwapAxes ? "50vw" : "50vh");

    if (windowName !== "table") {
        return;
    }

    const rotatedWidth = contentSwapAxes ? "100vh" : "100vw";
    const rotatedHeight = contentSwapAxes ? "100vw" : "100vh";

    [document.getElementById("fadeContainer"), document.getElementById("remote-launch-overlay")]
        .filter(Boolean)
        .forEach((element) => {
            element.style.position = "absolute";
            element.style.top = "50%";
            element.style.left = "50%";
            element.style.width = rotatedWidth;
            element.style.height = rotatedHeight;
            element.style.transformOrigin = "center center";
            element.style.transform = `translate(-50%, -50%) rotate(${rotation}deg)`;
        });

    const overlayRoot = document.getElementById("overlay-root");
    if (overlayRoot) {
        overlayRoot.style.position = "absolute";
        overlayRoot.style.top = "50%";
        overlayRoot.style.left = "50%";
        overlayRoot.style.width = rotatedWidth;
        overlayRoot.style.height = rotatedHeight;
        overlayRoot.style.transformOrigin = "center center";
        overlayRoot.style.transform = "translate(-50%, -50%)";
    }

    const overlay = ensureMenuOverlayContainer();
    if (overlay) {
        overlay.style.transformOrigin = "center center";
        overlay.style.transform = `rotate(${menuRotation}deg)`;
    }
}

function wrapIndex(index, length) {
    return (index + length) % length;
}

function clearAttractTimers() {
    if (attractIdleTimer) {
        window.clearTimeout(attractIdleTimer);
        attractIdleTimer = null;
    }
    if (attractAdvanceTimer) {
        window.clearTimeout(attractAdvanceTimer);
        attractAdvanceTimer = null;
    }
}

function stopAttractMode() {
    attractModeActive = false;
    clearAttractTimers();
}

function isCollectionMode() {
    return wheelMode === "collections";
}

function shouldPauseAttractMode() {
    return (
        windowName !== "table" ||
        attractSuspended ||
        isCollectionMode() ||
        !vpin.tableData ||
        vpin.tableData.length < 2 ||
        vpin.menuUP ||
        vpin.collectionMenuUP ||
        vpin.tutorialUP ||
        document.getElementById("remote-launch-overlay")?.style.display === "flex"
    );
}

function queueNextAttractAdvance() {
    if (!attractModeActive) {
        return;
    }

    attractAdvanceTimer = window.setTimeout(() => {
        runAttractAdvance();
    }, ATTRACT_STEP_MS);
}

function runAttractAdvance() {
    if (!attractModeActive || shouldPauseAttractMode()) {
        stopAttractMode();
        markUserActivity(false);
        return;
    }

    const nextIndex = wrapIndex(currentTableIndex + 1, vpin.tableData.length);
    if (nextIndex !== currentTableIndex) {
        currentTableIndex = nextIndex;
        setImage();
        vpin.sendMessageToAllWindows({
            type: "TableIndexUpdate",
            index: currentTableIndex
        });
    }

    queueNextAttractAdvance();
}

function startAttractMode() {
    if (shouldPauseAttractMode()) {
        markUserActivity(false);
        return;
    }

    attractModeActive = true;
    queueNextAttractAdvance();
}

function markUserActivity(stopAttract = true) {
    if (windowName !== "table") {
        return;
    }
    if (attractSuspended) {
        clearAttractTimers();
        return;
    }

    clearAttractTimers();
    if (stopAttract) {
        stopAttractMode();
    }

    attractIdleTimer = window.setTimeout(() => {
        startAttractMode();
    }, ATTRACT_IDLE_MS);
}

function setupAttractMode() {
    ["mousemove", "mousedown", "touchstart", "wheel", "keydown"].forEach((eventName) => {
        window.addEventListener(eventName, () => {
            markUserActivity();
        }, { passive: true });
    });
}

function suspendAttractMode() {
    attractSuspended = true;
    stopAttractMode();
}

function resumeAttractModeIdleCountdown() {
    attractSuspended = false;
    markUserActivity(false);
}

async function fadeOut() {
    const container = document.getElementById("fadeContainer");

    return new Promise((resolve) => {
        container.addEventListener("transitionend", (event) => {
            if (event.propertyName === "opacity") resolve();
        }, { once: true });

        container.style.opacity = 0;
    });
}

function fadeInScreen() {
    const container = document.getElementById("fadeContainer");
    container.style.opacity = 1;
}

function showRemoteLaunchOverlay(tableName) {
    const overlay = document.getElementById("remote-launch-overlay");
    const nameEl = document.getElementById("remote-launch-table-name");
    if (overlay && nameEl) {
        nameEl.textContent = tableName || "Unknown Table";
        overlay.style.display = "flex";
    }
}

function hideRemoteLaunchOverlay() {
    const overlay = document.getElementById("remote-launch-overlay");
    if (overlay) {
        overlay.style.display = "none";
    }
}

function showTableLoadingOverlay() {
    const overlay = document.getElementById("table-loading-overlay");
    if (overlay) {
        overlay.classList.add("is-visible");
        overlay.setAttribute("aria-hidden", "false");
    }
}

function hideTableLoadingOverlay() {
    const overlay = document.getElementById("table-loading-overlay");
    if (overlay) {
        overlay.classList.remove("is-visible");
        overlay.setAttribute("aria-hidden", "true");
    }
}

function hasUsableMedia(url) {
    return Boolean(url) && !String(url).includes("file_missing");
}

function getMediaContainer() {
    return document.getElementById("fsMediaContainer") || document.getElementById("fadeContainer");
}

function cleanupMediaElement(media) {
    if (!media) return;

    const actualMedia = media.matches?.("video, img") ? media : media.querySelector?.("video, img");
    if (!actualMedia) return;

    if (actualMedia.tagName === "VIDEO") {
        actualMedia.pause();
        actualMedia.removeAttribute("src");
        actualMedia.load();
    } else {
        actualMedia.removeAttribute("src");
    }
}

function renderFullscreenMedia(imageUrl, videoUrl = null) {
    const container = getMediaContainer();
    if (!container) return;

    const preferVideo = hasUsableMedia(videoUrl);
    const mediaTag = preferVideo ? "video" : "img";
    const mediaSrc = mediaTag === "video" ? videoUrl : (hasUsableMedia(imageUrl) ? imageUrl : "");

    if (windowName !== "table") {
        const activeFrame = container.querySelector(".media-frame.is-active");
        if (activeFrame && activeFrame.dataset.mediaTag === mediaTag && activeFrame.dataset.mediaSrc === mediaSrc) {
            return;
        }

        const legacyMedia = container.querySelector("#fsMedia:not(.media-frame #fsMedia)");
        if (legacyMedia) {
            cleanupMediaElement(legacyMedia);
            legacyMedia.remove();
        }

        const frame = document.createElement("div");
        frame.className = "media-frame";
        frame.dataset.mediaTag = mediaTag;
        frame.dataset.mediaSrc = mediaSrc;

        const media = document.createElement(mediaTag);
        media.id = "fsMedia";
        media.className = "fullscreen";

        if (mediaTag === "video") {
            media.autoplay = true;
            media.loop = true;
            media.muted = true;
            media.playsInline = true;
            media.poster = hasUsableMedia(imageUrl) ? imageUrl : "";
            media.src = videoUrl;
        } else {
            media.alt = "Fullscreen";
            media.src = mediaSrc;
        }

        frame.appendChild(media);
        container.appendChild(frame);

        const activateFrame = () => {
            requestAnimationFrame(() => {
                frame.classList.add("is-active");
                if (activeFrame) {
                    activeFrame.classList.remove("is-active");
                    window.setTimeout(() => {
                        cleanupMediaElement(activeFrame);
                        activeFrame.remove();
                    }, 340);
                }
            });
        };

        if (mediaTag === "video") {
            const onReady = () => {
                media.removeEventListener("loadeddata", onReady);
                media.removeEventListener("canplay", onReady);
                activateFrame();
            };

            media.addEventListener("loadeddata", onReady, { once: true });
            media.addEventListener("canplay", onReady, { once: true });
            media.load();
        } else if (media.complete) {
            activateFrame();
        } else {
            media.addEventListener("load", activateFrame, { once: true });
            media.addEventListener("error", activateFrame, { once: true });
        }
        return;
    }

    const activeFrame = container.querySelector(".media-frame.is-active");
    if (activeFrame && activeFrame.dataset.mediaTag === mediaTag && activeFrame.dataset.mediaSrc === mediaSrc) {
        return;
    }

    const frame = document.createElement("div");
    frame.className = "media-frame";
    frame.dataset.mediaTag = mediaTag;
    frame.dataset.mediaSrc = mediaSrc;

    const media = document.createElement(mediaTag);
    media.id = "fsMedia";
    media.className = "fullscreen";

    if (mediaTag === "video") {
        media.autoplay = true;
        media.loop = true;
        media.muted = true;
        media.playsInline = true;
        media.poster = hasUsableMedia(imageUrl) ? imageUrl : "";
        media.src = videoUrl;
    } else {
        media.alt = "Fullscreen";
        media.src = mediaSrc;
    }

    frame.appendChild(media);
    container.appendChild(frame);

    const activateFrame = () => {
        requestAnimationFrame(() => {
            frame.classList.add("is-active");
            if (activeFrame) {
                activeFrame.classList.remove("is-active");
                window.setTimeout(() => {
                    cleanupMediaElement(activeFrame);
                    activeFrame.remove();
                }, 260);
            }
        });
    };

    if (mediaTag === "video") {
        const onReady = () => {
            media.removeEventListener("loadeddata", onReady);
            media.removeEventListener("canplay", onReady);
            activateFrame();
        };

        media.addEventListener("loadeddata", onReady, { once: true });
        media.addEventListener("canplay", onReady, { once: true });
        media.load();
    } else if (media.complete) {
        activateFrame();
    } else {
        media.addEventListener("load", activateFrame, { once: true });
        media.addEventListener("error", activateFrame, { once: true });
    }
}

function getDisplayData(index) {
    const table = vpin.getTableMeta(index);
    const info = table?.meta?.Info || {};
    const user = table?.meta?.User || {};
    const vpx = table?.meta?.VPXFile || {};

    const title = info.Title || vpx.filename || table?.tableDirName || "Unknown Table";
    const manufacturer = info.Manufacturer || vpx.manufacturer || "Unknown";
    const year = info.Year || vpx.year || "Unknown";
    const type = info.Type || vpx.type || "Pinball";
    const filename = vpx.filename || table?.tableDirName || "No table file";

    return {
        title,
        authors: formatAuthors(info.Authors),
        manufacturer: String(manufacturer),
        year: String(year),
        type: String(type),
        ratingStars: formatRatingStars(coalesce(user.Rating, user.rating, 0)),
        runtimeText: formatRuntime(coalesce(user.RunTime, user.runtime, user.Runtime, 0)),
        startCountText: formatStartCount(coalesce(user.StartCount, user.startcount, user.Startcount, 0)),
        filename: String(filename),
        wheelUrl: vpin.getImageURL(index, "wheel")
    };
}

function getCollectionDisplayData(index) {
    const collection = collectionEntries[index] || {};
    const tableCount = Number(collection.table_count);
    const countText = Number.isFinite(tableCount)
        ? `${tableCount} ${tableCount === 1 ? "Table" : "Tables"}`
        : (collection.is_filter ? "Filter Collection" : "Collection");

    return {
        title: collection.name || "Collection",
        authors: countText,
        manufacturer: collection.type === "filter" ? "Filter" : "Collection",
        year: "",
        type: countText,
        ratingStars: "",
        runtimeText: "",
        startCountText: "",
        filename: collection.name || "",
        wheelUrl: collection.image_url || "",
        collection
    };
}

function coalesce(...values) {
    for (const value of values) {
        if (value !== undefined && value !== null && value !== "") {
            return value;
        }
    }
    return null;
}

function formatAuthors(authors) {
    if (Array.isArray(authors) && authors.length > 0) {
        return authors.join(", ");
    }
    if (typeof authors === "string" && authors.trim()) {
        return authors.trim();
    }
    return "Unknown Author";
}

function formatRatingStars(rating) {
    const numeric = Number(rating);
    const normalized = Number.isFinite(numeric) ? Math.max(0, Math.min(5, Math.round(numeric))) : 0;
    return `${"★".repeat(normalized)}${"☆".repeat(5 - normalized)}`;
}

function normalizeVPinPlayStars(cumulativeRating) {
    const numeric = Number(cumulativeRating);
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return 0;
    }
    if (numeric <= 5) {
        return Math.max(0, Math.min(5, numeric));
    }
    return Math.max(0, Math.min(5, numeric / 20));
}

function formatRuntime(runtimeValue) {
    const numeric = Number(runtimeValue);
    if (!Number.isFinite(numeric) || numeric <= 0) {
        return "0m";
    }

    const totalMinutes = Math.max(0, Math.floor(numeric));
    if (totalMinutes < 60) {
        return `${totalMinutes}m`;
    }

    const hours = totalMinutes / 60;
    if (Number.isInteger(hours)) {
        return `${hours}h`;
    }

    return `${hours.toFixed(1)}h`;
}

function formatStartCount(startCount) {
    const numeric = Number(startCount);
    if (!Number.isFinite(numeric) || numeric < 0) {
        return "0";
    }
    return String(Math.floor(numeric));
}

function updateVPinPlayRating(index) {
    const vpinPlayEl = document.getElementById("tableVPinPlayRating");
    if (!vpinPlayEl) {
        return;
    }

    const render = (payload) => {
        const cumulativeRating = payload?.cumulativeRating;
        const ratingCount = payload?.ratingCount ?? 0;
        const stars = normalizeVPinPlayStars(cumulativeRating);

        if (!Number.isFinite(stars) || stars <= 0 || ratingCount <= 0) {
            vpinPlayEl.textContent = "☆☆☆☆☆";
            vpinPlayEl.removeAttribute("title");
            return;
        }

        vpinPlayEl.textContent = formatRatingStars(stars);
        const scoreText = Number.isInteger(cumulativeRating) ? String(cumulativeRating) : Number(cumulativeRating).toFixed(1);
        const votesLabel = ratingCount === 1 ? "rating" : "ratings";
        vpinPlayEl.title = `${scoreText} cumulative VPinPlay rating from ${ratingCount} ${votesLabel}`;
    };

    render(vpin.getCachedVPinPlayRating(index));

    const token = ++vpinPlayRatingToken;
    vpin.getVPinPlayRating(index).then((payload) => {
        if (token !== vpinPlayRatingToken || index !== currentTableIndex) {
            return;
        }
        render(payload);
    }).catch(() => {
        if (token !== vpinPlayRatingToken || index !== currentTableIndex) {
            return;
        }
        render(null);
    });
}

function getWheelLayout(offset) {
    const normalized = offset / 3;
    const x = normalized * window.innerWidth * 0.43;
    const y = window.innerHeight * (0.165 - (1 - Math.cos(normalized * Math.PI / 2)) * 0.05);
    const rotation = -Math.abs(normalized) * 28;
    const scale = offset === 0 ? 1.18 : 1.02 - Math.abs(offset) * 0.08;
    const opacity = Math.max(0.18, 1 - Math.abs(offset) * 0.14);

    return {
        x,
        y,
        rotation,
        scale,
        opacity
    };
}

function applyWheelCardLayout(card, offset) {
    const layout = getWheelLayout(offset);

    card.style.setProperty("--arc-x", `${layout.x}px`);
    card.style.setProperty("--arc-y", `${layout.y}px`);
    card.style.setProperty("--arc-rotation", `${layout.rotation}deg`);
    card.style.setProperty("--arc-scale", String(layout.scale));
    card.style.setProperty("--arc-opacity", String(layout.opacity));
    card.dataset.offset = String(offset);
    card.classList.toggle("is-selected", offset === 0);
}

function updateTableMeta(data) {
    const panelEl = document.querySelector(".table-meta-panel");
    const titleEl = document.getElementById("tableTitle");
    const authorsEl = document.getElementById("tableAuthors");
    const manufacturerEl = document.getElementById("tableManufacturer");
    const yearEl = document.getElementById("tableYear");
    const typeEl = document.getElementById("tableType");
    const ratingEl = document.getElementById("tableRating");
    const runtimeEl = document.getElementById("tableRuntime");
    const startCountEl = document.getElementById("tableStartCount");

    if (!titleEl) {
        return;
    }

    titleEl.textContent = data.title;
    authorsEl.textContent = data.authors;
    manufacturerEl.textContent = data.manufacturer;
    yearEl.textContent = data.year;
    typeEl.textContent = data.type;
    ratingEl.textContent = data.ratingStars;
    runtimeEl.textContent = data.runtimeText;
    startCountEl.textContent = data.startCountText;
    updateVPinPlayRating(currentTableIndex);

    if (panelEl) {
        panelEl.classList.remove("is-entering");
        void panelEl.offsetWidth;
        panelEl.classList.add("is-entering");
        window.setTimeout(() => {
            panelEl.classList.remove("is-entering");
        }, 380);
    }
}

function updateCollectionMeta(data) {
    const panelEl = document.querySelector(".table-meta-panel");
    const titleEl = document.getElementById("tableTitle");
    const authorsEl = document.getElementById("tableAuthors");
    const manufacturerEl = document.getElementById("tableManufacturer");
    const yearEl = document.getElementById("tableYear");
    const typeEl = document.getElementById("tableType");
    const ratingEl = document.getElementById("tableRating");
    const vpinPlayEl = document.getElementById("tableVPinPlayRating");
    const runtimeEl = document.getElementById("tableRuntime");
    const startCountEl = document.getElementById("tableStartCount");

    if (!titleEl) {
        return;
    }

    titleEl.textContent = data.title;
    authorsEl.textContent = data.authors;
    manufacturerEl.textContent = data.manufacturer;
    yearEl.textContent = data.year;
    typeEl.textContent = data.type;
    ratingEl.textContent = "";
    if (vpinPlayEl) {
        vpinPlayEl.textContent = "";
        vpinPlayEl.removeAttribute("title");
    }
    runtimeEl.textContent = "";
    startCountEl.textContent = "";

    if (panelEl) {
        panelEl.classList.remove("is-entering");
        void panelEl.offsetWidth;
        panelEl.classList.add("is-entering");
        window.setTimeout(() => {
            panelEl.classList.remove("is-entering");
        }, 380);
    }
}

function buildWheelCard(index, offset) {
    const data = isCollectionMode() ? getCollectionDisplayData(index) : getDisplayData(index);
    const card = document.createElement("div");
    card.className = "wheel-card";
    card.dataset.itemIndex = String(index);
    card.dataset.tableIndex = String(index);
    card.classList.toggle("is-collection-card", isCollectionMode());

    const shell = document.createElement("div");
    shell.className = "wheel-card-shell";

    if (hasUsableMedia(data.wheelUrl)) {
        const img = document.createElement("img");
        img.src = data.wheelUrl;
        img.alt = data.title;
        shell.appendChild(img);
    } else {
        const fallback = document.createElement("div");
        fallback.className = "wheel-card-fallback";
        fallback.textContent = data.title;
        shell.appendChild(fallback);
    }

    card.appendChild(shell);
    applyWheelCardLayout(card, offset);

    return card;
}

function getCircularDelta(nextIndex, previousIndex, length) {
    let delta = nextIndex - previousIndex;

    if (delta > length / 2) {
        delta -= length;
    } else if (delta < -length / 2) {
        delta += length;
    }

    return delta;
}

function renderWheelCarousel(options = {}) {
    const carousel = document.getElementById("wheelCarousel");
    const itemCount = isCollectionMode() ? collectionEntries.length : (vpin.tableData?.length || 0);
    const currentIndex = isCollectionMode() ? currentCollectionIndex : currentTableIndex;
    if (!carousel || !itemCount) {
        return;
    }

    // PINCABOS_WHEEL_SMALL_LIBRARY_V1
    // Sept emplacements pour moins de sept tables, c'est le meme index
    // demande plusieurs fois : les cartes etant recensees par index, le
    // doublon en ecrasait un et l'emplacement orphelin restait fige. On borne
    // l'etalement a ce que la bibliotheque peut remplir — sans le forcer a
    // etre symetrique, sinon deux tables n'en afficheraient qu'une.
    const spanBack = Math.min(3, Math.floor((itemCount - 1) / 2));
    const spanForward = Math.min(3, itemCount - 1 - spanBack);
    const offsets = [];
    for (let offset = -spanBack; offset <= spanForward; offset += 1) {
        offsets.push(offset);
    }
    const nextVisible = offsets.map((offset) => ({
        offset,
        index: wrapIndex(currentIndex + offset, itemCount)
    }));

    if (options.animate === false || renderedWheelCenterIndex === null || !carousel.children.length) {
        const fragment = document.createDocumentFragment();

        nextVisible.forEach(({ index, offset }) => {
            fragment.appendChild(buildWheelCard(index, offset));
        });

        carousel.replaceChildren(fragment);
        renderedWheelCenterIndex = currentIndex;
        return;
    }

    const delta = getCircularDelta(currentIndex, renderedWheelCenterIndex, itemCount);
    if (Math.abs(delta) !== 1) {
        renderWheelCarousel({ animate: false });
        return;
    }

    const cardsByIndex = new Map(
        Array.from(carousel.children).map((card) => [Number(card.dataset.itemIndex), card])
    );
    const nextIndexSet = new Set(nextVisible.map(({ index }) => index));
    const enteringOffset = delta > 0 ? spanForward : -spanBack;
    const enteringStartOffset = delta > 0 ? spanForward + 1 : -(spanBack + 1);
    const exitingTargetOffset = delta > 0 ? -(spanBack + 1) : spanForward + 1;

    nextVisible.forEach(({ index, offset }) => {
        let card = cardsByIndex.get(index);

        if (!card) {
            card = buildWheelCard(index, enteringStartOffset);
            carousel.appendChild(card);
        }

        card.dataset.tableIndex = String(index);
        card.dataset.itemIndex = String(index);
        if (offset === enteringOffset && !cardsByIndex.has(index)) {
            applyWheelCardLayout(card, enteringStartOffset);
            requestAnimationFrame(() => applyWheelCardLayout(card, offset));
        } else {
            applyWheelCardLayout(card, offset);
        }
    });

    Array.from(carousel.children).forEach((card) => {
        const index = Number(card.dataset.itemIndex);
        if (nextIndexSet.has(index)) {
            return;
        }

        applyWheelCardLayout(card, exitingTargetOffset);
        window.setTimeout(() => {
            if (!nextIndexSet.has(Number(card.dataset.itemIndex)) && card.parentNode === carousel) {
                card.remove();
            }
        }, 260);
    });

    renderedWheelCenterIndex = currentIndex;
}

async function enterCollectionMode() {
    if (windowName !== "table") {
        return;
    }

    stopAttractMode();
    try {
        const metadata = await vpin.call("get_collections_metadata");
        collectionEntries = Array.isArray(metadata) ? metadata.filter((entry) => entry && entry.name) : [];
    } catch (error) {
        vpin.call("console_out", `Unable to load collections: ${error.message || error}`);
        collectionEntries = [];
    }

    if (!collectionEntries.length) {
        return;
    }

    wheelMode = "collections";
    currentCollectionIndex = 0;
    renderedWheelCenterIndex = null;
    document.body.classList.add("collection-wheel-mode");
    setImage();
    renderWheelCarousel({ animate: false });
}

async function selectCurrentCollection() {
    const collection = collectionEntries[currentCollectionIndex];
    if (!collection?.name) {
        return;
    }

    wheelMode = "tables";
    document.body.classList.remove("collection-wheel-mode");
    stopAttractMode();
    await vpin.call("set_tables_by_collection", collection.name);
    await vpin.getTableData();
    currentTableIndex = 0;
    renderedWheelCenterIndex = null;
    setImage();
    vpin.sendMessageToAllWindows({
        type: "TableDataChange",
        index: currentTableIndex,
        collection: collection.name
    });
    markUserActivity(false);
}

function leaveCollectionMode() {
    wheelMode = "tables";
    document.body.classList.remove("collection-wheel-mode");
    renderedWheelCenterIndex = null;
    setImage();
    markUserActivity(false);
}

async function receiveEvent(message) {
    vpin.call("console_out", message);
    await vpin.handleEvent(message);

    if (message.type === "TableIndexUpdate") {
        if (isCollectionMode()) {
            leaveCollectionMode();
        }
        currentTableIndex = message.index;
        setImage();
        if (!attractModeActive) {
            markUserActivity(false);
        }
    } else if (message.type === "TableLaunching") {
        suspendAttractMode();
        showTableLoadingOverlay();
        if (windowName === "table") {
            vpin.stopTableAudio();
        }
        await fadeOut();
    } else if (message.type === "TableRunning") {
        hideTableLoadingOverlay();
    } else if (message.type === "TableLaunchComplete") {
        hideTableLoadingOverlay();
        fadeInScreen();
        if (windowName === "table") {
            vpin.playTableAudio(currentTableIndex);
            resumeAttractModeIdleCountdown();
        }
    } else if (message.type === "RemoteLaunching") {
        showRemoteLaunchOverlay(message.table_name);
        suspendAttractMode();
        if (windowName === "table") {
            vpin.stopTableAudio();
        }
        await fadeOut();
    } else if (message.type === "RemoteLaunchComplete") {
        hideTableLoadingOverlay();
        hideRemoteLaunchOverlay();
        fadeInScreen();
        if (windowName === "table") {
            vpin.playTableAudio(currentTableIndex);
            resumeAttractModeIdleCountdown();
        }
    } else if (message.type === "TableDataChange") {
        if (isCollectionMode()) {
            leaveCollectionMode();
        }
        currentTableIndex = message.index;
        setImage();
        if (!attractModeActive) {
            markUserActivity(false);
        }
    }
}

window.receiveEvent = receiveEvent;

async function handleInput(input) {
    markUserActivity();

    switch (input) {
    case "joyleft":
        if (isCollectionMode()) {
            currentCollectionIndex = wrapIndex(currentCollectionIndex - 1, collectionEntries.length);
            updateCollectionMeta(getCollectionDisplayData(currentCollectionIndex));
            renderWheelCarousel();
            break;
        }
        currentTableIndex = wrapIndex(currentTableIndex - 1, vpin.tableData.length);
        setImage();
        vpin.sendMessageToAllWindows({
            type: "TableIndexUpdate",
            index: currentTableIndex
        });
        break;
    case "joyright":
        if (isCollectionMode()) {
            currentCollectionIndex = wrapIndex(currentCollectionIndex + 1, collectionEntries.length);
            updateCollectionMeta(getCollectionDisplayData(currentCollectionIndex));
            renderWheelCarousel();
            break;
        }
        currentTableIndex = wrapIndex(currentTableIndex + 1, vpin.tableData.length);
        setImage();
        vpin.sendMessageToAllWindows({
            type: "TableIndexUpdate",
            index: currentTableIndex
        });
        break;
    case "joyselect":
        if (isCollectionMode()) {
            await selectCurrentCollection();
            break;
        }
        suspendAttractMode();
        vpin.sendMessageToAllWindows({ type: "TableLaunching" });
        showTableLoadingOverlay();
        vpin.stopTableAudio({ immediate: true });
        await fadeOut();
        await vpin.launchTable(currentTableIndex);
        vpin.call("console_out", "FADEOUT done");
        break;
    case "joyback":
        if (isCollectionMode()) {
            leaveCollectionMode();
        } else {
            await enterCollectionMode();
        }
        break;
    case "joymenu":
    default:
        break;
    }
}

function setImage() {
    if (isCollectionMode()) {
        renderFullscreenMedia("img/collection_background.png", null);
        if (windowName === "table") {
            updateCollectionMeta(getCollectionDisplayData(currentCollectionIndex));
            renderWheelCarousel();
        }
        return;
    }

    if (!vpin.tableData || vpin.tableData.length === 0) {
        cleanupMediaElement(document.querySelector("#fsMediaContainer .media-frame.is-active, #fsMedia"));
        return;
    }

    const imageUrl = vpin.getImageURL(currentTableIndex, windowName);
    let videoUrl = null;

    if (windowName === "table" || windowName === "bg" || windowName === "dmd") {
        videoUrl = vpin.getVideoURL(currentTableIndex, windowName);
    }

    renderFullscreenMedia(imageUrl, videoUrl);

    if (windowName === "table") {
        updateTableMeta(getDisplayData(currentTableIndex));
        renderWheelCarousel();
        vpin.playTableAudio(currentTableIndex);
    }
}

window.addEventListener("resize", () => {
    if (windowName === "table") {
        renderWheelCarousel({ animate: false });
    }
});
