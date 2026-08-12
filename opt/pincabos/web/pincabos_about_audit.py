"""Synthèse fonctionnelle auditée pour la page About de PinCabOS."""

from __future__ import annotations

import html
import os
import platform
import subprocess
from pathlib import Path


MARKER = "PINCABOS_ABOUT_AUDIT_OVERVIEW_V1"
TABLES_ROOT = Path("/home/pinball/Tables")


def _run(command: list[str], timeout: float = 1.5) -> str:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception:
        return ""

    return (completed.stdout or "").strip()


def _service_state(name: str) -> str:
    value = _run(
        ["/usr/bin/systemctl", "is-active", name],
        timeout=1.0,
    )

    return value or "inconnu"


def _service_label(state: str) -> tuple[str, str]:
    if state == "active":
        return "Actif", "ok"

    if state in {"activating", "reloading"}:
        return "Transition", "warn"

    if state in {"inactive", "deactivating"}:
        return "Inactif", "neutral"

    if state == "failed":
        return "Erreur", "bad"

    return html.escape(state), "neutral"


def _os_name() -> str:
    values: dict[str, str] = {}

    try:
        for raw in Path("/etc/os-release").read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if "=" not in raw:
                continue

            key, value = raw.split("=", 1)
            values[key] = value.strip().strip('"')
    except Exception:
        pass

    return (
        values.get("PRETTY_NAME")
        or values.get("NAME")
        or platform.platform()
    )


def _gpu_summary() -> str:
    value = _run(
        [
            "/usr/bin/nvidia-smi",
            "--query-gpu=name,driver_version",
            "--format=csv,noheader",
        ],
        timeout=2.0,
    )

    if value:
        return value.splitlines()[0]

    lspci = _run(["/usr/bin/lspci", "-nn"], timeout=1.5)

    for line in lspci.splitlines():
        folded = line.casefold()

        if (
            "vga compatible controller" in folded
            or "3d controller" in folded
        ):
            return line.split(":", 2)[-1].strip()

    return "Détection GPU non disponible"


def _table_count() -> int:
    try:
        return sum(
            1
            for entry in TABLES_ROOT.iterdir()
            if entry.is_dir()
        )
    except Exception:
        return 0


def _service_row(name: str, title: str) -> str:
    state = _service_state(name)
    label, kind = _service_label(state)

    return (
        '<div class="pcos-about-status-row">'
        f'<span>{html.escape(title)}</span>'
        f'<span class="pcos-about-pill {kind}">{label}</span>'
        "</div>"
    )


