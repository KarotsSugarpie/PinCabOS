#!/usr/bin/env bash
clear
set -u
set -o pipefail

APP="/opt/pincabos-release-center"
APP_PY="$APP/app.py"
WEB_PY="$APP/multiplayer/web.py"
DB="/var/lib/pincabos-release/users.db"
SERVICE="pincabos-release-center.service"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$APP/backups/control-lease-v1-$STAMP"

rollback() {
    echo
    echo "================================================================"
    echo " NOGO [X] ROLLBACK CONTROL LEASE V1"
    echo "================================================================"
    systemctl stop "$SERVICE" >/dev/null 2>&1 || true
    [ -f "$BACKUP/app.py" ] && cp -a "$BACKUP/app.py" "$APP_PY"
    [ -f "$BACKUP/web.py" ] && cp -a "$BACKUP/web.py" "$WEB_PY"
    if [ -f "$BACKUP/users.db" ]; then
        BACKUP_DB="$BACKUP/users.db" LIVE_DB="$DB" python3 <<'PY'
import os, sqlite3
src = sqlite3.connect(os.environ["BACKUP_DB"])
dst = sqlite3.connect(os.environ["LIVE_DB"])
try:
    src.backup(dst)
    dst.commit()
finally:
    dst.close(); src.close()
PY
    fi
    rm -f "${DB}-wal" "${DB}-shm" 2>/dev/null || true
    systemctl start "$SERVICE" >/dev/null 2>&1 || true
    sleep 3
    systemctl is-active "$SERVICE" 2>/dev/null || true
    echo "Backup : $BACKUP"
    exit 1
}

echo "================================================================"
echo " PINFORGE-SAFE — PINCABOS.CC CONTROL LEASE V1"
echo " LOBBY READY -> ARMED -> COUNTDOWN/VIDEO -> RUNNING"
echo " BACKUP + VALIDATION + ROLLBACK"
echo "================================================================"

[ "$(id -u)" = "0" ] || { echo "NOGO root requis"; exit 1; }
[ -f "$APP_PY" ] || { echo "NOGO app.py absent"; exit 1; }
[ -f "$WEB_PY" ] || { echo "NOGO multiplayer/web.py absent"; exit 1; }
[ -f "$DB" ] || { echo "NOGO users.db absent"; exit 1; }
systemctl is-active --quiet "$SERVICE" || { echo "NOGO service non actif"; exit 1; }

grep -q 'PINCABOS_LOBBY_MULTIPLAYER_BRIDGE_V1_PRECHECK' "$APP_PY" || {
    echo "NOGO pont Lobby->Multiplayer V1 absent"; exit 1;
}
grep -q 'PINCABOS_LOBBY_RESET_MULTIPLAYER_V2' "$APP_PY" || {
    echo "NOGO RESET Multiplayer V2 absent"; exit 1;
}

if grep -q 'PINCABOS_CONTROL_LEASE_SERVER_V1' "$WEB_PY"; then
    echo "NOGO patch serveur déjà présent"
    exit 1
fi

mkdir -p "$BACKUP" || exit 1
cp -a "$APP_PY" "$BACKUP/app.py" || exit 1
cp -a "$WEB_PY" "$BACKUP/web.py" || exit 1

LIVE_DB="$DB" BACKUP_DB="$BACKUP/users.db" python3 <<'PY' || exit 1
import os, sqlite3
src = sqlite3.connect(os.environ["LIVE_DB"])
dst = sqlite3.connect(os.environ["BACKUP_DB"])
try:
    src.backup(dst)
    dst.commit()
finally:
    dst.close(); src.close()
PY

echo "GO [OK] Backup : $BACKUP"

APP_PY="$APP_PY" WEB_PY="$WEB_PY" python3 <<'PY' || rollback
from pathlib import Path
import os

app_path = Path(os.environ["APP_PY"])
web_path = Path(os.environ["WEB_PY"])
web = web_path.read_text(encoding="utf-8")
app = app_path.read_text(encoding="utf-8")

SERVER_MARK = "PINCABOS_CONTROL_LEASE_SERVER_V1"
START_MARK = "PINCABOS_LOBBY_CONTROL_LEASE_START_V1"
RESET_MARK = "PINCABOS_LOBBY_CONTROL_LEASE_RESET_V1"

