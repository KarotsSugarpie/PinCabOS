/*
 * PINCABOS_FULLDMD_NO_GLOBAL_DMD_CARD_V1
 *
 * - retire uniquement la carte visuelle Calibration DMD global;
 * - conserve la carte Calibration FullDMD;
 * - conserve le réglage du DMD par table;
 * - étend Valeurs actuelles VPX / VPinFE sur la colonne droite.
 */

(() => {
    "use strict";

    if (window.__pincabosFullDmdNoGlobalDmdCardV1) {
        return;
    }

    window.__pincabosFullDmdNoGlobalDmdCardV1 = true;

    const route =
        window.location.pathname.replace(/\/+$/, "") || "/";

    if (route !== "/fulldmd") {
        return;
    }

    const STYLE_ID =
        "pincabos-fulldmd-no-global-dmd-card-v1-style";

    const normalize = value =>
        String(value ?? "")
            .replace(/\s+/g, " ")
            .trim()
            .toLocaleLowerCase("fr-CA");

    function installStyle() {
        if (document.getElementById(STYLE_ID)) {
            return;
        }

        const style = document.createElement("style");
        style.id = STYLE_ID;

        style.textContent = `
            /*
             * Grille principale :
             *
             *   Calibration FullDMD | Valeurs VPX / VPinFE
             *   Réglage DMD         | Valeurs VPX / VPinFE
             */

            .pco-fulldmd-main-grid-v1 {
                display: grid !important;
                grid-template-columns:
                    minmax(0, 1fr)
                    minmax(0, 1fr) !important;
                grid-template-rows:
                    max-content
                    minmax(760px, auto) !important;
                grid-auto-flow: row !important;
                gap: 8px !important;
                align-items: stretch !important;
                width: 100% !important;
            }

            .pco-fulldmd-full-calibration-v1 {
                grid-column: 1 !important;
                grid-row: 1 !important;
                min-width: 0 !important;
                align-self: stretch !important;
            }

            .pco-fulldmd-dmd-tuner-v1 {
                grid-column: 1 !important;
                grid-row: 2 !important;
                min-width: 0 !important;
                width: auto !important;
                height: 100% !important;
                min-height: 760px !important;
                align-self: stretch !important;
                margin: 0 !important;
            }

            .pco-fulldmd-values-span-v1 {
                grid-column: 2 !important;
                grid-row: 1 / span 2 !important;
                min-width: 0 !important;
                min-height: 0 !important;
                height: auto !important;
                align-self: stretch !important;
                display: flex !important;
                flex-direction: column !important;
                overflow: hidden !important;
                margin: 0 !important;
            }

            /*
             * Les résumés VPX et VPinFE obtiennent une vraie hauteur,
             * plutôt que de devenir de minces lignes.
             */
            .pco-fulldmd-values-span-v1 > pre {
                flex: 0 0 170px !important;
                height: 170px !important;
                min-height: 170px !important;
                max-height: 170px !important;
                overflow: auto !important;
            }

            /*
             * Carte ajoutée dynamiquement par le tuner DMD.
             */
            .pco-fulldmd-values-span-v1 #pco-table-dmd4-card {
                flex: 1 1 auto !important;
                min-height: 0 !important;
                display: flex !important;
                flex-direction: column !important;
                overflow: hidden !important;
            }

            .pco-fulldmd-values-span-v1
            #pco-table-dmd4-card
            .pco-table-dmd4-sections {
                flex: 1 1 auto !important;
                min-height: 0 !important;
                overflow: auto !important;
                grid-auto-rows: minmax(230px, 1fr) !important;
                align-items: stretch !important;
            }

            .pco-fulldmd-values-span-v1
            #pco-table-dmd4-card
            .pco-table-dmd4-sections > div {
                min-width: 0 !important;
                min-height: 0 !important;
                display: flex !important;
                flex-direction: column !important;
            }

            .pco-fulldmd-values-span-v1
            #pco-table-dmd4-card
            .pco-table-dmd4-sections pre {
                flex: 1 1 auto !important;
                height: auto !important;
                min-height: 180px !important;
                max-height: none !important;
                overflow: auto !important;
            }

            /*
             * Retour en une colonne sur un petit écran.
             */
            @media (max-width: 1100px) {
                .pco-fulldmd-main-grid-v1 {
                    grid-template-columns: minmax(0, 1fr) !important;
                    grid-template-rows:
                        auto
                        auto
                        auto !important;
                }

                .pco-fulldmd-full-calibration-v1 {
                    grid-column: 1 !important;
                    grid-row: 1 !important;
                }

                .pco-fulldmd-dmd-tuner-v1 {
                    grid-column: 1 !important;
                    grid-row: 2 !important;
                }

                .pco-fulldmd-values-span-v1 {
                    grid-column: 1 !important;
                    grid-row: 3 !important;
                    min-height: 760px !important;
                }
            }
        `;

        document.head.appendChild(style);
    }

    function cardByTitle(title) {
        const wanted = normalize(title);

        for (
            const heading of
            document.querySelectorAll("h1, h2, h3, h4")
        ) {
            if (normalize(heading.textContent) !== wanted) {
                continue;
            }

            return (
                heading.closest(".card, .fulldmd-info-card")
                || heading.parentElement
            );
        }

        return null;
    }

    function applyLayout() {
        const fullDmdCard =
            cardByTitle("Calibration FullDMD");

        const globalDmdCard =
            cardByTitle("Calibration DMD global");

        const valuesCard =
            cardByTitle("Valeurs actuelles VPX / VPinFE");

        const tunerCard =
            document.getElementById(
                "pincabos-dmd-overlay-only-v4"
            );

        if (
            !fullDmdCard
            || !valuesCard
            || !tunerCard
        ) {
            return false;
        }

        const mainGrid = fullDmdCard.parentElement;

        if (!mainGrid) {
            return false;
        }

        const formerParents = new Set(
            [
                tunerCard.parentElement,
                valuesCard.parentElement
            ].filter(Boolean)
        );

        /*
         * Retrait visuel seulement.
         * Les routes et configurations DMD globales demeurent intactes.
         */
        if (globalDmdCard) {
            globalDmdCard.remove();
        }

        mainGrid.classList.add(
            "pco-fulldmd-main-grid-v1"
        );

        fullDmdCard.classList.add(
            "pco-fulldmd-full-calibration-v1"
        );

        tunerCard.classList.add(
            "pco-fulldmd-dmd-tuner-v1"
        );

        valuesCard.classList.add(
            "pco-fulldmd-values-span-v1"
        );

        /*
         * Les trois cartes sont réunies dans une seule grille.
         */
        mainGrid.append(
            tunerCard,
            valuesCard
        );

        /*
         * Retire l’ancienne grille de deuxième rangée
         * seulement lorsqu’elle est réellement vide.
         */
        formerParents.forEach(parent => {
            if (
                !parent
                || parent === mainGrid
            ) {
                return;
            }

            const remainingCards =
                Array.from(parent.children).filter(
                    child =>
                        child.matches
                        && child.matches(
                            ".card, .fulldmd-info-card"
                        )
                );

            if (remainingCards.length === 0) {
                parent.remove();
            }
        });

        document.body.classList.add(
            "pco-fulldmd-layout-v1-ready"
        );

        return true;
    }

    function start() {
        installStyle();

        if (applyLayout()) {
            return;
        }

        const observer = new MutationObserver(() => {
            if (applyLayout()) {
                observer.disconnect();
            }
        });

        observer.observe(
            document.documentElement,
            {
                childList: true,
                subtree: true
            }
        );

        window.setTimeout(
            () => observer.disconnect(),
            15000
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            start,
            { once: true }
        );
    } else {
        start();
    }
})();