def pincabos_about_audit_html() -> str:
    """Retourne la synthèse essentielle du rapport fonctionnel PinCabOS."""

    services = [
        ("pincabos-webapp.service", "WebApp"),
        ("pincabos-vpinfe.service", "VPinFE"),
        ("pincabos-dashboard-live.service", "Dashboard Live"),
        (
            "pincabos-dudescab-watchdog.service",
            "Watchdog DudesCab",
        ),
        (
            "pincabos-usb-secure-lock.service",
            "USB Secure Lock",
        ),
    ]

    required_states = {
        name: _service_state(name)
        for name, _title in services[:3]
    }

    healthy = all(
        state == "active"
        for state in required_states.values()
    )

    overall_label = (
        "Système opérationnel"
        if healthy
        else "Vérification recommandée"
    )

    overall_kind = "ok" if healthy else "warn"

    service_rows = "".join(
        _service_row(name, title)
        for name, title in services
    )

    os_name = html.escape(_os_name())
    gpu = html.escape(_gpu_summary())
    hostname = html.escape(platform.node() or "PinCabOS")
    kernel = html.escape(platform.release())
    table_count = _table_count()

    return f"""
<!-- PINCABOS_ABOUT_AUDIT_OVERVIEW_V1_START -->
<section id="pincabos-about-audit-v1"
         class="pcos-about-audit-v1"
         aria-labelledby="pcos-about-audit-title">

  <style>
    .pcos-about-audit-v1 {{
      margin-top:24px;
      padding-top:22px;
      border-top:1px solid var(--line, rgba(255,255,255,.14));
    }}

    .pcos-about-audit-v1 * {{
      box-sizing:border-box;
    }}

    .pcos-about-audit-head {{
      display:flex;
      align-items:flex-start;
      justify-content:space-between;
      gap:16px;
      margin-bottom:16px;
    }}

    .pcos-about-audit-head h2 {{
      margin:0 0 5px;
    }}

    .pcos-about-audit-head p {{
      margin:0;
      opacity:.78;
    }}

    .pcos-about-grid {{
      display:grid;
      grid-template-columns:repeat(
        auto-fit,
        minmax(min(100%, 250px), 1fr)
      );
      gap:14px;
    }}

    .pcos-about-panel {{
      min-width:0;
      padding:16px;
      border:1px solid var(--line, rgba(255,255,255,.14));
      border-radius:14px;
      background:var(--card, rgba(255,255,255,.035));
    }}

    .pcos-about-panel h3 {{
      margin:0 0 10px;
      font-size:1rem;
    }}

    .pcos-about-panel p {{
      margin:7px 0;
      line-height:1.45;
    }}

    .pcos-about-list {{
      display:grid;
      gap:7px;
      margin:0;
      padding:0;
      list-style:none;
    }}

    .pcos-about-list li {{
      position:relative;
      padding-left:18px;
      line-height:1.42;
    }}

    .pcos-about-list li::before {{
      content:"✓";
      position:absolute;
      left:0;
      top:0;
      font-weight:800;
      color:#58d68d;
    }}

    .pcos-about-pill {{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      min-height:25px;
      padding:3px 9px;
      border:1px solid currentColor;
      border-radius:999px;
      font-size:.78rem;
      font-weight:750;
      white-space:nowrap;
    }}

    .pcos-about-pill.ok {{
      color:#58d68d;
    }}

    .pcos-about-pill.warn {{
      color:#f7c948;
    }}

    .pcos-about-pill.bad {{
      color:#ff6b6b;
    }}

    .pcos-about-pill.neutral {{
      opacity:.72;
    }}

    .pcos-about-status {{
      display:grid;
      gap:7px;
    }}

    .pcos-about-status-row {{
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      min-width:0;
      padding:7px 0;
      border-bottom:1px solid
        var(--line, rgba(255,255,255,.09));
    }}

    .pcos-about-status-row:last-child {{
      border-bottom:0;
    }}

    .pcos-about-kv {{
      display:grid;
      grid-template-columns:minmax(92px, auto) minmax(0, 1fr);
      gap:7px 12px;
      margin:0;
    }}

    .pcos-about-kv dt {{
      font-weight:750;
      opacity:.8;
    }}

    .pcos-about-kv dd {{
      min-width:0;
      margin:0;
      overflow-wrap:anywhere;
    }}

    .pcos-about-highlight {{
      margin-top:14px;
      padding:14px 16px;
      border:1px solid rgba(88,214,141,.45);
      border-radius:13px;
      background:rgba(88,214,141,.07);
    }}

    .pcos-about-highlight strong {{
      color:#58d68d;
    }}

    .pcos-about-open {{
      margin-top:14px;
      border:1px solid var(--line, rgba(255,255,255,.14));
      border-radius:13px;
      overflow:hidden;
    }}

    .pcos-about-open summary {{
      padding:13px 15px;
      font-weight:750;
      cursor:pointer;
    }}

    .pcos-about-open-content {{
      padding:0 15px 15px;
    }}

    .pcos-about-open-content ul {{
      margin:0;
      padding-left:19px;
    }}

    @media (max-width:700px) {{
      .pcos-about-audit-head {{
        display:grid;
      }}

      .pcos-about-kv {{
        grid-template-columns:1fr;
        gap:2px;
      }}

      .pcos-about-kv dd {{
        margin-bottom:8px;
      }}
    }}
  </style>

  <header class="pcos-about-audit-head">
    <div>
      <h2 id="pcos-about-audit-title">
        PinCabOS — synthèse fonctionnelle auditée
      </h2>
      <p>
        Les principales capacités validées du système,
        du cabinet et de l’écosystème Visual Pinball.
      </p>
    </div>

    <span class="pcos-about-pill {overall_kind}">
      {overall_label}
    </span>
  </header>

  <div class="pcos-about-grid">

    <article class="pcos-about-panel">
      <h3>Plateforme</h3>

      <dl class="pcos-about-kv">
        <dt>Machine</dt>
        <dd>{hostname}</dd>

        <dt>Système</dt>
        <dd>{os_name}</dd>

        <dt>Noyau</dt>
        <dd>{kernel}</dd>

        <dt>GPU</dt>
        <dd>{gpu}</dd>

        <dt>Tables</dt>
        <dd>{table_count} dossier(s) détecté(s)</dd>
      </dl>
    </article>

    <article class="pcos-about-panel">
      <h3>Moteur de jeu</h3>

      <ul class="pcos-about-list">
        <li>Visual Pinball X 10.8 BGFX sous Vulkan</li>
        <li>Rendu X11 et configuration trois écrans</li>
        <li>Playfield, Backglass et FullDMD par rôles</li>
        <li>Mappings clavier et contrôleur SDL</li>
        <li>Plunger et nudge analogiques</li>
        <li>Audio séparé Playfield/SSF et Backglass/ROM</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>Frontend et WebApp</h3>

      <ul class="pcos-about-list">
        <li>VPinFE avec tables, collections et médias</li>
        <li>WebApp directe sur le port 80</li>
        <li>Dashboard personnalisable et widgets live</li>
        <li>Contrôle des services et table en cours</li>
        <li>Console Web et outils d’administration</li>
        <li>Mises à jour WebApp, VPinFE, système et GPU</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>Tables et médias</h3>

      <ul class="pcos-about-list">
        <li>Smart Import avec validation et sauvegarde</li>
        <li>Import et export Batch avec progression</li>
        <li>Destinations locales, USB et SMB</li>
        <li>ROM, B2S, PupPack, médias et FullDMD</li>
        <li>Gestion des conflits : ignorer, renommer, remplacer</li>
        <li>Protection des fichiers VPX et scripts de table</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>DMD, Backglass et FullDMD</h3>

      <ul class="pcos-about-list">
        <li>PinMAME, Serum, VNI, FlexDMD et ScoreView</li>
        <li>B2SLegacy et routage Backglass</li>
        <li>Support PUP et vidéos par écran</li>
        <li>Calibration FullDMD manuelle et automatique</li>
        <li>Layouts et images enregistrés par table</li>
        <li>AutoArrange avec cache mémoire multithread</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>Cabinet et DOF</h3>

      <ul class="pcos-about-list">
        <li>DudesCab détecté par VID/PID 2e8a:106f</li>
        <li>Clavier, gamepad, plunger, nudge et HID</li>
        <li>LED-Wiz #1, UMX #30 et DudesCab #90</li>
        <li>DOF VPX et DOF Helper VPinFE</li>
        <li>USB Secure Lock et watchdog DudesCab</li>
        <li>Récupération après renumérotation HIDRAW</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>Réseau et stockage</h3>

      <ul class="pcos-about-list">
        <li>Ethernet, Wi-Fi, DHCP et NetworkManager</li>
        <li>Navigation SMB et stockage réseau</li>
        <li>Montages USB et destinations d’export</li>
        <li>Vérifications de connectivité au démarrage</li>
        <li>Détection automatique des interfaces réseau</li>
        <li>Journaux et diagnostics centralisés</li>
      </ul>
    </article>

    <article class="pcos-about-panel">
      <h3>État des services</h3>

      <div class="pcos-about-status">
        {service_rows}
      </div>
    </article>

  </div>

  <div class="pcos-about-highlight">
    <strong>Optimisation FullDMD validée :</strong>
    la génération de la page AutoArrange est passée
    d’environ 28 secondes à moins de 0,01 seconde,
    et son API d’environ 26 secondes à moins de
    0,002 seconde grâce au cache mémoire.
  </div>

  <!-- PINCABOS_ABOUT_FUTURE_PROJECTS_V1_START -->
  <section class="pcos-about-audit-v1"
           aria-labelledby="pcos-about-future-title">

    <header class="pcos-about-audit-head">
      <div>
        <h2 id="pcos-about-future-title">
          Projets futurs
        </h2>

        <p>
          La feuille de route de PinCabOS continue de grandir.
          Plusieurs fonctions majeures sont déjà planifiées
          ou en cours de développement.
        </p>
      </div>

      <span class="pcos-about-pill warn">
        En développement
      </span>
    </header>

    <div class="pcos-about-grid">

      <article class="pcos-about-panel">
        <h3>DOF Commander</h3>

        <p>
          Finalisation d’une interface centrale pour configurer,
          diagnostiquer et contrôler les périphériques DOF,
          les toys, les sorties classiques et les éclairages
          adressables.
        </p>
      </article>

      <article class="pcos-about-panel">
        <h3>Auto Recording des tables</h3>

        <p>
          Enregistrement automatique des tables présentes dans
          PinCabOS afin de produire directement les vidéos,
          captures et autres médias nécessaires à VPinFE.
        </p>
      </article>

      <article class="pcos-about-panel">
        <h3>PinCabOS Battle</h3>

        <p>
          Système permettant de lancer une table en mode
          multijoueur réseau avec d’autres cabinets PinCabOS
          à travers Internet.
        </p>
      </article>

      <article class="pcos-about-panel">
        <h3>Mises à jour simplifiées</h3>

        <p>
          Mise en place d’un mécanisme centralisé et simple
          pour mettre à jour le cœur de PinCabOS, ses modules,
          ses outils et la WebApp.
        </p>
      </article>

      <article class="pcos-about-panel">
        <h3>Équipe de développement</h3>

        <p>
          Le plan et la feuille de route sont déjà construits.
          Le projet recherche des développeurs, testeurs,
          intégrateurs, créateurs et collaborateurs souhaitant
          participer à son évolution.
        </p>
      </article>

      <article class="pcos-about-panel">
        <h3>Et plusieurs autres projets…</h3>

        <p>
          De nouvelles fonctions pour l’automatisation,
          le cabinet, les médias, le jeu en réseau,
          la maintenance et l’expérience utilisateur
          sont également à l’étude.
        </p>
      </article>

    </div>

    <div class="pcos-about-highlight">
      <strong>Contribuer à PinCabOS :</strong>
      le projet dispose déjà d’une vision technique et d’un
      plan de développement. Toute aide sérieuse pour bâtir
      une équipe et accélérer son évolution est la bienvenue.
    </div>

  </section>
  <!-- PINCABOS_ABOUT_FUTURE_PROJECTS_V1_END -->

  <details class="pcos-about-open">
    <summary>Validations matérielles ou finales restantes</summary>

    <div class="pcos-about-open-content">
      <ul>
        <li>
          Tester physiquement le plunger et le flipper droit
          pour confirmer ou éliminer un cross-talk analogique.
        </li>
        <li>
          Valider la récupération complète du DOF Helper
          après la fermeture d’une table VPX active.
        </li>
        <li>
          Revalider le sous-dossier Batch Export sur SMB.
        </li>
        <li>
          Valider l’installation automatique des pilotes AMD
          et Intel dans une installation ISO réelle.
        </li>
        <li>
          Reconstruire l’ISO finale avec les derniers
          correctifs permanents.
        </li>
      </ul>
    </div>
  </details>

</section>
<!-- PINCABOS_ABOUT_AUDIT_OVERVIEW_V1_END -->
"""


__all__ = ["pincabos_about_audit_html"]
