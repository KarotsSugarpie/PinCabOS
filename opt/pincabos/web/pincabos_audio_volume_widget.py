# PINCABOS_AUDIO_VOLUME_API_V4_PERSIST
#
# V3 -> V4, trois corrections :
#  1. PERSISTANCE : rien n'ecrivait /var/lib/alsa/asound.state, donc volumes et
#     mute repartaient aux valeurs d'usine a chaque redemarrage (alsa-restore
#     tourne bien au boot, mais n'avait aucun etat a restaurer). Chaque
#     modification declenche desormais `alsactl store`.
#  2. MUTE : les controles sans interrupteur (Capabilities: pvolume seul, cas
#     de PCM sur la plupart des cartes) acceptaient `amixer sset ... toggle`
#     avec un code retour 0 SANS rien couper : le bouton repondait "ok" et le
#     son continuait. Ces controles sont maintenant coupes en logiciel
#     (volume a 0, valeur precedente memorisee) et l'API annonce
#     `has_switch: false`. Chaque reponse renvoie l'etat REEL apres action.
#  3. SELECTION : la liste des controles affiches etait memorisee par NUMERO
#     de carte ("0:Master"), or la numerotation ALSA depend de l'ordre de
#     detection : au redemarrage ou apres un changement materiel, la selection
#     pointait a cote. Elle est desormais memorisee par NOM de carte, avec
#     migration automatique des anciennes valeurs.
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from flask import jsonify, request

CONFIG_PATH = Path("/home/pinball/.config/pincabos/audio-volume-widget.json")

PREFERRED_CONTROLS = [
    "Master",
    "Speaker",
    "PCM",
    "Front",
    "Surround",
    "Center",
    "LFE",
    "Headphone",
]

def _run(args, timeout=4):
    try:
        p = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
        )
        return p.stdout or "", p.stderr or "", p.returncode
    except FileNotFoundError:
        return "", f"Commande absente: {args[0]}", 127
    except Exception as exc:
        return "", str(exc), 1

def _store_alsa_state():
    """Etat ALSA sur disque (utile des le boot, avant la session audio)."""
    _run(["/usr/bin/sudo", "-n", "/usr/sbin/alsactl", "store"], timeout=6)


# PINCABOS_AUDIO_LEVELS_V1
def _remember_level(card, control, volume, muted):
    """Memorise l'intention de l'utilisateur.

    Ni ALSA ni WirePlumber ne la conservent : alsa-restore reecrit son etat a
    l'extinction, et WirePlumber applique ses propres volumes au demarrage de
    la session. pincabos-audio-restore rejoue donc ces valeurs APRES elle.
    """
    levels = _read_config().get("levels", {})
    levels[_key(card, control)] = {"volume": int(volume), "muted": bool(muted)}
    _write_config(levels=levels)

def _discover_cards():
    cards = {}
    out, err, rc = _run(["aplay", "-l"])
    for line in out.splitlines():
        m = re.search(r"^card\s+(\d+):\s*([^\s]+)\s*\[(.*?)\]", line.strip())
        if m:
            cid = int(m.group(1))
            cards[cid] = {
                "card_id": cid,
                "short_name": m.group(2).strip(),
                "name": m.group(3).strip() or m.group(2).strip() or f"Carte {cid}",
            }

    if not cards and os.path.exists("/proc/asound/cards"):
        try:
            data = open("/proc/asound/cards", "r", encoding="utf-8", errors="ignore").read()
            for line in data.splitlines():
                m = re.match(r"\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.*)$", line)
                if m:
                    cid = int(m.group(1))
                    cards[cid] = {
                        "card_id": cid,
                        "short_name": m.group(2).strip(),
                        "name": m.group(3).strip() or m.group(2).strip() or f"Carte {cid}",
                    }
        except Exception:
            pass

    return [cards[k] for k in sorted(cards)]

def _card_token(card):
    """Identifiant STABLE d'une carte (le numero ALSA, lui, peut changer)."""
    token = str(card.get("short_name") or "").strip()
    return token or f"card{card.get('card_id', 0)}"

def _key(card, control):
    return f"{_card_token(card)}:{control}"

def _legacy_key(card_id, control):
    return f"{int(card_id)}:{control}"

def _simple_controls(card_id):
    out, err, rc = _run(["amixer", "-c", str(card_id), "scontrols"])
    found = []
    for name in re.findall(r"Simple mixer control '([^']+)',\d+", out):
        if name not in found:
            found.append(name)
    return found

def _selected_controls(controls):
    selected = []
    lower = {c.lower(): c for c in controls}
    for pref in PREFERRED_CONTROLS:
        c = lower.get(pref.lower())
        if c and c not in selected:
            selected.append(c)
    if not selected:
        selected = controls[:4]
    return selected[:8]

