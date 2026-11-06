# Spec: v4 improvements

## Why
Playtesting v3: mouse look still did not work, stock and shopping were hard to follow, mistakes at the counter could not be undone, reputation had no visible effect and never dropped, and progress seemed lost after closing the app.

## What
1. **Mouse look:** capturing the mouse works inside the Streamlit component (shadow DOM). The figure turns with the mouse while it is captured; dragging works as a fallback.
2. **Stock card** left of the reputation, always up to date (portions per product and shop).
3. **Minimap** without legend.
4. **Wholesaler card:** shopping list against the cart, total, cash.
5. **Start the day:** button under the clock jumps to 08:00 after shopping and stocking.
6. **Faster preparation** (coffee 2, juice 3, tea 2 minutes).
7. **Undo mistakes:** Cancel while a product is made, throw away the tray, cancel the order.
8. **Sold out** is labelled clearly.
9. **Reputation perks:** demand, patience, tips; shown in the HUD.
10. **Reputation penalties** for customers who leave (too long, sold out, turned away, cancelled), with toasts.
11. **Cheaper upgrades,** manager and competitor.
12. **Daily summary:** stock movements, history of the last days, competitor with prices.
13. **Storage shelf** shows real crates instead of the display bug.
14. **Saving:** Continue is the default on the start screen; a new game must be confirmed.
15. **Reset:** "New game" in the pause menu.

## Out of scope
- New products or buildings, sound, multiplayer.

## Done when
- `uv run pytest` passes, including `tests/test_v4.py`.
- Browser test: mouse capture is active after a click and turns camera and figure; Esc frees it.
- Stock card, wholesaler card and ⏩ button show the right values; ⏩ opens the café at 08:00.
- A wrong product can be stopped, thrown away and replaced; an order can be cancelled.
- Summary tabs show stock, competitor and history.
- Reloading the page offers Continue with the same day and cash; New game in the pause menu starts over after confirmation.