# ------------------------------------------------------------------
# web.py — schéma auxiliaire, désir serveur et ACK cabinet
# ------------------------------------------------------------------
init_old = '''    connection = db()\n    try:\n        migration = apply_migrations(connection)\n    finally:\n        connection.close()\n'''
init_new = '''    connection = db()\n    try:\n        migration = apply_migrations(connection)\n        # PINCABOS_CONTROL_LEASE_SERVER_V1\n        connection.execute(\n            """\n            CREATE TABLE IF NOT EXISTS multiplayer_control_state (\n                session_id TEXT PRIMARY KEY,\n                desired TEXT NOT NULL,\n                generation INTEGER NOT NULL,\n                updated_at TEXT NOT NULL\n            )\n            """\n        )\n        connection.execute(\n            """\n            CREATE TABLE IF NOT EXISTS multiplayer_control_acks (\n                session_id TEXT NOT NULL,\n                generation INTEGER NOT NULL,\n                cabinet_id TEXT NOT NULL,\n                state TEXT NOT NULL,\n                ok INTEGER NOT NULL,\n                detail TEXT,\n                updated_at TEXT NOT NULL,\n                PRIMARY KEY (session_id, generation, cabinet_id)\n            )\n            """\n        )\n        connection.commit()\n    finally:\n        connection.close()\n'''
if web.count(init_old) != 1:
    raise SystemExit("web_init_anchor_invalid")
web = web.replace(init_old, init_new, 1)

body_anchor = "    def body(allowed_fields: set[str]):\n"
if web.count(body_anchor) != 1:
    raise SystemExit("web_body_anchor_invalid")
helpers = r'''    _CONTROL_STATES = {"released", "armed", "linked", "video", "running", "handoff"}

    def lobby_all_ready(connection, room_id: int) -> bool:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN ready=1 THEN 1 ELSE 0 END) AS ready_count
            FROM lobby_members
            WHERE room_id=?
            """,
            (int(room_id),),
        ).fetchone()
        total = int(row["total"] or 0) if row else 0
        ready_count = int(row["ready_count"] or 0) if row else 0
        return total >= 2 and ready_count == total

    def desired_control(multiplayer_session, room, all_ready: bool) -> str:
        if not multiplayer_session or not room:
            return "released"
        phase = multiplayer_session.phase
        status = str(room["status"] or "")
        if status == "playing" and phase == SessionPhase.RUNNING:
            return "running"
        if status == "countdown":
            return "video"
        if status == "open" and all_ready and phase == SessionPhase.READY:
            return "armed"
        return "released"

    def control_payload(connection, multiplayer_session, room):
        if not multiplayer_session:
            return {"generation": 0, "desired": "released", "acked": 0, "required": 0}

        desired = desired_control(
            multiplayer_session,
            room,
            lobby_all_ready(connection, int(multiplayer_session.lobby_room_id)) if room else False,
        )
        current = connection.execute(
            "SELECT desired, generation FROM multiplayer_control_state WHERE session_id=?",
            (multiplayer_session.session_id,),
        ).fetchone()
        if not current:
            generation = 1
            connection.execute(
                "INSERT INTO multiplayer_control_state(session_id,desired,generation,updated_at) VALUES(?,?,?,?)",
                (multiplayer_session.session_id, desired, generation, stamp()),
            )
            connection.commit()
        elif str(current["desired"]) != desired:
            generation = int(current["generation"]) + 1
            connection.execute(
                "UPDATE multiplayer_control_state SET desired=?, generation=?, updated_at=? WHERE session_id=?",
                (desired, generation, stamp(), multiplayer_session.session_id),
            )
            connection.commit()
        else:
            generation = int(current["generation"])

        required = len(multiplayer_session.members)
        acked = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM multiplayer_control_acks
                WHERE session_id=? AND generation=? AND state=? AND ok=1
                """,
                (multiplayer_session.session_id, generation, desired),
            ).fetchone()[0]
        )
        return {
            "generation": generation,
            "desired": desired,
            "acked": acked,
            "required": required,
            "all_acked": required > 0 and acked == required,
        }

'''
web = web.replace(body_anchor, helpers + body_anchor, 1)

# Remplace uniquement le SELECT room dans device_multiplayer_state.
state_start = web.find("    def device_multiplayer_state():")
state_end = web.find("    @app.post(\n        \"/api/device/multiplayer/join\"", state_start)
if state_start < 0 or state_end < 0:
    raise SystemExit("device_state_block_invalid")
