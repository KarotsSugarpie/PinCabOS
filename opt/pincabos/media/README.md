# Medias PinCabOS

## Video d'intro au demarrage

Deposez votre video ici sous le nom **`boot-video.mp4`** : elle sera jouee
plein ecran sur le playfield (avec le son) pendant le chargement de VPinFE,
puis sa **derniere image reste affichee** jusqu'a ce que le frontend soit
pret — aucun ecran noir. Aucun fichier = demarrage normal.

- N'importe quel bouton du cab passe l'intro (et l'image finale).
- La video est adaptee a l'ecran playfield du cabinet (letterbox, jamais de
  deformation) et tournee automatiquement si son orientation differe de
  celle de l'ecran (meme convention que les medias playfield des tables).
- Reglages optionnels dans `/opt/pincabos/config/boot-video.conf` :

```ini
BOOT_VIDEO_ENABLED=1            # 0 pour desactiver sans supprimer la video
BOOT_VIDEO_ROTATE=auto          # auto | 0 | 90 | 180 | 270
BOOT_VIDEO_MAX_SECONDS=60       # duree maximale de lecture
BOOT_VIDEO_VOLUME=100           # 0-100
BOOT_VIDEO_HOLD_MAX_SECONDS=90  # duree max de l'image finale
```

Si la video apparait a l'envers sur votre cabinet, mettez
`BOOT_VIDEO_ROTATE=90`.
