/*
Template theme demonstrating all VPinFE theme patterns.
See theme.md for full documentation.
*/

// Globals
windowName = ""
currentTableIndex = 0;
config = null;
isTablePortrait = false;
tableDisplayPortrait = false;
tableRotationDegrees = 0;
lastWheelMoveDirection = 0;
lastHeroImageUrl = null;
lastHeroBgUrl = null;
lastRenderedTableIndex = -1;
const mediaPreloadCache = new Map();
let tableView = null;
let wheelMode = 'tables';
let collectionEntries = [];
let currentCollectionIndex = 0;
const collectionBackgroundUrl = "img/collection_background.png";

function setNodeText(node, value) {
    const nextValue = value || '';
    if (node.textContent !== nextValue) {
        node.textContent = nextValue;
    }
}

// init the core interface to VPinFE
const vpin = new VPinFECore();
vpin.init();
window.vpin = vpin // main menu needs this to call back in.

// Register receiveEvent globally BEFORE vpin.ready to avoid timing issues
window.receiveEvent = receiveEvent;

// wait for VPinFECore to be ready
vpin.ready.then(async () => {
    console.log("VPinFECore is fully initialized");

    await vpin.call("get_my_window_name")
        .then(result => {
            windowName = result;
        });

    // Register your input handler. VPinFECore handles all input (keyboard or gamepad)
    // and calls your handler when input is detected.
    vpin.registerInputHandler(handleInput);

    // Optional: load a config.json from your theme dir for user-customizable options
    config = await vpin.call("get_theme_config");

    if (windowName === "table") {
        vpin.enableCoreAudio(true);
        vpin.setAudioOptions({
            maxVolume: 0.8,
            fadeDuration: 350,
            loop: true
        });
        await applyTableLayout();
        window.addEventListener('resize', () => {
            applyTableLayout().then(() => {
                updateScreen();
            });
        });
    }

    const startInCollectionSelection = Boolean(config?.startCollectionSelection);

    if (windowName === "table" && startInCollectionSelection) {
        await enterCollectionMode();
        if (!isCollectionMode()) {
            updateScreen();
        }
    } else {
        // Initialize the display
        updateScreen();
    }
});

// Listener for window events. VPinFECore uses this to send events to all windows.
async function receiveEvent(message) {
    vpin.call("console_out", message); // debug: send to Python CLI console

    // Let VPinFECore handle the data refresh logic (TableDataChange, filters, sorts)
    await vpin.handleEvent(message);

    // Handle UI updates based on event type
    if (message.type == "TableIndexUpdate") {
        if (isCollectionMode()) {
            leaveCollectionMode();
        }
        currentTableIndex = message.index;
        updateScreen();
    }
    else if (message.type == "TableLaunching") {
        fadeOut();
    }
    else if (message.type == "TableLaunchComplete") {
        fadeIn();
    }
    else if (message.type == "RemoteLaunching") {
        // Remote launch from manager UI
        vpin.stopTableAudio();
        showRemoteLaunchOverlay(message.table_name);
        fadeOut();
    }
    else if (message.type == "RemoteLaunchComplete") {
        // Remote launch completed
        hideRemoteLaunchOverlay();
        fadeIn();
    }
    else if (message.type == "TableDataChange") {
        if (isCollectionMode()) {
            leaveCollectionMode();
        }
        currentTableIndex = message.index;
        updateScreen();
    }
}

// Input handler function. ***** Only for the "table" window *****
// These actions are passed to your handler:
//   joyleft, joyright, joyup, joydown, joyselect, joyback
// These actions are handled internally by VPinFECore (NOT passed to your handler):
//   joymenu, joycollectionmenu, joyexit
async function handleInput(input) {
    switch (input) {
        case "joyleft":
            if (isCollectionMode()) {
                lastWheelMoveDirection = -1;
                currentCollectionIndex = wrapIndex(currentCollectionIndex - 1, collectionEntries.length);
                updateScreen();
                break;
            }
            lastWheelMoveDirection = -1;
            currentTableIndex = wrapIndex(currentTableIndex - 1, vpin.tableData.length);
            updateScreen();

            // tell other windows the table index changed
            vpin.sendMessageToAllWindows({
                type: 'TableIndexUpdate',
                index: currentTableIndex
            });
            break;
        case "joyright":
            if (isCollectionMode()) {
                lastWheelMoveDirection = 1;
                currentCollectionIndex = wrapIndex(currentCollectionIndex + 1, collectionEntries.length);
                updateScreen();
                break;
            }
            lastWheelMoveDirection = 1;
            currentTableIndex = wrapIndex(currentTableIndex + 1, vpin.tableData.length);
            updateScreen();

            // tell other windows the table index changed
            vpin.sendMessageToAllWindows({
                type: 'TableIndexUpdate',
                index: currentTableIndex
            });
            break;
        case "joyselect":
            if (isCollectionMode()) {
                await selectCurrentCollection();
                break;
            }
            vpin.stopTableAudio();
            vpin.sendMessageToAllWindows({ type: "TableLaunching" });
            await fadeOut();
            await vpin.launchTable(currentTableIndex);
            break;
        case "joyback":
            if (isCollectionMode()) {
                leaveCollectionMode();
            } else {
                await enterCollectionMode();
            }
            break;
    }
}

