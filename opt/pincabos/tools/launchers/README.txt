PinCabOS — Trois launchers Original / PuP-Pack / Hybride
============================================================

Launchers installés
-------------------
1. pincabos-launch-hybrid.sh
   - Détecte automatiquement les modes de la table.
   - Original + PuP disponibles : affiche PCOSGamesChoices.png.
   - Un seul mode disponible : démarre immédiatement sans afficher l'image.
   - Aucun mode prouvé : utilise le mode par défaut de PinCabOS-Hybrid.json,
     sinon Original.

2. pincabos-launch-original.sh
   - Masque temporairement le dossier pupvideos/pupvideo.
   - Lance la table en mode Original.
   - Restaure automatiquement le PuP-Pack après la fermeture de VPX.

3. pincabos-launch-puppack.sh
   - Vérifie qu'un PuP-Pack est détecté.
   - Restaure le dossier PuP si nécessaire.
   - Lance la table avec le PuP-Pack actif.

Contrôles du chooser
--------------------
Flipper gauche / Left Shift / Left : Original
Flipper droit  / Right Shift / Right : PuP-Pack
Launch / Plunger / Enter / Space : confirmer

Détection
---------
Original :
- ROM locale ou globale associée à la table;
- ou .directb2s portant le même nom que la table.

PuP-Pack :
- dossier pupvideos ou pupvideo;
- contenant screens.pup et/ou des médias.

Option par table
----------------
Un fichier PinCabOS-Hybrid.json peut définir :

{
  "default": "original",
  "timeout": 0,
  "rom": "nom_de_rom",
  "availability": {
    "original": true,
    "pup": true
  }
}

timeout = 0 signifie : attendre la confirmation sans limite.

Diagnostic sans lancer
----------------------
/opt/pincabos/launchers/pincabos-launch-hybrid.sh --detect-only "/chemin/table.vpx"
