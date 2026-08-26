# PinCabOS — Configuration système requise / System Requirements

English follows below.

---

## 🇫🇷 Français

### Prérequis matériels et graphiques

PinCabOS installe et gère directement sa base système. L'utilisateur n'a donc pas à préinstaller Ubuntu ni à fournir un kernel Linux spécifique.

Les prérequis concernent principalement le matériel et la compatibilité graphique :

- Architecture : **x86-64 / AMD64**
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
- stabilité après mises à jour système PinCabOS ;
- audio / SSF ;
- périphériques USB et contrôleurs du cabinet.

### Stockage

Le minimum de 128 Go concerne uniquement une installation de base.

Une bibliothèque de tables, médias, ROM, PuP-Packs, sauvegardes et packages peut rapidement nécessiter plusieurs centaines de gigaoctets. Pour un cabinet réel, **500 Go est un minimum pratique** et **1 To ou plus est recommandé**.

### Principe de compatibilité PinCabOS

Une machine n'est pas considérée compatible uniquement parce que l'installation PinCabOS se termine.

Avant de considérer un cabinet comme compatible PinCabOS, les points suivants doivent être validés :

1. Le matériel démarre correctement avec PinCabOS.
2. Le pilote GPU est chargé correctement.
3. Vulkan fonctionne.
4. Les écrans sont détectés et assignables.
5. L'audio est détecté.
6. Les périphériques USB nécessaires sont présents.
7. VPX démarre et exécute une table de test.
8. VPinFE démarre et peut lancer VPX.
9. Les fonctions PinCabOS essentielles restent stables après redémarrage.

---

## 🇬🇧 English

### Hardware and graphics prerequisites

PinCabOS installs and manages its own system base directly. Users therefore do not need to preinstall Ubuntu or provide a specific Linux kernel.

The prerequisites mainly concern hardware and graphics compatibility:

- Architecture: **x86-64 / AMD64**
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
- stability after PinCabOS system updates;
- audio / SSF;
- USB devices and cabinet controllers.

### Storage

The 128 GB minimum only covers a basic installation.

A real collection of tables, media, ROMs, PuP-Packs, backups and packages can quickly require several hundred gigabytes. For an actual cabinet, **500 GB is a practical minimum** and **1 TB or more is recommended**.

### PinCabOS compatibility principle

A machine is not considered compatible simply because the PinCabOS installation completes.

Before a cabinet is considered PinCabOS-compatible, the following must be validated:

1. The hardware boots correctly with PinCabOS.
2. The GPU driver loads correctly.
3. Vulkan works.
4. Displays are detected and can be assigned.
5. Audio devices are detected.
6. Required USB peripherals are present.
7. VPX starts and runs a test table.
8. VPinFE starts and can launch VPX.
9. Essential PinCabOS functions remain stable after reboot.
