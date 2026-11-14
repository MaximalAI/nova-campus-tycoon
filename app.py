"""Streamlit entry point for Nova Campus Tycoon (UI only).

The page shows only the 3D game. The game itself lives in game/ (Three.js)
and runs as a Streamlit v2 component. It sends batches of events; this file
passes them to bridge/logic, saves the state to SQLite and sends the new
view back. See docs/architecture.md.

v12: players have accounts (e-mail and password, see auth.py). Without a login the
browser shows the landing page; every save belongs to one account.

Run with: uv run streamlit run app.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import streamlit as st

import auth
import bridge
import db
import logic
import timeclock
from config import CONFIG

st.set_page_config(page_title="Nova Campus Tycoon", page_icon="☕", layout="wide",
                   initial_sidebar_state="collapsed")

# Hide everything Streamlit draws around the game.
st.markdown(
    """<style>
    header[data-testid="stHeader"], footer, [data-testid="stSidebar"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display: none !important;}
    .block-container {padding: 0 !important; max-width: 100% !important;}
    html, body, [data-testid="stAppViewContainer"] {overflow: hidden !important; background: #0d1b2a;}
    </style>""",
    unsafe_allow_html=True,
)

GAME_DIR = Path(__file__).parent / "game"
game_component = st.components.v2.component(
    "nova_campus_tycoon",
    html=(GAME_DIR / "game.html").read_text(encoding="utf-8"),
    css=(GAME_DIR / "game.css").read_text(encoding="utf-8"),
    # The browser code is split into readable files and joined in this order.
    js="\n".join((GAME_DIR / "js" / f).read_text(encoding="utf-8")
                 for f in ("core.js", "sound.js", "world.js", "people.js", "ui.js", "flow.js", "eggs.js", "main.js")),
)

ss = st.session_state
ss.setdefault("game_id", None)
ss.setdefault("last_seq", None)
ss.setdefault("results", [])
ss.setdefault("session", 0)  # changes whenever a game is (re)loaded
ss.setdefault("user_id", None)  # v12: the account that is logged in
ss.setdefault("token", None)

AUTH_EVENTS = ("auth_register", "auth_login", "auth_token", "auth_logout")


def _conn():
    return db.connect()


def _auth_event(conn, ev: dict) -> dict:
    """v12: register, log in (with password or with the token the browser kept), log out."""
    kind = ev.get("type")
    try:
        if kind == "auth_logout":
            if ss.token:
                db.end_session(conn, ss.token)
            ss.user_id = ss.token = ss.game_id = None
            return {"cid": ev.get("cid"), "ok": True, "result": {}}
        if kind == "auth_token":
            uid = db.session_user(conn, ev.get("token") or "")
            if uid is None:
                raise auth.AuthError("Your login has expired. Please log in again.")
            token = ev.get("token")
        else:
            if kind == "auth_register":
                uid = db.create_user(conn, ev.get("email", ""), ev.get("password", ""))
            else:
                uid = db.check_login(conn, ev.get("email", ""), ev.get("password", ""))
            token = db.create_session(conn, uid)
    except auth.AuthError as error:
        if kind == "auth_login":
            time.sleep(0.5)  # slows down password guessing
        return {"cid": ev.get("cid"), "ok": False, "error": str(error)}
    ss.user_id, ss.token, ss.game_id = uid, token, None
    return {"cid": ev.get("cid"), "ok": True, "result": {"token": token, "email": db.user_email(conn, uid)}}


def handle_events() -> None:
    """Called by Streamlit when the browser sends a new batch of events."""
    batch = ss["game"]["events"] if "game" in ss else None
    if not batch or batch.get("seq") == ss.last_seq:
        return
    ss.last_seq = batch["seq"]
    conn = _conn()
    if any(e.get("type") in AUTH_EVENTS for e in batch["events"]):
        ss.results = [_auth_event(conn, e) if e.get("type") in AUTH_EVENTS
                      else {"cid": e.get("cid"), "ok": False, "error": "Please log in first."} for e in batch["events"]]
        if any(r["ok"] for r in ss.results):
            ss.session += 1  # logged in or out: the browser shows the title menu or the landing page
        return
    if ss.user_id is None:
        ss.results = [{"cid": e.get("cid"), "ok": False, "error": "Please log in first."} for e in batch["events"]]
        return
    system = [e for e in batch["events"] if e.get("type") in ("new_game", "continue_game", "quit")]
    if system:
        kind = system[-1]["type"]
        if kind == "new_game":
            db.abandon_running(conn, ss.user_id)  # a new game replaces this player's old one (reset)
            ss.game_id = db.save_game(conn, logic.new_game(), user_id=ss.user_id)
        elif kind == "continue_game":
            ss.game_id = db.latest_game_id(conn, ss.user_id)
        else:
            ss.game_id = None
        ss.session += 1
        ss.results = [{"cid": e.get("cid"), "ok": True, "result": {}} for e in batch["events"]]
        return
    if ss.game_id is None or db.game_owner(conn, ss.game_id) != ss.user_id:
        ss.results = [{"cid": e.get("cid"), "ok": False, "error": "No game loaded."} for e in batch["events"]]
        return
    state = db.load_game(conn, ss.game_id)
    state, ss.results = bridge.process_batch(state, batch["events"])
    if os.environ.get("NCT_DEBUG"):
        for ev, r in zip(batch["events"], ss.results):
            if not r["ok"]:
                print("REJECTED", ev, r["error"], flush=True)
    db.save_game(conn, state, ss.game_id)


def _save_info(conn) -> dict | None:
    """Day, money and last save time of the game that "Continue" would load."""
    if ss.user_id is None:
        return None
    gid = db.latest_game_id(conn, ss.user_id)
    if gid is None:
        return None
    day, money, updated = conn.execute("SELECT day, money, updated_at FROM saves WHERE id=?", (gid,)).fetchone()
    return {"day": day, "money": money, "saved_at": updated}


def payload() -> dict:
    conn = _conn()
    state = db.load_game(conn, ss.game_id) if ss.game_id is not None and ss.user_id is not None else None
    if state is None:
        ss.game_id = None
    else:
        logic.migrate(state)
    info = _save_info(conn)
    return {
        "ack": ss.last_seq,
        "results": ss.results,
        "session": ss.session,
        # v12: landing page and login first, then the title menu, then the game
        "screen": "landing" if ss.user_id is None else ("game" if state else "title"),
        "user": {"email": db.user_email(conn, ss.user_id)} if ss.user_id is not None else None,
        "has_save": info is not None,
        "save_info": info,
        "view": logic.view(state) if state else None,
        "plan": logic.day_plan(state) if state else None,
        "config": CONFIG,
        "lighting": timeclock.lighting_table(10),
    }


game_component(key="game", data=payload(), on_events_change=handle_events)
