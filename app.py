"""Streamlit entry point for Nova Campus Tycoon (UI only).

The page shows only the 3D game. The game itself lives in game/ (Three.js)
and runs as a Streamlit v2 component. It sends batches of events; this file
passes them to bridge/logic, saves the state to SQLite and sends the new
view back. See docs/architecture.md.

Run with: uv run streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

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
                 for f in ("core.js", "world.js", "people.js", "ui.js", "flow.js", "main.js")),
)

ss = st.session_state
ss.setdefault("game_id", None)
ss.setdefault("last_seq", None)
ss.setdefault("results", [])
ss.setdefault("session", 0)  # changes whenever a game is (re)loaded


def _conn():
    return db.connect()


def handle_events() -> None:
    """Called by Streamlit when the browser sends a new batch of events."""
    batch = ss["game"]["events"] if "game" in ss else None
    if not batch or batch.get("seq") == ss.last_seq:
        return
    ss.last_seq = batch["seq"]
    conn = _conn()
    system = [e for e in batch["events"] if e.get("type") in ("new_game", "continue_game", "quit")]
    if system:
        kind = system[-1]["type"]
        if kind == "new_game":
            db.abandon_running(conn)  # a new game replaces the old one (reset)
            ss.game_id = db.save_game(conn, logic.new_game())
        elif kind == "continue_game":
            ss.game_id = db.latest_game_id(conn)
        else:
            ss.game_id = None
        ss.session += 1
        ss.results = [{"cid": e.get("cid"), "ok": True, "result": {}} for e in batch["events"]]
        return
    if ss.game_id is None:
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
    gid = db.latest_game_id(conn)
    if gid is None:
        return None
    day, money, updated = conn.execute("SELECT day, money, updated_at FROM saves WHERE id=?", (gid,)).fetchone()
    return {"day": day, "money": money, "saved_at": updated}


def payload() -> dict:
    conn = _conn()
    state = db.load_game(conn, ss.game_id) if ss.game_id is not None else None
    if state is None:
        ss.game_id = None
    else:
        logic.migrate(state)
    return {
        "ack": ss.last_seq,
        "results": ss.results,
        "session": ss.session,
        "screen": "game" if state else "title",
        "has_save": db.latest_game_id(conn) is not None,
        "save_info": _save_info(conn),
        "view": logic.view(state) if state else None,
        "plan": logic.day_plan(state) if state else None,
        "config": CONFIG,
        "lighting": timeclock.lighting_table(10),
    }


game_component(key="game", data=payload(), on_events_change=handle_events)
