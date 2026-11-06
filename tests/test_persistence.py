"""Saving and continuing (brief section 12)."""

import db
import logic
import simulation as sim


def test_save_and_continue_restores_the_state(tmp_path):
    path = tmp_path / "game.db"
    state = sim.morning_setup(logic.new_game(seed=8))
    state, _ = logic.apply(state, {"type": "set_prices", "shop": "cafe", "prices": {"coffee": 100}, "t": 7.0})
    conn = db.connect(path)
    game_id = db.save_game(conn, state)
    conn.close()

    conn = db.connect(path)
    assert db.latest_game_id(conn) == game_id
    loaded = db.load_game(conn, game_id)
    assert loaded == state
    assert loaded["shops"]["cafe"]["prices"]["coffee"] == 100


def test_saving_again_updates_the_same_row(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    state = logic.new_game(seed=1)
    gid = db.save_game(conn, state)
    state, _ = logic.apply(state, {"type": "confirm_plan", "plan": {"coffee": 5}, "t": 5.2})
    assert db.save_game(conn, state, gid) == gid
    assert conn.execute("SELECT COUNT(*) FROM saves").fetchone()[0] == 1
    assert db.load_game(conn, gid)["plan"] == {"coffee": 5}


def test_finished_games_are_not_offered_for_continue(tmp_path):
    conn = db.connect(tmp_path / "game.db")
    state = logic.new_game(seed=1)
    state["status"] = logic.GAME_OVER
    db.save_game(conn, state)
    assert db.latest_game_id(conn) is None


def test_state_is_json_after_a_full_day(tmp_path):
    state = sim.simulate_day(sim.morning_setup(logic.new_game(seed=2)), speed=8)
    conn = db.connect(tmp_path / "game.db")
    gid = db.save_game(conn, state)
    assert db.load_game(conn, gid) == state


def test_resume_resets_open_orders_and_queues():
    state, _ = logic.apply(logic.new_game(seed=4), {"type": "tick", "t": 8.0})
    s = state["students"]["s1"]
    s["status"], s["intent"] = "queuing", {"shop": "cafe", "items": ["coffee"]}
    state["current_order"] = {"shop": "cafe", "student": "s1", "items": ["coffee"], "accepted_at": 8.0}
    state["tray"] = ["coffee"]
    state, _ = logic.apply(state, {"type": "resume", "t": 8.5})
    assert state["students"]["s1"]["status"] == "wandering"
    assert state["current_order"] is None and state["tray"] == []
