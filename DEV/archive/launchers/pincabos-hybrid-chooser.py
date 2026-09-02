#!/usr/bin/env python3
# PINCABOS_HYBRID_CHOOSER_PILOT_V1
import json
import os
import sys
import time
from pathlib import Path

try:
    import pygame
except Exception as exc:
    print(f"pygame absent: {exc}", file=sys.stderr)
    sys.exit(10)

ASSET = Path(sys.argv[1])
RUNTIME = Path(sys.argv[2])
DEFAULT_CHOICE = (sys.argv[3] if len(sys.argv) > 3 else "original").strip().lower()
TIMEOUT = int(sys.argv[4]) if len(sys.argv) > 4 else 20

if not ASSET.exists():
    print(f"asset introuvable: {ASSET}", file=sys.stderr)
    sys.exit(11)

pygame.init()
pygame.display.init()
pygame.font.init()
pygame.joystick.init()

for idx in range(pygame.joystick.get_count()):
    try:
        js = pygame.joystick.Joystick(idx)
        js.init()
    except Exception:
        pass

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("PinCabOS Hybrid Game Chooser")
width, height = screen.get_size()

img = pygame.image.load(str(ASSET)).convert()
img = pygame.transform.smoothscale(img, (width, height))
font = pygame.font.SysFont(None, max(28, height // 28))
small = pygame.font.SysFont(None, max(22, height // 40))

choice = "pup" if DEFAULT_CHOICE in ("pup", "puppack", "pup-pack") else "original"
start = time.time()
clock = pygame.time.Clock()
selected = None

left_rect = pygame.Rect(int(width * 0.05), int(height * 0.12), int(width * 0.42), int(height * 0.72))
right_rect = pygame.Rect(int(width * 0.53), int(height * 0.12), int(width * 0.42), int(height * 0.72))

K_LEFT_SET = {pygame.K_LEFT, pygame.K_LSHIFT, pygame.K_a, pygame.K_z}
K_RIGHT_SET = {pygame.K_RIGHT, pygame.K_RSHIFT, pygame.K_d, pygame.K_x}
K_CONFIRM_SET = {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE}
K_CANCEL_SET = {pygame.K_ESCAPE, pygame.K_BACKSPACE}


def render():
    screen.blit(img, (0, 0))
    overlay = pygame.Surface((width, height), pygame.SRCALPHA)
    if choice == "original":
        pygame.draw.rect(overlay, (255, 120, 20, 70), left_rect, border_radius=28)
        pygame.draw.rect(overlay, (90, 20, 255, 28), right_rect, border_radius=28)
    else:
        pygame.draw.rect(overlay, (255, 120, 20, 28), left_rect, border_radius=28)
        pygame.draw.rect(overlay, (90, 20, 255, 70), right_rect, border_radius=28)
    screen.blit(overlay, (0, 0))

    border_color = (255, 170, 40) if choice == "original" else (80, 200, 255)
    pygame.draw.rect(screen, border_color, left_rect if choice == "original" else right_rect, width=max(6, height // 150), border_radius=28)

    msg1 = font.render("Flipper gauche = Original · Flipper droit = PuP-Pack", True, (255, 255, 255))
    msg2 = font.render("Launch / Plunger / Enter = Confirmer", True, (255, 255, 255))
    remaining = max(0, TIMEOUT - int(time.time() - start))
    label = "ORIGINAL" if choice == "original" else "PUP-PACK"
    msg3 = small.render(f"Sélection actuelle : {label} · Auto-démarrage dans {remaining}s", True, (255, 230, 160))
    screen.blit(msg1, (max(12, (width - msg1.get_width()) // 2), height - msg1.get_height() * 3 - 24))
    screen.blit(msg2, (max(12, (width - msg2.get_width()) // 2), height - msg2.get_height() * 2 - 14))
    screen.blit(msg3, (max(12, (width - msg3.get_width()) // 2), height - msg3.get_height() - 8))
    pygame.display.flip()


while selected is None:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            selected = choice
        elif event.type == pygame.KEYDOWN:
            if event.key in K_LEFT_SET:
                choice = "original"
            elif event.key in K_RIGHT_SET:
                choice = "pup"
            elif event.key in K_CONFIRM_SET:
                selected = choice
            elif event.key in K_CANCEL_SET:
                selected = DEFAULT_CHOICE if DEFAULT_CHOICE in ("original", "pup") else "original"
        elif event.type == pygame.JOYBUTTONDOWN:
            # Mapping permissif : bouton 0/7/9 = confirmer, 4 = gauche, 5 = droite
            if event.button in (4,):
                choice = "original"
            elif event.button in (5,):
                choice = "pup"
            elif event.button in (0, 7, 9, 13):
                selected = choice
        elif event.type == pygame.JOYHATMOTION:
            hx, hy = event.value
            if hx < 0:
                choice = "original"
            elif hx > 0:
                choice = "pup"

    if time.time() - start >= TIMEOUT:
        selected = choice

    render()
    clock.tick(30)

RUNTIME.write_text(json.dumps({"choice": selected, "timestamp": int(time.time())}), encoding="utf-8")
pygame.quit()
sys.exit(0)
