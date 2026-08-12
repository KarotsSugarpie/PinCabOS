"""Guide pratique, dépannage et récupération pour PinCabOS Help."""

from __future__ import annotations


def pincabos_help_guide_html() -> str:
    return r"""
<!-- PINCABOS_HELP_GUIDE_PRACTICAL_V1_START -->

<style>
  .pcos-help-guide-v1 {
    margin-top:24px;
    padding-top:22px;
    border-top:1px solid var(--line,rgba(255,255,255,.14));
  }

  .pcos-help-guide-v1 * {
    box-sizing:border-box;
  }

  .pcos-help-guide-v1__intro {
    margin-bottom:16px;
  }

  .pcos-help-guide-v1__nav {
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin:14px 0 18px;
  }

  .pcos-help-guide-v1__nav a {
    display:inline-flex;
    padding:7px 10px;
    border:1px solid var(--line,rgba(255,255,255,.16));
    border-radius:999px;
    text-decoration:none;
  }

  .pcos-help-guide-v1__grid {
    display:grid;
    grid-template-columns:repeat(
      auto-fit,
      minmax(min(100%,310px),1fr)
    );
    gap:14px;
  }

  .pcos-help-guide-v1__card {
    min-width:0;
  }

  .pcos-help-guide-v1__card h3 {
    margin-top:0;
  }

  .pcos-help-guide-v1__steps {
    margin:0;
    padding-left:22px;
  }

  .pcos-help-guide-v1__steps li {
    margin:7px 0;
    line-height:1.45;
  }

  .pcos-help-guide-v1__table {
    width:100%;
  }

  .pcos-help-guide-v1__table td,
  .pcos-help-guide-v1__table th {
    vertical-align:top;
  }

  .pcos-help-guide-v1__warning {
    margin-top:14px;
    padding:13px 15px;
    border:1px solid rgba(247,201,72,.48);
    border-radius:12px;
    background:rgba(247,201,72,.07);
  }

  .pcos-help-guide-v1__safe {
    margin-top:14px;
    padding:13px 15px;
    border:1px solid rgba(88,214,141,.45);
    border-radius:12px;
    background:rgba(88,214,141,.07);
  }

  .pcos-help-guide-v1 pre {
    overflow:auto;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
  }

  .pcos-help-guide-v1 code {
    overflow-wrap:anywhere;
  }
</style>

<section id="guide-pratique-pincabos"
         class="pcos-help-guide-v1">

  <div class="card pcos-help-guide-v1__intro">
    <h2>Guide pratique, dépannage et récupération</h2>

    <p>
      Cette section complète l’aide existante sans la remplacer.
      Elle rassemble le parcours de configuration recommandé,
      les premières vérifications à effectuer et les procédures
      de récupération sécuritaires.
    </p>

    <nav class="pcos-help-guide-v1__nav"
         aria-label="Navigation du guide pratique">
      <a href="#help-demarrage-rapide">Démarrage rapide</a>
      <a href="#help-utilisation-quotidienne">Utilisation</a>
      <a href="#help-depannage">Dépannage</a>
      <a href="#help-dudescab-usb">DudesCab et USB</a>
      <a href="#help-limites-connues">Limites connues</a>
      <a href="#help-journaux">Journaux</a>
    </nav>
  </div>

  <div class="pcos-help-guide-v1__grid">

    <article id="help-demarrage-rapide"
             class="card pcos-help-guide-v1__card">
      <h3>Démarrage rapide recommandé</h3>

      <ol class="pcos-help-guide-v1__steps">
        <li>
          Configurer le réseau Ethernet ou Wi-Fi et confirmer
          l’accès à la WebApp.
        </li>
        <li>
          Vérifier le GPU, son pilote et le fonctionnement
          de Vulkan.
        </li>
        <li>
          Assigner les rôles Playfield, Backglass et FullDMD,
          puis valider leurs positions.
        </li>
        <li>
          Configurer les sorties audio Playfield/SSF et
          Backglass/DMD/ROM.
        </li>
        <li>
          Ouvrir <a href="/inputs">Inputs Studio</a>,
          conserver le mode automatique et tester les entrées.
        </li>
        <li>
          Importer une première table, valider ses médias,
          son Backglass, son DMD et son DOF.
        </li>
      </ol>
    </article>

    <article id="help-utilisation-quotidienne"
             class="card pcos-help-guide-v1__card">
      <h3>Utilisation quotidienne</h3>

      <ul class="pcos-help-guide-v1__steps">
        <li>
          Utiliser VPinFE pour parcourir et lancer les tables.
        </li>
        <li>
          Fermer une table normalement avant de redémarrer
          VPinFE ou de modifier les périphériques USB.
        </li>
        <li>
          Utiliser Smart Import pour ajouter une table et
          ses composants associés.
        </li>
        <li>
          Utiliser Batch Import/Export pour les opérations
          portant sur plusieurs tables.
        </li>
        <li>
          Utiliser <a href="/fulldmd">FullDMD</a> pour la
          calibration et AutoArrange.
        </li>
        <li>
          Consulter le Dashboard pour l’état des services,
          les écrans live et la table actuellement en jeu.
        </li>
        <li>
          Vérifier les mises à jour avant de modifier
          manuellement le système.
        </li>
      </ul>
    </article>

  </div>

  <section id="help-depannage"
           class="card"
           style="margin-top:14px;">
    <h3>Dépannage rapide par symptôme</h3>

    <div style="overflow:auto;">
      <table class="pcos-help-guide-v1__table">
        <thead>
          <tr>
            <th>Symptôme</th>
            <th>Première vérification</th>
          </tr>
        </thead>

        <tbody>
          <tr>
            <td>WebApp inaccessible</td>
            <td>
              Vérifier <code>pincabos-webapp.service</code>
              et l’écoute du port 80.
            </td>
          </tr>

          <tr>
            <td>VPinFE ne démarre pas</td>
            <td>
              Vérifier le service VPinFE, la session X11 et
              la topologie des écrans.
            </td>
          </tr>

          <tr>
            <td>Une table reste ouverte</td>
            <td>
              Utiliser la carte de table en cours et son
              bouton Stop avant de redémarrer VPinFE.
            </td>
          </tr>

          <tr>
            <td>Backglass absent</td>
            <td>
              Vérifier B2SLegacy, le rôle Backglass et la
              présence du fichier <code>.directb2s</code>.
            </td>
          </tr>

          <tr>
            <td>FullDMD vide ou mal placé</td>
            <td>
              Vérifier le rôle FullDMD, le layout local de
              la table et relancer AutoArrange si nécessaire.
            </td>
          </tr>

          <tr>
            <td>DMD ou ROM absent</td>
            <td>
              Vérifier PinMAME, le nom de la ROM, DMDUtil,
              Serum/VNI et les chemins de la table.
            </td>
          </tr>

          <tr>
            <td>Bouton ou plunger incorrect</td>
            <td>
              Vérifier Inputs Studio en mode Auto, puis
              tester séparément le clavier et le gamepad.
            </td>
          </tr>

          <tr>
            <td>DOF bloqué après un changement USB</td>
            <td>
              Fermer la table VPX et vérifier le service
              DudesCab Hotplug Recovery.
            </td>
          </tr>

          <tr>
            <td>Import ou export échoué</td>
            <td>
              Consulter les journaux Smart Import/Export,
              l’espace disque et la destination sélectionnée.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>

  <div class="pcos-help-guide-v1__grid"
       style="margin-top:14px;">

    <article id="help-dudescab-usb"
             class="card pcos-help-guide-v1__card">
      <h3>DudesCab et USB</h3>

      <ul class="pcos-help-guide-v1__steps">
        <li>
          PinCabOS reconnaît le DudesCab avec le VID/PID
          <code>2e8a:106f</code>.
        </li>
        <li>
          Les noms <code>hidrawN</code>,
          <code>eventN</code> et <code>jsN</code>
          peuvent changer après une reconnexion.
        </li>
        <li>
          Ne jamais dépendre manuellement d’un numéro
          <code>hidraw</code> fixe.
        </li>
        <li>
          Le lien série stable fourni par PinCabOS est
          <code>/dev/dudescab</code>.
        </li>
        <li>
          Dans Inputs Studio, le mode automatique est
          recommandé plutôt qu’un chemin
          <code>/dev/input/eventN</code> fixé manuellement.
        </li>
        <li>
          VPX utilise l’identité SDL du contrôleur et non
          directement un numéro <code>hidraw</code>.
        </li>
        <li>
          La navigation VPinFE utilise principalement les
          entrées clavier configurées.
        </li>
      </ul>

      <div class="pcos-help-guide-v1__warning">
        <strong>Important :</strong>
        un reset USB logique peut réénumérer le DudesCab,
        mais il ne garantit pas la coupure de son alimentation
        électrique 5 V.
      </div>
    </article>

    <article class="card pcos-help-guide-v1__card">
      <h3>Récupération après hotplug</h3>

      <ol class="pcos-help-guide-v1__steps">
        <li>
          Ne pas interrompre brutalement une table VPX active.
        </li>
        <li>
          Fermer la table normalement.
        </li>
        <li>
          Laisser le service Hotplug Recovery vérifier le
          DOF Helper.
        </li>
        <li>
          VPinFE peut être redémarré automatiquement lorsque
          VPX n’est plus actif.
        </li>
        <li>
          Vérifier qu’aucun fichier
          <code>hidraw (deleted)</code> ne demeure ouvert.
        </li>
      </ol>

      <pre>systemctl status pincabos-dudescab-hotplug-recovery.service
journalctl -u pincabos-dudescab-hotplug-recovery.service -n 100</pre>

      <div class="pcos-help-guide-v1__warning">
        Ne jamais couper un hub USB avec
        <code>uhubctl</code> sans avoir confirmé que le
        DudesCab est réellement branché sur le hub et le
        port ciblés.
      </div>
    </article>

  </div>

  <section id="help-limites-connues"
           class="card"
           style="margin-top:14px;">
    <h3>Limites connues et validations restantes</h3>

    <ul class="pcos-help-guide-v1__steps">
      <li>
        Une interaction possible entre le plunger et
        l’entrée analogique du flipper droit doit encore
        être confirmée par un test physique.
      </li>
      <li>
        Le Hotplug Recovery attend volontairement la
        fermeture de VPX avant de redémarrer VPinFE.
      </li>
      <li>
        Un reset logique USB ne constitue pas un véritable
        power cycle matériel.
      </li>
      <li>
        Une vraie remise hors tension du DudesCab peut
        nécessiter un débranchement ou un hub supportant la
        coupure électrique individuelle.
      </li>
      <li>
        La sélection d’un sous-dossier SMB pour certains
        exports Batch doit être validée avant une opération
        importante.
      </li>
      <li>
        L’installation automatique des pilotes AMD et Intel
        doit être validée sur du matériel réel avant d’être
        considérée universelle.
      </li>
      <li>
        Les fonctions annoncées comme projets futurs dans
        About ne sont pas encore des fonctions publiées.
      </li>
    </ul>
  </section>

  <div class="pcos-help-guide-v1__grid"
       style="margin-top:14px;">

    <article id="help-journaux"
             class="card pcos-help-guide-v1__card">
      <h3>Journaux et diagnostic</h3>

      <p>Répertoires principaux :</p>

      <pre>/opt/pincabos/logs/
/opt/pincabos/logs/updates/
/opt/pincabos/logs/input-audits/
/opt/pincabos/logs/help-audits/
/opt/pincabos/logs/about-audits/</pre>

      <p>Commandes de première vérification :</p>

      <pre>systemctl status pincabos-webapp.service
systemctl status pincabos-vpinfe.service
systemctl status pincabos-dashboard-live.service
systemctl status pincabos-dudescab-watchdog.service
systemctl status pincabos-usb-secure-lock.service

journalctl -u pincabos-webapp.service -n 100
journalctl -u pincabos-vpinfe.service -n 100</pre>
    </article>

    <article class="card pcos-help-guide-v1__card">
      <h3>Protection des tables et configurations</h3>

      <ul class="pcos-help-guide-v1__steps">
        <li>
          Toujours effectuer une sauvegarde avant de remplacer
          une table existante.
        </li>
        <li>
          Privilégier Smart Import et les outils PinCabOS pour
          conserver les composants associés.
        </li>
        <li>
          Ne pas modifier automatiquement les fichiers
          <code>.vpx</code>, <code>.vbs</code> ou
          <code>.directb2s</code> pour corriger un problème
          système.
        </li>
        <li>
          Vérifier les chemins VPX et VPinFE avant de déplacer
          la bibliothèque de tables.
        </li>
        <li>
          Conserver les layouts FullDMD et configurations
          spécifiques dans le dossier local de la table.
        </li>
      </ul>

      <div class="pcos-help-guide-v1__safe">
        <strong>Bonne pratique PinCabOS :</strong>
        auditer le fichier ou le service réellement utilisé,
        sauvegarder, appliquer une correction ciblée, puis
        valider le fonctionnement avant tout autre changement.
      </div>
    </article>

  </div>

  <p style="margin-top:16px;">
    <a class="button secondary" href="/about">
      Voir la présentation et la feuille de route
    </a>
  </p>

</section>

<!-- PINCABOS_HELP_GUIDE_PRACTICAL_V1_END -->
"""


__all__ = ["pincabos_help_guide_html"]
