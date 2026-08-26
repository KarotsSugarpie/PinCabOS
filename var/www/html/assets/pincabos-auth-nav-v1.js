




/*
 * ==============================================================
 * PINCABOS_GLOBAL_HEADER_V6
 * Header canonique global pincabos.cc
 * ==============================================================
 */

(function () {
    "use strict";

    const VERSION = "PINCABOS_GLOBAL_HEADER_V6";

    const LANGUAGE_KEY =
        "pincabos_language";

    const PRIMARY = [
        {
            href: "/",
            fr: "Accueil",
            en: "Home",
            key: "home"
        },
        {
            href: "/about/",
            fr: "À propos",
            en: "About",
            key: "about"
        },
        {
            href: "/lobby/",
            fr: "Lobby",
            en: "Lobby",
            key: "lobby"
        },
        
        {
            href: "/login/",
            fr: "Connexion",
            en: "Sign in",
            key: "login"
        }
    ];

    const AUTH = [
        {
            href: "/user/account/",
            fr: "Mon compte",
            en: "My account",
            key: "account"
        },
        {
            href: "/download/",
            fr: "Téléchargement",
            en: "Download",
            key: "download"
        },
        {
            href: "/updates/",
            fr: "Mises à jour",
            en: "Updates",
            key: "updates"
        },
        {
            href: "/tables/",
            fr: "Tables",
            en: "Tables",
            key: "tables"
        }
    ];


    function currentLanguage() {
        let value = "fr";

        try {
            value =
                window.localStorage.getItem(
                    LANGUAGE_KEY
                ) || "fr";
        } catch (error) {
            value = "fr";
        }

        return value === "en"
            ? "en"
            : "fr";
    }


    function normalPath() {
        let path =
            window.location.pathname || "/";

        if (!path.startsWith("/")) {
            path = "/" + path;
        }

        return path;
    }


    function isActive(key) {
        const path = normalPath();

        switch (key) {
            case "home":
                return path === "/";

            case "about":
                return path.startsWith("/about");

            case "lobby":
                return path.startsWith("/lobby");

            case "register":
                return path.startsWith("/register");

            case "login":
                return (
                    path.startsWith("/login")
                    || path.startsWith("/admin")
                );

            case "account":
                return path.startsWith(
                    "/user/account"
                );

            case "download":
                return path.startsWith(
                    "/download"
                );

            case "updates":
                return path.startsWith(
                    "/updates"
                );

            case "tables":
                return (
                    path === "/tables"
                    || path.startsWith("/tables/")
                );

            case "admin":
                return (
                    path.startsWith(
                        "/user/iso-manager"
                    )
                    || path.startsWith(
                        "/tables-manager"
                    )
                );

            default:
                return false;
        }
    }


    function makeLink(item) {
        const link =
            document.createElement("a");

        link.href = item.href;

        link.dataset.pcoFr =
            item.fr;

        link.dataset.pcoEn =
            item.en;

        link.dataset.pcoKey =
            item.key;

        if (isActive(item.key)) {
            link.classList.add("active");
        }

        return link;
    }


    function updateHeaderLanguage(
        header,
        lang
    ) {
        header
            .querySelectorAll(
                "[data-pco-fr][data-pco-en]"
            )
            .forEach(function (element) {
                element.textContent =
                    lang === "en"
                        ? element.dataset.pcoEn
                        : element.dataset.pcoFr;
            });

        header
            .querySelectorAll(
                "[data-set-lang]"
            )
            .forEach(function (button) {
                button.classList.toggle(
                    "active",
                    button.dataset.setLang === lang
                );
            });
    }


    function signalLanguage(lang) {
        try {
            window.dispatchEvent(
                new CustomEvent(
                    "pincabos:language",
                    {
                        detail: {
                            language: lang
                        }
                    }
                )
            );
        } catch (error) {
            // Le header reste fonctionnel
            // même sans CustomEvent.
        }
    }


    function selectLanguage(
        header,
        lang
    ) {
        lang =
            lang === "en"
                ? "en"
                : "fr";

        try {
            window.localStorage.setItem(
                LANGUAGE_KEY,
                lang
            );
        } catch (error) {
            // localStorage indisponible :
            // le header fonctionne quand même.
        }

        document.documentElement.lang =
            lang;

        updateHeaderLanguage(
            header,
            lang
        );

        signalLanguage(lang);
    }


    function renderHeader(header) {
        header.classList.add(
            "pco-global-header-v6"
        );

        header.dataset.pcoHeaderVersion =
            VERSION;

        header.innerHTML = "";

        const brand =
            document.createElement("a");

        brand.className =
            "pc-brand";

        brand.href = "/";

        brand.setAttribute(
            "aria-label",
            "PinCabOS - Accueil"
        );

        const logo =
            document.createElement("img");

        logo.src =
            "/assets/img/logo5.png?v=20260826-023209";

        logo.alt =
            "PinCabOS";

        logo.className =
            "pco-header-logo5";

        brand.appendChild(logo);


        const mobile =
            document.createElement("div");

        mobile.className =
            "pc-mobile-nav";


        const primary =
            document.createElement("nav");

        primary.className =
            "pc-nav pco-global-primary";

        primary.setAttribute(
            "aria-label",
            "Navigation principale"
        );

        PRIMARY.forEach(function (item) {
            primary.appendChild(
                makeLink(item)
            );
        });


        const languages =
            document.createElement("div");

        languages.className =
            "pc-language";


        const fr =
            document.createElement("button");

        fr.type = "button";
        fr.dataset.setLang = "fr";
        fr.textContent = "FR";


        const en =
            document.createElement("button");

        en.type = "button";
        en.dataset.setLang = "en";
        en.textContent = "English";


        languages.appendChild(fr);
        languages.appendChild(en);

        mobile.appendChild(primary);
        mobile.appendChild(languages);


        const authRow =
            document.createElement("div");

        authRow.className =
            "pco-auth-row";


        const authNav =
            document.createElement("nav");

        authNav.className =
            "pco-auth-nav";

        authNav.setAttribute(
            "aria-label",
            "Navigation du compte"
        );

        authRow.appendChild(authNav);


        header.appendChild(brand);
        header.appendChild(mobile);
        header.appendChild(authRow);


        languages
            .querySelectorAll(
                "[data-set-lang]"
            )
            .forEach(function (button) {

                button.addEventListener(
                    "click",
                    function () {
                        selectLanguage(
                            header,
                            button.dataset.setLang
                        );
                    }
                );

            });


        updateHeaderLanguage(
            header,
            currentLanguage()
        );

        return {
            header: header,
            authRow: authRow,
            authNav: authNav
        };
    }


    async function currentUser() {
        try {
            const response =
                await fetch(
                    "/api/me",
                    {
                        method: "GET",
                        credentials:
                            "same-origin",
                        cache: "no-store",
                        headers: {
                            "Accept":
                                "application/json"
                        }
                    }
                );

            if (!response.ok) {
                return null;
            }

            const payload =
                await response.json();

            if (
                !payload
                || !payload.user
            ) {
                return null;
            }

            return payload.user;

        } catch (error) {
            return null;
        }
    }


    async function logout() {

        /* PINCABOS_MENU_LOGOUT_FINAL_V31 */

        window.location.assign(
            "/logout"
        );
    }


    function renderAuthenticated(
        state,
        user
    ) {
        const nav =
            state.authNav;

        nav.innerHTML = "";

        AUTH.forEach(function (item) {
            nav.appendChild(
                makeLink(item)
            );
        });


        if (
            String(
                user.role || ""
            ).toLowerCase() === "admin"
        ) {
            nav.appendChild(
                makeLink({
                    href:
                        "/user/iso-manager/",
                    fr:
                        "Gestion Admin",
                    en:
                        "Admin management",
                    key:
                        "admin"
                })
            );
        }


        const signOut =
            makeLink({
                href: "/logout",
                fr: "Déconnexion",
                en: "Sign out",
                key: "logout"
            });

        signOut.classList.add(
            "pco-logout"
        );

        signOut.addEventListener(
            "click",
            function (event) {
                event.preventDefault();
                logout();
            }
        );

        nav.appendChild(signOut);

        state.authRow.classList.add(
            "pco-authenticated"
        );

        updateHeaderLanguage(
            state.header,
            currentLanguage()
        );
    }


    async function boot() {
        const headers =
            Array.from(
                document.querySelectorAll(
                    ".pc-header"
                )
            );

        if (!headers.length) {
            return;
        }

        const states =
            headers.map(renderHeader);

        const user =
            await currentUser();

        if (!user) {
            return;
        }

        states.forEach(
            function (state) {
                renderAuthenticated(
                    state,
                    user
                );
            }
        );
    }


    /*
     * Le script est charge avec defer sur le site.
     * Ce garde permet aussi une execution correcte
     * si une page le charge autrement.
     */

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            boot,
            {
                once: true
            }
        );
    } else {
        boot();
    }

})();