// Main update function - called when table index changes or data refreshes.
// All three windows (table, bg, dmd) load the same theme.js, so use windowName
// to branch logic per window.
function updateScreen() {
    if (windowName === "table") {
        if (isCollectionMode()) {
            updateCollectionWindow();
            return;
        }
        updateTableWindow();
        vpin.playTableAudio(currentTableIndex);
        preloadNearbyMedia();
    } else if (windowName === "bg") {
        updateBGWindow();
    } else if (windowName === "dmd") {
        updateDMDWindow();
    }
}

function isCollectionMode() {
    return wheelMode === 'collections';
}

// ---- Table Window (main screen) ----
function updateTableWindow() {
    const container = document.getElementById('rootContainer');
    tableView = ensureTableView(container);

    if (!vpin.tableData || vpin.tableData.length === 0) {
        tableView.shell.style.display = 'none';
        tableView.emptyState.style.display = 'flex';
        tableView.emptyState.textContent = 'No tables found';
        return;
    }

    tableView.shell.style.display = '';
    tableView.emptyState.style.display = 'none';

    const table = vpin.getTableMeta(currentTableIndex);
    const info = table.meta.Info || {};
    const vpx = table.meta.VPXFile || {};
    const title = info.Title || vpx.filename || table.tableDirName || 'Unknown Table';
    const manufacturer = info.Manufacturer || vpx.manufacturer || 'Unknown';
    const year = info.Year || vpx.year || '';
    const authors = formatAuthors(info.Authors);
    const tableType = info.Type || vpx.type || '';
    const featureFlags = [
        { key: "detectnfozzy", label: "Nfozzy" },
        { key: "detectfleep", label: "Fleep" },
        { key: "detectssf", label: "SSF" },
        { key: "detectfastflips", label: "FastFlips" },
        { key: "detectlut", label: "LUT" },
        { key: "detectscorebit", label: "ScoreBit" },
        { key: "detectflex", label: "FlexDMD" },
    ];
    const addonFlags = [
        { key: "altSoundExists", label: "AltSound" },
        { key: "altColorExists", label: "AltColor" },
        { key: "pupPackExists", label: "PuP-Pack" },
    ];

    const wheelUrl = vpin.getImageURL(currentTableIndex, 'cab');
    updateWheelCarousel(tableView);
    updateTitleBlock(tableView, {
        eyebrow: [manufacturer, year ? String(year) : '', tableType].filter(Boolean).join(' / '),
        title,
        authors,
        wheelUrl,
    });
    updateHeroMedia(tableView.heroMedia, title);
    updateFeaturePanel(tableView.featurePanel, featureFlags, vpx);
    updateFeaturePanel(tableView.addonPanel, addonFlags, vpx);

    lastRenderedTableIndex = currentTableIndex;
    lastWheelMoveDirection = 0;
}

function updateCollectionWindow() {
    const container = document.getElementById('rootContainer');
    tableView = ensureTableView(container);

    if (!collectionEntries.length) {
        tableView.shell.style.display = 'none';
        tableView.emptyState.style.display = 'flex';
        tableView.emptyState.textContent = 'No collections found';
        return;
    }

    tableView.shell.style.display = '';
    tableView.emptyState.style.display = 'none';

    const data = getCollectionDisplayData(currentCollectionIndex);
    updateWheelCarousel(tableView);
    updateTitleBlock(tableView, {
        eyebrow: data.eyebrow,
        title: data.title,
        authors: data.authors,
        wheelUrl: data.wheelUrl,
    });
    updateHeroMedia(tableView.heroMedia, data.title);
    updateFeaturePanel(tableView.featurePanel, data.featureFlags, {
        collectionActive: true,
        collectionCount: true,
    });
    updateFeaturePanel(tableView.addonPanel, [], {});

    lastRenderedTableIndex = currentCollectionIndex;
    lastWheelMoveDirection = 0;
}

// ---- BG Window (backglass) ----
function updateBGWindow() {
    const container = document.getElementById('rootContainer');
    if (!vpin.tableData || vpin.tableData.length === 0) {
        container.innerHTML = '';
        return;
    }

    const bgUrl = vpin.getImageURL(currentTableIndex, "bg");
    const bgVideoUrl = vpin.getVideoURL(currentTableIndex, "bg");
    renderWindowMedia(container, bgUrl, bgVideoUrl, 'Backglass');
}

// ---- DMD Window ----
function updateDMDWindow() {
    const container = document.getElementById('rootContainer');
    if (!vpin.tableData || vpin.tableData.length === 0) {
        container.innerHTML = '';
        return;
    }

    const dmdUrl = vpin.getImageURL(currentTableIndex, "dmd");
    const dmdVideoUrl = vpin.getVideoURL(currentTableIndex, "dmd");
    renderWindowMedia(container, dmdUrl, dmdVideoUrl, 'DMD');
}

//
// Support functions
//

