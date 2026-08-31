# Nettoyage sûr appliqué — 2026-08-31

## GitHub

- 94 fichiers suivis supprimés.
- Déchets de session root, états runtime, anciennes sauvegardes et snapshot d’installation retirés.
- 42 manifestes APT consolidés vers quatre instantanés canoniques.
- Huit scripts historiques de PR retirés après absence de référence détectée.
- Onze patches/artefacts désactivés retirés après confirmation de leur dormance.
- Règles `.gitignore` ajoutées pour empêcher le retour des états générés.

## Cab PinCabOS

L’outil `/usr/local/sbin/pincabos-cleanup-safe-v1` réalise le nettoyage live en deux étapes :

1. `--audit` vérifie la cible et les références actives sans modifier le cab ;
2. `--apply` crée un backup `.tar.zst`, vérifie son SHA-256, puis supprime uniquement les cibles approuvées.

Le rollback est fourni par `--rollback <répertoire-backup>`.

## Protections conservées

Les marqueurs suivants sortent de GitHub, mais ne sont jamais supprimés du cab :

- `/var/lib/pincabos/doctor-firstboot.done`
- `/var/lib/pincabos/firstboot-initramfs-refresh.done`
- `/var/lib/pincabos/firstboot-network-webapp.done`
- `/var/lib/pincabos/hardware-autoconfig.done`
- `/var/lib/pincabos/doctor-last.json`

## Éléments reportés

Aucune suppression n’est faite dans les groupes suivants :

- overlays DOF ;
- pile display-role/screen-topology ;
- doubles modules d’installation ;
- outils Python sans référence automatique mais pouvant être lancés manuellement.

Les réparations et les verrous de modules restent désactivés.
