# PinCabOS-AboutHelp.py
# Généré par PINCABOS — REFACTOR ABOUT/HELP V1.
# Source originale: /opt/pincabos/web/app.py
#
# IMPORTANT:
# Ce fichier est chargé par app.py avec importlib parce que son nom contient un tiret.
# Routes fournies:
#   /help
#   /about

from __future__ import annotations
from pincabos_about_audit import pincabos_about_audit_html
from pincabos_help_guide import pincabos_help_guide_html

# Dépendances injectées par register().
def page(title, body):
    raise RuntimeError("PinCabOS AboutHelp module not registered: page() missing")

def esc(value):
    return str(value)

def pco_path_text(key):
    return ""

def pincabos_version():
    return {"version": "Alpha 1.3", "build": ""}


def help_page():
    ver = pincabos_version() or {}
    version_label = esc(str(ver.get("version") or ver.get("label") or "PinCabOS"))
    build_label = esc(str(ver.get("build") or ""))

    replacements = {
        "__VERSION__": version_label,
        "__BUILD__": build_label or "non spécifié",
        "__VPX_DIR__": esc(pco_path_text("vpx_dir")),
        "__VPX_WRAPPER__": esc(pco_path_text("vpx_wrapper")),
        "__VPINFE_CURRENT__": esc(pco_path_text("vpinfe_current")),
        "__VPINFE_ROOT__": esc(pco_path_text("vpinfe_root")),
    }

    body = r"""
<style>
.pco-help-v24{--a:#ffb000;--b:#ff7900;--line:rgba(255,176,0,.28);--soft:rgba(255,176,0,.09)}
.pco-help-v24 h1,.pco-help-v24 h2,.pco-help-v24 h3{color:var(--a)}
.pco-help-v24 .help-search{width:100%;padding:14px 16px;font-size:18px;border-radius:14px;border:1px solid var(--b);background:#120719;color:#fff;box-sizing:border-box}
.pco-help-v24 .help-toc{columns:2 320px;gap:24px}
.pco-help-v24 .help-toc a{display:block;padding:5px 0;color:#fff;text-decoration:none}
.pco-help-v24 .help-toc a:hover{color:var(--a)}
.pco-help-v24 .help-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:12px}
.pco-help-v24 .help-mini{border:1px solid var(--line);border-radius:14px;padding:12px;background:var(--soft)}
.pco-help-v24 .help-mini strong{color:var(--a)}
.pco-help-v24 .help-note{border-left:5px solid var(--a);background:var(--soft);padding:10px 12px;border-radius:10px;margin:12px 0}
.pco-help-v24 .help-danger{border-left:5px solid #ff5a68;background:rgba(255,90,104,.10);padding:10px 12px;border-radius:10px;margin:12px 0}
.pco-help-v24 .help-good{border-left:5px solid #2ed18a;background:rgba(46,209,138,.10);padding:10px 12px;border-radius:10px;margin:12px 0}
.pco-help-v24 ul,.pco-help-v24 ol{line-height:1.62}
.pco-help-v24 li{margin:5px 0}
.pco-help-v24 code{color:var(--a)}
.pco-help-v24 pre{white-space:pre-wrap;background:rgba(0,0,0,.45);border:1px solid var(--line);border-radius:12px;padding:12px;overflow:auto}
.pco-help-v24 table{width:100%;border-collapse:collapse;margin:10px 0}
.pco-help-v24 th,.pco-help-v24 td{border:1px solid rgba(255,176,0,.22);padding:8px 10px;vertical-align:top}
.pco-help-v24 th{color:var(--a);background:rgba(255,176,0,.08)}
.pco-help-v24 details{border:1px solid var(--line);border-radius:12px;background:rgba(0,0,0,.20);margin:10px 0;padding:10px 12px}
.pco-help-v24 summary{cursor:pointer;color:var(--a);font-weight:900}
.pco-help-v24 .help-tag{display:inline-block;margin:3px;padding:5px 9px;border-radius:999px;background:rgba(255,176,0,.12);border:1px solid var(--line);color:#ffd27a;font-weight:800}
.pco-help-v24 .pco-password-image-box{display:inline-flex;align-items:center;justify-content:center;padding:10px 14px;margin:8px 0 12px;border-radius:13px;border:1px solid rgba(255,176,0,.34);background:rgba(0,0,0,.38);max-width:100%}
.pco-help-v24 .pco-password-image{display:block;height:52px;max-width:100%;user-select:none;-webkit-user-drag:none}
</style>

<div class="pco-help-v24">

<div class="card help-block">
  <h1>📖 Aide PinCabOS — Documentation complète</h1>
  <p>
    Guide complet pour installer, configurer, utiliser et dépanner PinCabOS :
    quoi cliquer, dans quel ordre, quoi vérifier, et quoi faire quand une fonction ne réagit pas comme prévu.
  </p>
  <p>
    <span class="help-tag">Version __VERSION__</span>
    <span class="help-tag">Build __BUILD__</span>
    <span class="help-tag">Dashboard widgets</span>
    <span class="help-tag">PinCab Explorer</span>
    <span class="help-tag">Image Studio</span>
    <span class="help-tag">Batch Import/Export</span>
    <span class="help-tag">ConfigTools</span>
    <span class="help-tag">Medias Hunter</span>
  </p>
  <input id="helpSearch" class="help-search" placeholder="🔎 Recherche : dashboard, widget, batch import, batch export, apparence, clavier, nudge, plunger, DMD, FullDMD, VPinFE, VPS, ConfigTools...">
</div>

<div class="card help-block">
  <h2>🧭 Plan rapide</h2>
  <div class="help-toc">
    <a href="#help-understand">1. Comprendre PinCabOS</a>
    <a href="#help-first-boot">2. Premier démarrage</a>
    <a href="#help-remote">3. Accès WebApp</a>
    <a href="#help-menu">4. Barre du haut et boutons rapides</a>
    <a href="#help-dashboard">5. Dashboard configurable</a>
    <a href="#help-widgets">6. Widgets disponibles</a>
    <a href="#help-appearance">7. Apparence</a>
    <a href="#help-keyboard">8. Clavier régional</a>
    <a href="#help-explorer">9. PinCab Explorer</a>
    <a href="#help-image-studio">10. Image Studio</a>
    <a href="#help-import-export">11. Smart Import / Export</a>
    <a href="#help-batch">12. Batch Smart Import / Export</a>
    <a href="#help-vpx">13. VPX</a>
    <a href="#help-vpinfe">14. VPinFE / VPS / ConfigTools</a>
    <a href="#help-media-hunter">14B. Medias Hunter</a>
    <a href="#help-screens">15. Écrans / GPU</a>
    <a href="#help-fulldmd">16. FullDMD / DMD</a>
    <a href="#help-audio">17. Audio / SSF</a>
    <a href="#help-inputs">18. Inputs / Map Commander</a>
    <a href="#help-dof">19. DOF / Outputs</a>
    <a href="#help-network">20. Réseau / SMB / USB</a>
    <a href="#help-console">21. Console Web</a>
    <a href="#help-paths">22. Chemins importants</a>
    <a href="#help-troubleshooting">23. Dépannage</a>
  </div>
</div>

<div id="help-understand" class="card help-block help-item">
  <h2>1. 🧠 Comprendre PinCabOS</h2>
  <p>
    PinCabOS est la couche système du pincab. VPX fait rouler la table, VPinFE affiche et lance les tables,
    et PinCabOS ajoute les outils autour : configuration, Dashboard, écrans, audio, inputs, DOF,
    import/export, fichiers, console, apparence, réseau et maintenance.
  </p>
  <div class="help-grid">
    <div class="help-mini"><strong>PinCabOS</strong><p>WebApp, outils, services, scripts, fichiers, Dashboard, import/export, configuration et maintenance.</p></div>
    <div class="help-mini"><strong>VPX</strong><p>Moteur qui exécute les tables <code>.vpx</code>.</p></div>
    <div class="help-mini"><strong>VPinFE</strong><p>Frontend qui affiche les tables, médias, wheels, collections et lance VPX.</p></div>
    <div class="help-mini"><strong>Cabinet</strong><p>Écrans, audio, boutons, plunger, nudge, toys DOF, DMD et FullDMD.</p></div>
  </div>
</div>

<div id="help-first-boot" class="card help-block help-item">
  <h2>2. 🚀 Premier démarrage</h2>
  <ol>
    <li>Valider le réseau et l’accès WebApp.</li>
    <li>Configurer la région et le clavier avant de mapper les inputs.</li>
    <li>Configurer GPU et écrans : Playfield, Backglass, FullDMD.</li>
    <li>Configurer audio / SSF.</li>
    <li>Configurer inputs, Map Commander, plunger et nudge.</li>
    <li>Valider VPX avec une table simple.</li>
    <li>Valider VPinFE et ses chemins.</li>
    <li>Tester DOF seulement quand VPX et les inputs sont stables.</li>
    <li>Ensuite seulement : Smart Import, Batch Import, Batch Export et personnalisation avancée.</li>
  </ol>
</div>

<div id="help-remote" class="card help-block help-item">
  <h2>3. 🌐 Accès WebApp</h2>
  <p>Sur le cab lui-même : <code>http://127.0.0.1/</code>. Depuis un autre appareil : <code>http://IP_DU_PINCAB/</code>.</p>
  <p><code>127.0.0.1</code> veut dire “cet appareil lui-même”. Sur un iPad, ça pointe vers l’iPad, pas vers le cab.</p>
</div>

<div id="help-menu" class="card help-block help-item">
  <h2>4. 🧭 Barre du haut et boutons rapides</h2>
  <p>Le menu PinCabOS ne sert pas juste à naviguer. Il donne aussi des commandes rapides utiles pendant les tests.</p>
  <ul>
    <li><strong>Bouton Playfield :</strong> afficher ou retirer la WebApp PinCabOS sur l’écran Playfield.</li>
    <li><strong>Bouton Backglass :</strong> afficher ou retirer la WebApp PinCabOS sur l’écran Backglass.</li>
    <li><strong>Ouvrir VPinFE :</strong> lancer ou ramener le frontend principal.</li>
    <li><strong>Ouvrir VPS :</strong> ouvrir l’outil/lien VPS quand disponible pour l’association et les infos de tables.</li>
    <li><strong>ConfigTools :</strong> accéder aux outils de configuration utiles pour VPX, VPinFE, DOF et cabinet selon les modules installés.</li>
    <li><strong>Outils PinCabOS :</strong> ouvrir la page qui regroupe Explorer, Console, Apparence, Audio, Inputs, FullDMD, VPinFE, VPX et Import/Export.</li>
  </ul>
</div>

<div id="help-dashboard" class="card help-block help-item">
  <h2>5. 📊 Dashboard entièrement configurable</h2>
  <p>
    Le Dashboard fonctionne avec des widgets. Un widget peut être un raccourci, un panneau de statut,
    un contrôle de service, une fonction utile, un aperçu live ou un outil de diagnostic.
  </p>
  <h3>Mode édition</h3>
  <ol>
    <li>Ouvrir le Dashboard.</li>
    <li>Activer le mode édition.</li>
    <li>Ajouter un widget depuis le catalogue.</li>
    <li>Déplacer le widget à l’endroit voulu.</li>
    <li>Fermer un widget inutile.</li>
    <li>Sauvegarder ou laisser PinCabOS conserver le layout selon le comportement du Dashboard.</li>
  </ol>
  <div class="help-note">
    Un espace vide dans le Dashboard veut dire qu’un widget a été retiré ou déplacé. En mode édition, on peut remettre un widget utile à cet endroit.
  </div>
</div>


<!-- PINCABOS_HELP_V25_DASHBOARD_WIDGET_DETAILS START -->
<div class="card help-block help-item">
  <h2>5B. 🧩 Dashboard : logique complète des widgets</h2>
  <p>
    Le Dashboard PinCabOS est pensé comme une surface de travail configurable.
    Chaque widget peut servir de <strong>raccourci</strong>, de <strong>panneau d’état</strong>,
    de <strong>fonction utile</strong>, de <strong>contrôle rapide</strong> ou de
    <strong>diagnostic visuel</strong>.
  </p>

  <h3>Types de widgets</h3>
  <table>
    <tr><th>Type</th><th>À quoi ça sert</th><th>Exemple</th></tr>
    <tr><td>Raccourci</td><td>Ouvre rapidement une page ou un outil.</td><td>PinCab Explorer, Audio, FullDMD, Inputs, Apparence.</td></tr>
    <tr><td>Statut</td><td>Montre si une fonction ou un service est actif.</td><td>WebApp, VPinFE, Batch Import, Batch Export.</td></tr>
    <tr><td>Contrôle</td><td>Permet d’agir sans ouvrir une autre page.</td><td>Stop service, restart, stop table, volume.</td></tr>
    <tr><td>Live</td><td>Montre un aperçu visuel.</td><td>Playfield, Backglass, FullDMD.</td></tr>
    <tr><td>Progression</td><td>Montre l’avancement d’un travail.</td><td>Import batch, export batch, copie, analyse.</td></tr>
  </table>

  <h3>Comportement attendu en mode édition</h3>
  <ol>
    <li>Un widget fermé doit libérer son emplacement.</li>
    <li>Un widget ajouté devrait pouvoir être placé dans un espace libre.</li>
    <li>Le Dashboard doit permettre d’organiser les widgets selon la façon de travailler du cab.</li>
    <li>Les widgets les plus utilisés peuvent rester visibles en permanence.</li>
    <li>Les raccourcis moins utilisés peuvent être retirés et ajoutés seulement au besoin.</li>
  </ol>

  <div class="help-note">
    Le Dashboard n’est pas une page fixe. C’est un panneau de contrôle personnalisable pour le cab.
    L’idée est que chaque utilisateur puisse garder seulement les outils utiles pour son setup.
  </div>
</div>
<!-- PINCABOS_HELP_V25_DASHBOARD_WIDGET_DETAILS END -->

<div id="help-widgets" class="card help-block help-item">
  <h2>6. 🧩 Widgets Dashboard disponibles</h2>
  <p>Les widgets disponibles peuvent évoluer selon la version, mais les grandes familles sont :</p>
  <table>
    <tr><th>Widget</th><th>Rôle</th><th>Utilité</th></tr>
    <tr><td>Services PinCabOS</td><td>Statut/contrôle</td><td>Voir WebApp, VPinFE, VPX, Batch Import/Export et agir rapidement.</td></tr>
    <tr><td>Live Playfield</td><td>Aperçu écran</td><td>Voir si le Playfield affiche quelque chose au bon endroit.</td></tr>
    <tr><td>Live Backglass</td><td>Aperçu écran</td><td>Voir si le Backglass/B2S est actif.</td></tr>
    <tr><td>Live FullDMD</td><td>Aperçu écran</td><td>Voir si le DMD/FullDMD est visible et non gelé.</td></tr>
    <tr><td>Volumes audio</td><td>Contrôle utile</td><td>Afficher/masquer les sorties audio voulues et ajuster rapidement les volumes.</td></tr>
    <tr><td>Batch Import status</td><td>Progression</td><td>Voir l’analyse/import de plusieurs packages et l’état du job.</td></tr>
    <tr><td>Batch Export status</td><td>Progression</td><td>Voir la création/export de packages et l’état du job.</td></tr>
    <tr><td>Table en cours</td><td>Statut jeu</td><td>Voir la table active et arrêter proprement si le bouton Stop est disponible.</td></tr>
    <tr><td>Réseau / trafic</td><td>Diagnostic</td><td>Surveiller IP, réseau, trafic ou état réseau selon le widget installé.</td></tr>
    <tr><td>Raccourci PinCab Explorer</td><td>Raccourci</td><td>Ouvrir rapidement les fichiers du cab.</td></tr>
    <tr><td>Raccourci Console</td><td>Raccourci</td><td>Ouvrir la PinCab Console.</td></tr>
    <tr><td>Raccourci Audio / SSF</td><td>Raccourci</td><td>Aller directement aux tests audio.</td></tr>
    <tr><td>Raccourci Inputs</td><td>Raccourci</td><td>Ouvrir Map Commander et la configuration des entrées.</td></tr>
    <tr><td>Raccourci FullDMD</td><td>Raccourci</td><td>Ouvrir l’outil FullDMD / DMD.</td></tr>
    <tr><td>Raccourci Apparence</td><td>Raccourci</td><td>Ouvrir la personnalisation visuelle.</td></tr>
    <tr><td>Raccourci VPinFE</td><td>Raccourci</td><td>Ouvrir config, update, tables, collections ou médias VPinFE.</td></tr>
    <tr><td>Raccourci VPX</td><td>Raccourci</td><td>Ouvrir l’INI VPX, écrans/GPU ou outils VPX cabinet.</td></tr>
    <tr><td>Raccourci DOF</td><td>Raccourci</td><td>Ouvrir DOF Commander et tests outputs.</td></tr>
  </table>
</div>


<!-- PINCABOS_HELP_V25_WIDGET_CATALOG_DETAILS START -->
<div class="card help-block help-item">
  <h2>6B. 📋 Catalogue de widgets — description détaillée</h2>
  <p>
    Les widgets peuvent varier selon la version installée, mais voici les familles que PinCabOS peut utiliser
    ou afficher selon les modules présents.
  </p>

  <table>
    <tr><th>Famille</th><th>Widget</th><th>Description explicite</th></tr>

    <tr><td>Services</td><td>WebApp</td><td>Indique l’état de la WebApp PinCabOS. Utile pour confirmer que l’interface est active.</td></tr>
    <tr><td>Services</td><td>VPinFE</td><td>Indique l’état du frontend. Peut aider à redémarrer ou vérifier si VPinFE est disponible.</td></tr>
    <tr><td>Services</td><td>VPX</td><td>Indique si un moteur/table semble actif selon l’intégration disponible.</td></tr>
    <tr><td>Services</td><td>Batch Import / Export</td><td>Permet de suivre les traitements longs sans rester dans la page batch.</td></tr>

    <tr><td>Live screens</td><td>Playfield</td><td>Aperçu image de l’écran principal. Sert à confirmer que la table ou la WebApp apparaît au bon endroit.</td></tr>
    <tr><td>Live screens</td><td>Backglass</td><td>Aperçu image de l’écran arrière. Sert à vérifier B2S, backglass ou fenêtre WebApp déplacée.</td></tr>
    <tr><td>Live screens</td><td>FullDMD</td><td>Aperçu image du DMD complet. Sert à vérifier un DMD noir, gelé ou mal placé.</td></tr>

    <tr><td>Audio</td><td>Volumes</td><td>Permet de voir et contrôler les sorties audio. Le bouton engrenage sert à choisir quelles sorties afficher.</td></tr>
    <tr><td>Audio</td><td>Audio / SSF</td><td>Raccourci vers les tests audio, rôles SSF, backglass, playfield et bass shaker.</td></tr>

    <tr><td>Batch</td><td>Batch Import status</td><td>Montre la progression d’un import de plusieurs packages, les erreurs et le statut.</td></tr>
    <tr><td>Batch</td><td>Batch Export status</td><td>Montre la progression d’un export de plusieurs tables vers local, USB ou SMB.</td></tr>

    <tr><td>Jeu</td><td>Table en cours</td><td>Affiche la table active quand détectée. Peut offrir un bouton Stop selon l’intégration.</td></tr>

    <tr><td>Outils</td><td>PinCab Explorer</td><td>Raccourci vers l’explorateur de fichiers Web.</td></tr>
    <tr><td>Outils</td><td>Image Studio</td><td>Accessible depuis les images ouvertes dans PinCab Explorer.</td></tr>
    <tr><td>Outils</td><td>Console</td><td>Raccourci vers la console Web pour diagnostic et maintenance.</td></tr>
    <tr><td>Outils</td><td>Apparence</td><td>Raccourci vers la personnalisation visuelle.</td></tr>
    <tr><td>Outils</td><td>FullDMD</td><td>Raccourci vers calibration, DMD, auto-réglage et AutoArrange.</td></tr>
    <tr><td>Outils</td><td>Inputs / Map Commander</td><td>Raccourci vers mapping, auto mapping, nudge et plunger.</td></tr>
    <tr><td>Outils</td><td>DOF Commander</td><td>Raccourci vers les périphériques, outputs, toys et tests DOF.</td></tr>

    <tr><td>VPinFE</td><td>Config INI</td><td>Ouvre ou aide à gérer les chemins et réglages VPinFE.</td></tr>
    <tr><td>VPinFE</td><td>Update VPinFE</td><td>Raccourci vers la mise à jour VPinFE.</td></tr>
    <tr><td>VPinFE</td><td>Tables</td><td>Raccourci vers la gestion ou visualisation des tables VPinFE.</td></tr>
    <tr><td>VPinFE</td><td>Collections</td><td>Raccourci vers les collections.</td></tr>
    <tr><td>VPinFE</td><td>Médias</td><td>Raccourci vers wheels, vidéos, backglass et médias associés.</td></tr>

    <tr><td>Réseau</td><td>Network status</td><td>Affiche IP, état réseau ou trafic selon le widget disponible.</td></tr>
    <tr><td>Réseau</td><td>SMB / USB</td><td>Raccourcis ou états liés aux partages réseau et clés USB.</td></tr>
  </table>
</div>
<!-- PINCABOS_HELP_V25_WIDGET_CATALOG_DETAILS END -->

<div id="help-appearance" class="card help-block help-item">
  <h2>7. 🎨 Apparence PinCabOS</h2>
  <p>La page Apparence sert à personnaliser l’identité visuelle de la WebApp et du cab.</p>
  <ul>
    <li>Changer ou ajuster des éléments visuels de PinCabOS.</li>
    <li>Gérer les images/médias système quand l’outil le permet.</li>
    <li>Utiliser PinCab Explorer et Image Studio pour modifier des images sous <code>/opt/pincabos/media</code>.</li>
    <li>Conserver une apparence cohérente entre Dashboard, Tools, Footer et pages de configuration.</li>
  </ul>
</div>

<div id="help-keyboard" class="card help-block help-item">
  <h2>8. ⌨️ Configuration clavier régional</h2>
  <p>
    La configuration du clavier régional est importante avant de mapper les boutons.
    Un clavier FR/CA, US ou autre layout peut changer les symboles envoyés.
  </p>
  <ul>
    <li>Choisir le bon layout clavier selon la région.</li>
    <li>Valider les touches spéciales avant Map Commander.</li>
    <li>Éviter de mapper un bouton avec un layout puis jouer avec un autre layout.</li>
    <li>Vérifier la console et VPX si une touche semble inversée ou incorrecte.</li>
  </ul>
</div>


<!-- PINCABOS_HELP_V25_APPEARANCE_KEYBOARD_DETAILS START -->
<div class="card help-block help-item">
  <h2>7B. 🎨 Apparence et identité visuelle — détails</h2>
  <p>
    L’apparence ne sert pas seulement à faire beau. Elle permet de rendre le système plus clair
    pour un cabinet réel : bons logos, bons médias, boutons lisibles, footer propre, notes de version visibles
    et raccourcis reconnaissables.
  </p>
  <ul>
    <li>Les images système peuvent être placées sous <code>/opt/pincabos/media</code>.</li>
    <li>Les images peuvent être ouvertes depuis PinCab Explorer.</li>
    <li>Image Studio peut servir à ajuster rapidement logos, billes, fonds, decals ou médias système.</li>
    <li>Les éléments visuels doivent rester lisibles sur PC, tablette et écran de cab.</li>
  </ul>

  <h2>8B. ⌨️ Clavier régional — pourquoi c’est important</h2>
  <p>
    Le clavier régional doit être réglé avant de mapper les boutons, parce qu’une touche physique
    peut produire un symbole différent selon le layout.
  </p>
  <table>
    <tr><th>Situation</th><th>Problème possible</th><th>Solution</th></tr>
    <tr><td>Clavier US</td><td>Certains symboles ne sont pas au même endroit qu’en FR/CA.</td><td>Choisir le layout réel utilisé.</td></tr>
    <tr><td>Clavier FR/CA</td><td>Les touches spéciales peuvent différer du mapping VPX attendu.</td><td>Valider dans Map Commander.</td></tr>
    <tr><td>Encodeur bouton</td><td>L’encodeur peut envoyer une touche clavier.</td><td>Configurer le layout avant auto mapping.</td></tr>
    <tr><td>Traduction navigateur</td><td>Le navigateur peut changer du texte affiché, mais pas les touches système.</td><td>Ne pas se fier au texte traduit pour les mots de passe ou symboles.</td></tr>
  </table>
</div>
<!-- PINCABOS_HELP_V25_APPEARANCE_KEYBOARD_DETAILS END -->

<div id="help-explorer" class="card help-block help-item">
  <h2>9. 🗂️ PinCab Explorer</h2>
  <ul>
    <li>Parcourir Tables, Exports, Backups, USB, SMB, Share et médias PinCabOS.</li>
    <li>Uploader, télécharger, renommer, dupliquer, supprimer, créer des dossiers et extraire des ZIP.</li>
    <li>Ouvrir les fichiers texte/INI/VBS/JSON/XML dans un éditeur Web.</li>
    <li>Ouvrir les images dans Image Studio.</li>
  </ul>
</div>

<div id="help-image-studio" class="card help-block help-item">
  <h2>10. 🎨 Image Studio</h2>
  <p>Mini éditeur d’images intégré pour PNG/JPG/WEBP.</p>
  <ul>
    <li>Brush, Eraser, Text, Line, Rectangle, Ellipse, Crop, Resize.</li>
    <li>Magic Wand pour enlever un fond avec tolérance.</li>
    <li>Sauvegarde avec backup automatique.</li>
    <li>PNG recommandé pour garder la transparence.</li>
  </ul>
</div>

<div id="help-import-export" class="card help-block help-item">
  <h2>11. 📦 Smart Import / Export</h2>
  <h3>Smart Import simple</h3>
  <ul>
    <li>Importer une table ou archive une à la fois.</li>
    <li>Analyser le contenu avant installation.</li>
    <li>Détecter VPX, B2S, ROM, PupPack, médias, DMD, INI, POV et scripts.</li>
    <li>Choisir quoi faire en cas de conflit : ignorer, renommer ou remplacer.</li>
  </ul>
  <h3>Smart Export simple</h3>
  <ul>
    <li>Choisir une table installée.</li>
    <li>Créer un package portable PinCabOS.</li>
    <li>Inclure manifest et fichiers associés quand détectés.</li>
    <li>Télécharger ou transférer le package selon l’outil utilisé.</li>
  </ul>
</div>

<div id="help-batch" class="card help-block help-item">
  <h2>12. 📚 Batch Smart Import / Batch Smart Export</h2>
  <h3>Batch Smart Import</h3>
  <p>Batch Smart Import sert à traiter plusieurs packages de tables dans une seule opération guidée.</p>
  <ol>
    <li>Ajouter plusieurs fichiers ou packages au lot.</li>
    <li>Lancer l’analyse.</li>
    <li>Lire les conflits ou avertissements.</li>
    <li>Choisir le mode : skip, rename ou replace selon la situation.</li>
    <li>Confirmer l’installation.</li>
    <li>Suivre la progression dans la page et/ou le widget Dashboard Batch Import.</li>
  </ol>
  <h3>Batch Smart Export</h3>
  <p>Batch Smart Export sert à créer plusieurs packages PinCabOS à partir de tables installées.</p>
  <ol>
    <li>Sélectionner les tables à exporter.</li>
    <li>Choisir la destination : local, USB ou SMB quand disponible.</li>
    <li>Lancer l’export.</li>
    <li>Surveiller le pourcentage, les logs et les erreurs.</li>
    <li>Utiliser le widget Dashboard Batch Export pour suivre l’état sans rester dans la page.</li>
  </ol>
</div>


<!-- PINCABOS_HELP_V25_BATCH_DETAILS START -->
<div class="card help-block help-item">
  <h2>12B. 📚 Batch Smart Import / Export — détails pratiques</h2>

  <h3>Différence entre Smart Import simple et Batch Smart Import</h3>
  <table>
    <tr><th>Mode</th><th>Quand l’utiliser</th><th>Avantage</th></tr>
    <tr><td>Smart Import simple</td><td>Une seule table ou un seul package.</td><td>Contrôle très précis.</td></tr>
    <tr><td>Batch Smart Import</td><td>Plusieurs packages à traiter.</td><td>Gain de temps et suivi global.</td></tr>
  </table>

  <h3>Ce que le Batch Import doit aider à éviter</h3>
  <ul>
    <li>Copier des fichiers dans les mauvais dossiers.</li>
    <li>Écraser une table existante sans backup.</li>
    <li>Oublier une ROM, un PupPack, un B2S ou un média.</li>
    <li>Ne pas voir quel package a échoué.</li>
    <li>Perdre le fil pendant un import long.</li>
  </ul>

  <h3>Différence entre Smart Export simple et Batch Smart Export</h3>
  <table>
    <tr><th>Mode</th><th>Quand l’utiliser</th><th>Destination typique</th></tr>
    <tr><td>Smart Export simple</td><td>Exporter une table précise.</td><td>Téléchargement ou dossier local.</td></tr>
    <tr><td>Batch Smart Export</td><td>Exporter plusieurs tables.</td><td>Exports, USB ou SMB/NAS.</td></tr>
  </table>

  <h3>Suivi Dashboard</h3>
  <p>
    Les widgets Batch Import et Batch Export servent à suivre la progression sans rester dans la page.
    Ils doivent afficher un statut clair : en attente, en cours, terminé, erreur ou interrompu.
  </p>
</div>
<!-- PINCABOS_HELP_V25_BATCH_DETAILS END -->

<div id="help-vpx" class="card help-block help-item">
  <h2>13. 🕹️ VPinballX / VPX</h2>
  <pre>VPX directory : __VPX_DIR__
VPX wrapper   : __VPX_WRAPPER__
INI VPX       : /home/pinball/.local/share/VPinballX/10.8/VPinballX.ini
Tables        : /home/pinball/Tables</pre>
  <ul>
    <li>VPX exécute les fichiers <code>.vpx</code>.</li>
    <li>Le wrapper PinCabOS est le point de lancement recommandé.</li>
    <li>Les réglages écrans, audio et inputs doivent être cohérents avec VPX.</li>
  </ul>
</div>

<div id="help-vpinfe" class="card help-block help-item">
  <h2>14. 🧭 VPinFE / VPS / ConfigTools</h2>
  <h3>VPinFE</h3>
  <ul>
    <li>Frontend principal : liste de tables, médias, collections, wheels, vidéos et lancement.</li>
    <li>Boutons/outils pour ouvrir VPinFE ou ses sections lorsque disponibles.</li>
    <li>Outils VPinFE : INI, update, tables, collections, médias.</li>
  </ul>
  <h3>VPS</h3>
  <ul>
    <li>VPS sert d’aide pour identifier, associer ou documenter les tables selon l’intégration disponible.</li>
    <li>Le bouton VPS doit être utilisé pour faciliter l’association/import quand la fonction est présente.</li>
  </ul>
  <h3>ConfigTools</h3>
  <ul>
    <li>ConfigTools regroupe les fonctions de configuration avancée disponibles selon le contexte.</li>
    <li>Exemples : fichiers INI VPX/VPinFE, chemins, paramètres cabinet, DOF Config Tool ou outils liés aux tables.</li>
    <li>Après modification via ConfigTools, redémarrer le service concerné ou relancer VPX/VPinFE si nécessaire.</li>
  </ul>
</div>


<!-- PINCABOS_HELP_V25_VPINFE_VPS_CONFIGTOOLS_DETAILS START -->
<div class="card help-block help-item">
  <h2>14B. 🧭 VPinFE, VPS et ConfigTools — utilisation détaillée</h2>

  <h3>Bouton Ouvrir VPinFE</h3>
  <p>
    Ce bouton sert à ouvrir ou ramener l’interface VPinFE. VPinFE est le frontend principal :
    c’est lui que l’utilisateur voit pour choisir une table dans le cab.
  </p>

  <h3>Bouton Ouvrir VPS</h3>
  <p>
    VPS peut aider à identifier ou associer des tables avec des informations externes.
    Dans un workflow d’import, ça peut aider à retrouver le bon nom, la bonne version ou les médias associés.
  </p>

  <h3>ConfigTools</h3>
  <p>
    ConfigTools désigne les outils de configuration avancée disponibles dans PinCabOS ou autour de l’écosystème.
    Selon les modules installés, cela peut toucher :
  </p>
  <ul>
    <li>Configuration VPX.</li>
    <li>Configuration VPinFE.</li>
    <li>Chemins de tables et médias.</li>
    <li>Fichiers DOF et Cabinet JSON.</li>
    <li>Paramètres DMD / FullDMD.</li>
    <li>Fichiers INI, JSON, XML ou VBS ouverts avec prudence.</li>
  </ul>

  <div class="help-danger">
    ConfigTools peut modifier des fichiers importants. Avant une modification majeure :
    backup, un changement à la fois, test, puis validation.
  </div>
</div>
<!-- PINCABOS_HELP_V25_VPINFE_VPS_CONFIGTOOLS_DETAILS END -->


<!-- PINCABOS_HELP_MEDIA_HUNTER_V1 START -->
<div id="help-media-hunter" class="card help-block help-item">
  <h2>14B. 🕵️ Medias Hunter — recherche et installation des médias manquants</h2>

  <p>
    <strong>Medias Hunter</strong> est un outil PinCabOS indépendant de VPinFE.
    Il analyse chaque dossier de table, détecte les médias absents, cherche ces fichiers dans une liste
    de sources configurables et installe seulement les médias réellement manquants.
  </p>

  <p><a class="button" href="/tools/vpinfe/media-hunter">🕵️ Ouvrir Medias Hunter</a></p>

  <div class="help-good">
    Medias Hunter complète la bibliothèque de médias sans remplacer le gestionnaire de médias de VPinFE.
    Il ne modifie pas le code de VPinFE et ne déclenche pas la synchronisation média interne de VPinFE.
  </div>

  <h3>Emplacement et fichiers utilisés</h3>
  <table>
    <tr><th>Élément</th><th>Chemin</th></tr>
    <tr><td>Page Web</td><td><code>/tools/vpinfe/media-hunter</code></td></tr>
    <tr><td>Module</td><td><code>/opt/pincabos/web/pincabos_media_hunter.py</code></td></tr>
    <tr><td>Configuration des sources</td><td><code>/opt/pincabos/config/media-hunter/sources.json</code></td></tr>
    <tr><td>État courant</td><td><code>/var/lib/pincabos/media-hunter/state.json</code></td></tr>
    <tr><td>Résultats du dernier scan</td><td><code>/var/lib/pincabos/media-hunter/results.json</code></td></tr>
    <tr><td>Cache des index Web</td><td><code>/var/lib/pincabos/media-hunter/cache</code></td></tr>
    <tr><td>Image</td><td><code>/opt/pincabos/web/static/pincabos-assets/PCOSMediaHunter.png</code></td></tr>
  </table>

  <h3>Ce que le moteur lit</h3>
  <ul>
    <li><code>tablerootdir</code> dans <code>/home/pinball/.config/vpinfe/vpinfe.ini</code>.</li>
    <li>Les dossiers de tables, normalement sous <code>/home/pinball/Tables</code>.</li>
    <li>Les fichiers <code>.info</code> pour le titre, le fabricant, l’année et l’identifiant VPS.</li>
    <li>Le nom du dossier de table lorsque les métadonnées sont absentes.</li>
    <li>La base VPS locale disponible pour compléter l’association.</li>
    <li>Les sources activées dans <code>sources.json</code>, classées par priorité.</li>
  </ul>

  <h3>Ce que Medias Hunter ne modifie jamais</h3>
  <ul>
    <li>Tables <code>.vpx</code>, scripts <code>.vbs</code> et backglass <code>.directb2s</code>.</li>
    <li>Fichiers <code>.info</code> et métadonnées.</li>
    <li><code>vpinfe.ini</code>, code, thèmes ou services internes de VPinFE.</li>
    <li>Médias existants et non vides.</li>
    <li>Fichiers présents dans les bibliothèques sources.</li>
  </ul>

  <div class="help-danger">
    Medias Hunter n’est pas un outil de suppression. Son réglage
    <code>overwrite_existing</code> est forcé à <code>false</code>.
  </div>

  <h3>Médias surveillés</h3>
  <table>
    <tr><th>Type</th><th>Fichier attendu</th><th>Rôle</th></tr>
    <tr><td><code>bg</code></td><td><code>bg.png</code></td><td>Backglass.</td></tr>
    <tr><td><code>dmd</code></td><td><code>dmd.png</code></td><td>Image DMD.</td></tr>
    <tr><td><code>table</code></td><td><code>table.png</code></td><td>Image Playfield/table.</td></tr>
    <tr><td><code>wheel</code></td><td><code>wheel.png</code></td><td>Logo ou wheel.</td></tr>
    <tr><td><code>cab</code></td><td><code>cab.png</code></td><td>Image cabinet.</td></tr>
    <tr><td><code>realdmd</code></td><td><code>realdmd.png</code></td><td>RealDMD monochrome.</td></tr>
    <tr><td><code>realdmd_color</code></td><td><code>realdmd-color.png</code></td><td>RealDMD couleur.</td></tr>
    <tr><td><code>flyer</code></td><td><code>flyer.png</code></td><td>Flyer ou Game Info.</td></tr>
    <tr><td><code>bg_video</code></td><td><code>bg.mp4</code></td><td>Vidéo Backglass.</td></tr>
    <tr><td><code>dmd_video</code></td><td><code>dmd.mp4</code></td><td>Vidéo DMD.</td></tr>
    <tr><td><code>table_video</code></td><td><code>table.mp4</code></td><td>Vidéo Playfield/table.</td></tr>
    <tr><td><code>audio</code></td><td><code>audio.mp3</code></td><td>Audio de lancement.</td></tr>
  </table>

  <p>
    La destination est toujours <code>[Nom de la table]/medias/</code>.
    Un fichier existant avec une taille supérieure à zéro est considéré présent et n’est jamais remplacé.
  </p>

  <h3>Boutons principaux</h3>
  <table>
    <tr><th>Bouton</th><th>Fonction</th><th>Écrit des médias</th></tr>
    <tr>
      <td><strong>Analyser les médias manquants</strong></td>
      <td>Scanne les tables, calcule les médias présents/manquants et tente l’association VPS.</td>
      <td>Non.</td>
    </tr>
    <tr>
      <td><strong>Chercher tous les manquants</strong></td>
      <td>Traite toutes les tables incomplètes et essaie les sources actives par priorité.</td>
      <td>Oui, seulement pour un fichier absent.</td>
    </tr>
    <tr>
      <td><strong>Chercher la sélection</strong></td>
      <td>Traite uniquement les tables cochées.</td>
      <td>Oui, seulement pour un fichier absent.</td>
    </tr>
    <tr>
      <td><strong>Arrêter</strong></td>
      <td>Demande l’arrêt propre du travail en arrière-plan.</td>
      <td>Le fichier temporaire courant est retiré en cas d’interruption.</td>
    </tr>
  </table>

  <h3>Association VPS</h3>
  <ol>
    <li><code>VPinFE.altvpsid</code> dans le fichier <code>.info</code>.</li>
    <li><code>Info.VPSId</code> dans le fichier <code>.info</code>.</li>
    <li>Correspondance exacte nom + fabricant + année.</li>
    <li>Correspondance exacte nom + année seulement si elle n’est pas ambiguë.</li>
  </ol>

  <div class="help-note">
    Le moteur ne choisit pas un VPS ID avec une correspondance approximative dangereuse.
    Sans association VPS, les sources par nom peuvent fonctionner, mais VPinMediaDB ne peut pas construire le média.
  </div>

  <h3>Sources de médias et priorité</h3>
  <p>
    Le plus petit numéro de priorité est essayé en premier. Dès qu’un média valide est installé,
    les sources suivantes ne sont pas consultées pour ce média.
  </p>

  <h4>Superhac VPinMediaDB</h4>
  <ul>
    <li>Source initiale de Medias Hunter.</li>
    <li>Même dépôt média Superhac utilisé comme source fournie dans VPin Studio.</li>
    <li>Aucune source TrueNAS ou personnelle n’est préconfigurée.</li>
    <li>L’index <code>vpinmdb.json</code> est mis en cache.</li>
    <li>Un identifiant VPS valide est nécessaire.</li>
    <li>Les préférences de résolution VPinFE sont utilisées pour les images et vidéos de table.</li>
  </ul>

  <h4>Dossier local ou réseau monté</h4>
  <ul>
    <li>Peut viser un disque local, une clé USB ou un partage réseau déjà monté sous Linux.</li>
    <li>Le bouton <strong>📁 Parcourir</strong> permet de sélectionner le chemin.</li>
    <li>La recherche peut être récursive ou limitée au dossier choisi.</li>
    <li>Le fichier source est copié en lecture seule; il n’est jamais déplacé ou supprimé.</li>
    <li>Chaque source peut être limitée à un ou plusieurs types de médias.</li>
  </ul>

  <p>Racines offertes par Parcourir :</p>
  <ul>
    <li><code>/home/pinball/NetworkDrives</code></li>
    <li><code>/home/pinball</code></li>
    <li><code>/mnt</code></li>
    <li><code>/media</code></li>
    <li><code>/run/media</code></li>
    <li><code>/opt/pincabos/media</code></li>
  </ul>

  <div class="help-danger">
    Un chemin Windows comme <code>\\SERVEUR\Partage\Dossier</code> ou une URL <code>smb://</code>
    n’est pas monté automatiquement. Le partage doit être connecté avec les outils PinCabOS,
    puis ajouté avec son chemin Linux. Medias Hunter ne conserve aucun identifiant réseau.
  </div>

  <h4>Lien Web</h4>
  <ul>
    <li>Accepte une URL HTTP/HTTPS contenant des fichiers directement accessibles.</li>
    <li>Sans modèle, le moteur essaie plusieurs noms construits depuis la table et le média.</li>
    <li>Avec un modèle, le chemin est construit avec des variables.</li>
    <li>Les pages HTML, formulaires de connexion et réponses JSON sont refusés.</li>
  </ul>

  <p>Variables d’un modèle Web :</p>
  <pre>{vps_id}
{name}
{title}
{manufacturer}
{year}
{media}
{filename}</pre>

  <p>Exemples :</p>
  <pre>{vps_id}/1k/{filename}
{title}/{filename}
https://media.exemple.net/{manufacturer}/{year}/{title}/{filename}</pre>

  <h3>Ajouter une source avec Parcourir</h3>
  <ol>
    <li>Ouvrir <strong>Tools → VPinFE → Medias Hunter</strong>.</li>
    <li>Choisir <strong>Dossier local ou réseau monté</strong>.</li>
    <li>Donner un nom clair à la source.</li>
    <li>Cliquer sur <strong>📁 Parcourir</strong>.</li>
    <li>Entrer dans les sous-dossiers et choisir le dossier voulu.</li>
    <li>Choisir la priorité.</li>
    <li>Sélectionner uniquement les types réellement contenus dans ce dossier.</li>
    <li>Choisir si la recherche doit être récursive.</li>
    <li>Enregistrer, puis utiliser <strong>Tester</strong>.</li>
  </ol>

  <div class="help-good">
    Un dossier contenant uniquement des wheels doit être limité au type <code>wheel</code>.
    Autoriser cette source pour tous les types peut faire associer les wheels à des médias incorrects.
  </div>

  <h3>Noms recherchés dans un dossier</h3>
  <p>Les noms candidats utilisent :</p>
  <ul>
    <li>Le nom complet du dossier de table.</li>
    <li>Le titre.</li>
    <li>Le titre avec fabricant et année.</li>
    <li>L’identifiant VPS.</li>
    <li>Les alias du média : wheel, logo, backglass, playfield, etc.</li>
  </ul>

  <pre>Medieval Madness.png
Medieval Madness (Williams 1997).webp
Medieval Madness wheel.png
Medieval Madness-logo.png
-5yMpqSy.png</pre>

  <p>
    La comparaison normalise la casse, les accents, la ponctuation, les espaces,
    les tirets et les traits de soulignement.
  </p>

  <h3>Validation sécurisée du fichier</h3>
  <ol>
    <li>Copie ou téléchargement vers un fichier temporaire <code>.part</code>.</li>
    <li>Nouvelle vérification que la destination est toujours absente.</li>
    <li>Refus d’un fichier vide ou trop petit.</li>
    <li>Refus d’une page HTML ou d’une réponse JSON déguisée en média.</li>
    <li>Conversion JPG/WEBP/BMP vers PNG lorsque la destination attend un PNG.</li>
    <li>Installation atomique seulement après validation.</li>
    <li>Suppression du <code>.part</code> en cas d’arrêt ou d’erreur.</li>
  </ol>

  <h3>Statistiques, filtres et sélection</h3>
  <ul>
    <li><strong>Tables, complètes, incomplètes et manquants :</strong> état global du scan.</li>
    <li><strong>VPS associés/non associés :</strong> disponibilité d’un identifiant VPS.</li>
    <li><strong>Filtrer une table :</strong> recherche par nom.</li>
    <li><strong>Filtre de média :</strong> montre les tables auxquelles manque un média précis.</li>
    <li><strong>Sélectionner visibles :</strong> coche les lignes actuellement filtrées.</li>
    <li><strong>Vider sélection :</strong> retire toutes les coches.</li>
    <li><strong>Dernière action et journal :</strong> source utilisée, fichier installé, introuvable ou erreur.</li>
  </ul>

  <h3>Erreurs courantes</h3>
  <table>
    <tr><th>Problème</th><th>Cause</th><th>Correction</th></tr>
    <tr>
      <td>Dossier inaccessible</td>
      <td>Montage absent, partage déconnecté ou permissions insuffisantes.</td>
      <td>Reconnecter le partage, utiliser Parcourir et tester la source.</td>
    </tr>
    <tr>
      <td>Chemin SMB/UNC non monté</td>
      <td>Un chemin Windows ou <code>smb://</code> a été saisi directement.</td>
      <td>Monter le partage, puis utiliser son chemin Linux.</td>
    </tr>
    <tr>
      <td>VPS non associé</td>
      <td>Aucun VPS ID et aucune correspondance exacte.</td>
      <td>Corriger l’association VPS dans les outils VPinFE/VPS, puis rescanner.</td>
    </tr>
    <tr>
      <td>Réponse non média</td>
      <td>L’URL renvoie une page Web, une connexion ou une erreur.</td>
      <td>Utiliser une URL directe ou corriger le modèle Web.</td>
    </tr>
    <tr>
      <td>Même wheel installé comme plusieurs médias</td>
      <td>La source de wheels était autorisée pour tous les types.</td>
      <td>Limiter la source au type <code>wheel</code>, nettoyer les mauvais fichiers et recommencer sur une petite sélection.</td>
    </tr>
  </table>

  <h3>Repartir après une mauvaise configuration</h3>
  <p>
    Arrêter Medias Hunter, corriger les types autorisés de la source, nettoyer séparément
    les fichiers incorrects, relancer l’analyse, puis tester quelques tables avant une recherche complète.
  </p>

  <div class="help-danger">
    Le nettoyage destructif n’est pas intégré à Medias Hunter.
    Le script séparé <code>pincabos-delete-png-webp-and-media-subfolders.sh</code>
    supprime les PNG/WEBP et les sous-répertoires dans les dossiers <code>medias</code>.
    Il conserve notamment les MP4, MP3, GIF, JPG et JPEG.
  </div>

  <h3>Procédure recommandée</h3>
  <ol>
    <li>Ajouter ou vérifier les sources.</li>
    <li>Limiter chaque source aux bons types de médias.</li>
    <li>Tester chaque source.</li>
    <li>Lancer une analyse sans téléchargement.</li>
    <li>Filtrer un type de média.</li>
    <li>Tester <strong>Chercher la sélection</strong> sur quelques tables.</li>
    <li>Vérifier le résultat dans VPinFE.</li>
    <li>Seulement après validation, utiliser <strong>Chercher tous les manquants</strong>.</li>
  </ol>
</div>
<!-- PINCABOS_HELP_MEDIA_HUNTER_V1 END -->

<div id="help-screens" class="card help-block help-item">
  <h2>15. 🖥️ Écrans / GPU</h2>
  <ul>
    <li>Assigner Playfield, Backglass et FullDMD.</li>
    <li>Vérifier la géométrie, la résolution et l’ordre des écrans.</li>
    <li>Utiliser les boutons Playfield/Backglass du menu pour afficher la WebApp sur les bons écrans.</li>
    <li>Valider les widgets live du Dashboard après changement.</li>
  </ul>
</div>

<div id="help-fulldmd" class="card help-block help-item">
  <h2>16. 📺 FullDMD / DMD</h2>
  <p>L’outil FullDMD ne sert pas seulement à afficher une image : il aide à placer et régler le DMD dans le contexte cabinet.</p>
  <ul>
    <li>Détection du rôle FullDMD.</li>
    <li>Calibration du FullDMD.</li>
    <li>Auto-réglage du DMD quand l’outil peut détecter la bonne géométrie.</li>
    <li>AutoArrange pour placer les éléments DMD/FullDMD selon les écrans.</li>
    <li>Vérification que le DMD n’est pas caché derrière une autre fenêtre.</li>
    <li>Validation avec le widget live FullDMD du Dashboard.</li>
  </ul>
</div>


<!-- PINCABOS_HELP_V25_FULLDMD_DMD_AUTOFIT_DETAILS START -->
<div class="card help-block help-item">
  <h2>16B. 📺 FullDMD : auto-réglage DMD et AutoArrange</h2>
  <p>
    L’outil FullDMD doit aider à éviter les réglages manuels répétitifs.
    Son rôle est de relier le DMD, le FullDMD, les écrans et les paramètres VPX/VPinFE.
  </p>

  <h3>Fonctions attendues</h3>
  <ul>
    <li>Détecter le rôle FullDMD.</li>
    <li>Afficher la géométrie utilisée.</li>
    <li>Aider à placer le DMD au bon endroit.</li>
    <li>Appliquer un auto-réglage quand la géométrie est détectable.</li>
    <li>Préparer ou ajuster les fichiers nécessaires pour une table.</li>
    <li>Valider avec le widget live FullDMD.</li>
  </ul>

  <h3>Quand utiliser l’auto-réglage DMD</h3>
  <ul>
    <li>Le DMD apparaît trop petit.</li>
    <li>Le DMD apparaît sur le mauvais écran.</li>
    <li>Le DMD est décalé.</li>
    <li>Le FullDMD est bon, mais le DMD interne ne remplit pas la zone voulue.</li>
    <li>Une table a besoin d’un layout local pour bien se placer.</li>
  </ul>
</div>
<!-- PINCABOS_HELP_V25_FULLDMD_DMD_AUTOFIT_DETAILS END -->

<div id="help-audio" class="card help-block help-item">
  <h2>17. 🔊 Audio / SSF</h2>
  <ul>
    <li>Détection des cartes audio.</li>
    <li>Rôles backglass, ROM, musique, playfield, surround et bass shaker.</li>
    <li>Tests audio par rôle.</li>
    <li>Widget volumes audio avec engrenage pour choisir les sorties visibles.</li>
  </ul>
</div>

<div id="help-inputs" class="card help-block help-item">
  <h2>18. 🎛️ Inputs / Map Commander / Nudge / Plunger</h2>
  <h3>Map Commander</h3>
  <ul>
    <li>Détection des boutons réels.</li>
    <li>Mapping guidé des commandes VPX.</li>
    <li>Application du mapping vers les paramètres utiles.</li>
    <li>Retour aux valeurs par défaut quand nécessaire.</li>
  </ul>
  <h3>Mapping automatique</h3>
  <ul>
    <li>Le mapping auto sert à accélérer la configuration des boutons standards.</li>
    <li>Il faut ensuite tester chaque bouton physiquement.</li>
    <li>Ne jamais supposer que Start/Coin/Exit/Launch sont corrects sans test réel.</li>
  </ul>
  <h3>Visuel Nudge et Plunger</h3>
  <ul>
    <li>Le visuel du nudge aide à voir si les axes bougent correctement.</li>
    <li>Le visuel du plunger aide à confirmer la course analogique du lance-bille.</li>
    <li>Si le plunger réagit avec un délai, vérifier qu’il n’est pas traité comme simple bouton LaunchBall.</li>
    <li>Si le nudge part dans le mauvais sens, vérifier les axes, inversion et sensibilité.</li>
  </ul>
</div>


<!-- PINCABOS_HELP_V25_INPUTS_MAP_COMMANDER_DETAILS START -->
<div class="card help-block help-item">
  <h2>18B. 🎛️ Inputs : Map Commander, auto mapping, nudge et plunger</h2>

  <h3>Map Commander</h3>
  <p>
    Map Commander sert à faire le lien entre les boutons physiques du cab et les actions attendues dans VPX.
    Il faut tester les boutons avec les vrais boutons du cab, pas seulement avec un clavier externe.
  </p>

  <h3>Mapping automatique</h3>
  <ol>
    <li>Choisir le bon layout clavier régional.</li>
    <li>Lancer la détection ou l’auto mapping.</li>
    <li>Appuyer sur chaque bouton réel.</li>
    <li>Confirmer que chaque fonction correspond à la bonne action.</li>
    <li>Tester dans VPX avec une table simple.</li>
  </ol>

  <h3>Visuel du nudge</h3>
  <p>
    Le visuel du nudge doit montrer si le cab détecte les mouvements et dans quelle direction.
    Il aide à diagnostiquer un axe inversé, trop sensible ou absent.
  </p>

  <h3>Visuel du plunger</h3>
  <p>
    Le visuel du plunger doit montrer la course analogique du lance-bille.
    Un bon plunger analogique doit bouger progressivement, pas seulement ON/OFF.
  </p>

  <table>
    <tr><th>Symptôme</th><th>Cause probable</th><th>Action</th></tr>
    <tr><td>Plunger avec délai</td><td>VPX le traite comme LaunchBall digital.</td><td>Vérifier axe analogique et mapping LaunchBall.</td></tr>
    <tr><td>Plunger inversé</td><td>Axe inversé.</td><td>Changer ReversePlungerAxis ou inversion équivalente.</td></tr>
    <tr><td>Nudge trop fort</td><td>Sensibilité trop haute.</td><td>Réduire gain/sensibilité.</td></tr>
    <tr><td>Nudge absent</td><td>Périphérique ou axe non lu.</td><td>Vérifier détection dans Map Commander.</td></tr>
  </table>
</div>
<!-- PINCABOS_HELP_V25_INPUTS_MAP_COMMANDER_DETAILS END -->

<div id="help-dof" class="card help-block help-item">
  <h2>19. 💡 DOF / Outputs</h2>
  <ul>
    <li>DOF Commander sert à voir les périphériques, outputs physiques, toys et combos.</li>
    <li>Tests OFF/ON, durée, intensité, repeat et journal.</li>
    <li>Import DOF : <code>.ini</code>, <code>.xml</code>, <code>.zip</code> et Cabinet JSON quand disponible.</li>
    <li>Référence testée : LedWiz32 original, DudesCab, MX Downy.</li>
  </ul>
</div>

<div id="help-network" class="card help-block help-item">
  <h2>20. 🌍 Réseau / SMB / USB</h2>
  <ul>
    <li>DHCP au départ, IP fixe recommandée ensuite.</li>
    <li>Wi-Fi selon matériel.</li>
    <li>Partages SMB/NAS dans <code>/home/pinball/NetworkDrives</code>.</li>
    <li>USB pour import/export rapide.</li>
  </ul>
</div>

<div id="help-console" class="card help-block help-item">
  <h2>21. 🖥️ Console Web</h2>
  <p>L’utilisateur Linux principal est <code>pinball</code>. Le mot de passe est affiché en image pour éviter qu’un traducteur modifie les caractères spéciaux.</p>
  <div class="pco-password-image-box notranslate" translate="no">
    <img class="pco-password-image"
         src="/static/pincabos-assets/pincabos-pinball-password-v23.png?v=password-v23"
         alt="Mot de passe utilisateur pinball affiché sous forme d'image"
         draggable="false">
  </div>
  <p>Pour passer root :</p>
  <pre>sudo -i</pre>
  <div class="help-danger">La console est puissante. Lire les commandes, faire des backups, et éviter les changements à l’aveugle.</div>
</div>

<div id="help-paths" class="card help-block help-item">
  <h2>22. 📁 Chemins importants</h2>
  <table>
    <tr><th>Élément</th><th>Chemin</th></tr>
    <tr><td>Base PinCabOS</td><td><code>/opt/pincabos</code></td></tr>
    <tr><td>WebApp</td><td><code>/opt/pincabos/web</code></td></tr>
    <tr><td>About/Help</td><td><code>/opt/pincabos/web/PinCabOS-AboutHelp.py</code></td></tr>
    <tr><td>Tables</td><td><code>/home/pinball/Tables</code></td></tr>
    <tr><td>VPX INI</td><td><code>/home/pinball/.local/share/VPinballX/10.8/VPinballX.ini</code></td></tr>
    <tr><td>VPinFE config</td><td><code>/home/pinball/.config/vpinfe/vpinfe.ini</code></td></tr>
    <tr><td>Médias PinCabOS</td><td><code>/opt/pincabos/media</code></td></tr>
    <tr><td>SMB</td><td><code>/home/pinball/NetworkDrives</code></td></tr>
  </table>
</div>

<div id="help-troubleshooting" class="card help-block help-item">
  <h2>23. 🧰 Dépannage</h2>
  <table>
    <tr><th>Problème</th><th>À vérifier</th></tr>
    <tr><td>Widget Dashboard manquant</td><td>Mode édition, catalogue de widgets, layout sauvegardé.</td></tr>
    <tr><td>Batch bloqué</td><td>Widget Batch status, logs, service WebApp, espace disque, accès SMB/USB.</td></tr>
    <tr><td>Clavier incorrect</td><td>Layout régional avant Map Commander.</td></tr>
    <tr><td>Plunger lent</td><td>Axe analogique, LaunchBall digital, mapping VPX.</td></tr>
    <tr><td>DMD mauvais endroit</td><td>FullDMD, auto-réglage DMD, géométrie, screen ID.</td></tr>
    <tr><td>WebApp pas sur bon écran</td><td>Boutons Playfield/Backglass du menu.</td></tr>
  </table>
</div>

<script>
(function(){
  const search = document.getElementById("helpSearch");
  if (!search) return;
  function normalize(s){return (s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");}
  search.addEventListener("input", function(){
    const q = normalize(this.value.trim());
    document.querySelectorAll(".help-item").forEach(function(card){
      card.style.display = !q || normalize(card.innerText || "").includes(q) ? "" : "none";
    });
  });
})();
</script>

</div>
"""
    for key, value in replacements.items():
        body = body.replace(key, value)

    # PINCABOS_HELP_GUIDE_ATTACH_V1
    body += pincabos_help_guide_html()
    return page("Aide PinCabOS", body)




