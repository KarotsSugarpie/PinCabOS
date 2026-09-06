#!/usr/bin/env python3
"""B2S de démonstration pour les tables d'exemple de PinCabOS (PINCABOS_SAMPLE_B2S_V1, Yann).

Les deux tables livrées par VPX (Nudge, Example) n'ont pas de backglass : en jeu,
la fenêtre Backglass et le Score View restent noirs. On leur fabrique un
.directb2s générique : sur le backglass, un visuel Miss Tilt de la galerie de
démarrage avec le logo Visual Pinball et celui de PinCabOS ; sur le full DMD,
le logo Visual Pinball sur fond noir. Même structure qu'un B2S « full dmd »
courant (TableType 3, DMDType 3 : image DMD sur le troisième écran).

Les images sont composées ici, sur le cab, avec GdkPixbuf (livré avec GTK) :
rien à embarquer de lourd dans le dépôt.

  pincabos-sample-b2s.py --vpx "/home/pinball/Tables/PinCabOS Calibration Nudge/PinCabOS Calibration Nudge.vpx" --key nudge
"""
from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import os
import sys
from pathlib import Path

GALERIE = Path("/opt/pincabos/media/splash")
LOGO_VPX = Path("/opt/pincabos/web/static/pincabos-assets/vpx-wordmark.png")
LOGO_PCO = Path("/opt/pincabos/web/static/pincabos-logo.png")
LARGEUR, HAUTEUR = 1920, 1080


def visuel_pour(cle: str, galerie: Path = GALERIE) -> Path | None:
    """Un paysage de la galerie, toujours le même pour une clé donnée."""
    paysages = sorted(p for p in galerie.glob("paysage*") if p.suffix.lower() in (".png", ".jpg", ".jpeg"))
    if not paysages:
        return None
    i = int(hashlib.sha256(cle.encode("utf-8")).hexdigest(), 16) % len(paysages)
    return paysages[i]


def xml_b2s(nom: str, backglass_b64: str, dmd_b64: str, vignette_b64: str) -> str:
    """Fichier .directb2s minimal mais complet : ce que VPX (B2SLegacy) lit."""
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    n = esc(nom)
    return (
        '<DirectB2SData Version="1.26">\n'
        f'  <Name Value="{n}" />\n'
        '  <TableType Value="3" />\n'
        '  <DMDType Value="3" />\n'
        '  <DMDDefaultLocation LocX="0" LocY="0" />\n'
        '  <GrillHeight Value="0" />\n'
        '  <ProjectGUID Value="6F1C2D3E-0000-4000-8000-50494E434142" />\n'
        '  <ProjectGUID2 Value="6F1C2D3E-0000-4000-8000-50494E434143" />\n'
        '  <AssemblyGUID Value="6F1C2D3E-0000-4000-8000-50494E434144" />\n'
        f'  <VSName Value="{n}" />\n'
        '  <DualBackglass Value="0" />\n'
        '  <Author Value="PinCabOS" />\n'
        '  <Artwork Value="PinCabOS - Miss Tilt" />\n'
        '  <GameName Value="" />\n'
        '  <AddEMDefaults Value="0" />\n'
        '  <CommType Value="1" />\n'
        '  <DestType Value="1" />\n'
        '  <NumberOfPlayers Value="4" />\n'
        '  <B2SDataCount Value="0" />\n'
        '  <ReelType Value="" />\n'
        '  <UseDream7LEDs Value="0" />\n'
        '  <D7Glow Value="0" />\n'
        '  <D7Thickness Value="0" />\n'
        '  <D7Shear Value="0" />\n'
        '  <ReelColor Value="255.69.0" />\n'
        '  <ReelRollingDirection Value="0" />\n'
        '  <ReelRollingInterval Value="0" />\n'
        '  <ReelIntermediateImageCount Value="0" />\n'
        '  <Animations />\n'
        '  <Scores ReelCountOfIntermediates="0" ReelRollingDirection="Up" ReelRollingInterval="0" />\n'
        '  <Illumination />\n'
        '  <Images>\n'
        f'    <ThumbnailImage Value="{vignette_b64}" />\n'
        f'    <BackglassImage Value="{backglass_b64}" FileName="pincabos-backglass.png" />\n'
        f'    <DMDImage Value="{dmd_b64}" FileName="pincabos-dmd.png" />\n'
        '  </Images>\n'
        '</DirectB2SData>\n'
    )


