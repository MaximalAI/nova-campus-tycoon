# Spec: v5 managers, second café and polish

## Why
Playtesting v4: the clock stopped in every pop-up, the manager only stood behind the counter, buying the competitor ended the challenge, reputation never recovered, quiet hours were too long, and several small display and control issues.

## What
1. Clock keeps running in pop-ups; leaving the browser tab pauses the game.
2. No dirt circle in the café before closing.
3. Clickable minimap: big map with teleport to the cafés and the wholesaler.
4. Wholesaler: empty cart, take products stand by stand, pay at the checkout; no shopping list during the day.
5. More customers during lectures and in the evening.
6. Patience bars follow the game speed (also in the order pop-up).
7. Register only before opening.
8. Lower and wider camera inside buildings.
9. Order bubbles centred and sized by the order.
10. People do not overlap; leaving customers use a side lane; no "walking on the spot".
11. Sold out: explain why customers stay or leave.
12. Throw away single products or only the extras.
13. Manager: starts the next day, proposes shopping list and prices every morning (accept or change), buys, walks to the stations, cleans after closing, and raises the reputation with happy customers.
14. Day gain next to the cash with a statistics pop-up and charts over all days.
15. Price boards in front of both cafés ("-" before prices are set).
16. "FOR SALE" sign at the competitor once you could buy it.
17. After buying the competitor you run it yourself from the next day (start the day there), the manager runs the first café; a manager in both means victory.

## Out of scope
- New products, sound, multiplayer, path finding inside buildings beyond the counter gap.

## Done when
- `uv run pytest` passes, including `tests/test_v5.py` and the rewritten manager tests in `tests/test_progression.py`.
- Browser test: clock runs with a pop-up open; cart starts empty and fills at the stands; register disabled after opening; extras can be thrown away; big map teleports; leaving the tab pauses; manager proposal is shown and buys; the manager walks to the stations and cleans; next day starts in the bought café.