block = web[state_start:state_end]
block = block.replace(
    '"SELECT code FROM lobby_rooms WHERE id=? LIMIT 1",',
    '"SELECT * FROM lobby_rooms WHERE id=? LIMIT 1",',
    1,
)
needle = '''                    "session": session_payload(\n                        multiplayer_session,\n                        cabinet_id=int(identity["id"]),\n                        room_code=room_code,\n                    ),\n'''
if block.count(needle) != 1:
    raise SystemExit("device_state_payload_anchor_invalid")
block = block.replace(
    needle,
    needle + '''                    "control": control_payload(\n                        connection, multiplayer_session, room if multiplayer_session else None\n                    ),\n''',
    1,
)

ack_route = r'''    @app.post(
        "/api/device/multiplayer/control-ack",
        endpoint="pincabos_device_multiplayer_control_ack_v1",
    )
    def device_multiplayer_control_ack():
        payload, error = body({"session_id", "generation", "state", "ok", "detail"})
        if error:
            return error
        session_id = str(payload.get("session_id") or "").strip()
        state = str(payload.get("state") or "").strip().lower()
        detail = payload.get("detail")
        if not session_id:
            return json_response({"ok": False, "error": "session_id_required"}, 400)
        try:
            generation = int(payload.get("generation"))
        except (TypeError, ValueError):
            return json_response({"ok": False, "error": "generation_invalid"}, 400)
        if generation < 1 or state not in _CONTROL_STATES:
            return json_response({"ok": False, "error": "control_ack_invalid"}, 400)
        if not isinstance(payload.get("ok"), bool):
            return json_response({"ok": False, "error": "control_ack_ok_invalid"}, 400)
        if detail is not None and len(str(detail)) > 500:
            return json_response({"ok": False, "error": "control_ack_detail_too_long"}, 400)

        connection = db()
        try:
            identity, _actor, error = device_context(connection)
            if error:
                return error
            repository = SQLiteSessionRepository(connection)
            multiplayer_session = repository.get(session_id)
            cabinet_id = str(identity["id"])
            membership = next(
                (
                    member for member in multiplayer_session.members
                    if member.cabinet_id == cabinet_id
                    and member.user_id == str(identity["owner_user_id"])
                ),
                None,
            )
            if not membership:
                return json_response({"ok": False, "error": "session_membership_required"}, 403)
            current = connection.execute(
                "SELECT desired, generation FROM multiplayer_control_state WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if (
                not current
                or int(current["generation"]) != generation
                or str(current["desired"]) != state
            ):
                return json_response({"ok": False, "error": "control_generation_stale"}, 409)

            connection.execute(
                """
                INSERT INTO multiplayer_control_acks(
                    session_id,generation,cabinet_id,state,ok,detail,updated_at
                ) VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(session_id,generation,cabinet_id)
                DO UPDATE SET state=excluded.state, ok=excluded.ok,
                              detail=excluded.detail, updated_at=excluded.updated_at
                """,
                (
                    session_id,
                    generation,
                    cabinet_id,
                    state,
                    1 if payload["ok"] else 0,
                    None if detail is None else str(detail),
                    stamp(),
                ),
            )
            connection.commit()
            return json_response(
                {
                    "ok": True,
                    "session_id": session_id,
                    "generation": generation,
                    "state": state,
                    "cabinet_id": cabinet_id,
                }
            )
        finally:
            connection.close()

'''
block = block + ack_route
web = web[:state_start] + block + web[state_end:]

# ------------------------------------------------------------------
# app.py — START attend les ACK armed; RESET force released.
# ------------------------------------------------------------------
if START_MARK not in app:
    fn_start = app.find("def pincabos_lobby_start(code):")
    fn_end = app.find("\n@app.", fn_start + 1)
    if fn_start < 0 or fn_end < 0:
        raise SystemExit("app_start_function_invalid")
    start_block = app[fn_start:fn_end]
    anchor = "    start_at = (\n"
    if start_block.count(anchor) != 1:
        raise SystemExit("app_start_at_anchor_invalid")
    gate = r'''    # PINCABOS_LOBBY_CONTROL_LEASE_START_V1
    _control_state = conn.execute(
        "SELECT desired, generation FROM multiplayer_control_state WHERE session_id=?",
        (_multiplayer_session.session_id,),
    ).fetchone()

    if not _control_state or str(_control_state["desired"]) != "armed":
        _desired = str(_control_state["desired"]) if _control_state else "missing"
        conn.close()
        return jsonify(
            ok=False,
            error="cabinet_control_not_armed",
            control_state=_desired,
        ), 409

    _required_control = len(_multiplayer_session.members)
    _acked_control = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM multiplayer_control_acks
            WHERE session_id=? AND generation=? AND state='armed' AND ok=1
            """,
            (_multiplayer_session.session_id, int(_control_state["generation"])),
        ).fetchone()[0]
    )

    if _acked_control != _required_control:
        conn.close()
        return jsonify(
            ok=False,
            error="cabinet_control_not_ready",
            acked=_acked_control,
            required=_required_control,
            generation=int(_control_state["generation"]),
        ), 409

'''
    start_block = start_block.replace(anchor, gate + anchor, 1)
    app = app[:fn_start] + start_block + app[fn_end:]