# ---------------------------------------------------------------- images (GdkPixbuf)

def _pixbuf():
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    return GdkPixbuf


def couvrir(pb, largeur: int, hauteur: int):
    """Mise à l'échelle « cover » puis recadrage centré."""
    GdkPixbuf = _pixbuf()
    w, h = pb.get_width(), pb.get_height()
    echelle = max(largeur / w, hauteur / h)
    sw, sh = max(largeur, round(w * echelle)), max(hauteur, round(h * echelle))
    grand = pb.scale_simple(sw, sh, GdkPixbuf.InterpType.BILINEAR)
    return grand.new_subpixbuf((sw - largeur) // 2, (sh - hauteur) // 2, largeur, hauteur).copy()


def poser(fond, logo, x: int, y: int, largeur: int):
    """Compose `logo` (avec alpha) sur `fond`, redimensionné à `largeur` px, coin haut gauche en (x, y)."""
    GdkPixbuf = _pixbuf()
    ratio = largeur / logo.get_width()
    lh = max(1, round(logo.get_height() * ratio))
    logo.composite(fond, x, y, min(largeur, fond.get_width() - x), min(lh, fond.get_height() - y),
                   x, y, ratio, ratio, GdkPixbuf.InterpType.BILINEAR, 255)


def png_b64(pb) -> str:
    ok, donnees = pb.save_to_bufferv("png", [], [])
    if not ok:
        raise RuntimeError("PNG non encode")
    return base64.b64encode(bytes(donnees)).decode("ascii")


def composer(visuel: Path, logo_vpx: Path, logo_pco: Path) -> tuple[str, str, str]:
    GdkPixbuf = _pixbuf()
    fond = couvrir(GdkPixbuf.Pixbuf.new_from_file(str(visuel)), LARGEUR, HAUTEUR)
    vpx =GdkPixbuf.Pixbuf.new_from_file(str(logo_vpx)) if logo_vpx.is_file() else None
    pco = GdkPixbuf.Pixbuf.new_from_file(str(logo_pco)) if logo_pco.is_file() else None
    if pco is not None and not pco.get_has_alpha():
        pco = pco.add_alpha(False, 0, 0, 0)
    if vpx is not None:
        lv = round(LARGEUR * 0.30)
        poser(fond, vpx, LARGEUR - lv - 60, HAUTEUR - round(vpx.get_height() * lv / vpx.get_width()) - 50, lv)
    if pco is not None:
        poser(fond, pco, 40, 40, 150)
    dmd = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, LARGEUR, HAUTEUR)
    dmd.fill(0x000000FF)
    if vpx is not None:
        lv = round(LARGEUR * 0.55)
        lh = round(vpx.get_height() * lv / vpx.get_width())
        poser(dmd, vpx, (LARGEUR - lv) // 2, (HAUTEUR - lh) // 2, lv)
    vignette = fond.scale_simple(32, 32, GdkPixbuf.InterpType.BILINEAR)
    return png_b64(fond), png_b64(dmd), png_b64(vignette)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--vpx", required=True, help="chemin de la table (.vpx) ; le .directb2s va a cote")
    ap.add_argument("--key", default="", help="cle de la table d exemple (choix du visuel)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv[1:])
    vpx = Path(a.vpx)
    if not vpx.is_file():
        print(f"table absente : {vpx}", file=sys.stderr)
        return 2
    cible = vpx.with_suffix(".directb2s")
    if cible.exists() and not a.force:
        print(f"deja present : {cible}")
        return 0
    visuel = visuel_pour(a.key or vpx.stem)
    if visuel is None:
        print("aucun visuel paysage dans la galerie : pas de B2S", file=sys.stderr)
        return 1
    try:
        bg, dmd, vignette = composer(visuel, LOGO_VPX, LOGO_PCO)
    except Exception as exc:   # GdkPixbuf absent, image illisible : la table reste jouable sans B2S
        print(f"B2S non compose ({exc})", file=sys.stderr)
        return 1
    tmp = cible.with_suffix(".directb2s.tmp")
    tmp.write_text(xml_b2s(vpx.stem, bg, dmd, vignette), encoding="utf-8")
    os.replace(tmp, cible)
    print(f"B2S ecrit : {cible} (visuel {visuel.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
