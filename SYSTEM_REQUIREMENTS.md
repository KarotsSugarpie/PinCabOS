# PinCabOS — Configuration système requise / System Requirements

English follows below.

---

## 🇫🇷 Français

### Base système officielle

PinCabOS cible actuellement :

- Architecture : **x86-64 / AMD64**
- Système : **Ubuntu 26.04 LTS 64 bits**
- Kernel : **Linux 7.0 (pile GA Ubuntu 26.04 LTS)**
- API graphique : **Vulkan fonctionnel requis**
- Firmware recommandé : **UEFI x86-64**

Ces valeurs constituent les exigences du projet PinCabOS. Elles ne doivent pas être interprétées comme des exigences officielles publiées par VPX ou VPinFE.

### Niveaux de configuration

| Composant | Minimum PinCabOS — 1080p | Recommandé | Recommandé 4K / 3 écrans |
|---|---|---|---|
| CPU | 4 cœurs / 4 threads, environ 3 GHz | 6 cœurs ou plus | 6 cœurs ou plus, génération récente |
| Exemples CPU | Intel Core i5-6500 / AMD Ryzen équivalent | Ryzen 5 3600 / Intel Core i5-10400 ou mieux | Ryzen 5 / Core i5 récent ou mieux |
| RAM | 8 Go | 16 Go | 16 Go ou plus |
| GPU | GPU dédié compatible Vulkan | NVIDIA RTX 2060 / classe équivalente | NVIDIA RTX 3060 Ti / RTX 4060 ou mieux |
| VRAM | 6 Go | 6 Go ou plus | 8 Go ou plus recommandé |
| Stockage système | SSD 128 Go | SSD/NVMe 500 Go | NVMe 1 To ou plus |
| Réseau | Ethernet ou Wi-Fi fonctionnel | Ethernet 1 Gb/s | Ethernet 1 Gb/s |
| USB | USB 2.0/3.x | USB 3.x | USB 3.x avec capacité suffisante pour les contrôleurs du cabinet |
| Affichage cible | 1080p | 1080p / 1440p | Playfield 4K + Backglass + FullDMD |

### Minimum PinCabOS

Le niveau **Minimum PinCabOS** vise un cabinet 1080p capable d'exécuter PinCabOS, VPX et VPinFE dans des conditions normales.

Configuration de référence minimale :

- Intel Core i5-6500 ou CPU x86-64 comparable ;
- 8 Go de RAM ;
- NVIDIA GTX 1060 6 Go ou GPU dédié de classe comparable avec Vulkan fonctionnel ;
- SSD 128 Go minimum ;
- Ubuntu 26.04 LTS 64 bits ;
- kernel Linux 7.0 ;
- Vulkan validé avant l'utilisation de VPX.

Certaines tables lourdes, PuP-Packs, médias haute résolution ou configurations multi-écrans peuvent dépasser ce niveau.

### Configuration recommandée

Pour une installation confortable et durable :

- CPU 6 cœurs ou plus ;
- 16 Go de RAM ;
- NVIDIA RTX 2060 ou mieux ;
- SSD/NVMe 500 Go ou plus ;
- Ethernet 1 Gb/s recommandé.

### Configuration recommandée 4K / 3 écrans

Pour un cabinet avec Playfield 4K, Backglass et FullDMD :

- Ryzen 5 3600 / Intel Core i5-10400 ou mieux ;
- 16 Go de RAM ou plus ;
- NVIDIA RTX 3060 Ti / RTX 4060 ou mieux ;
- 8 Go de VRAM ou plus recommandé ;
- NVMe 1 To ou plus recommandé.

Les tables VPX, les shaders, les PuP-Packs, le nombre d'écrans, la résolution et le taux de rafraîchissement peuvent faire varier fortement les besoins GPU et CPU.

### GPU et support officiel

PinCabOS exige un GPU dont la pile graphique fournit **Vulkan correctement fonctionnel**.

Le support matériel officiellement annoncé doit rester limité aux configurations réellement validées par le projet. Tant qu'une matrice de tests complète AMD/Intel n'a pas été exécutée, une configuration qui fonctionne techniquement ne doit pas automatiquement être présentée comme officiellement supportée.

Pour les builds de développement actuels, la validation doit notamment couvrir :

- installation du pilote ;
- Vulkan ;
- VPX/BGFX ;
- VPinFE ;
- Playfield / Backglass / FullDMD ;
- reprise après mise à jour du kernel ;
- audio / SSF ;
- périphériques USB et contrôleurs du cabinet.

### Stockage

Le minimum de 128 Go concerne uniquement une installation de base.

Une bibliothèque de tables, médias, ROM, PuP-Packs, sauvegardes et packages peut rapidement nécessiter plusieurs centaines de gigaoctets. Pour un cabinet réel, **500 Go est un minimum pratique** et **1 To ou plus est recommandé**.

### Principe de compatibilité PinCabOS

Une machine n'est pas considérée compatible uniquement parce qu'Ubuntu démarre.

Avant de considérer un cabinet comme compatible PinCabOS, les points suivants doivent être validés :