def about_page():
    ver = pincabos_version() or {}

    version_label = esc(str(ver.get("version") or ver.get("label") or "PinCabOS"))
    build_label = esc(str(ver.get("build") or ""))
    channel_label = esc(str(ver.get("channel") or ""))
    codename_label = esc(str(ver.get("codename") or ""))
    author_label = esc(str(ver.get("author") or "Karots Sugarpie"))
    site_label = esc(str(ver.get("site") or "pincabos.cc"))

    version_full = version_label
    if build_label:
        version_full += " Build " + build_label

    pills = ""
    for label, value in [
        ("Version", version_label),
        ("Build", build_label),
        ("Channel", channel_label),
        ("Codename", codename_label),
        ("Author", author_label),
        ("Site", site_label),
    ]:
        if value:
            pills += '<span class="about-pill"><strong>' + esc(label) + ':</strong> ' + esc(value) + '</span>\n'

    replacements = {
        "__VERSION_FULL__": esc(version_full),
        "__VERSION__": version_label,
        "__BUILD__": build_label or "non spécifié",
        "__CHANNEL__": channel_label or "non spécifié",
        "__CODENAME__": codename_label or "non spécifié",
        "__AUTHOR__": author_label,
        "__SITE__": site_label,
        "__PILLS__": pills,
        "__VPX_DIR__": esc(pco_path_text("vpx_dir")),
        "__VPX_WRAPPER__": esc(pco_path_text("vpx_wrapper")),
        "__VPINFE_CURRENT__": esc(pco_path_text("vpinfe_current")),
    }

    body = r"""
<div class="about-page about-v24">
<style>
.about-v24 h2,.about-v24 h3{color:#ffb000}
.about-v24 .about-pill{display:inline-block;padding:6px 10px;margin:4px 6px 4px 0;border:1px solid rgba(255,176,0,.35);border-radius:999px;background:rgba(255,176,0,.08);color:#ffcc68;font-weight:800}
.about-v24 .about-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.about-v24 .about-mini{border:1px solid rgba(255,176,0,.24);border-radius:14px;padding:12px;background:rgba(255,176,0,.07)}
.about-v24 .about-mini strong{color:#ffb000}
.about-v24 .about-note{border-left:5px solid #ffb000;padding:10px 12px;background:rgba(255,176,0,.08);border-radius:10px;margin:12px 0}
.about-v24 .about-danger{border-left:5px solid #ff5a68;padding:10px 12px;background:rgba(255,90,104,.10);border-radius:10px;margin:12px 0}
.about-v24 ul{line-height:1.62}.about-v24 li{margin:5px 0}.about-v24 code{color:#ffb000}
.about-v24 table{width:100%;border-collapse:collapse;margin:10px 0}.about-v24 th,.about-v24 td{border:1px solid rgba(255,176,0,.22);padding:8px 10px;vertical-align:top}.about-v24 th{color:#ffb000;background:rgba(255,176,0,.08)}
</style>

<div class="card">
  <h2>À propos de PinCabOS</h2>

<!-- PINCABOS_ABOUT_V26_RESTORE_ACTION_BUTTONS START -->
<div class="pco-about-action-row"
     style="display:flex; gap:10px; flex-wrap:wrap; margin:10px 0 16px;">
  <a class="button" href="/help">📖 Aide / Documentation</a>
  <a class="button" href="/dev">🧪 Développeur / rapport testeur</a>
</div>
<!-- PINCABOS_ABOUT_V26_RESTORE_ACTION_BUTTONS END -->

  <p>
    <strong>PinCabOS __VERSION_FULL__</strong> est un système Linux spécialisé pour les pincabs virtuels.
    Il ajoute autour de VPX Linux et VPinFE une WebApp centrale, un Dashboard configurable, des outils de fichiers,
    des fonctions de configuration cabinet, des imports/exports, des widgets, des services système et des outils de dépannage.
  </p>
  <p>
    PinCabOS agit comme backend système : il ne remplace pas VPX, ne remplace pas VPinFE,
    mais les relie avec les écrans, l’audio, les inputs, le DOF, le FullDMD, le réseau, les médias et les outils de maintenance.
  </p>
  <p>
__PILLS__
    <span class="about-pill">Dashboard widgets</span>
    <span class="about-pill">PinCab Explorer</span>
    <span class="about-pill">Image Studio</span>
    <span class="about-pill">Smart Import</span>
    <span class="about-pill">Batch Smart Import</span>
    <span class="about-pill">Batch Smart Export</span>
    <span class="about-pill">Apparence</span>
    <span class="about-pill">Clavier régional</span>
    <span class="about-pill">Map Commander</span>
    <span class="about-pill">FullDMD auto DMD</span>
    <span class="about-pill">ConfigTools</span>
    <span class="about-pill">Medias Hunter</span>
  </p>
</div>

<div class="card">
  <h2>Version et source de vérité</h2>
  <p>Les informations de version doivent venir de <code>/opt/pincabos/version.json</code>.</p>
  <table>
    <tr><th>Champ</th><th>Valeur</th></tr>
    <tr><td>Version</td><td><code>__VERSION__</code></td></tr>
    <tr><td>Build</td><td><code>__BUILD__</code></td></tr>
    <tr><td>Channel</td><td><code>__CHANNEL__</code></td></tr>
    <tr><td>Codename</td><td><code>__CODENAME__</code></td></tr>
    <tr><td>Author</td><td><code>__AUTHOR__</code></td></tr>
    <tr><td>Site</td><td><code>__SITE__</code></td></tr>
  </table>
</div>

<div class="card">
  <h2>Fonctions principales PinCabOS</h2>
  <div class="about-grid">
    <div class="about-mini"><strong>Dashboard configurable</strong><p>Dashboard construit avec widgets : raccourcis, fonctions utiles, services, live screens, audio, batch status et table en cours.</p></div>
    <div class="about-mini"><strong>Widgets</strong><p>Services, live Playfield/Backglass/FullDMD, volumes audio, Batch Import/Export, table active, réseau et raccourcis outils.</p></div>
    <div class="about-mini"><strong>Apparence</strong><p>Personnalisation visuelle PinCabOS et gestion des médias système via les outils disponibles.</p></div>
    <div class="about-mini"><strong>Clavier régional</strong><p>Configuration du layout clavier avant mapping pour éviter les erreurs de touches et symboles.</p></div>
    <div class="about-mini"><strong>PinCab Explorer</strong><p>Explorateur Web : fichiers, dossiers, upload, download, rename, duplicate, delete, ZIP, live viewer et éditeur texte.</p></div>
    <div class="about-mini"><strong>Image Studio</strong><p>Édition PNG/JPG/WEBP avec dessin, texte, crop, resize, erase et Magic Wand.</p></div>
    <div class="about-mini"><strong>Smart Import</strong><p>Analyse et import de tables, archives, médias, ROMs, B2S, PupPack et fichiers associés.</p></div>
    <div class="about-mini"><strong>Batch Smart Import</strong><p>Import de plusieurs packages avec analyse, conflits, progression et suivi Dashboard.</p></div>
    <div class="about-mini"><strong>Batch Smart Export</strong><p>Export de plusieurs tables vers packages PinCabOS, local, USB ou SMB selon configuration.</p></div>
    <div class="about-mini"><strong>VPX</strong><p>Wrapper, INI, chemins, tables, rendu BGFX et paramètres cabinet.</p></div>
    <div class="about-mini"><strong>VPinFE</strong><p>Frontend principal, tables, médias, collections, wheels, launch, update et sections intégrées.</p></div>
    <div class="about-mini"><strong>VPS / ConfigTools</strong><p>Outils d’association, documentation et configuration avancée quand disponibles.</p></div>
    <!-- PINCABOS_ABOUT_MEDIA_HUNTER_V1 START -->
    <div class="about-mini"><strong>Medias Hunter</strong><p>Analyse les dossiers medias des tables, détecte seulement les fichiers absents et les recherche dans VPinMediaDB, des dossiers locaux ou réseau montés et des sources Web configurables, sans modifier VPinFE ni écraser les médias existants.</p></div>
    <!-- PINCABOS_ABOUT_MEDIA_HUNTER_V1 END -->
    <div class="about-mini"><strong>Écrans / GPU</strong><p>Playfield, Backglass, FullDMD, géométrie, rôles, widgets live et boutons menu Playfield/Backglass.</p></div>
    <div class="about-mini"><strong>FullDMD / DMD</strong><p>Calibration, AutoArrange, auto-réglage DMD, validation du DMD et rôle FullDMD.</p></div>
    <div class="about-mini"><strong>Audio / SSF</strong><p>Cartes audio, rôles, tests, surround, bass shaker et widget volumes.</p></div>
    <div class="about-mini"><strong>Inputs / Map Commander</strong><p>Mapping, auto mapping, détection, visuel nudge, visuel plunger et réglages analogiques.</p></div>
    <div class="about-mini"><strong>DOF / Outputs</strong><p>LedWiz, DudesCab, MX, toys, tests, configs et sécurité outputs.</p></div>
    <div class="about-mini"><strong>Réseau / SMB / USB</strong><p>DHCP, IP fixe, Wi-Fi, NAS/SMB, USB, Share et accès remote.</p></div>
  </div>
</div>

<div class="card">
  <h2>Boutons et raccourcis importants</h2>
  <ul>
    <li><strong>Playfield :</strong> afficher ou retirer la WebApp sur le Playfield.</li>
    <li><strong>Backglass :</strong> afficher ou retirer la WebApp sur le Backglass.</li>
    <li><strong>Ouvrir VPinFE :</strong> ouvrir ou ramener le frontend.</li>
    <li><strong>Ouvrir VPS :</strong> utiliser l’aide VPS quand disponible pour tables et association.</li>
    <li><strong>ConfigTools :</strong> accéder aux configurations avancées VPX, VPinFE, DOF ou cabinet selon les modules présents.</li>
    <li><strong>Medias Hunter :</strong> ouvrir l’analyseur indépendant sous <code>/tools/vpinfe/media-hunter</code>.</li>
  </ul>
</div>


<!-- PINCABOS_ABOUT_V25_ADD_ONLY_FUNCTIONS START -->
<div class="card">
  <h2>Fonctions additionnelles documentées</h2>
  <p>
    PinCabOS inclut aussi des fonctions qui méritent d’être visibles dans la page À propos,
    car elles font partie de l’expérience réelle du cab.
  </p>
  <ul>
    <li><strong>Apparence :</strong> personnalisation visuelle, médias système et cohérence graphique de la WebApp.</li>
    <li><strong>Batch Smart Import :</strong> traitement de plusieurs packages avec analyse, conflits, progression et suivi.</li>
    <li><strong>Batch Smart Export :</strong> export de plusieurs tables vers packages PinCabOS, USB, SMB ou local selon configuration.</li>
    <li><strong>Dashboard configurable :</strong> widgets pouvant servir de raccourcis, statuts, contrôles, fonctions utiles ou diagnostics live.</li>
    <li><strong>Clavier régional :</strong> configuration du layout avant mapping pour éviter les erreurs de touches.</li>
    <li><strong>Inputs avancés :</strong> Map Commander, mapping automatique, visuel nudge et visuel plunger.</li>
    <li><strong>FullDMD avancé :</strong> calibration, AutoArrange et auto-réglage DMD lorsque la géométrie est détectable.</li>
    <li><strong>Boutons Playfield / Backglass :</strong> affichage ou retrait rapide de la WebApp sur les écrans du cab.</li>
    <li><strong>Boutons VPinFE / VPS :</strong> accès rapide au frontend et aux informations de tables.</li>
    <li><strong>ConfigTools :</strong> accès aux fonctions de configuration avancée selon les modules installés.</li>
    <li><strong>Medias Hunter :</strong> détection des médias absents, sources configurables et installation protégée sans écrasement.</li>
  </ul>
</div>
<!-- PINCABOS_ABOUT_V25_ADD_ONLY_FUNCTIONS END -->

<div class="card">
  <h2>Matériel de référence</h2>
  <p>Le développement et les tests ont été réalisés principalement autour de :</p>
  <ul>
    <li>GPU NVIDIA.</li>
    <li>LedWiz32 original.</li>
    <li>Carte DudesCab.</li>
    <li>Module MX Downy.</li>
    <li>Plunger slider de L’atelier d’Arnoz.</li>
  </ul>
  <div class="about-danger">
    D’autres périphériques peuvent fonctionner, mais peuvent nécessiter des ajustements via PinCab Console,
    ConfigTools ou assistance ChatGPT, à vos risques, avec backups.
  </div>
</div>

<div class="card">
  <h2>Chemins importants</h2>
  <table>
    <tr><th>Élément</th><th>Chemin</th></tr>
    <tr><td>Base PinCabOS</td><td><code>/opt/pincabos</code></td></tr>
    <tr><td>WebApp</td><td><code>/opt/pincabos/web</code></td></tr>
    <tr><td>About/Help</td><td><code>/opt/pincabos/web/PinCabOS-AboutHelp.py</code></td></tr>
    <tr><td>VPX</td><td><code>__VPX_DIR__</code></td></tr>
    <tr><td>VPX wrapper</td><td><code>__VPX_WRAPPER__</code></td></tr>
    <tr><td>VPinFE</td><td><code>__VPINFE_CURRENT__</code></td></tr>
    <tr><td>Tables</td><td><code>/home/pinball/Tables</code></td></tr>
    <tr><td>Médias PinCabOS</td><td><code>/opt/pincabos/media</code></td></tr>
    <tr><td>SMB</td><td><code>/home/pinball/NetworkDrives</code></td></tr>
  </table>
</div>

<div class="card">
  <h2>Auteur</h2>
  <p><strong>__AUTHOR__</strong><br>
  Projet développé autour de VPX Linux, VPinFE, PinCabOS Web, Dashboard, widgets, Smart Import/Export,
  FullDMD, audio/SSF, inputs, DOF, réseau, fichiers et automatisation pour pincabs.</p>
  <p><a href="https://__SITE__" target="_blank" rel="noopener">https://__SITE__</a></p>
</div>

</div>
"""
    for key, value in replacements.items():
        body = body.replace(key, value)

    # PINCABOS_ABOUT_AUDIT_ATTACH_V2
    body += pincabos_about_audit_html()
    return page("À propos", body)





def register(app, page_func=None, esc_func=None, pco_path_text_func=None, pincabos_version_func=None):
    """
    Enregistre les routes About/Help dans Flask.

    Les helpers viennent de app.py pour conserver le rendu existant:
    - page()
    - esc()
    - pco_path_text()
    - pincabos_version()
    """
    global page, esc, pco_path_text, pincabos_version

    if page_func is not None:
        page = page_func
    if esc_func is not None:
        esc = esc_func
    if pco_path_text_func is not None:
        pco_path_text = pco_path_text_func
    if pincabos_version_func is not None:
        pincabos_version = pincabos_version_func

    if "help_page" not in app.view_functions:
        app.add_url_rule("/help", "help_page", help_page, methods=["GET"])

    if "about_page" not in app.view_functions:
        app.add_url_rule("/about", "about_page", about_page, methods=["GET"])
