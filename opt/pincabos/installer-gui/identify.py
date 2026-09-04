#!/usr/bin/env python3
"""Numérote chaque dalle du cab pendant l'installation (PINCABOS_INSTALLEUR_ECRANS_V1).

Une fenêtre GTK 4 plein écran par moniteur : un grand numéro, le nom de la
sortie, le rôle proposé, la taille. Fermeture automatique. GTK est déjà là
pour le kiosque WebKit ; feh/convert/xdotool de l'outil du cab installé ne
le sont pas dans une session d'installation.

  python3 identify.py --seconds 6 --labels '{"HDMI-0": {"number": 1, "role": "Playfield"}}'
"""
import argparse
import json
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

CSS = b"""
window { background-color: #160a1e; }
.num { font-size: 260px; font-weight: 900; color: #ff9d3d; }
.name { font-size: 42px; font-weight: 700; color: #f0e6f4; }
.role { font-size: 34px; color: #ffb000; }
.geo { font-size: 24px; color: #8b7697; }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--labels", default="{}")
    args = ap.parse_args()
    labels = json.loads(args.labels or "{}")
    secondes = max(2, min(30, args.seconds))

    app = Gtk.Application(application_id="org.pincabos.installer.identify")

    def on_activate(app):
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        mons = Gdk.Display.get_default().get_monitors()
        n = mons.get_n_items()
        if n == 0:
            print("aucun moniteur", file=sys.stderr)
            app.quit()
            return
        for i in range(n):
            mon = mons.get_item(i)
            connector = mon.get_connector() or f"#{i + 1}"
            geo = mon.get_geometry()
            info = labels.get(connector, {})
            numero = info.get("number", i + 1)
            role = info.get("role", "")
            win = Gtk.ApplicationWindow(application=app)
            win.set_decorated(False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER, halign=Gtk.Align.CENTER)
            for texte, classe in ((str(numero), "num"), (connector, "name"), (role, "role"), (f"{geo.width} × {geo.height}", "geo")):
                if not texte:
                    continue
                lab = Gtk.Label(label=texte)
                lab.add_css_class(classe)
                box.append(lab)
            win.set_child(box)
            win.present()
            win.fullscreen_on_monitor(mon)
        GLib.timeout_add(secondes * 1000, lambda: (app.quit(), GLib.SOURCE_REMOVE)[1])

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
