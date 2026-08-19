PinCabOS

English will follow 🇬🇧

PinCabOS est la couche système du pincab. Il relie le matériel du cabinet, Visual Pinball X (VPX), VPinFE et les outils de configuration dans une interface cohérente pensée pour l’installation, l’utilisation, le diagnostic et la maintenance d’un pincab.

État du projet : Alpha 2.0 — build de développement

🇫🇷 Français

Un environnement complet pour votre pincab

PinCabOS centralise les fonctions essentielles d’un cabinet Visual Pinball afin de réduire les manipulations manuelles, garder une configuration cohérente et faciliter le diagnostic lorsqu’un élément ne fonctionne pas comme prévu.

PinCabOS ne remplace pas VPX ou VPinFE :

VPX exécute les tables, la physique, les scripts, les contrôles et le rendu.

VPinFE sert de frontend pour parcourir les tables, les médias et les collections, puis lancer les parties.

PinCabOS relie ces applications au matériel du cabinet et fournit les outils système qui les entourent.

Fonctions principales

Domaine

Fonctions

Dashboard

Interface personnalisable, statuts, raccourcis, contrôles, aperçus live et suivi des opérations

PinCab Explorer

Explorateur de fichiers Web pour tables, sauvegardes, USB, SMB, médias et fichiers de configuration

Smart Import / Export

Analyse et installation structurée d’une table ou création d’un package complet

Batch Smart Import / Export

Traitement de plusieurs packages ou tables avec progression, erreurs et gestion des conflits

Image Studio

Édition intégrée des images PNG, JPG, JPEG et WEBP

VPX

Gestion des chemins, paramètres, écrans, audio, latence et contexte cabinet

VPinFE

Configuration du frontend, tables, collections, wheels, vidéos et médias

GPU et écrans

Détection, attribution Playfield / Backglass / FullDMD, résolutions et géométrie

DMD / FullDMD

Calibration, placement, layouts et AutoArrange

Audio / SSF

Détection des cartes, attribution des rôles et tests des sorties

Inputs

Map Commander, boutons, clavier, plunger, nudge et axes analogiques

DOF

Détection et test des sorties, LED-Wiz, DudesCab, UMX/MX, toys et éclairage

Réseau / SMB / USB

Ethernet, Wi-Fi, partages réseau, imports, exports et stockage externe

Console Web

Accès au terminal Linux directement depuis l’interface

Diagnostic

Services, journaux, widgets live, audits et procédures de récupération

Ordre de configuration recommandé

Pour obtenir un cabinet stable, PinCabOS recommande de configurer les éléments dans cet ordre :

Réseau — commencer en DHCP et vérifier l’accès à la WebApp.

Région et clavier — sélectionner le bon layout avant de mapper les boutons.

GPU et écrans — valider le pilote, Vulkan et les rôles Playfield / Backglass / FullDMD.

Audio et SSF — identifier les cartes et tester chaque sortie.

Inputs — tester les boutons, le plunger, le nudge et les axes analogiques.

VPX — valider les chemins, lancer une table simple et tester le cabinet.

VPinFE — vérifier les chemins, les médias et le lancement depuis le frontend.

DOF — configurer les sorties seulement lorsque VPX, les écrans, l’audio et les contrôles sont stables.

Imports et personnalisation — utiliser Smart Import, Batch, Image Studio et le Dashboard une fois la base validée.

PinCab Explorer

PinCab Explorer permet de gérer le contenu du cabinet depuis un navigateur :

parcourir les dossiers;

créer, renommer, dupliquer ou supprimer;

uploader et télécharger;

créer et extraire des archives ZIP;

ouvrir des images;

visualiser des fichiers;

modifier des fichiers texte et de configuration.

Les fichiers de configuration importants doivent toujours être modifiés avec prudence et après sauvegarde.

Smart Import et Smart Export

Smart Import peut détecter les composants associés à une table, notamment :

table VPX;

Backglass B2S;

ROM;

PuP-Pack;

médias;

fichiers DMD / FullDMD;

INI / POV;

scripts et fichiers complémentaires.

Smart Export permet de reconstruire un package à partir d’une table installée avec ses composants associés.

Pour les grandes bibliothèques, Batch Smart Import et Batch Smart Export permettent de traiter plusieurs tables ou packages dans une seule opération, avec progression et suivi des erreurs.

Dashboard configurable

Le Dashboard est une surface de travail personnalisable. Il peut afficher :

état des services;

table active;

progression des imports et exports;

informations réseau;

volumes audio;

raccourcis vers les outils;

aperçu live du Playfield;

aperçu live du Backglass;

aperçu live du FullDMD.

Chaque utilisateur peut organiser le Dashboard selon son propre cabinet.

Écrans, DMD et FullDMD

