"""Click through the Streamlit app headlessly, including a restart."""

import pytest
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "game.db"
    monkeypatch.setenv("NCT_DB_PATH", str(path))
    return path


def start(db_path):
    import importlib

    import db

    importlib.reload(db)  # pick up NCT_DB_PATH
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    return at


def click(at, label):
    button = next(b for b in at.button if b.label == label)
    button.click().run()
    assert not at.exception, at.exception


def balance(at):
    return next(m for m in at.metric if m.label == "Balance").value


def test_play_one_day_then_restart(db_path):
    at = start(db_path)
    assert [b.label for b in at.button] == ["🆕 New game"]
    click(at, "🆕 New game")
    assert balance(at) == "€100.00"

    # Wholesaler: 10 coffee beans, 5 oranges, 4 pastel = €9.00
    inputs = {n.label: n for n in at.number_input}
    inputs["Coffee beans (€0.40)"].set_value(10)
    inputs["Oranges (€0.60)"].set_value(5)
    inputs["Frozen Pastel de Nata (€0.50)"].set_value(4)
    at.run()
    next(b for b in at.button if b.label == "Buy").click().run()
    assert balance(at) == "€91.00"
    assert any("Bought ingredients" in s.value for s in at.success)

    # Rejected purchase shows an error and changes nothing
    inputs = {n.label: n for n in at.number_input}
    inputs["Oranges (€0.60)"].set_value(200)
    at.run()
    next(b for b in at.button if b.label == "Buy").click().run()
    assert any("Not enough money" in e.value for e in at.error)
    assert balance(at) == "€91.00"

    click(at, "🔔 Open shop")
    while any(b.label == "✅ Accept next order" for b in at.button):
        click(at, "✅ Accept next order")
        if any("Not enough time" in e.value for e in at.error):
            break
    click(at, "🌙 End day")
    assert any(m.label == "Profit today" for m in at.metric)
    click(at, "☀️ Next day")
    day2_balance = balance(at)

    # Restart: a brand-new app session with the same database file
    at2 = start(db_path)
    assert "▶️ Continue" in [b.label for b in at2.button]
    click(at2, "▶️ Continue")
    assert balance(at2) == day2_balance
    assert any("Day 2" in md.value for md in at2.markdown)


def test_open_selling_day_survives_restart(db_path):
    at = start(db_path)
    click(at, "🆕 New game")
    click(at, "🔔 Open shop")
    before = [md.value for md in at.markdown if md.value.startswith("**Next:**")]

    at2 = start(db_path)
    click(at2, "▶️ Continue")
    after = [md.value for md in at2.markdown if md.value.startswith("**Next:**")]
    assert after == before
    assert any(b.label == "🌙 End day" for b in at2.button)


def test_save_and_quit_returns_to_start(db_path):
    at = start(db_path)
    click(at, "🆕 New game")
    at.sidebar.button[0].click().run()
    assert "▶️ Continue" in [b.label for b in at.button]
