#!/usr/bin/env python3
"""Generer les annonces de position, dans les langues de l'installeur.

PINCABOS_AUDIO_VOIX_V1

Les echantillons parles fournis par alsa-utils sont en anglais et fixes. Sur
un cabinet installe en francais, s'entendre annoncer « rear left » pendant
qu'on cherche quelle prise porte quoi n'aide personne.

Les annonces sont donc produites ici, a la construction de l'image, et
livrees comme des fichiers : aucune synthese vocale n'est installee sur le
cabinet, et le test fonctionne sans reseau.
"""
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "media/audio-voix"

VOIX = {"fr": "fr", "en": "en-gb", "es": "es", "it": "it"}

TEXTES = {
    "front-left": {
        "fr": "Avant gauche", "en": "Front left",
        "es": "Frontal izquierdo", "it": "Anteriore sinistro",
    },
    "front-right": {
        "fr": "Avant droit", "en": "Front right",
        "es": "Frontal derecho", "it": "Anteriore destro",
    },
    "front-center": {
        "fr": "Centre", "en": "Center",
        "es": "Central", "it": "Centrale",
    },
    "lfe": {
        "fr": "Caisson de basses", "en": "Subwoofer",
        "es": "Subgrave", "it": "Subwoofer",
    },
    "rear-left": {
        "fr": "Arrière gauche", "en": "Rear left",
        "es": "Trasero izquierdo", "it": "Posteriore sinistro",
    },
    "rear-right": {
        "fr": "Arrière droit", "en": "Rear right",
        "es": "Trasero derecho", "it": "Posteriore destro",
    },
    "rear-center": {
        "fr": "Arrière centre", "en": "Rear center",
        "es": "Trasero central", "it": "Posteriore centrale",
    },
    "side-left": {
        "fr": "Latéral gauche", "en": "Side left",
        "es": "Lateral izquierdo", "it": "Laterale sinistro",
    },
    "side-right": {
        "fr": "Latéral droit", "en": "Side right",
        "es": "Lateral derecho", "it": "Laterale destro",
    },
    "mono": {
        "fr": "Mono", "en": "Mono", "es": "Mono", "it": "Mono",
    },
}


def main() -> int:
    total = 0
    for langue, voix in VOIX.items():
        dossier = RACINE / langue
        dossier.mkdir(parents=True, exist_ok=True)

        for position, traductions in TEXTES.items():
            texte = traductions[langue]
            brut = dossier / f".{position}.brut.wav"
            final = dossier / f"{position}.opus"

            synthese = subprocess.run(
                ["espeak-ng", "-v", voix, "-s", "150", "-w", str(brut), texte],
                capture_output=True, text=True,
            )
            if synthese.returncode != 0 or not brut.exists():
                print(f"NOGO {langue}/{position}: {synthese.stderr.strip()}")
                return 1

            # Format unique : mono 48 kHz, celui des cartes son des cabinets.
            conversion = subprocess.run(
                # Opus a 24 kb/s : 40 annonces tiennent en 230 Kio, ce qui
                # compte sur une image que l on veut garder sous les 3 Go.
                ["ffmpeg", "-v", "error", "-y", "-i", str(brut),
                 "-ac", "1", "-c:a", "libopus", "-b:a", "24k", str(final)],
                capture_output=True, text=True,
            )
            brut.unlink(missing_ok=True)

            if conversion.returncode != 0 or not final.exists():
                print(f"NOGO conversion {langue}/{position}: {conversion.stderr.strip()}")
                return 1

            total += 1

    poids = sum(f.stat().st_size for f in RACINE.rglob("*.opus"))
    print(f"  {total} annonces generees dans {len(VOIX)} langues "
          f"({poids // 1024} Kio au total)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