1. Ubuntu 26.04 LTS démarre normalement.
2. Le kernel Linux 7.0 fonctionne avec le matériel du cabinet.
3. Le pilote GPU est chargé correctement.
4. Vulkan fonctionne.
5. Les écrans sont détectés et assignables.
6. L'audio est détecté.
7. Les périphériques USB nécessaires sont présents.
8. VPX démarre et exécute une table de test.
9. VPinFE démarre et peut lancer VPX.
10. Les fonctions PinCabOS essentielles restent stables après redémarrage.

---

## 🇬🇧 English

### Official system base

PinCabOS currently targets:

- Architecture: **x86-64 / AMD64**
- Operating system: **Ubuntu 26.04 LTS 64-bit**
- Kernel: **Linux 7.0 (Ubuntu 26.04 LTS GA stack)**
- Graphics API: **working Vulkan support required**
- Recommended firmware: **x86-64 UEFI**

These values are project-defined PinCabOS requirements. They should not be interpreted as official minimum requirements published by VPX or VPinFE.

### Configuration tiers

| Component | PinCabOS Minimum — 1080p | Recommended | Recommended 4K / 3 displays |
|---|---|---|---|
| CPU | 4 cores / 4 threads, around 3 GHz | 6 cores or more | 6 cores or more, recent generation |
| CPU examples | Intel Core i5-6500 / comparable AMD Ryzen | Ryzen 5 3600 / Intel Core i5-10400 or better | Recent Ryzen 5 / Core i5 or better |
| RAM | 8 GB | 16 GB | 16 GB or more |
| GPU | Dedicated Vulkan-capable GPU | NVIDIA RTX 2060 / equivalent class | NVIDIA RTX 3060 Ti / RTX 4060 or better |
| VRAM | 6 GB | 6 GB or more | 8 GB or more recommended |
| System storage | 128 GB SSD | 500 GB SSD/NVMe | 1 TB NVMe or more |
| Network | Working Ethernet or Wi-Fi | 1 Gb/s Ethernet | 1 Gb/s Ethernet |
| USB | USB 2.0/3.x | USB 3.x | USB 3.x with enough capacity for cabinet controllers |
| Display target | 1080p | 1080p / 1440p | 4K Playfield + Backglass + FullDMD |

### PinCabOS Minimum

The **PinCabOS Minimum** tier targets a 1080p cabinet capable of running PinCabOS, VPX and VPinFE under normal conditions.

Minimum reference configuration:

- Intel Core i5-6500 or comparable x86-64 CPU;
- 8 GB RAM;
- NVIDIA GTX 1060 6 GB or comparable dedicated GPU with working Vulkan support;
- 128 GB SSD minimum;
- Ubuntu 26.04 LTS 64-bit;
- Linux kernel 7.0;
- Vulkan validated before using VPX.

Heavy tables, PuP-Packs, high-resolution media and multi-display configurations may exceed this tier.

### Recommended configuration

For a comfortable long-term installation:

- 6-core CPU or better;
- 16 GB RAM;
- NVIDIA RTX 2060 or better;
- 500 GB or larger SSD/NVMe;
- 1 Gb/s Ethernet recommended.

### Recommended 4K / 3-display configuration

For a cabinet using a 4K Playfield, Backglass and FullDMD:

- Ryzen 5 3600 / Intel Core i5-10400 or better;
- 16 GB RAM or more;
- NVIDIA RTX 3060 Ti / RTX 4060 or better;
- 8 GB VRAM or more recommended;
- 1 TB NVMe or more recommended.

VPX tables, shaders, PuP-Packs, display count, resolution and refresh rate can significantly change GPU and CPU requirements.

### GPU and official support

PinCabOS requires a GPU whose graphics stack provides **working Vulkan support**.

Official hardware support should remain limited to configurations that have actually been validated by the project. Until a complete AMD/Intel test matrix has been executed, hardware that happens to work should not automatically be presented as officially supported.

Current development validation should include:

- driver installation;
- Vulkan;
- VPX/BGFX;
- VPinFE;
- Playfield / Backglass / FullDMD;
- recovery after kernel updates;
- audio / SSF;
- USB devices and cabinet controllers.

### Storage

The 128 GB minimum only covers a basic installation.

A real collection of tables, media, ROMs, PuP-Packs, backups and packages can quickly require several hundred gigabytes. For an actual cabinet, **500 GB is a practical minimum** and **1 TB or more is recommended**.

### PinCabOS compatibility principle

A machine is not considered compatible simply because Ubuntu boots.

Before a cabinet is considered PinCabOS-compatible, the following must be validated:

1. Ubuntu 26.04 LTS boots normally.
2. Linux kernel 7.0 works with the cabinet hardware.
3. The GPU driver loads correctly.
4. Vulkan works.
5. Displays are detected and can be assigned.
6. Audio devices are detected.
7. Required USB peripherals are present.
8. VPX starts and runs a test table.
9. VPinFE starts and can launch VPX.
10. Essential PinCabOS functions remain stable after reboot.