// circular table index
function wrapIndex(index, length) {
    return (index + length) % length;
}

function getCollectionDisplayData(index) {
    const collection = collectionEntries[index] || {};
    const tableCount = Number(collection.table_count);
    const countText = Number.isFinite(tableCount)
        ? `${tableCount} ${tableCount === 1 ? 'Table' : 'Tables'}`
        : (collection.is_filter ? 'Filter Collection' : 'Collection');
    const imageUrl = collection.image_url || '';

    return {
        title: collection.name || 'Collection',
        eyebrow: collection.type === 'filter' ? 'Filter collection' : 'Collection',
        authors: countText,
        wheelUrl: imageUrl,
        heroUrl: collectionBackgroundUrl,
        bgUrl: collectionBackgroundUrl,
        featureFlags: [
            { key: 'collectionActive', label: collection.type === 'filter' ? 'Filter' : 'Collection' },
            { key: 'collectionCount', label: countText },
        ],
        collection,
    };
}

async function enterCollectionMode() {
    if (windowName !== 'table') {
        return;
    }

    try {
        const metadata = await vpin.call('get_collections_metadata');
        collectionEntries = Array.isArray(metadata) ? metadata.filter((entry) => entry && entry.name) : [];
    } catch (error) {
        vpin.call('console_out', `Unable to load collections: ${error.message || error}`);
        collectionEntries = [];
    }

    if (!collectionEntries.length) {
        return;
    }

    wheelMode = 'collections';
    currentCollectionIndex = 0;
    lastRenderedTableIndex = -1;
    lastWheelMoveDirection = 0;
    lastHeroImageUrl = null;
    lastHeroBgUrl = null;
    document.body.classList.add('collection-wheel-mode');
    updateScreen();
}

async function selectCurrentCollection() {
    const collection = collectionEntries[currentCollectionIndex];
    if (!collection?.name) {
        return;
    }

    wheelMode = 'tables';
    document.body.classList.remove('collection-wheel-mode');
    await vpin.call('set_tables_by_collection', collection.name);
    await vpin.getTableData();
    currentTableIndex = 0;
    lastRenderedTableIndex = -1;
    lastWheelMoveDirection = 0;
    lastHeroImageUrl = null;
    lastHeroBgUrl = null;
    updateScreen();
    vpin.sendMessageToAllWindows({
        type: 'TableDataChange',
        index: currentTableIndex,
        collection: collection.name
    });
}

function leaveCollectionMode() {
    wheelMode = 'tables';
    document.body.classList.remove('collection-wheel-mode');
    lastRenderedTableIndex = -1;
    lastWheelMoveDirection = 0;
    lastHeroImageUrl = null;
    lastHeroBgUrl = null;
    updateScreen();
}

function formatAuthors(authors) {
    if (Array.isArray(authors) && authors.length > 0) return authors.join(', ');
    if (typeof authors === 'string' && authors.trim()) return authors.trim();
    return 'Unknown author';
}

function isTruthyFlag(value) {
    return value === true || value === "true" || value === 1 || value === "1";
}

function hasUsableMedia(url) {
    return Boolean(url) && !String(url).includes('file_missing');
}

