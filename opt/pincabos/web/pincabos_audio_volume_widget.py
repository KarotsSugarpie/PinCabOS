# PINCABOS_AUDIO_VOLUME_API_V3_CONFIG
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

def _key(card_id, control):
    return f"{int(card_id)}:{str(control)}"

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

def _read_control(card_id, control):
    out, err, rc = _run(["amixer", "-c", str(card_id), "sget", control])
    values = [int(x) for x in re.findall(r"\[(\d{1,3})%\]", out)]
    if not values:
        return None
    muted = bool(re.search(r"\[off\]", out))
    volume = max(0, min(100, int(round(sum(values) / len(values)))))
    return {
        "key": _key(card_id, control),
        "name": control,
        "volume": volume,
        "muted": muted,
    }

def _read_cards():
    result = []
    for card in _discover_cards():
        cid = card["card_id"]
        rows = []
        for control in _selected_controls(_simple_controls(cid)):
            info = _read_control(cid, control)
            if info:
                rows.append(info)
        result.append({
            "card_id": cid,
            "name": card.get("name") or f"Carte {cid}",
            "short_name": card.get("short_name") or "",
            "controls": rows,
        })
    return result

def _available_keys(cards=None):
    cards = cards if cards is not None else _read_cards()
    keys = []
    for card in cards:
        for control in card.get("controls", []):
            key = str(control.get("key") or _key(card.get("card_id", 0), control.get("name", "")))
            if key not in keys:
                keys.append(key)
    return keys

def _read_config():
    configured = CONFIG_PATH.exists()
    selected = []
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("selected"), list):
            selected = [str(x) for x in data.get("selected", []) if isinstance(x, str)]
    except Exception:
        selected = []
    return {"configured": configured, "selected": selected}

def _write_config(selected):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"selected": selected}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o640)
    try:
        shutil.chown(tmp, user="pinball", group="pinball")
    except Exception:
        pass
    os.replace(tmp, CONFIG_PATH)

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
            return jsonify({
                "ok": True,
                "engine": "alsa-amixer",
                "cards": cards,
                "config": cfg,
            })
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "cards": []}), 500

    @app.route("/api/pincabos/audio-volume/config", methods=["GET"])
    def pincabos_audio_volume_config_get_v3():
        try:
            cards = _read_cards()
            cfg = _read_config()
            allowed = set(_available_keys(cards))
            selected = [key for key in cfg.get("selected", []) if key in allowed]
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
        selected = [key for key in allowed_order if key in wanted]

        try:
            _write_config(selected)
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

        if not control or not _valid_control(card_id, control):
            return jsonify({"ok": False, "error": "Contrôle ALSA invalide"}), 400

        out, err, rc = _run(["amixer", "-q", "-c", str(card_id), "sset", control, f"{volume}%"])
        if rc != 0:
            return jsonify({"ok": False, "error": err or out or "amixer a échoué"}), 500

        _run(["amixer", "-q", "-c", str(card_id), "sset", control, "unmute"], timeout=2)
        return jsonify({"ok": True, "card_id": card_id, "control": control, "volume": volume})

    @app.route("/api/pincabos/audio-volume/mute-toggle", methods=["POST"])
    def pincabos_audio_volume_mute_toggle_v3():
        data = request.get_json(silent=True) or {}
        try:
            card_id = int(data.get("card_id"))
            control = str(data.get("control", "")).strip()
        except Exception:
            return jsonify({"ok": False, "error": "Paramètres invalides"}), 400

        if not control or not _valid_control(card_id, control):
            return jsonify({"ok": False, "error": "Contrôle ALSA invalide"}), 400

        out, err, rc = _run(["amixer", "-q", "-c", str(card_id), "sset", control, "toggle"])
        if rc != 0:
            return jsonify({"ok": False, "error": err or out or "toggle impossible"}), 500
        return jsonify({"ok": True})
