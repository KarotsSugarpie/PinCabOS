#!/usr/bin/env python3
"""Numérote chaque dalle du cab pendant l'installation (PINCABOS_INSTALLEUR_ECRANS_V1).

PINCABOS_INSTALLEUR_IDENTIFY_OVERLAY_V1 (Yann) : un badge dans le coin de chaque
dalle, par-dessus ce qui s'y affiche, sans prendre le focus ni couvrir
l'assistant ; plus de fenêtre plein écran. Le placement par dalle est confié à
openbox (règles « pincabos-identify-N » du kiosk-rc.xml : coin haut gauche du
moniteur N, calque au-dessus, jamais le focus) : GTK 4 ne positionne pas ses
fenêtres lui-même sous X11.

PINCABOS_INSTALLEUR_IDENTIFY_XINERAMA_V1 (cab de Yann, 06/09/2026) : le moniteur
N d'openbox est le N-ième écran Xinerama (ordre des CRTC : HDMI-0, DP-0, DP-2 sur
le cab), alors que GTK énumère les moniteurs dans l'ordre RandR (HDMI-0, DP-2,
DP-0). Le badge du i-ième moniteur GTK partait sur le i-ième écran openbox : la
dalle DP-2 affichait « 2 · DP-0 · Backglass » et Yann, qui lisait juste, a
enregistré le backglass sur DP-0. Le numéro d'openbox est désormais retrouvé
par la géométrie de la dalle dans la liste Xinerama (xdpyinfo), jamais par
l'index GTK.

  python3 identify.py --seconds 6 --labels '{"HDMI-0": {"number": 1, "role": "Playfield"}}'
"""
import argparse
import json
import re
import subprocess
import sys

TITRE = "pincabos-identify-{n}"     # repris tel quel par kiosk-rc.xml (position par moniteur)
HEAD = re.compile(r"head\s+#(\d+):\s*(\d+)x(\d+)\s*@\s*(-?\d+),(-?\d+)")

CSS = b"""
window { background-color: #160a1e; }
.badge { padding: 14px 26px 16px 22px; border: 3px solid #ff9d3d; border-radius: 14px; background-color: #160a1e; }
.num { font-size: 120px; font-weight: 900; color: #ff9d3d; }
.name { font-size: 26px; font-weight: 700; color: #f0e6f4; }
.role { font-size: 24px; color: #ffb000; }
.geo { font-size: 17px; color: #8b7697; }
"""


def heads_xinerama(texte: str) -> list:
    """[(x, y, w, h)] dans l'ordre des écrans Xinerama (= moniteurs d'openbox), depuis
    `xdpyinfo -ext XINERAMA` : « head #0: 3840x2160 @ 0,0 »."""
    heads = {}
    for m in HEAD.finditer(texte or ""):
        heads[int(m.group(1))] = (int(m.group(4)), int(m.group(5)), int(m.group(2)), int(m.group(3)))
    return [heads[i] for i in sorted(heads)]


def numero_openbox(geometrie: tuple, heads: list, defaut: int) -> int:
    """Numéro de moniteur openbox (1 = premier écran Xinerama) de la dalle dont la
    géométrie X (x, y, w, h) est donnée ; `defaut` si la liste ne la contient pas."""
    for i, h in enumerate(heads):
        if tuple(h) == tuple(geometrie):
            return i + 1
    return defaut


def lire_heads(run=subprocess.run) -> list:
    try:
        r = run(["xdpyinfo", "-ext", "XINERAMA"], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    return heads_xinerama(r.stdout if r.returncode == 0 else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=6)
    ap.add_argument("--labels", default="{}")
    args = ap.parse_args()
    labels = json.loads(args.labels or "{}")
    secondes = max(2, min(30, args.seconds))

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    heads = lire_heads()
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
            # la dalle d'openbox est celle qui porte cette géométrie, pas le i-ième moniteur GTK
            win.set_title(TITRE.format(n=numero_openbox((geo.x, geo.y, geo.width, geo.height), heads, i + 1)))
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