/* PINFORGE_GLOBAL_FOOTER_LOADER_458E_START */
(function () {
    "use strict";

    const FOOTER_ID =
        "pincabos-global-footer-v2";

    const LOADER_ATTR =
        "data-pincabos-footer-v2-global-loader";

    const FOOTER_SRC =
        "/assets/pincabos-footer-global-v2.js?v=20260826-footer-github-v11";

    function ensurePinCabOSFooter() {

        if (
            document.getElementById(
                FOOTER_ID
            )
        ) {
            return;
        }

        /*
         * Si une page charge deja V1/V2,
         * ne pas injecter une deuxieme copie.
         */
        if (
            document.querySelector(
                'script[src*="pincabos-footer-global-v2.js"],' +
                'script[src*="pincabos-footer-global-v1.js"]'
            )
        ) {
            return;
        }

        if (
            document.querySelector(
                "script[" + LOADER_ATTR + "]"
            )
        ) {
            return;
        }

        const script =
            document.createElement(
                "script"
            );

        script.src =
            FOOTER_SRC;

        script.setAttribute(
            LOADER_ATTR,
            "footer-global-458e-20260825-143650"
        );

        script.async = false;

        document.head.appendChild(
            script
        );
    }

    ensurePinCabOSFooter();

})();
/* PINFORGE_GLOBAL_FOOTER_LOADER_458E_END */


