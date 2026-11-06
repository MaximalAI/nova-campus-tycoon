"""The Streamlit page starts and hands event batches to the rules (docs/architecture.md)."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"


def test_app_starts_on_the_title_screen(tmp_path, monkeypatch):
    monkeypatch.setenv("NCT_DB_PATH", str(tmp_path / "game.db"))
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    assert at.session_state["game_id"] is None


def test_game_files_exist_and_export_the_component_entry():
    game = APP.parent / "game"
    for name in ("game.html", "game.css"):
        assert (game / name).exists()
    main = (game / "js" / "main.js").read_text(encoding="utf-8")
    assert "export default function" in main
    core = (game / "js" / "core.js").read_text(encoding="utf-8")
    assert core.lstrip().startswith("//") and "import * as THREE" in core
