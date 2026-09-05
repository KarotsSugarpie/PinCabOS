#!/usr/bin/env python3
"""Kiosk plein ecran du GUI installer : WebKitGTK sous X11 + openbox.

Leger (~80 Mo avec ses deps) la ou Chromium/snap est impraticable dans un
live server. Lance par pincabos-kiosk-session, via xinit.
"""
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, GLib, Gtk, WebKit  # noqa: E402

URL = "http://127.0.0.1:8046/"

# PINCABOS_KIOSK_NO_WHITE_FLASH_V1
# Fond du wizard : la fenetre et la WebView sont peintes avec, pour qu'aucune
# surface blanche n'apparaisse avant le premier rendu.
BACKGROUND = "#050007"
PRESENT_TIMEOUT_MS = 4000


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    win.set_decorated(False)

    # PINCABOS_KIOSK_THEME_SOMBRE_V1
    # Les listes deroulantes (<select>) du wizard sont des popups GTK natifs :
    # sans ceci elles sortent en Adwaita clair, noir sur blanc, hors du theme.
    Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)

    css = Gtk.CssProvider()
    css.load_from_data(
        ("window, window > * { background-color: %s; }" % BACKGROUND).encode())
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), css,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    view = WebKit.WebView()
    s = view.get_settings()
    s.set_enable_developer_extras(False)

    rgba = Gdk.RGBA()
    rgba.parse(BACKGROUND)
    view.set_background_color(rgba)

    presented = False

    def present_once(*_args):
        nonlocal presented
        if not presented:
            presented = True
            win.present()
        return GLib.SOURCE_REMOVE

    def on_load_changed(_view, event):
        # COMMITTED : le document est engage, le fond du wizard est en place.
        if event >= WebKit.LoadEvent.COMMITTED:
            present_once()

    view.connect("load-changed", on_load_changed)
    # Filet : une page qui ne repond pas ne doit pas laisser le kiosk invisible
    # (un kiosk qui ne tient pas finit en panne franche, pincabos-installer-failure).
    GLib.timeout_add(PRESENT_TIMEOUT_MS, present_once)

    view.load_uri(URL)
    win.set_child(view)
    win.fullscreen()

    # PINCABOS_KIOSK_SUIT_LE_PLAYFIELD_V1
    # L'étape Écrans peut changer de playfield et déplacer les sorties : le
    # wizard écrit la sortie retenue dans /run/pincabos/kiosk-target et le
    # kiosque s'y replace en plein écran. Sans ce suivi, l'assistant resterait
    # sur l'ancienne dalle, parfois devenue le fronton.
    cible = {"connector": "", "geometrie": None}

    def geometrie(mon):
        g = mon.get_geometry()
        return (g.x, g.y, g.width, g.height)

    def suivre_le_playfield():
        # PINCABOS_KIOSK_SUIT_LA_GEOMETRIE_V1 : la dalle peut garder son nom et
        # changer de mode ou de position (xrandr de l'etape Ecrans) ; la fenetre
        # se replace, repasse devant et rend le focus a la WebView (molette).
        try:
            nom = Path("/run/pincabos/kiosk-target").read_text(encoding="utf-8").strip()
        except OSError:
            nom = cible["connector"]
        mons = Gdk.Display.get_default().get_monitors()
        for i in range(mons.get_n_items()):
            mon = mons.get_item(i)
            if nom and mon.get_connector() != nom:
                continue
            if nom != cible["connector"] or geometrie(mon) != cible["geometrie"]:
                win.unfullscreen()
                win.fullscreen_on_monitor(mon)
                win.present()
                view.grab_focus()
                # PINCABOS_KIOSK_ZOOM_4K_V1 : l assistant est dessine pour ~1280-1920 px de large ;
                # sur une dalle 4K (mode natif applique par l etape Ecrans) il est agrandi 2x.
                g = mon.get_geometry()
                view.set_zoom_level(2.0 if max(g.width, g.height) >= 3000 else 1.0)
                cible["connector"] = nom
                cible["geometrie"] = geometrie(mon)
            break
        return GLib.SOURCE_CONTINUE

    GLib.timeout_add(700, suivre_le_playfield)


app = Gtk.Application(application_id="org.pincabos.installer.kiosk")
app.connect("activate", on_activate)
app.run(None)