def _read_control(card, control):
    card_id = card["card_id"]
    out, err, rc = _run(["amixer", "-c", str(card_id), "sget", control])
    values = [int(x) for x in re.findall(r"\[(\d{1,3})%\]", out)]
    if not values:
        return None

    states = re.findall(r"\[(on|off)\]", out)
    has_switch = "pswitch" in out.lower() or bool(states)
    hardware_muted = bool(states) and all(state == "off" for state in states)
    volume = max(0, min(100, int(round(sum(values) / len(values)))))

    # Controle sans interrupteur : mute logiciel (volume a 0, valeur d'avant
    # memorisee) — sinon le bouton mute reste decoratif.
    soft = _read_config().get("soft_mute", {})
    soft_key = _key(card, control)
    soft_muted = bool(volume == 0 and soft.get(soft_key) is not None)

    return {
        "key": soft_key,
        "legacy_key": _legacy_key(card_id, control),
        "name": control,
        "volume": volume,
        "muted": hardware_muted or soft_muted,
        "has_switch": has_switch,
        "soft_muted": soft_muted,
    }

def _read_cards():
    result = []
    for card in _discover_cards():
        rows = []
        for control in _selected_controls(_simple_controls(card["card_id"])):
            info = _read_control(card, control)
            if info:
                rows.append(info)
        result.append({
            "card_id": card["card_id"],
            "name": card.get("name") or f"Carte {card['card_id']}",
            "short_name": card.get("short_name") or "",
            "controls": rows,
        })
    return result

def _available_keys(cards=None):
    cards = cards if cards is not None else _read_cards()
    keys = []
    for card in cards:
        for control in card.get("controls", []):
            key = str(control.get("key") or "")
            if key and key not in keys:
                keys.append(key)
    return keys

def _read_config():
    configured = CONFIG_PATH.exists()
    selected = []
    soft_mute = {}
    levels = {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("selected"), list):
                selected = [str(x) for x in data.get("selected", []) if isinstance(x, str)]
            if isinstance(data.get("soft_mute"), dict):
                soft_mute = {str(k): v for k, v in data["soft_mute"].items()}
            if isinstance(data.get("levels"), dict):
                levels = {str(k): v for k, v in data["levels"].items()}
    except Exception:
        selected = []
        soft_mute = {}
        levels = {}
    return {
        "configured": configured,
        "selected": selected,
        "soft_mute": soft_mute,
        "levels": levels,
    }

def _write_config(selected=None, soft_mute=None, levels=None):
    current = _read_config()
    payload = {
        "selected": current["selected"] if selected is None else selected,
        "soft_mute": current["soft_mute"] if soft_mute is None else soft_mute,
        "levels": current["levels"] if levels is None else levels,
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o640)
    try:
        shutil.chown(tmp, user="pinball", group="pinball")
    except Exception:
        pass
    os.replace(tmp, CONFIG_PATH)

def _migrate_selection(selected, cards):
    """Ancienne selection par NUMERO de carte -> selection par NOM de carte."""
    if not selected:
        return selected, False
    by_legacy = {}
    for card in cards:
        for control in card.get("controls", []):
            by_legacy[str(control.get("legacy_key"))] = str(control.get("key"))
    migrated = []
    changed = False
    for key in selected:
        if re.match(r"^\d+:", key) and key in by_legacy:
            migrated.append(by_legacy[key])
            changed = True
        else:
            migrated.append(key)
    return migrated, changed

def _find_card(card_id):
    for card in _discover_cards():
        if card["card_id"] == int(card_id):
            return card
    return None

def _valid_control(card_id, control):
    return control in _simple_controls(card_id)

