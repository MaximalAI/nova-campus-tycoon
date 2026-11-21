"""v16: order bubbles without queue numbers and without stacking, one style for the "i" buttons
(see specs/v16-bubbles-and-info-i.md). These are browser changes, so the tests read the static files."""
import re
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent / "game"


def _css_rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    return match.group(1)


def test_bubbles_have_no_queue_number():
    main = (GAME / "js" / "main.js").read_text()
    css = (GAME / "game.css").read_text()
    assert "qpos" not in main
    assert "qpos" not in css


def test_bubbles_are_not_moved_up():
    main = (GAME / "js" / "main.js").read_text()
    body = main[main.index("  declutter(list) {"):main.index("  liftHint() {")]
    assert "style.top" not in body
    assert "zIndex" in body


def test_stock_i_looks_like_gain_i():
    css = (GAME / "game.css").read_text()
    stock = _css_rule(css, "#stock-info")
    gain = _css_rule(css, "#gain .info-i")
    for part in ("italic 800 11px/1 Georgia, serif", "var(--green-dark)", "-webkit-text-fill-color: #fff"):
        assert part in gain
        assert part in stock
    assert "text-transform: none" in stock
    assert "letter-spacing: 0" in stock