function renderWindowMedia(container, imageUrl, videoUrl, altText) {
    const existingMedia = container.querySelector('video, img');
    const wantsVideo = hasUsableMedia(videoUrl);

    if (existingMedia) {
        if (existingMedia.tagName === 'VIDEO') {
            existingMedia.pause();
            existingMedia.removeAttribute('src');
            existingMedia.load();
        }
        existingMedia.remove();
    }

    if (wantsVideo) {
        const video = document.createElement('video');
        video.src = videoUrl;
        video.poster = hasUsableMedia(imageUrl) ? imageUrl : '';
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.playsInline = true;
        video.style.cssText = 'width: 100%; height: 100%; object-fit: cover;';
        video.onerror = () => {
            if (!hasUsableMedia(imageUrl)) return;
            const fallback = document.createElement('img');
            fallback.src = imageUrl;
            fallback.alt = altText;
            fallback.style.cssText = 'width: 100%; height: 100%; object-fit: cover;';
            video.replaceWith(fallback);
        };
        container.appendChild(video);
        return;
    }

    const img = document.createElement('img');
    img.src = hasUsableMedia(imageUrl) ? imageUrl : '';
    img.alt = altText;
    img.style.cssText = 'width: 100%; height: 100%; object-fit: cover;';
    container.appendChild(img);
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function buildWheelCarousel() {
    const carousel = document.createElement('div');
    carousel.className = 'wheel-carousel';

    const track = document.createElement('div');
    track.className = 'wheel-track';
    if (lastWheelMoveDirection > 0) {
        track.classList.add('reel-next');
    } else if (lastWheelMoveDirection < 0) {
        track.classList.add('reel-prev');
    }

    const visibleCount = isTablePortrait ? 5 : 5;
    const half = Math.floor(visibleCount / 2);
    for (let offset = -half; offset <= half; offset += 1) {
        const index = wrapIndex(currentTableIndex + offset, vpin.getTableCount());
        const table = vpin.getTableMeta(index);
        const info = table.meta.Info || {};
        const vpx = table.meta.VPXFile || {};
        const title = info.Title || vpx.filename || table.tableDirName || 'Unknown Table';
        const wheelUrl = vpin.getImageURL(index, 'wheel');

        const card = document.createElement('div');
        card.className = `wheel-card${offset === 0 ? ' active' : ''}${Math.abs(offset) === 1 ? ' dim-near' : ''}`;
        card.dataset.offset = String(offset);

        if (hasUsableMedia(wheelUrl)) {
            const img = document.createElement('img');
            img.src = wheelUrl;
            img.alt = title;
            img.onerror = () => {
                const fallback = document.createElement('div');
                fallback.className = 'wheel-fallback';
                fallback.textContent = title;
                img.replaceWith(fallback);
            };
            card.appendChild(img);
        } else {
            const fallback = document.createElement('div');
            fallback.className = 'wheel-fallback';
            fallback.textContent = title;
            card.appendChild(fallback);
        }

        track.appendChild(card);
    }

    carousel.appendChild(track);
    return carousel;
}

function buildHeroImage(imageUrl, title) {
    const img = document.createElement('img');
    img.src = imageUrl;
    img.alt = title;
    img.className = 'hero-media-asset';
    img.onerror = () => {
        img.removeAttribute('src');
        img.alt = `${title} media unavailable`;
    };
    return img;
}

function preloadImage(url) {
    if (!hasUsableMedia(url)) return;
    if (mediaPreloadCache.has(url)) return;

    const img = new Image();
    img.decoding = 'async';
    img.src = url;
    const promise = img.decode ? img.decode().catch(() => {}) : Promise.resolve();
    mediaPreloadCache.set(url, promise);

    // Keep cache bounded.
    if (mediaPreloadCache.size > 18) {
        const firstKey = mediaPreloadCache.keys().next().value;
        mediaPreloadCache.delete(firstKey);
    }
}

function preloadNearbyMedia() {
    if (!vpin.tableData || vpin.getTableCount() === 0) return;

    const indices = [
        currentTableIndex,
        wrapIndex(currentTableIndex - 1, vpin.getTableCount()),
        wrapIndex(currentTableIndex + 1, vpin.getTableCount()),
    ];

    indices.forEach((index) => {
        preloadImage(vpin.getImageURL(index, 'table'));
        preloadImage(vpin.getImageURL(index, 'bg'));
        preloadImage(vpin.getImageURL(index, 'wheel'));
        preloadImage(vpin.getImageURL(index, 'cab'));
    });
}

function buildDetailCard(label, value) {
    const card = document.createElement('div');
    card.className = 'detail-card';
    card.innerHTML = `
        <div class="detail-label">${escapeHtml(label)}</div>
        <div class="detail-value">${escapeHtml(value)}</div>
    `;
    return card;
}

function buildFeaturePanel(title, items, vpx) {
    const panel = document.createElement('section');
    panel.className = 'feature-panel';

    const heading = document.createElement('h2');
    heading.className = 'feature-panel-title';
    heading.textContent = title;
    panel.appendChild(heading);

    const strip = document.createElement('div');
    strip.className = 'feature-strip';
    items.forEach(({ key, label }) => {
        const tag = document.createElement('div');
        const isOn = isTruthyFlag(vpx[key]);
        tag.className = `feature-tag${isOn ? ' active' : ''}`;
        tag.textContent = label;
        strip.appendChild(tag);
    });

    panel.appendChild(strip);
    return panel;
}

function ensureTableView(container) {
    if (tableView && tableView.container === container) return tableView;

    container.innerHTML = '';

    const emptyState = document.createElement('div');
    emptyState.className = 'empty-state';
    emptyState.textContent = 'No tables found';
    emptyState.style.display = 'none';

    const shell = document.createElement('div');
    shell.className = 'table-shell';

    const wheelColumn = document.createElement('section');
    wheelColumn.className = 'wheel-column';
    const carousel = document.createElement('div');
    carousel.className = 'wheel-carousel';
    const selectionHalo = document.createElement('div');
    selectionHalo.className = 'wheel-selection-halo';
    const wheelTrack = createWheelTrack();
    carousel.appendChild(selectionHalo);
    carousel.appendChild(wheelTrack);
    wheelColumn.appendChild(carousel);

    const heroColumn = document.createElement('section');
    heroColumn.className = 'hero-column';

    const titleHeader = document.createElement('div');
    titleHeader.className = 'title-header';
    titleHeader.innerHTML = `
        <div class="title-copy">
            <div class="title-main">
                <div class="title-wheel"></div>
                <div class="title-text">
                    <div class="eyebrow"></div>
                    <h1 class="table-title"></h1>
                    <div class="meta-line"></div>
                </div>
            </div>
        </div>
    `;

    const heroMedia = document.createElement('div');
    heroMedia.className = 'hero-media';

    const featureSections = document.createElement('div');
    featureSections.className = 'feature-sections';
    const featurePanel = buildFeaturePanel('Features', [], {});
    const addonPanel = buildFeaturePanel('Add-ons', [], {});
    featureSections.appendChild(featurePanel);
    featureSections.appendChild(addonPanel);

    heroColumn.appendChild(titleHeader);
    heroColumn.appendChild(heroMedia);
    heroColumn.appendChild(featureSections);

    shell.appendChild(wheelColumn);
    shell.appendChild(heroColumn);
    container.appendChild(emptyState);
    container.appendChild(shell);

    tableView = {
        container,
        emptyState,
        shell,
        wheelCarousel: carousel,
        wheelTrack,
        titleHeader,
        titleWheel: titleHeader.querySelector('.title-wheel'),
        eyebrow: titleHeader.querySelector('.eyebrow'),
        title: titleHeader.querySelector('.table-title'),
        authorLine: titleHeader.querySelector('.meta-line'),
        heroMedia,
        featurePanel,
        addonPanel,
    };
    return tableView;
}

function createWheelTrack() {
    const wheelTrack = document.createElement('div');
    wheelTrack.className = 'wheel-track';
    for (let offset = -3; offset <= 3; offset += 1) {
        const card = document.createElement('div');
        card.className = 'wheel-card';
        card.dataset.offset = String(offset);
        wheelTrack.appendChild(card);
    }
    return wheelTrack;
}

function renderWheelCarousel(track, centerIndex) {
    const cards = Array.from(track.children);
    const itemCount = isCollectionMode() ? collectionEntries.length : vpin.getTableCount();
    if (!itemCount) return;

    cards.forEach((card) => {
        const offset = Number(card.dataset.offset || 0);
        const index = wrapIndex(centerIndex + offset, itemCount);
        let title;
        let wheelUrl;
        if (isCollectionMode()) {
            const data = getCollectionDisplayData(index);
            title = data.title;
            wheelUrl = data.wheelUrl;
        } else {
            const table = vpin.getTableMeta(index);
            const info = table.meta.Info || {};
            const vpx = table.meta.VPXFile || {};
            title = info.Title || vpx.filename || table.tableDirName || 'Unknown Table';
            wheelUrl = vpin.getImageURL(index, 'wheel');
        }
        const isActive = offset === 0;
        const isNear = Math.abs(offset) === 1;

        card.className = `wheel-card${isActive ? ' active' : ''}${isNear ? ' dim-near' : ''}${isCollectionMode() ? ' collection-card' : ''}`;

        let img = card.querySelector('img');
        let fallback = card.querySelector('.wheel-fallback');

        if (hasUsableMedia(wheelUrl)) {
            if (!img) {
                img = document.createElement('img');
                img.onerror = () => {
                    img.removeAttribute('src');
                    img.style.display = 'none';
                    let nextFallback = card.querySelector('.wheel-fallback');
                    if (!nextFallback) {
                        nextFallback = document.createElement('div');
                        nextFallback.className = 'wheel-fallback';
                        card.appendChild(nextFallback);
                    }
                    nextFallback.textContent = title;
                    nextFallback.style.display = '';
                };
                card.appendChild(img);
            }
            img.alt = title;
            if (img.src !== wheelUrl) {
                img.src = wheelUrl;
            }
            img.style.display = '';
            if (fallback) fallback.style.display = 'none';
        } else {
            if (!fallback) {
                fallback = document.createElement('div');
                fallback.className = 'wheel-fallback';
                card.appendChild(fallback);
            }
            fallback.textContent = title;
            fallback.style.display = '';
            if (img) {
                img.removeAttribute('src');
                img.style.display = 'none';
            }
        }
    });
}

function getWheelStep(track) {
    const cards = Array.from(track.children);
    if (cards.length < 2) return 0;
    const first = cards[0];
    const second = cards[1];
    if (isTablePortrait) {
        return second.offsetLeft - first.offsetLeft;
    }
    return second.offsetTop - first.offsetTop;
}

function updateWheelCarousel(view) {
    const carousel = view.wheelCarousel;
    let track = view.wheelTrack;
    if (view.wheelTrackResetTimer) {
        clearTimeout(view.wheelTrackResetTimer);
        view.wheelTrackResetTimer = null;
    }

    const existingTracks = Array.from(carousel.querySelectorAll('.wheel-track'));
    existingTracks.forEach((existingTrack) => {
        existingTrack.getAnimations().forEach((animation) => animation.cancel());
        existingTrack.classList.remove('wheel-track-transition');
        existingTrack.style.transform = '';
        existingTrack.style.zIndex = '';
        if (existingTrack !== track) {
            existingTrack.remove();
        }
    });

    const canAnimate =
        lastRenderedTableIndex !== -1 &&
        lastWheelMoveDirection !== 0 &&
        (isCollectionMode() ? collectionEntries.length : vpin.getTableCount()) > 1;

    if (!canAnimate) {
        renderWheelCarousel(track, isCollectionMode() ? currentCollectionIndex : currentTableIndex);
        return;
    }

    renderWheelCarousel(track, lastRenderedTableIndex);
    const step = getWheelStep(track);
    if (!step) {
        renderWheelCarousel(track, currentTableIndex);
        return;
    }

    const incomingTrack = createWheelTrack();
    renderWheelCarousel(incomingTrack, isCollectionMode() ? currentCollectionIndex : currentTableIndex);
    incomingTrack.classList.add('wheel-track-transition');
    incomingTrack.style.zIndex = '2';
    track.classList.add('wheel-track-transition');
    track.style.zIndex = '1';
    carousel.appendChild(incomingTrack);

    const outgoingDelta = lastWheelMoveDirection > 0 ? -step : step;
    const incomingStart = -outgoingDelta;
    const translateValue = (value) => (
        isTablePortrait ? `translateX(${value}px)` : `translateY(${value}px)`
    );

    incomingTrack.style.transform = translateValue(incomingStart);
    incomingTrack.offsetWidth;

    const animationDuration = 520;
    const animationOptions = {
        duration: animationDuration,
        easing: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
        fill: 'forwards',
    };

    track.animate(
        [
            { transform: translateValue(0) },
            { transform: translateValue(outgoingDelta) },
        ],
        animationOptions
    );

    incomingTrack.animate(
        [
            { transform: translateValue(incomingStart) },
            { transform: translateValue(0) },
        ],
        animationOptions
    );

    view.wheelTrackResetTimer = setTimeout(() => {
        track.remove();
        incomingTrack.classList.remove('wheel-track-transition');
        incomingTrack.style.transform = '';
        incomingTrack.style.zIndex = '';
        view.wheelTrack = incomingTrack;
        view.wheelTrackResetTimer = null;
    }, animationDuration);
}

function updateTitleBlock(view, data) {
    setNodeText(view.eyebrow, data.eyebrow);
    setNodeText(view.title, data.title);
    setNodeText(view.authorLine, data.authors);
    updateTitleWheel(view.titleWheel, data.wheelUrl, data.title);
}

function updateTitleWheel(container, imageUrl, title) {
    let img = container.querySelector('img');
    let fallback = container.querySelector('.wheel-fallback');
    if (hasUsableMedia(imageUrl)) {
        if (!img) {
            img = document.createElement('img');
            img.onerror = () => {
                img.removeAttribute('src');
                img.style.display = 'none';
                let nextFallback = container.querySelector('.wheel-fallback');
                if (!nextFallback) {
                    nextFallback = document.createElement('div');
                    nextFallback.className = 'wheel-fallback';
                    container.appendChild(nextFallback);
                }
                nextFallback.textContent = title;
                nextFallback.style.display = '';
            };
            container.appendChild(img);
        }
        img.alt = title;
        if (img.src !== imageUrl) {
            img.src = imageUrl;
        }
        img.style.display = '';
        if (fallback) fallback.style.display = 'none';
    } else {
        if (!fallback) {
            fallback = document.createElement('div');
            fallback.className = 'wheel-fallback';
            container.appendChild(fallback);
        }
        fallback.textContent = title;
        fallback.style.display = '';
        if (img) {
            img.removeAttribute('src');
            img.style.display = 'none';
        }
    }
}

function updateHeroMedia(container, title) {
    const collectionData = isCollectionMode() ? getCollectionDisplayData(currentCollectionIndex) : null;
    const imageUrl = collectionData ? collectionData.heroUrl : vpin.getImageURL(currentTableIndex, 'table');
    const bgUrl = collectionData ? collectionData.bgUrl : vpin.getImageURL(currentTableIndex, 'bg');

    if (isCollectionMode()) {
        const existingLayer = container.querySelector('.hero-media-frame');
        if (
            existingLayer &&
            existingLayer.dataset.imageUrl === imageUrl &&
            existingLayer.dataset.bgUrl === bgUrl &&
            container.children.length === 1
        ) {
            return;
        }

        const frame = document.createElement('div');
        frame.className = 'hero-media-frame hero-media-layer is-active';
        frame.dataset.imageUrl = imageUrl;
        frame.dataset.bgUrl = bgUrl;

        const image = buildHeroImage(imageUrl, title);
        image.classList.add('collection-hero-image');
        frame.appendChild(image);
        container.replaceChildren(frame);
        lastHeroImageUrl = imageUrl;
        lastHeroBgUrl = bgUrl;
        return;
    }

    const previousLayer = container.querySelector('.hero-media-frame.is-active, .hero-media-frame');

    if (
        previousLayer &&
        previousLayer.dataset.imageUrl === imageUrl &&
        previousLayer.dataset.bgUrl === bgUrl
    ) {
        if (!isCollectionMode()) {
            previousLayer.querySelectorAll('.hero-media-asset').forEach(applyMediaRotation);
        }
        previousLayer.classList.remove('is-entering', 'is-exiting');
        previousLayer.classList.add('is-active');
        return;
    }

    const frame = document.createElement('div');
    frame.className = 'hero-media-frame hero-media-layer is-entering';
    frame.dataset.imageUrl = imageUrl;
    frame.dataset.bgUrl = bgUrl;

    const videoUrl = isCollectionMode() ? null : vpin.getVideoURL(currentTableIndex, 'table');
    let activated = false;
    const activateLayer = () => {
        if (activated) return;
        activated = true;
        requestAnimationFrame(() => {
            frame.classList.remove('is-entering');
            frame.classList.add('is-active');
            if (previousLayer) {
                previousLayer.classList.add('is-exiting');
                setTimeout(() => previousLayer.remove(), 220);
            }
        });
    };

    if (hasUsableMedia(videoUrl)) {
        const video = document.createElement('video');
        video.src = videoUrl;
        video.poster = imageUrl;
        video.autoplay = true;
        video.loop = true;
        video.muted = true;
        video.playsInline = true;
        video.className = 'hero-media-asset';
        video.onerror = () => {
            const fallback = buildHeroImage(imageUrl, title);
            video.replaceWith(fallback);
            if (isCollectionMode()) {
                fallback.classList.add('collection-hero-image');
            } else {
                applyMediaRotation(fallback);
            }
            activateLayer();
        };
        video.addEventListener('loadeddata', activateLayer, { once: true });
        frame.appendChild(video);
        applyMediaRotation(video);
    } else {
        const image = buildHeroImage(imageUrl, title);
        if (isCollectionMode()) {
            image.classList.add('collection-hero-image');
        }
        if (image.complete) {
            activateLayer();
        } else {
            image.addEventListener('load', activateLayer, { once: true });
            image.addEventListener('error', activateLayer, { once: true });
        }
        frame.appendChild(image);
        if (!isCollectionMode()) {
            applyMediaRotation(image);
        }
    }

    container.appendChild(frame);
    if (!isCollectionMode()) {
        frame.querySelectorAll('.hero-media-asset').forEach(applyMediaRotation);
    }
    lastHeroImageUrl = imageUrl;
    lastHeroBgUrl = bgUrl;
    setTimeout(activateLayer, 16);
}

function updateFeaturePanel(panel, items, vpx) {
    const strip = panel.querySelector('.feature-strip');
    strip.innerHTML = '';
    items.forEach(({ key, label }) => {
        const tag = document.createElement('div');
        const isOn = isTruthyFlag(vpx[key]);
        tag.className = `feature-tag${isOn ? ' active' : ''}`;
        tag.textContent = label;
        strip.appendChild(tag);
    });
}

function getTableSubtitle() {
    const table = vpin.getTableMeta(currentTableIndex);
    const info = table.meta.Info || {};
    const vpx = table.meta.VPXFile || {};
    const manufacturer = info.Manufacturer || vpx.manufacturer || 'Unknown manufacturer';
    const year = info.Year || vpx.year || '';
    const type = info.Type || vpx.type || 'Pinball table';
    return `${manufacturer}${year ? ' • ' + year : ''}${type ? ' • ' + type : ''}`;
}

function getMediaModeLabel() {
    if (!isTablePortrait) return 'Landscape view';
    return 'Portrait cab view';
}

function applyMediaRotation(element) {
    if (!element) return;

    const normalized = ((tableRotationDegrees % 360) + 360) % 360;
    const swapAxes = normalized === 90 || normalized === 270;
    const viewportPortrait = tableDisplayPortrait;
    const mediaRotation = viewportPortrait
        ? (normalized === 0 ? 90 : 180)
        : (swapAxes ? (normalized === 270 ? 90 : 0) : tableRotationDegrees);
    const rotateMedia = Math.abs(mediaRotation) === 90 || Math.abs(mediaRotation) === 270;

    if (rotateMedia) {
        const sizeToFrame = () => {
            const frame = element.closest('.hero-media-frame') || element.parentElement;
            const frameWidth = frame?.clientWidth || frame?.offsetWidth || 0;
            const frameHeight = frame?.clientHeight || frame?.offsetHeight || 0;
            if (frameWidth > 0 && frameHeight > 0) {
                element.style.width = `${frameHeight}px`;
                element.style.height = `${frameWidth}px`;
            } else {
                element.style.width = tableDisplayPortrait ? "177.78%" : "56.25%";
                element.style.height = tableDisplayPortrait ? "56.25%" : "177.78%";
            }
        };

        sizeToFrame();
        requestAnimationFrame(sizeToFrame);
        element.style.position = "absolute";
        element.style.top = "50%";
        element.style.left = "50%";
        element.style.maxWidth = "none";
        element.style.maxHeight = "none";
        element.style.minWidth = "0";
        element.style.minHeight = "0";
        element.style.objectFit = "cover";
        element.style.transformOrigin = "center center";
        element.style.transform = `translate(-50%, -50%) rotate(${mediaRotation}deg)`;
    } else {
        element.style.position = "";
        element.style.top = "";
        element.style.left = "";
        element.style.width = "100%";
        element.style.height = "100%";
        element.style.maxWidth = "";
        element.style.maxHeight = "";
        element.style.minWidth = "";
        element.style.minHeight = "";
        element.style.objectFit = "cover";
        element.style.transformOrigin = "";
        element.style.transform = mediaRotation !== 0
            ? `rotate(${mediaRotation}deg)`
            : "none";
    }
}

function ensureMenuOverlayContainer() {
    const overlayRoot = document.getElementById("overlay-root");
    if (!overlayRoot) return null;

    let container = document.getElementById("menu-overlay-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "menu-overlay-container";
        overlayRoot.appendChild(container);
    }

    Array.from(overlayRoot.children).forEach((child) => {
        if (child !== container) {
            container.appendChild(child);
            applyMenuFrameFit(child);
        }
    });

    if (!overlayRoot._menuObserver) {
        const observer = new MutationObserver(() => {
            Array.from(overlayRoot.children).forEach((child) => {
                if (child !== container) {
                    container.appendChild(child);
                    applyMenuFrameFit(child);
                }
            });
        });
        observer.observe(overlayRoot, { childList: true });
        overlayRoot._menuObserver = observer;
    }

    return container;
}

function applyMenuFrameFit(frame) {
    if (!frame || frame.id !== "menu-frame" || frame._revolutionFitApplied) return;

    const injectFitStyles = () => {
        try {
            const doc = frame.contentDocument;
            if (!doc || doc.getElementById("revolution-menu-fit")) return;

            const style = doc.createElement("style");
            style.id = "revolution-menu-fit";
            style.textContent = `
                #menu-container {
                    padding: 16.5% 10% 21%;
                }

                ul.menu {
                    transform: none;
                }

                li.menu-item {
                    padding-top: clamp(6px, 1.35vmin, 20px);
                    padding-bottom: clamp(6px, 1.35vmin, 20px);
                    margin-bottom: clamp(3px, 0.72vmin, 12px);
                    font-size: clamp(14px, 2.05vh, 34px);
                }

                #menu-qr-panels {
                    bottom: 4.8%;
                    transform: translateX(-50%) scale(0.84);
                    transform-origin: bottom center;
                }
            `;
            doc.head.appendChild(style);
        } catch (_e) {
            // Same-origin during normal VPinFE use; ignore if the iframe is not ready yet.
        }
    };

    frame._revolutionFitApplied = true;
    frame.addEventListener("load", injectFitStyles);
    injectFitStyles();
}

async function applyTableLayout() {
    if (windowName !== "table") return;

    const screen = document.getElementById('tableScreen');
    const overlayRoot = document.getElementById('overlay-root');
    if (!screen) return;

    const cabMode = await vpin.call("get_cab_mode");
    const tableOrientation = String(await vpin.call("get_table_orientation") || "").toLowerCase();
    const rotationDegree = Number(await vpin.call("get_table_rotation")) || 0;
    tableRotationDegrees = rotationDegree;
    const normalized = ((rotationDegree % 360) + 360) % 360;
    const swapAxes = normalized === 90 || normalized === 270;
    tableDisplayPortrait = tableOrientation === "portrait";
    isTablePortrait = swapAxes || tableDisplayPortrait;

    const surfaceWidth = swapAxes ? window.innerHeight : window.innerWidth;
    const surfaceHeight = swapAxes ? window.innerWidth : window.innerHeight;
    const menuRotation =
        normalized === 90 ? 90 :
        normalized === 180 ? 90 :
        normalized === 270 ? 270 :
        0;
    const menuSwapAxes = Math.abs(menuRotation) === 90 || Math.abs(menuRotation) === 270;
    const root = document.documentElement;
    root.style.setProperty(
        "--menu-width",
        menuSwapAxes
            ? "min(82vh, calc(82vw * 1.5), 1800px)"
            : "min(82vw, calc(82vh * 1.5), 1800px)"
    );

    screen.style.width = `${surfaceWidth}px`;
    screen.style.height = `${surfaceHeight}px`;
    screen.style.transform = rotationDegree !== 0
        ? `rotate(${rotationDegree}deg)`
        : "none";
    screen.style.visibility = "visible";

    if (overlayRoot) {
        overlayRoot.style.width = `${surfaceWidth}px`;
        overlayRoot.style.height = `${surfaceHeight}px`;
        overlayRoot.style.top = '50%';
        overlayRoot.style.left = '50%';
        overlayRoot.style.transform = 'translate(-50%, -50%)';
    }

    const menuOverlay = ensureMenuOverlayContainer();
    if (menuOverlay) {
        menuOverlay.style.transformOrigin = "center center";
        menuOverlay.style.transform = menuRotation !== 0
            ? `rotate(${menuRotation}deg)`
            : "none";
    }

    document.body.classList.toggle('table-screen-portrait', isTablePortrait);
    document.body.classList.toggle('table-screen-cab', Boolean(cabMode));
}

// Fade transition using the fadeOverlay pattern
function fadeOut() {
    const overlay = document.getElementById("fadeOverlay");
    if (overlay) overlay.classList.add("show");
}

function fadeIn() {
    const overlay = document.getElementById("fadeOverlay");
    if (overlay) overlay.classList.remove("show");
}

// Remote launch overlay functions
function showRemoteLaunchOverlay(tableName) {
    const overlay = document.getElementById('remote-launch-overlay');
    const nameEl = document.getElementById('remote-launch-table-name');
    if (overlay && nameEl) {
        nameEl.textContent = tableName || 'Unknown Table';
        overlay.style.display = 'flex';
    }
}

function hideRemoteLaunchOverlay() {
    const overlay = document.getElementById('remote-launch-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}
