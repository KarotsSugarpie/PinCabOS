#!/usr/bin/env python3
"""Fonds d'écran des dalles secondaires pendant l'installation (PINCABOS_INSTALLEUR_DECOR_V1, Yann).

Une fois la disposition appliquée, chaque dalle qui n'est pas le playfield
(backglass, full DMD, topper, dalles non attribuées) reçoit un visuel de la
galerie de démarrage (Miss Tilt en vedette), plein écran, sous le kiosque et
sans jamais prendre le focus (règles « pincabos-decor-N » du kiosk-rc.xml).
Le programme reste jusqu'à ce qu'on le tue (nouvelle application, redémarrage).

PINCABOS_INSTALLEUR_DECOR_ROLE_V1 (cab de Yann, 06/09/2026 : backglass et full DMD
enregistrés à l'envers sans que rien ne le montre) : chaque dalle affiche son
RÔLE en toutes lettres par-dessus le visuel. Une inversion saute aux yeux.

  python3 decor.py --monitors '{"DP-0": "/opt/pincabos/media/splash/paysage2.jpg"}' --labels '{"DP-0": "BACKGLASS"}'
"""
import argparse
import json
import shutil
import subprocess
import sys

TITRE = "pincabos-decor-{n}"     # repris tel quel par kiosk-rc.xml (calque en dessous, jamais le focus)
KIOSQUE = "pincabos-kiosk"        # titre de la fenetre de l'assistant (pincabos-kiosk.py)

CSS = b"""
window { background-color: #050007; }
.role { font-size: 110px; font-weight: 900; color: #ffb000; letter-spacing: 6px;
        background-color: rgba(5, 0, 7, 0.74); border: 4px solid #ff9d3d; border-radius: 28px;
        padding: 18px 70px 26px 76px; }
"""


def rendre_le_focus_au_kiosque():
    """PINCABOS_INSTALLEUR_DECOR_FOCUS_V1 : une fenetre GTK4 qui apparait demande
    l'activation ; openbox la donnait au decor et le clavier de l'assistant se
    perdait (phrase INSTALL PINCABOS, mot de passe Wi-Fi, IP fixe : rien ne
    s'ecrivait). Une fois les fonds poses, le kiosque reprend le focus."""
    xdotool = shutil.which("xdotool")
    if not xdotool:
        return False
    try:
        subprocess.run([xdotool, "search", "--name", f"^{KIOSQUE}$", "windowactivate"],
                       check=False, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return False   # une seule fois (GLib.timeout_add)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--monitors", default="{}", help="JSON {connecteur: chemin d image}")
    ap.add_argument("--labels", default="{}", help="JSON {connecteur: role en toutes lettres}")
    args = ap.parse_args()
    images = json.loads(args.monitors or "{}")
    libelles = json.loads(args.labels or "{}")

    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, GLib, Gtk

    app = Gtk.Application(application_id="org.pincabos.installer.decor")

    def on_activate(app):
        css = Gtk.CssProvider()
        css.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        mons = Gdk.Display.get_default().get_monitors()
        poses = 0
        for i in range(mons.get_n_items()):
            mon = mons.get_item(i)
            connecteur = mon.get_connector() or ""
            chemin = images.get(connecteur)
            if not chemin:
                continue
            win = Gtk.ApplicationWindow(application=app)
            win.set_decorated(False)
            win.set_title(TITRE.format(n=i + 1))
            win.set_focusable(False)
            pic = Gtk.Picture.new_for_filename(chemin)
            pic.set_content_fit(Gtk.ContentFit.COVER)
            texte = str(libelles.get(connecteur) or "").strip()
            if texte:
                overlay = Gtk.Overlay()
                overlay.set_child(pic)
                role = Gtk.Label(label=texte)
                role.add_css_class("role")
                role.set_halign(Gtk.Align.CENTER)
                role.set_valign(Gtk.Align.END)
                role.set_margin_bottom(90)
                overlay.add_overlay(role)
                win.set_child(overlay)
            else:
                win.set_child(pic)
            win.fullscreen_on_monitor(mon)
            # set_visible, pas present() : present() demande l'activation et openbox
            # donnait le focus clavier au decor (DECOR_FOCUS_V1).
            win.set_visible(True)
            poses += 1
        if poses == 0:
            print("aucune dalle a habiller", file=sys.stderr)
            app.quit()
            return
        GLib.timeout_add(700, rendre_le_focus_au_kiosque)

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
