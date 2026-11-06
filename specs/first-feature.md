# First feature: Start a game and buy ingredients

Source of truth: `docs/product-brief.md` (sections 3, 5, 6.2, 11 and 12).

## Why
Buying ingredients is the first decision of every game day. Without a saved balance and inventory, no later feature (pricing, selling, end of day) can work. This feature also proves the core architecture: rules in `logic.py`, storage in `db.py`, screens in `app.py`, and state that survives a restart.

## What
- **Start screen:** "New game" creates a game with day 1, balance €100.00, phase `morning`, status `running` and an empty inventory. "Continue" is shown only if a saved game exists and loads it.
- **Header:** balance top right, day and phase.
- **Wholesaler screen:** one whole-number input per ingredient (Coffee beans €0.40, Oranges €0.60, Frozen Pastel de Nata €0.50), the live total cost, and a "Buy" button.
- **Inventory panel** showing the stock of the player café.

### Rule
A purchase is valid only if all of the following hold:
- the game phase is `morning` and the status is `running`;
- every quantity is a whole number ≥ 0, and at least one quantity is > 0;
- the total cost is ≤ the current balance.

Valid purchase: the balance decreases by the total cost, the inventory increases by the quantities, and both are saved.
Invalid purchase: rejected with a clear message; balance, inventory and database stay unchanged.

### State to save
- `games`: id, day, balance_cents, phase, status, seed
- `inventory`: game_id, shop (always `player_cafe` in this feature), ingredient, quantity

## Out of scope
Prices, demand, selling, end of day, spoilage, upgrades, employees, competitor, 3D map.

## Done when
All checks below pass as pytest tests (using a temporary database) and can be repeated by hand in the running app:
1. **Allowed purchase:** new game, buy 10 coffee beans, 5 oranges, 4 frozen pastel → total €9.00, balance €91.00, inventory 10 / 5 / 4.
2. **Repeated purchases add up:** buying 10 coffee beans twice → 20 in inventory, balance €92.00.
3. **Exact balance is allowed:** buying 250 coffee beans (€100.00) → balance €0.00.
4. **Too expensive is rejected:** buying 200 oranges (€120.00) → error, balance €100.00, inventory empty.
5. **Invalid quantities are rejected:** a negative quantity, or all quantities 0 → error, nothing changes.
6. **Wrong phase is rejected:** a purchase when the phase is not `morning` → error, nothing changes.
7. **Restart:** after check 1, close the database connection and load the game again from the same file → balance €91.00 and inventory 10 / 5 / 4. In the app: stop Streamlit, start it again, click "Continue" → same values (refreshing the browser alone does not count).
