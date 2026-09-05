#!/usr/bin/env python3
"""Numérote chaque dalle du cab pendant l'installation (PINCABOS_INSTALLEUR_ECRANS_V1).

PINCABOS_INSTALLEUR_IDENTIFY_OVERLAY_V1 (Yann) : un badge dans le coin de chaque
dalle, par-dessus ce qui s'y affiche, sans prendre le focus ni couvrir
l'assistant ; plus de fenêtre plein écran. Le placement par dalle est confié à
openbox (règles « pincabos-identify-N » du kiosk-rc.xml : coin haut gauche du
moniteur N, calque au-dessus, jamais le focus) : GTK 4 ne positionne pas ses
fenêtres lui-même sous X11.

  python3 identify.py --seconds 6 --labels '{"HDMI-0": {"number": 1, "role": "Playfield"}}'
"""
import argparse
import json
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

TITRE = "pincabos-identify-{n}"     # repris tel quel par kiosk-rc.xml (position par moniteur)

CSS = b"""
window { background-color: #160a1e; }
.badge { padding: 14px 26px 16px 22px; border: 3px solid #ff9d3d; border-radius: 14px; background-color: #160a1e; }
.num { font-size: 120px; font-weight: 900; color: #ff9d3d; }
.name { font-size: 26px; font-weight: 700; color: #f0e6f4; }
.role { font-size: 24px; color: #ffb000; }
.geo { font-size: 17px; color: #8b7697; }
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
            win.set_resizable(False)
            win.set_title(TITRE.format(n=i + 1))
            ligne = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18, valign=Gtk.Align.CENTER)
            ligne.add_css_class("badge")
            num = Gtk.Label(label=str(numero))
            num.add_css_class("num")
            ligne.append(num)
            colonne = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
            for texte, classe in ((connector, "name"), (role, "role"), (f"{geo.width} × {geo.height}", "geo")):
                if not texte:
                    continue
                lab = Gtk.Label(label=texte, xalign=0)
                lab.add_css_class(classe)
                colonne.append(lab)
            ligne.append(colonne)
            win.set_child(ligne)
            win.present()
        GLib.timeout_add(secondes * 1000, lambda: (app.quit(), GLib.SOURCE_REMOVE)[1])

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