PinCabOS attribue des rôles précis aux écrans du cabinet :

Playfield

Backglass

FullDMD

Les outils d’écran permettent de vérifier la détection, les résolutions, la géométrie et la position. L’outil FullDMD permet ensuite de calibrer et placer le DMD, créer des layouts et utiliser AutoArrange.

Audio et SSF

PinCabOS peut gérer différents rôles audio :

Playfield;

SSF;

Backglass;

ROM;

DMD;

musique;

surround;

bass shaker.

La procédure recommandée consiste à détecter les cartes, identifier physiquement les sorties, attribuer les rôles puis tester chaque canal séparément.

Inputs, nudge et plunger

Map Commander relie les contrôles physiques du cabinet aux actions VPX.

Les tests doivent être effectués avec les véritables boutons du pincab. Le plunger analogique doit produire une progression analogique et le nudge peut être vérifié pour la direction, la sensibilité, les inversions et les mouvements parasites.

DOF et sorties

DOF Commander peut être utilisé pour détecter et tester différents périphériques et sorties :

LED-Wiz;

DudesCab;

UMX / MX;

contacteurs;

solénoïdes;

moteurs;

éclairage;

bandes de LED adressables.

Pour protéger le matériel, tester une sortie à la fois, utiliser une courte durée et éviter de laisser un toy actif inutilement.

Sécurité et protection des tables

La philosophie PinCabOS est de corriger le système concerné sans modifier inutilement les tables.

Avant une modification importante :

identifier le fichier ou le service réellement utilisé;

créer une sauvegarde datée;

appliquer une correction ciblée;

valider la syntaxe;

redémarrer uniquement le composant concerné;

vérifier les journaux;

tester le fonctionnement réel;

conserver le backup jusqu’à validation complète.

Les fichiers .vpx, .vbs et .directb2s ne devraient pas être modifiés automatiquement pour corriger un problème de système, d’écran, d’audio ou de service.

Chemins principaux

Base PinCabOS       /opt/pincabos
WebApp              /opt/pincabos/web
Tables              /home/pinball/Tables
VPX INI             /home/pinball/.local/share/VPinballX/10.8/VPinballX.ini
VPinFE INI          /home/pinball/.config/vpinfe/vpinfe.ini
Médias PinCabOS     /opt/pincabos/media
Lecteurs SMB        /home/pinball/NetworkDrives
Journaux            /opt/pincabos/logs

Diagnostic rapide

Les premiers points à vérifier lorsqu’un composant ne répond pas sont généralement :

systemctl status pincabos-webapp.service
systemctl status pincabos-vpinfe.service
journalctl -u pincabos-webapp.service -n 100
journalctl -u pincabos-vpinfe.service -n 100

La méthode recommandée reste : identifier le symptôme → vérifier le service → lire les journaux → vérifier les chemins et droits → sauvegarder → corriger de façon ciblée → tester.

État du projet

PinCabOS est actuellement documenté en Alpha 2.0 / build dev.

Certaines fonctions peuvent dépendre du matériel, du pilote ou du module installé. Les fonctions annoncées comme futures ne doivent pas être considérées comme disponibles avant leur validation dans la version installée.

🇬🇧 English

A complete environment for your virtual pinball cabinet

PinCabOS is the system layer of the pinball cabinet. It connects the cabinet hardware, Visual Pinball X (VPX), VPinFE, and the configuration tools into a coherent environment designed for setup, daily use, diagnostics, and maintenance.

Project status: Alpha 2.0 — development build

PinCabOS does not replace VPX or VPinFE:

VPX runs the tables, physics, scripts, controls, audio, and rendering.

VPinFE is the frontend used to browse tables, media, and collections and to launch games.

PinCabOS connects these applications to the cabinet hardware and provides the system tools around them.

Main features

Area

Features

Dashboard

Customizable interface, service status, shortcuts, controls, live previews, and operation progress

PinCab Explorer

Web file explorer for tables, backups, USB, SMB, media, and configuration files

Smart Import / Export

Structured analysis and installation of a table or creation of a complete package

Batch Smart Import / Export

Multi-package and multi-table processing with progress, errors, and conflict handling

Image Studio

Built-in image editor for PNG, JPG, JPEG, and WEBP

VPX

Paths, settings, displays, audio, latency, and cabinet context

VPinFE

Frontend configuration, tables, collections, wheels, videos, and media

GPU and displays

Detection, Playfield / Backglass / FullDMD roles, resolutions, and geometry

DMD / FullDMD

Calibration, positioning, layouts, and AutoArrange

Audio / SSF

Sound card detection, role assignment, and output testing

Inputs

Map Commander, buttons, keyboard, plunger, nudge, and analog axes

DOF

Output detection and testing, LED-Wiz, DudesCab, UMX/MX, toys, and lighting