def register(app):
    if getattr(app, "_pincabos_audio_volume_api_v3_config_registered", False):
        return
    app._pincabos_audio_volume_api_v3_config_registered = True

    @app.route("/api/pincabos/audio-volume/cards", methods=["GET"])
    def pincabos_audio_volume_cards_v3():
        try:
            cards = _read_cards()
            cfg = _read_config()
            selected, changed = _migrate_selection(cfg.get("selected", []), cards)
            if changed:
                _write_config(selected=selected)
                cfg["selected"] = selected
            return jsonify({
                "ok": True,
                "engine": "alsa-amixer",
                "cards": cards,
                "config": {"configured": cfg["configured"], "selected": cfg["selected"]},
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "cards": []}), 500

    @app.route("/api/pincabos/audio-volume/config", methods=["GET"])
    def pincabos_audio_volume_config_get_v3():
        try:
            cards = _read_cards()
            cfg = _read_config()
            selected, changed = _migrate_selection(cfg.get("selected", []), cards)
            if changed:
                _write_config(selected=selected)
            allowed = set(_available_keys(cards))
            selected = [key for key in selected if key in allowed]
            return jsonify({
                "ok": True,
                "configured": bool(cfg.get("configured")),
                "selected": selected,
                "available": _available_keys(cards),
                "cards": cards,
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/pincabos/audio-volume/config", methods=["POST"])
    def pincabos_audio_volume_config_post_v3():
        data = request.get_json(silent=True) or {}
        raw = data.get("selected", [])
        if not isinstance(raw, list):
            return jsonify({"ok": False, "error": "selected doit être une liste"}), 400

        cards = _read_cards()
        allowed_order = _available_keys(cards)
        wanted = {str(x) for x in raw if isinstance(x, str)}
        # tolere une selection envoyee a l'ancien format
        legacy = {}
        for card in cards:
            for control in card.get("controls", []):
                legacy[str(control.get("legacy_key"))] = str(control.get("key"))
        wanted = {legacy.get(key, key) for key in wanted}
        selected = [key for key in allowed_order if key in wanted]

        try:
            _write_config(selected=selected)
        except Exception as exc:
            return jsonify({"ok": False, "error": f"Sauvegarde impossible: {exc}"}), 500

        return jsonify({
            "ok": True,
            "configured": True,
            "selected": selected,
        })

    @app.route("/api/pincabos/audio-volume/set", methods=["POST"])
    def pincabos_audio_volume_set_v3():
        data = request.get_json(silent=True) or {}
        try:
            card_id = int(data.get("card_id"))
            control = str(data.get("control", "")).strip()
            volume = max(0, min(100, int(float(data.get("volume")))))
        except Exception:
            return jsonify({"ok": False, "error": "Paramètres invalides"}), 400

        card = _find_card(card_id)
        if not card or not control or not _valid_control(card_id, control):
            return jsonify({"ok": False, "error": "Contrôle ALSA invalide"}), 400

        out, err, rc = _run(["amixer", "-q", "-c", str(card_id), "sset", control, f"{volume}%"])
        if rc != 0:
            return jsonify({"ok": False, "error": err or out or "amixer a échoué"}), 500

        # Regler le volume sort du mute (materiel comme logiciel).
        _run(["amixer", "-q", "-c", str(card_id), "sset", control, "unmute"], timeout=2)
        soft = _read_config().get("soft_mute", {})
        if soft.pop(_key(card, control), None) is not None:
            _write_config(soft_mute=soft)

        _store_alsa_state()
        state = _read_control(card, control) or {}
        _remember_level(card, control, state.get("volume", volume), state.get("muted", False))
        return jsonify({
            "ok": True,
            "card_id": card_id,
            "control": control,
            "volume": state.get("volume", volume),
            "muted": state.get("muted", False),
        })

    @app.route("/api/pincabos/audio-volume/mute-toggle", methods=["POST"])
    def pincabos_audio_volume_mute_toggle_v3():
        data = request.get_json(silent=True) or {}
        try:
            card_id = int(data.get("card_id"))
            control = str(data.get("control", "")).strip()
        except Exception:
            return jsonify({"ok": False, "error": "Paramètres invalides"}), 400

        card = _find_card(card_id)
        if not card or not control or not _valid_control(card_id, control):
            return jsonify({"ok": False, "error": "Contrôle ALSA invalide"}), 400

        before = _read_control(card, control) or {}
        key = _key(card, control)
        soft = _read_config().get("soft_mute", {})

        if before.get("has_switch"):
            out, err, rc = _run(["amixer", "-q", "-c", str(card_id), "sset", control, "toggle"])
            if rc != 0:
                return jsonify({"ok": False, "error": err or out or "toggle impossible"}), 500
        elif before.get("soft_muted"):
            restore = int(soft.pop(key, 0) or 0)
            _run(["amixer", "-q", "-c", str(card_id), "sset", control, f"{max(restore, 1)}%"])
            _write_config(soft_mute=soft)
        else:
            # Pas d'interrupteur materiel : on coupe en mettant le volume a 0
            # apres avoir memorise la valeur courante.
            soft[key] = int(before.get("volume", 0))
            _run(["amixer", "-q", "-c", str(card_id), "sset", control, "0%"])
            _write_config(soft_mute=soft)

        _store_alsa_state()
        after = _read_control(card, control) or {}
        _remember_level(card, control, after.get("volume", 0), after.get("muted", False))
        return jsonify({
            "ok": True,
            "card_id": card_id,
            "control": control,
            "muted": after.get("muted", False),
            "volume": after.get("volume", 0),
            "has_switch": after.get("has_switch", False),
        })
