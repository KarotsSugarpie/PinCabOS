# Module « lancement hybride »

Premier module décrit au format cible de la refonte (manifeste + requis).
Le code vit encore à ses emplacements historiques (`tools/launchers`, `bin`,
`scripts`) ; `manifest.json` est la description de référence — fichiers,
requis, état pendant la partie, tests — et sera la source de la liste
blanche privilégiée et du contrôle « requis satisfiables » en CI.

## Ce que fait le module

1. VPinFE appelle `/opt/pincabos/launchers/pincabos-launch-hybrid.sh`.
2. `launch-core` détecte les modes de la table (Original / PuP-Pack). Si les
   deux existent, le chooser plein écran laisse choisir (flippers, Launch).
3. **Original** : le dossier PuP est masqué le temps de la partie.
   **PuP-Pack** : lien `pupvideos` posé si le pack porte un autre nom
   (VPX ne lit que `pupvideos/`), puis *split* si le pack utilise les écrans
   1/5 : le DMD réel de VPX est incrusté dans la vidéo du pack sur le
   FullDMD (voir ci-dessous).
4. `VPXlauncher.real.sh` applique la politique DMD/FullDMD, place les
   fenêtres une fois, puis `VPXlauncher.pincabos-original.sh` exécute VPX en
   `pinball` avec `-PrefPath`.

## Le split, sans root

Le pack affiche sa vidéo sur le FullDMD (écran 5) ; le DMD réel de VPX n'y a
plus de place. Le split déplace les écrans PuP 1 et 5 vers l'écran PuP 0
(rendu dans la fenêtre Topper de VPX), pose cette fenêtre plein écran sur le
FullDMD, et place le ScoreView (le DMD réel) **au-dessus**, dans le rectangle
calibré de la page FullDMD.

Avant : un montage en *mount namespace* remplaçait `screens.pup` — il
exigeait root, la chaîne tourne en `pinball` : jamais fonctionné.
Maintenant : `screens.pup` est **sauvegardé** (`screens.pup.pincabos-split-avant`),
remplacé par le fichier préparé, puis **restauré** à la sortie. Une partie
interrompue laisse une sauvegarde : le helper la remet en place au lancement
suivant, avant toute lecture.

La géométrie est recalculée **à chaque lancement selon le mode** : rien n'est
persisté, les coordonnées d'un PuP-Pack ne peuvent plus « fuir » dans le mode
Original.
