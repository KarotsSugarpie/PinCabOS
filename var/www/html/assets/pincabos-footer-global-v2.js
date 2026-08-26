/* PINCABOS FOOTER GLOBAL V2 */

(function () {
    "use strict";

    const FOOTER_ID = "pincabos-global-footer-v2";

    const CSS_URL =
        "/assets/pincabos-footer-global-v22-shift-right.css?v=20260825-footer-v22-shift-right";

    const QR_URL =
        "/assets/img/pcbo_pay_qr_bbb5611b723f953dc3fad1e42e7dbd66fe9fa8d53de4293c.png?v=20260825-footer-v2-final";

    const DONATE_URL =
        "https://www.paypal.com/ncp/payment/SE79XX45T2NBG";


    /* PINCABOS_FOOTER_GITHUB_DATA_V11 */

    const TESTERS_URL =
        "https://raw.githubusercontent.com/KarotsSugarpie/PinCabOS/main/docs/site/footer.json";

    const RELEASES_URL =
        "https://api.github.com/repos/KarotsSugarpie/PinCabOS/releases?per_page=10";

    const GITHUB_CACHE_KEY =
        "pincabos-footer-github-data-v11";

    const GITHUB_CACHE_TTL =
        15 * 60 * 1000;


    function loadCss() {

        document
            .querySelectorAll(
                'link[data-pincabos-footer-v2]'
            )
            .forEach(function (item) {
                item.remove();
            });

        const css = document.createElement("link");

        css.rel = "stylesheet";
        css.href = CSS_URL;

        css.setAttribute(
            "data-pincabos-footer-v2",
            "20260825-footer-v2-final"
        );

        document.head.appendChild(css);
    }


    function removeOldFooters() {

        document
            .querySelectorAll(
                "#pincabos-global-footer-v1," +
                "#pincabos-global-footer-v2," +
                "footer.footer"
            )
            .forEach(function (node) {
                node.remove();
            });
    }


    function language() {

        const htmlLang =
            (
                document.documentElement.lang || ""
            ).toLowerCase();

        return htmlLang.startsWith("en")
            ? "en"
            : "fr";
    }


    function applyLanguage(root) {

        const lang = language();

        root
            .querySelectorAll("[data-fr][data-en]")
            .forEach(function (node) {

                node.textContent =
                    node.getAttribute(
                        lang === "en"
                            ? "data-en"
                            : "data-fr"
                    );
            });
    }


    function cacheRead() {

        try {

            const raw =
                window.localStorage.getItem(
                    GITHUB_CACHE_KEY
                );

            if (!raw) {
                return null;
            }

            const parsed =
                JSON.parse(raw);

            if (
                !parsed ||
                typeof parsed !== "object"
            ) {
                return null;
            }

            return parsed;

        } catch (error) {

            return null;
        }
    }


    function cacheWrite(value) {

        try {

            window.localStorage.setItem(
                GITHUB_CACHE_KEY,
                JSON.stringify(value)
            );

        } catch (error) {
            /* cache facultatif */
        }
    }


    async function fetchJson(url) {

        const response =
            await fetch(
                url,
                {
                    method: "GET",
                    cache: "no-store",
                    headers: {
                        "Accept":
                            "application/vnd.github+json"
                    }
                }
            );

        if (!response.ok) {

            throw new Error(
                "HTTP " +
                response.status +
                " pour " +
                url
            );
        }

        return await response.json();
    }


    function renderTesters(
        footer,
        testers
    ) {

        if (!Array.isArray(testers)) {
            return;
        }


        const target =
            footer.querySelector(
                "[data-pcgf-testers]"
            );


        if (!target) {
            return;
        }


        const valid =
            testers.filter(
                function (item) {

                    return (
                        item &&
                        typeof item.name === "string" &&
                        item.name.trim() !== ""
                    );
                }
            );


        if (!valid.length) {
            return;
        }


        target.textContent = "";


        valid.forEach(
            function (item) {

                const badge =
                    document.createElement(
                        "span"
                    );

                badge.className =
                    "pcgf-badge";


                const stars =
                    Math.max(
                        1,
                        Math.min(
                            3,
                            Number(
                                item.stars || 1
                            )
                        )
                    );


                const left =
                    document.createElement(
                        "span"
                    );

                left.className =
                    "pcgf-star";

                left.textContent =
                    "★".repeat(stars);


                const right =
                    document.createElement(
                        "span"
                    );

                right.className =
                    "pcgf-star";

                right.textContent =
                    "★".repeat(stars);


                badge.appendChild(left);

                badge.appendChild(
                    document.createTextNode(
                        "\u00a0" +
                        item.name.trim() +
                        "\u00a0"
                    )
                );

                badge.appendChild(right);

                target.appendChild(
                    badge
                );
            }
        );
    }


    function renderRelease(
        footer,
        release
    ) {

        if (
            !release ||
            typeof release !== "object"
        ) {
            return;
        }


        const versionNode =
            footer.querySelector(
                "[data-pcgf-version]"
            );


        const buildNode =
            footer.querySelector(
                "[data-pcgf-build]"
            );


        let releaseName =
            String(
                release.name || ""
            ).trim();


        const tag =
            String(
                release.tag_name || ""
            ).trim();


        releaseName =
            releaseName.replace(
                /^PinCabOS\s+/i,
                ""
            );


        if (
            versionNode &&
            releaseName
        ) {

            versionNode.textContent =
                releaseName;
        }


        if (
            buildNode &&
            tag
        ) {

            buildNode.textContent =
                tag;
        }
    }


    function applyGithubData(
        footer,
        data
    ) {

        if (
            !data ||
            typeof data !== "object"
        ) {
            return;
        }


        if (
            Array.isArray(
                data.testers
            )
        ) {

            renderTesters(
                footer,
                data.testers
            );
        }


        if (data.release) {

            renderRelease(
                footer,
                data.release
            );
        }
    }


    async function refreshGithubFooter(
        footer
    ) {

        const now =
            Date.now();


        const cached =
            cacheRead();


        if (cached) {

            applyGithubData(
                footer,
                cached
            );


            if (
                cached.fetched_at &&
                now -
                Number(
                    cached.fetched_at
                ) <
                GITHUB_CACHE_TTL
            ) {

                return;
            }
        }


        const results =
            await Promise.allSettled(
                [
                    fetchJson(
                        TESTERS_URL
                    ),
                    fetchJson(
                        RELEASES_URL
                    )
                ]
            );


        const next = {
            fetched_at: now
        };


        if (
            cached &&
            Array.isArray(
                cached.testers
            )
        ) {

            next.testers =
                cached.testers;
        }


        if (
            cached &&
            cached.release
        ) {

            next.release =
                cached.release;
        }


        if (
            results[0].status ===
            "fulfilled"
        ) {

            const payload =
                results[0].value;


            if (
                payload &&
                Array.isArray(
                    payload.testers
                )
            ) {

                next.testers =
                    payload.testers;
            }
        }


        if (
            results[1].status ===
            "fulfilled"
        ) {

            const releases =
                results[1].value;


            if (
                Array.isArray(
                    releases
                )
            ) {

                const release =
                    releases.find(
                        function (item) {

                            return (
                                item &&
                                !item.draft
                            );
                        }
                    );


                if (release) {

                    next.release =
                        release;
                }
            }
        }


        if (
            next.testers ||
            next.release
        ) {

            cacheWrite(
                next
            );


            applyGithubData(
                footer,
                next
            );
        }
    }


    function build() {

        removeOldFooters();

        const footer =
            document.createElement("footer");

        footer.id = FOOTER_ID;

        footer.setAttribute(
            "data-pincabos-footer",
            "v2"
        );

        footer.innerHTML = `
<div class="pcgf-grid">

    <section class="pcgf-support">

        <h2
            class="pcgf-title"
            data-fr="Soutenir PinCabOS"
            data-en="Support PinCabOS"
        >
            Soutenir PinCabOS
        </h2>

        <div class="pcgf-support-layout">

            <a
                class="pcgf-qr-link"
                href="${DONATE_URL}"
                target="_blank"
                rel="noopener noreferrer"
            >
                <img
                    class="pcgf-qr"
                    src="${QR_URL}"
                    alt="QR Code PinCabOS"
                >
            </a>

            <div class="pcgf-support-content">

                <p
                    class="pcgf-support-text"
                    data-fr="Si vous aimez PinCabOS, vous pouvez me le montrer en offrant ce que vous voulez. Merci pour votre soutien."
                    data-en="If you enjoy PinCabOS, you can show your support by contributing whatever you like. Thank you for your support."
                >
                    Si vous aimez PinCabOS, vous pouvez me le
                    montrer en offrant ce que vous voulez.
                    Merci pour votre soutien.
                </p>

                <a
                    class="pcgf-donate"
                    href="${DONATE_URL}"
                    target="_blank"
                    rel="noopener noreferrer"
                    data-fr="Faire un don"
                    data-en="Make a donation"
                >
                    Faire un don
                </a>

                <div
                    class="pcgf-payment"
                    data-fr="Paiement sécurisé par PayPal"
                    data-en="Secure payment by PayPal"
                >
                    Paiement sécurisé par PayPal
                </div>

            </div>

        </div>

    </section>


    <section class="pcgf-founders">

        <h2
            class="pcgf-title"
            data-fr="★★ Testeurs ★ / ★★ Soutiens Fondateurs ★★★"
            data-en="★★ Testers ★ / ★★ Founding Supporters ★★★"
        >
            ★★ Testeurs ★ / ★★ Soutiens Fondateurs ★★★
        </h2>

        <p
            class="pcgf-founders-text"
            data-fr="Merci aux personnes qui aident à tester PinCabOS, rapporter les problèmes, proposer des idées et soutenir le développement du projet."
            data-en="Thanks to everyone helping test PinCabOS, report issues, propose ideas and support the project."
        >
            Merci aux personnes qui aident à tester PinCabOS,
            rapporter les problèmes, proposer des idées et
            soutenir le développement du projet.
        </p>

        <div class="pcgf-badges" data-pcgf-testers>

            <span class="pcgf-badge">
                <span class="pcgf-star">★★</span>
                &nbsp;Karots Sugarpie&nbsp;
                <span class="pcgf-star">★★</span>
            </span>

            <span class="pcgf-badge">
                <span class="pcgf-star">★★</span>
                &nbsp;Yan Fox&nbsp;
                <span class="pcgf-star">★★</span>
            </span>

            <span class="pcgf-badge">
                <span class="pcgf-star">★</span>
                &nbsp;Strung Flo&nbsp;
                <span class="pcgf-star">★</span>
            </span>

            <span class="pcgf-badge">
                <span class="pcgf-star">★</span>
                &nbsp;Olivier Chéron&nbsp;
                <span class="pcgf-star">★</span>
            </span>

        </div>

    </section>


    <section class="pcgf-version">

        <h2
            class="pcgf-title"
            data-fr="Notes de version"
            data-en="Release notes"
        >
            Notes de version
        </h2>

        <dl class="pcgf-meta">

            <dt data-fr="Nom :" data-en="Name :">
                Nom :
            </dt>
            <dd>PinCabOS</dd>

            <dt>Version :</dt>
            <dd data-pcgf-version>Alpha 2.48</dd>

            <dt>Build :</dt>
            <dd data-pcgf-build>alpha2.48-beta.20260826.1</dd>

            <dt data-fr="Canal :" data-en="Channel :">
                Canal :
            </dt>
            <dd>pincabos.cc</dd>

            <dt>Codename :</dt>
            <dd>Stark</dd>

            <dt data-fr="Auteur :" data-en="Author :">
                Auteur :
            </dt>
            <dd>Karots Sugarpie</dd>

            <dt>Site :</dt>
            <dd>
                <a href="https://pincabos.cc/">
                    pincabos.cc
                </a>
            </dd>

        </dl>

    </section>

</div>
`;

        document.body.appendChild(footer);

        applyLanguage(footer);

        refreshGithubFooter(
            footer
        ).catch(
            function (error) {

                console.warn(
                    "PinCabOS footer GitHub:",
                    error
                );
            }
        );
    }


    function init() {

        loadCss();

        /*
         * On attend un court instant pour que les anciens scripts
         * aient fini, puis V2 devient l'unique footer.
         */

        window.setTimeout(
            function () {
                build();
            },
            20
        );

        window.setTimeout(
            function () {

                if (
                    !document.getElementById(
                        FOOTER_ID
                    )
                ) {
                    build();
                }

            },
            350
        );
    }


    if (document.readyState === "loading") {

        document.addEventListener(
            "DOMContentLoaded",
            init,
            {
                once: true
            }
        );

    } else {

        init();
    }


    const observer =
        new MutationObserver(function () {

            const footer =
                document.getElementById(
                    FOOTER_ID
                );

            if (footer) {
                applyLanguage(footer);
            }
        });

    observer.observe(
        document.documentElement,
        {
            attributes: true,
            attributeFilter: ["lang"]
        }
    );

})();