Network / SMB / USB

Ethernet, Wi-Fi, network shares, imports, exports, and external storage

Web Console

Direct access to the cabinet Linux terminal from the WebApp

Diagnostics

Services, logs, live widgets, audits, and recovery procedures

Recommended setup order

For a stable cabinet, PinCabOS recommends configuring the system in this order:

Network — start with DHCP and verify access to the WebApp.

Region and keyboard — select the correct keyboard layout before mapping buttons.

GPU and displays — validate the driver, Vulkan, and Playfield / Backglass / FullDMD roles.

Audio and SSF — identify sound devices and test each output.

Inputs — test buttons, plunger, nudge, and analog axes.

VPX — validate paths, launch a simple table, and test the cabinet.

VPinFE — verify paths, media, and launching from the frontend.

DOF — configure outputs only after VPX, displays, audio, and controls are stable.

Imports and customization — use Smart Import, Batch tools, Image Studio, and the Dashboard after the base system is validated.

PinCab Explorer

PinCab Explorer provides browser-based file management for the cabinet:

browse folders;

create, rename, duplicate, or delete items;

upload and download files;

create and extract ZIP archives;

open images;

preview files;

edit text and configuration files.

Important configuration files should always be edited carefully and backed up first.

Smart Import and Smart Export

Smart Import can detect components associated with a table, including:

VPX table;

B2S Backglass;

ROM;

PuP-Pack;

media;

DMD / FullDMD files;

INI / POV files;

scripts and additional files.

Smart Export can rebuild a package from an installed table and its associated components.

For large libraries, Batch Smart Import and Batch Smart Export can process multiple tables or packages in one operation with progress tracking and error reporting.

Customizable Dashboard

The Dashboard is a customizable workspace that can display:

service status;

active table;

import and export progress;

network information;

audio volumes;

tool shortcuts;

live Playfield preview;

live Backglass preview;

live FullDMD preview.

Each user can arrange the Dashboard to match their own cabinet.

Displays, DMD, and FullDMD

PinCabOS assigns specific roles to cabinet displays:

Playfield

Backglass

FullDMD

Display tools help verify detection, resolution, geometry, and positioning. The FullDMD tool can then calibrate and position the DMD, create layouts, and use AutoArrange.

Audio and SSF

PinCabOS can manage multiple audio roles:

Playfield;

SSF;

Backglass;

ROM;

DMD;

music;

surround;

bass shaker.

The recommended procedure is to detect the sound cards, physically identify the outputs, assign roles, and test each channel separately.

Inputs, nudge, and plunger

Map Commander connects the cabinet's physical controls to VPX actions.

Testing should be performed with the actual cabinet buttons. An analog plunger should provide analog progression, while the nudge visualizer can be used to check direction, sensitivity, inversion, and unwanted movement.

DOF and outputs

DOF Commander can detect and test multiple output devices:

LED-Wiz;

DudesCab;

UMX / MX;

contactors;

solenoids;

motors;

lighting;

addressable LED strips.

To protect the hardware, test one output at a time, use short durations, and avoid leaving a toy active unnecessarily.

Safety and table protection

The PinCabOS approach is to fix the actual system component involved without unnecessarily modifying table files.

Before an important change:

identify the file or service actually in use;

create a dated backup;

apply one targeted change;

validate syntax;

restart only the affected component;

review the logs;

test the real behavior;

keep the backup until the change is fully validated.

Files such as .vpx, .vbs, and .directb2s should not be automatically modified to solve system, display, audio, or service issues.

Main paths

PinCabOS base       /opt/pincabos
WebApp              /opt/pincabos/web
Tables              /home/pinball/Tables
VPX INI             /home/pinball/.local/share/VPinballX/10.8/VPinballX.ini
VPinFE INI          /home/pinball/.config/vpinfe/vpinfe.ini
PinCabOS media      /opt/pincabos/media
SMB drives          /home/pinball/NetworkDrives
Logs                /opt/pincabos/logs

Quick diagnostics

Common first checks include:

systemctl status pincabos-webapp.service
systemctl status pincabos-vpinfe.service
journalctl -u pincabos-webapp.service -n 100
journalctl -u pincabos-vpinfe.service -n 100

The recommended troubleshooting method is: identify the symptom → check the service → read the logs → verify paths and permissions → create a backup → apply a targeted fix → test.

Project status

PinCabOS is currently documented as Alpha 2.0 / dev build.

Some features may depend on the installed hardware, drivers, or modules. Features described as future work should not be considered available until they have been validated in the installed version.

Documentation

The complete PinCabOS guide covers installation, configuration, daily use, troubleshooting, recovery procedures, important paths, logs, and table-protection best practices.

PinCabOS — Installation, configuration, use and troubleshooting.
