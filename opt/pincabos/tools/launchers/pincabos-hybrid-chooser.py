#!/usr/bin/env python3
# PINCABOS_HYBRID_CHOOSER_V3_1
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

try:
    import pygame
except Exception as exc:
    print(f"NOGO [X] pygame indisponible : {exc}", file=sys.stderr)
    raise SystemExit(10)


def parse_int_set(name: str, default: set[int]) -> set[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return set(default)

    parsed: set[int] = set()
    for value in raw.split(","):
        try:
            parsed.add(int(value.strip()))
        except ValueError:
            pass
    return parsed or set(default)


def parse_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def scaled_rect(
    image_pos: tuple[int, int],
    render_size: tuple[int, int],
    x: float,
    y: float,
    width: float,
    height: float,
) -> pygame.Rect:
    image_x, image_y = image_pos
    render_w, render_h = render_size
    return pygame.Rect(
        image_x + int(render_w * x),
        image_y + int(render_h * y),
        max(1, int(render_w * width)),
        max(1, int(render_h * height)),
    )


if len(sys.argv) != 5:
    print("Usage: chooser.py ASSET RESULT DEFAULT TIMEOUT", file=sys.stderr)
    raise SystemExit(11)

asset_path = Path(sys.argv[1])
result_path = Path(sys.argv[2])
default = "pup" if sys.argv[3].strip().lower().startswith("pup") else "original"

try:
    timeout = max(0, int(sys.argv[4]))
except ValueError:
    timeout = 0

if not asset_path.is_file():
    print(f"NOGO [X] Image absente : {asset_path}", file=sys.stderr)
    raise SystemExit(12)

# Clavier : les flippers changent seulement le choix. Launch/Plunger confirme.
left_keys = {
    pygame.K_LEFT,
    pygame.K_LSHIFT,
    pygame.K_LCTRL,
    pygame.K_a,
    pygame.K_z,
}
right_keys = {
    pygame.K_RIGHT,
    pygame.K_RSHIFT,
    pygame.K_RCTRL,
    pygame.K_d,
    pygame.K_x,
}
confirm_keys = {
    pygame.K_RETURN,
    pygame.K_KP_ENTER,
    pygame.K_SPACE,
}

# Valeurs par défaut permissives pour les encodeurs de pincab courants.
# Elles restent entièrement personnalisables par variables d'environnement.
left_buttons = parse_int_set("PINCABOS_LEFT_FLIPPER_BUTTONS", {4, 6, 10})
right_buttons = parse_int_set("PINCABOS_RIGHT_FLIPPER_BUTTONS", {5, 7, 11})
launch_buttons = parse_int_set("PINCABOS_LAUNCH_BUTTONS", {0, 1, 8, 9, 13})
plunger_buttons = parse_int_set("PINCABOS_PLUNGER_BUTTONS", {2, 3, 12})
confirm_buttons = launch_buttons | plunger_buttons

# Un plunger analogique confirme seulement après un vrai tirage puis relâchement.
# Le seuil élevé évite que les petits mouvements de nudge lancent la table.
plunger_axes = parse_int_set("PINCABOS_PLUNGER_AXES", {2, 3, 5})
plunger_pull_threshold = parse_float("PINCABOS_PLUNGER_PULL_THRESHOLD", 0.78, 0.50, 1.00)
plunger_release_threshold = parse_float("PINCABOS_PLUNGER_RELEASE_THRESHOLD", 0.20, 0.02, 0.45)

pygame.init()
pygame.display.init()
pygame.joystick.init()

joysticks: list[pygame.joystick.Joystick] = []
for index in range(pygame.joystick.get_count()):
    try:
        joystick = pygame.joystick.Joystick(index)
        joystick.init()
        joysticks.append(joystick)
    except Exception:
        pass

try:
    display_index = max(0, int(os.environ.get("PINCABOS_CHOOSER_DISPLAY", "0")))
except ValueError:
    display_index = 0

flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
try:
    screen = pygame.display.set_mode((0, 0), flags, display=display_index)
except TypeError:
    screen = pygame.display.set_mode((0, 0), flags)

pygame.display.set_caption("PinCabOS Original / PuP-Pack")
pygame.mouse.set_visible(False)

screen_w, screen_h = screen.get_size()
source = pygame.image.load(str(asset_path)).convert_alpha()
source_w, source_h = source.get_size()
scale = min(screen_w / source_w, screen_h / source_h)
render_w = max(1, int(source_w * scale))
render_h = max(1, int(source_h * scale))
image = pygame.transform.smoothscale(source, (render_w, render_h))
image_pos = ((screen_w - render_w) // 2, (screen_h - render_h) // 2)

# L'image fournie est orientée pour le playfield :
# - sa moitié basse devient la partie gauche physique = ORIGINAL;
# - sa moitié haute devient la partie droite physique = PUP-PACK.
# Utiliser PINCABOS_CHOOSER_LAYOUT=horizontal seulement si l'écran est déjà
# transformé et que les deux choix apparaissent réellement gauche/droite dans SDL.
layout = os.environ.get("PINCABOS_CHOOSER_LAYOUT", "playfield").strip().lower()
if layout in {"horizontal", "landscape", "left-right"}:
    original_rect = scaled_rect(image_pos, (render_w, render_h), 0.02, 0.04, 0.475, 0.92)
    pup_rect = scaled_rect(image_pos, (render_w, render_h), 0.505, 0.04, 0.475, 0.92)
else:
    # Zones principales de l'illustration, sans les bandeaux externes.
    pup_rect = scaled_rect(image_pos, (render_w, render_h), 0.12, 0.025, 0.81, 0.455)
    original_rect = scaled_rect(image_pos, (render_w, render_h), 0.12, 0.515, 0.81, 0.455)

choice = default
selected: str | None = None
selected_by = ""
selection_changed_at = time.monotonic()
start_time = selection_changed_at
armed_at = start_time + 0.40
clock = pygame.time.Clock()
plunger_was_pulled: dict[tuple[int, int], bool] = {}


def choose(mode: str, source_name: str) -> None:
    global choice, selection_changed_at
    if mode not in {"original", "pup"}:
        return
    if choice != mode:
        choice = mode
        selection_changed_at = time.monotonic()
    # La source est volontairement conservée pour faciliter le diagnostic visuel.
    os.environ["PINCABOS_CHOOSER_LAST_SELECTION_INPUT"] = source_name


def confirm(source_name: str) -> None:
    global selected, selected_by
    selected = choice
    selected_by = source_name


def render() -> None:
    screen.fill((0, 0, 0))
    screen.blit(image, image_pos)

    active_rect = original_rect if choice == "original" else pup_rect
    inactive_rect = pup_rect if choice == "original" else original_rect
    active_color = (255, 181, 36) if choice == "original" else (38, 207, 255)

    overlay = pygame.Surface((screen_w, screen_h), pygame.SRCALPHA)

    # La partie non sélectionnée est fortement assombrie.
    pygame.draw.rect(overlay, (0, 0, 0, 150), inactive_rect, border_radius=28)

    # La partie sélectionnée reçoit une légère teinte et un halo pulsant.
    pygame.draw.rect(overlay, (*active_color, 25), active_rect, border_radius=28)
    pulse = (math.sin(time.monotonic() * 5.0) + 1.0) / 2.0
    glow_alpha = int(65 + pulse * 80)
    border_width = max(7, screen_h // 120)

    for expansion, alpha_scale in ((18, 0.22), (11, 0.38), (5, 0.62)):
        glow_rect = active_rect.inflate(expansion * 2, expansion * 2)
        pygame.draw.rect(
            overlay,
            (*active_color, int(glow_alpha * alpha_scale)),
            glow_rect,
            width=max(2, border_width // 2),
            border_radius=34,
        )

    pygame.draw.rect(
        overlay,
        (*active_color, 245),
        active_rect,
        width=border_width,
        border_radius=28,
    )

    # Petit flash visuel après le changement de côté.
    age = time.monotonic() - selection_changed_at
    if age < 0.18:
        flash_alpha = int(100 * (1.0 - age / 0.18))
        pygame.draw.rect(
            overlay,
            (255, 255, 255, flash_alpha),
            active_rect.inflate(8, 8),
            width=max(3, border_width // 2),
            border_radius=32,
        )

    screen.blit(overlay, (0, 0))
    pygame.display.flip()


pygame.event.clear()

while selected is None:
    now = time.monotonic()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            confirm("window-close")
            break

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                confirm("escape-current")
                break

            if now < armed_at:
                continue

            if event.key in left_keys:
                choose("original", f"keyboard-left:{event.key}")
                continue
            if event.key in right_keys:
                choose("pup", f"keyboard-right:{event.key}")
                continue
            if event.key in confirm_keys:
                confirm(f"keyboard-confirm:{event.key}")
                break

        if now < armed_at:
            continue

        if event.type == pygame.JOYHATMOTION:
            x_value, _ = event.value
            if x_value < 0:
                choose("original", f"joyhat-left:{event.joy}")
            elif x_value > 0:
                choose("pup", f"joyhat-right:{event.joy}")
            continue

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button in left_buttons:
                choose("original", f"joybutton-left:{event.joy}:{event.button}")
                continue
            if event.button in right_buttons:
                choose("pup", f"joybutton-right:{event.joy}:{event.button}")
                continue
            if event.button in confirm_buttons:
                confirm(f"joybutton-confirm:{event.joy}:{event.button}")
                break

        if event.type == pygame.JOYAXISMOTION and event.axis in plunger_axes:
            key = (event.joy, event.axis)
            axis_value = abs(float(event.value))

            if axis_value >= plunger_pull_threshold:
                plunger_was_pulled[key] = True
                continue

            if plunger_was_pulled.get(key, False) and axis_value <= plunger_release_threshold:
                plunger_was_pulled[key] = False
                confirm(f"plunger-axis-release:{event.joy}:{event.axis}")
                break

    if selected is None and timeout > 0 and now - start_time >= timeout:
        confirm("timeout-current")

    render()
    clock.tick(120)

result_path.parent.mkdir(parents=True, exist_ok=True)
temporary = result_path.with_suffix(result_path.suffix + ".tmp")
temporary.write_text(
    json.dumps(
        {
            "choice": selected,
            "input": selected_by,
            "layout": layout,
            "timestamp": int(time.time()),
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
temporary.replace(result_path)

pygame.quit()
raise SystemExit(0)
