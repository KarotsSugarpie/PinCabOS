#!/usr/bin/env python3
"""Generer les annonces de position, dans les langues de l'installeur.

PINCABOS_AUDIO_VOIX_V2

Les echantillons parles fournis par alsa-utils sont en anglais et fixes. Sur
un cabinet installe en francais, s'entendre annoncer « rear left » pendant
qu'on cherche quelle prise porte quoi n'aide personne.

Les annonces sont produites ici, a la construction de l'image, et livrees
comme des fichiers : aucune synthese vocale n'est installee sur le cabinet, et
le test fonctionne sans reseau.

Deux exigences dictent la fabrication.

La voix : pico2wave (SVOX Pico) plutot qu'espeak-ng. espeak est un
synthetiseur a formants — intelligible, mais franchement robotique. Pico
concatene des echantillons enregistres : c'est nettement plus humain, ca reste
minuscule, et il couvre exactement les quatre langues de l'installeur.

Le niveau : toutes les annonces sont ramenees au meme niveau percu. Sans cela
« Avant gauche » et « Avant droit » sortent a des volumes differents — de
simples mots differents suffisent a creer six decibels d'ecart — et on croit
entendre un desequilibre d'enceintes la ou il n'y a qu'un desequilibre
d'enregistrement. Un test de cablage doit comparer des enceintes, pas des mots.

Prerequis (poste de construction uniquement) : libttspico-utils, ffmpeg.

  pincabos-generer-voix-audio.py
"""
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1] / "media/audio-voix"

# PINCABOS_AUDIO_VOIX_DE_V1 — les cinq langues de l'installeur, pas quatre.
VOIX = {
    "fr": "fr-FR",
    "en": "en-GB",
    "es": "es-ES",
    "it": "it-IT",
    "de": "de-DE",
}

# Niveau moyen vise, et plafond de crete. Le niveau moyen fait la sensation de
# volume ; le plafond evite l ecretage sur les annonces les plus percussives.
NIVEAU_MOYEN_CIBLE = -20.0
CRETE_MAXIMALE = -3.0

# Retire les silences de tete et de queue : pico en laisse, et une annonce qui
# tarde a sortir se confond avec un haut-parleur muet.
TAILLAGE = (
    "silenceremove=start_periods=1:start_silence=0.03:"
    "start_threshold=-50dB:detection=peak,"
    "areverse,"
    "silenceremove=start_periods=1:start_silence=0.08:"
    "start_threshold=-50dB:detection=peak,"
    "areverse"
)

TEXTES = {
    "front-left": {
        "fr": "Avant gauche", "en": "Front left",
        "es": "Frontal izquierdo", "it": "Anteriore sinistro",
        "de": "Vorne links",
    },
    "front-right": {
        "fr": "Avant droit", "en": "Front right",
        "es": "Frontal derecho", "it": "Anteriore destro",
        "de": "Vorne rechts",
    },
    "front-center": {
        "fr": "Centre", "en": "Center",
        "es": "Central", "it": "Centrale",
        "de": "Mitte",
    },
    "lfe": {
        "fr": "Caisson de basses", "en": "Subwoofer",
        "es": "Subgrave", "it": "Subwoofer",
        "de": "Subwoofer",
    },
    "rear-left": {
        "fr": "Arrière gauche", "en": "Rear left",
        "es": "Trasero izquierdo", "it": "Posteriore sinistro",
        "de": "Hinten links",
    },
    "rear-right": {
        "fr": "Arrière droit", "en": "Rear right",
        "es": "Trasero derecho", "it": "Posteriore destro",
        "de": "Hinten rechts",
    },
    "rear-center": {
        "fr": "Arrière centre", "en": "Rear center",
        "es": "Trasero central", "it": "Posteriore centrale",
        "de": "Hinten Mitte",
    },
    "side-left": {
        "fr": "Latéral gauche", "en": "Side left",
        "es": "Lateral izquierdo", "it": "Laterale sinistro",
        "de": "Seite links",
    },
    "side-right": {
        "fr": "Latéral droit", "en": "Side right",
        "es": "Lateral derecho", "it": "Laterale destro",
        "de": "Seite rechts",
    },
    "mono": {
        "fr": "Mono", "en": "Mono", "es": "Mono", "it": "Mono",
        "de": "Mono",
    },
}


def ffmpeg(*args, mesure=False):
    resultat = subprocess.run(
        ["ffmpeg", "-hide_banner", "-y", *args],
        capture_output=True, text=True,
    )
    if resultat.returncode != 0:
        raise RuntimeError((resultat.stderr or "").strip()[-400:])
    return resultat.stderr if mesure else ""


def niveaux(chemin):
    """Niveau moyen et niveau de crete du fichier, en decibels."""
    rapport = ffmpeg("-i", str(chemin), "-af", "volumedetect",
                     "-f", "null", "/dev/null", mesure=True)
    moyen = re.search(r"mean_volume:\s*(-?[\d.]+) dB", rapport)
    crete = re.search(r"max_volume:\s*(-?[\d.]+) dB", rapport)
    if not moyen or not crete:
        raise RuntimeError(f"niveaux illisibles pour {chemin}")
    return float(moyen.group(1)), float(crete.group(1))


def main() -> int:
    if not subprocess.run(["which", "pico2wave"],
                          capture_output=True).returncode == 0:
        print("NOGO: pico2wave absent (paquet libttspico-utils)")
        return 1

    total = 0
    ecarts = []

    for langue, voix in VOIX.items():
        dossier = RACINE / langue
        dossier.mkdir(parents=True, exist_ok=True)

        for position, traductions in TEXTES.items():
            texte = traductions[langue]
            brut = dossier / f".{position}.brut.wav"
            taille = dossier / f".{position}.taille.wav"
            final = dossier / f"{position}.opus"

            synthese = subprocess.run(
                ["pico2wave", "-l", voix, "-w", str(brut), texte],
                capture_output=True, text=True,
            )
            if synthese.returncode != 0 or not brut.exists():
                print(f"NOGO {langue}/{position}: {synthese.stderr.strip()}")
                return 1

            try:
                ffmpeg("-i", str(brut), "-af", TAILLAGE,
                       "-ac", "1", "-ar", "48000", str(taille))

                moyen, crete = niveaux(taille)
                gain = min(NIVEAU_MOYEN_CIBLE - moyen, CRETE_MAXIMALE - crete)
                ecarts.append(moyen + gain)

                # Opus a 24 kb/s : les quarante annonces tiennent en 230 Kio,
                # ce qui compte sur une image qu on veut garder sous 3 Go.
                ffmpeg("-i", str(taille), "-af", f"volume={gain:.2f}dB",
                       "-ac", "1", "-c:a", "libopus", "-b:a", "24k", str(final))
            except RuntimeError as exc:
                print(f"NOGO {langue}/{position}: {exc}")
                return 1
            finally:
                brut.unlink(missing_ok=True)
                taille.unlink(missing_ok=True)

            total += 1

    poids = sum(f.stat().st_size for f in RACINE.rglob("*.opus"))
    dispersion = max(ecarts) - min(ecarts) if ecarts else 0.0
    print(f"  {total} annonces generees dans {len(VOIX)} langues "
          f"({poids // 1024} Kio au total)")
    print(f"  ecart de niveau residuel : {dispersion:.2f} dB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
