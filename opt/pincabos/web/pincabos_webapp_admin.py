#!/usr/bin/env python3
# PinCabOS-File created by Karots Sugarpie
"""
PinCabOS WebApp admin helpers.

Objectif:
- garder app.py plus propre;
- centraliser les helpers admin/publish/cleanup;
- ne pas lancer de commande au moment de l'import;
- ne pas toucher aux routes Flask dans ce module au Stage 5B.1.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from pathlib import Path
from typing import Iterable, Sequence


def pco_admin_cmd_for_script(script: str | Path, *args: str | Path) -> list[str]:
    """
    Construit une commande sudo non interactive pour scripts PinCabOS.

    Exemple:
        pco_admin_cmd_for_script("/opt/pincabos/tools/pincabos-publish-tree.sh", "--apply")

    Retour:
        ["/usr/bin/sudo", "-n", "/opt/...", "--apply"]
    """
    return ["/usr/bin/sudo", "-n", str(script), *[str(arg) for arg in args]]


def pco_admin_cmd_for_systemctl(action: str, service: str) -> list[str]:
    """
    Construit une commande systemctl sudo non interactive.
    """
    return ["/usr/bin/sudo", "-n", "/usr/bin/systemctl", str(action), str(service)]


def pco_admin_shell_join(cmd: Sequence[str | Path]) -> str:
    """
    Affichage shell safe pour logs/debug.
    """
    return " ".join(shlex.quote(str(part)) for part in cmd)


def pco_admin_run_capture(
    cmd: Sequence[str | Path],
    timeout: int = 1800,
) -> tuple[int, str]:
    """
    Lance une commande et retourne (returncode, stdout+stderr).

    Aucun Flask ici: ce module reste testable hors WebApp.
    """
    try:
        proc = subprocess.run(
            [str(x) for x in cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ((proc.stdout or "") + (proc.stderr or "")).strip()
        return proc.returncode, output
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") + (exc.stderr or "")).strip()
        if not output:
            output = f"Timeout apres {timeout} secondes."
        return 124, output
    except Exception as exc:
        return 1, f"Erreur commande: {exc}"


def pco_admin_now_stamp() -> str:
    """
    Timestamp simple pour logs admin.
    """
    return time.strftime("%Y%m%d-%H%M%S")


def pco_admin_tail_text(text: str, max_chars: int = 20000) -> str:
    """
    Limite proprement une sortie longue avant affichage HTML/log.
    """
    text = str(text or "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def pco_admin_existing_scripts(paths: Iterable[str | Path]) -> list[Path]:
    """
    Retourne seulement les scripts/fichiers existants.
    """
    out: list[Path] = []
    for item in paths:
        p = Path(item)
        if p.exists():
            out.append(p)
    return out


def pco_admin_escape_html(value: object) -> str:
    """
    Escape HTML minimal sans dépendre de Flask.
    """
    import html
    return html.escape(str(value or ""))


def pco_admin_output_html(title: str, cmd: Sequence[str | Path], rc: int, output: str) -> str:
    """
    Génère seulement le body HTML de résultat commande admin.
    app.py garde la fonction page().
    """
    css = "ok" if rc == 0 else "bad"
    safe_title = pco_admin_escape_html(title)
    safe_cmd = pco_admin_escape_html(pco_admin_shell_join(cmd))
    safe_output = pco_admin_escape_html(pco_admin_tail_text(output, 24000))

    return f"""
<h1>{safe_title}</h1>
<div class="card">
  <h2>Résultat commande</h2>
  <p>Code retour: <strong class="{css}">{rc}</strong></p>
  <p>Commande:</p>
  <pre>{safe_cmd}</pre>
  <p>Sortie:</p>
  <pre style="white-space:pre-wrap;max-height:70vh;overflow:auto;">{safe_output}</pre>
  <p>
    <a class="button" href="/admin">Retour Admin</a>
  </p>
</div>
"""


def pco_admin_iframe_body(title: str, cmd: Sequence[str | Path], timeout: int = 1800) -> tuple[int, str]:
    """
    Lance la commande admin et retourne (returncode, body_html).

    Aucun redirect/session ici: la route Flask dans app.py garde le contrôle.
    """
    rc, output = pco_admin_run_capture(cmd, timeout=timeout)
    return rc, pco_admin_output_html(title, cmd, rc, output)