/* PINCABOS_REMOVE_REGISTER_MENU_V11_START */
(function () {
    "use strict";

    function clean() {

        document
            .querySelectorAll(
                ".pc-nav a"
            )
            .forEach(function (link) {

                var label =
                    String(
                        link.textContent || ""
                    )
                    .normalize("NFD")
                    .replace(
                        /[\u0300-\u036f]/g,
                        ""
                    )
                    .toLowerCase();

                var href =
                    String(
                        link.getAttribute(
                            "href"
                        ) || ""
                    )
                    .toLowerCase();

                if (
                    (
                        label.indexOf(
                            "creer un compte"
                        ) !== -1
                        ||
                        label.indexOf(
                            "create account"
                        ) !== -1
                        ||
                        label.trim()
                            === "register"
                    )
                    &&
                    (
                        href.indexOf(
                            "register"
                        ) !== -1
                        ||
                        href.indexOf(
                            "#register"
                        ) !== -1
                    )
                ) {
                    link.remove();
                }
            });
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            clean
        );
    } else {
        clean();
    }

    setTimeout(clean, 0);
    setTimeout(clean, 250);
    setTimeout(clean, 750);

    window.addEventListener(
        "pincabos:language",
        clean
    );

})();
/* PINCABOS_REMOVE_REGISTER_MENU_V11_END */



/* ============================================================
   PINCABOS_HEADER_HOME_STYLE_V6_LOADER
   ============================================================ */

(function () {
    "use strict";

    if (
        document.querySelector(
            'script[data-pco-header-home-style-v6]'
        )
    ) {
        return;
    }


    const script =
        document.createElement("script");


    script.src =
        "/assets/" +
        "pincabos-header-home-style-v6.js" +
        "?v=20260825-header-home-style-v6";


    script.defer =
        true;


    script.setAttribute(
        "data-pco-header-home-style-v6",
        "1"
    );


    document.head.appendChild(
        script
    );

})();