if RESET_MARK not in app:
    fn_start = app.find("def pincabos_lobby_reset(code):")
    fn_end = app.find("\n@app.", fn_start + 1)
    if fn_start < 0 or fn_end < 0:
        raise SystemExit("app_reset_function_invalid")
    reset_block = app[fn_start:fn_end]
    members_pos = reset_block.find("UPDATE lobby_members")
    if members_pos < 0:
        raise SystemExit("app_reset_members_anchor_invalid")
    commit_pos = reset_block.find("    conn.commit()", members_pos)
    if commit_pos < 0:
        raise SystemExit("app_reset_commit_anchor_invalid")
    commit_end = reset_block.find("\n", commit_pos) + 1
    release = r'''
    # PINCABOS_LOBBY_CONTROL_LEASE_RESET_V1
    _control_session = conn.execute(
        "SELECT session_id FROM multiplayer_sessions WHERE lobby_room_id=? LIMIT 1",
        (str(room["id"]),),
    ).fetchone()
    if _control_session:
        _sid = str(_control_session["session_id"])
        _current_control = conn.execute(
            "SELECT generation FROM multiplayer_control_state WHERE session_id=?",
            (_sid,),
        ).fetchone()
        _next_generation = int(_current_control["generation"]) + 1 if _current_control else 1
        conn.execute(
            """
            INSERT INTO multiplayer_control_state(session_id,desired,generation,updated_at)
            VALUES(?,?,?,?)
            ON CONFLICT(session_id)
            DO UPDATE SET desired=excluded.desired,
                          generation=excluded.generation,
                          updated_at=excluded.updated_at
            """,
            (_sid, "released", _next_generation, stamp()),
        )
        conn.execute(
            "DELETE FROM multiplayer_control_acks WHERE session_id=?",
            (_sid,),
        )
        conn.commit()

'''
    reset_block = reset_block[:commit_end] + release + reset_block[commit_end:]
    app = app[:fn_start] + reset_block + app[fn_end:]

if web.count(SERVER_MARK) != 1:
    raise SystemExit("server_marker_invalid")
if app.count(START_MARK) != 1 or app.count(RESET_MARK) != 1:
    raise SystemExit("app_marker_invalid")

web_path.write_text(web, encoding="utf-8")
app_path.write_text(app, encoding="utf-8")
print("GO [OK] Patch source appliqué")
PY

python3 -m py_compile "$APP_PY" "$WEB_PY" || rollback

echo "GO [OK] Compilation Python"

cd "$APP" || rollback
PYTHONPATH="$APP" python3 -m unittest discover -s multiplayer/tests -p 'test_*.py' -v || rollback

echo "GO [OK] Tests serveur Multiplayer"

systemctl restart "$SERVICE" || rollback
sleep 3
systemctl is-active --quiet "$SERVICE" || rollback

echo "GO [OK] Service actif"

python3 <<'PY' || rollback
import sqlite3
conn = sqlite3.connect("/var/lib/pincabos-release/users.db")
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
required = {"multiplayer_control_state", "multiplayer_control_acks"}
print("Tables control:", sorted(required & tables))
if not required.issubset(tables):
    raise SystemExit(1)
conn.close()
PY

echo
echo "================================================================"
echo " GO FINAL — CONTROL LEASE SERVEUR V1 INSTALLE"
echo "================================================================"
echo " IMPORTANT: cliquer RESET une fois AVANT de déployer les agents CAB."
echo " Ensuite déployer la PR #190 sur CAB1 et CAB10."
echo "================================================================"
