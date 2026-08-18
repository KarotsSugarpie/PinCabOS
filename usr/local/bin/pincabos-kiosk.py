#!/usr/bin/env python3
"""Kiosk plein ecran du GUI installer : WebKitGTK sous X11 + openbox.

Leger (~80 Mo avec ses deps) la ou Chromium/snap est impraticable dans un
live server. Lance par pincabos-kiosk-session, via xinit.
"""
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
    # Filet : une page qui ne repond pas ne doit pas laisser le kiosk invisible,
    # le repli TUI le prendrait pour un crash.
    GLib.timeout_add(PRESENT_TIMEOUT_MS, present_once)

    view.load_uri(URL)
    win.set_child(view)
    win.fullscreen()


app = Gtk.Application(application_id="org.pincabos.installer.kiosk")
app.connect("activate", on_activate)
app.run(None)
