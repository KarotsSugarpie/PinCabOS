#!/usr/bin/env python3
"""Kiosk plein ecran du GUI installer : WebKitGTK dans cage (Wayland).

Leger (~80 Mo avec ses deps) la ou Chromium/snap est impraticable dans un
live server. Lance par cage : `cage -- pincabos-kiosk.py`.
"""
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit  # noqa: E402

URL = "http://127.0.0.1:8046/"


def on_activate(app):
    win = Gtk.ApplicationWindow(application=app)
    view = WebKit.WebView()
    s = view.get_settings()
    s.set_enable_developer_extras(False)
    view.load_uri(URL)
    win.set_child(view)
    win.fullscreen()
    win.present()


app = Gtk.Application(application_id="org.pincabos.installer.kiosk")
app.connect("activate", on_activate)
app.run(None)
