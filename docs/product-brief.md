# Nova Campus Tycoon: Product Brief

## 1. Vision
Nova Campus Tycoon is a management game. The player owns a small café on a university campus and competes against a bot-run café. As in Monopoly, the goal is to grow the business until the player owns every shop on the campus and holds the monopoly.

## 2. Scope of the first release
The first release is a **day-based management game in Streamlit**. It contains the full economic loop: buying ingredients, setting prices, student demand, serving orders, upgrades, hiring, acquiring the competitor, and win/lose conditions, all with persistent saves.

Out of scope for this release: the real-time 3D campus map (walking character, 3D stalls, 3D students, live 12-minute clock). It is planned for a later release.

## 3. Technical requirements
- **Stack:** Python, Streamlit (UI), SQLite (storage), pytest (tests), uv (environment and commands).
- **Run the app:** `uv run streamlit run app.py`
- **Run the tests:** `uv run pytest`
- **Folder structure:**
  ```
  nova-campus-tycoon/
  ├── app.py              # screens only, no game rules
  ├── logic.py            # all game rules as pure functions, no Streamlit or SQL imports
  ├── db.py               # SQLite schema, load and save
  ├── tests/              # pytest tests
  ├── specs/first-feature.md
  ├── docs/product-brief.md
  ├── AGENTS.md
  └── pyproject.toml
  ```
- All balancing values (prices, costs, times, utility ranges, upgrade effects) live in one `CONFIG` dict in `logic.py`.
- Money is stored and calculated as **integer cents** to avoid rounding errors; it is shown as euros in the UI.
- Randomness is **seeded** per game and day (seed saved in the database), so a day can be reproduced after a restart and in tests.
- The game state is **saved to SQLite after every action**. Stopping and restarting the app continues exactly where the player left off.
- The database file lives in `data/` and is ignored by git. No secrets in the repository.
- Invalid actions are rejected by `logic.py` with a clear error message and leave the saved state unchanged.

## 4. Shops and products
| Shop | Owner at start | Products |
|---|---|---|
| Player café | Player | Coffee, Orange Juice, Pastel de Nata |
| Competitor café | Bot | Coffee, Tea, Croissant |
| Wholesaler | (supplier) | Raw ingredients |

## 5. Screens
1. **Start screen:** "New game" and "Continue" (if a saved game exists).
2. **Header on every screen:** balance top right (starts at €100.00), current day, current phase.
3. **Morning planning:** wholesaler, prices, upgrades, hiring and acquisition. Button "Open shop" starts the selling phase.
4. **Selling day:** order queue, remaining preparation time, "Accept next order", "End day".
5. **End-of-day summary:** statistics, then "Next day".
6. **Game over / Victory screen** with a "New game" button.

The game only advances through player actions, so there is no running clock to pause. A "Save & quit" button returns to the start screen; the state is already saved.

## 6. Day flow

### 6.1 Morning planning
The player makes three decisions:
1. **Buy ingredients** at the wholesaler at fixed unit prices, choosing the quantity of each.
2. **Set the selling price** of each product in the café.
3. **Buy upgrades** (optional), and later hire employees or buy the competitor.

### 6.2 Ingredients and inventory
| Ingredient | Used for | Unit cost |
|---|---|---|
| Coffee beans | Coffee | €0.40 |
| Oranges | Orange Juice | €0.60 |
| Frozen Pastel de Nata | Pastel de Nata | €0.50 |
| Tea leaves (only after acquisition) | Tea | €0.30 |
| Frozen croissants (only after acquisition) | Croissant | €0.70 |

- 1 ingredient unit = 1 finished product.
- Inventory is kept per shop.
- At the end of every day all remaining inventory **spoils and resets to 0**.

### 6.3 Student demand
- 10 students. Each receives a **budget of €10.00** at the start of every day; unspent money does not carry over.
- Every day, each student *i* draws a **new random base utility u_ij for every product j**, uniform between €0.50 and €4.00 (configurable).
- Each shop *s* has a **shop utility factor F_s**. The player café starts at 1.0; the competitor has a fixed 1.2.
- The utility of buying product *j* at shop *s* is `F_s * u_ij`.
- Each student chooses the bundle (binary decision x_j ∈ {0,1} for each of the 6 products) that maximizes

  `U_i = Σ_j x_j * F_s(j) * u_ij + (10 - Σ_j x_j * p_j)`

  subject to `Σ_j x_j * p_j ≤ 10`.
  Unspent money yields utility 1 per euro. With 6 products there are only 64 bundles, so solve by brute force.
- Coffee is offered by both shops and treated as two products, but a student buys at most one coffee in total.
- A student's purchases at one shop form one order at that shop.

### 6.4 Selling phase
- On "Open shop", the logic generates the day's demand and puts the orders for the player café into a **queue** in random arrival order.
- A day has a **preparation time budget of 720 seconds** (12 minutes).
- Preparation time per item: Coffee 15 s, Orange Juice 25 s, Pastel de Nata 20 s, Tea 10 s, Croissant 20 s.
- "Accept next order" processes the first order in the queue:
  - Items that are out of stock are dropped and count as lost sales.
  - The remaining items consume their preparation time and their price is credited to the balance.
- An order cannot be accepted if the remaining time is less than its preparation time.
- "End day" closes the shop; orders still in the queue count as lost customers.
- The competitor bot serves all its orders automatically (unlimited stock, no time limit).

### 6.5 End-of-day summary
Per shop: units sold per product, revenue, ingredient cost, value of spoiled inventory, spending on upgrades and hiring, profit of the day, customers served vs. lost, market share vs. the competitor, and the new balance. A simple bar chart of sales per product.

## 7. Upgrades
Three one-time upgrades per shop, each permanently increasing the shop utility factor:

| Upgrade | Effect on F | Cost |
|---|---|---|
| Better coffee machine | +0.15 | €60 |
| Seating & decoration | +0.20 | €120 |
| Branding & signage | +0.25 | €200 |

## 8. Competitor bot
- Fixed prices: Coffee €2.00, Tea €1.80, Croissant €2.20.
- Fixed shop utility factor 1.2.
- No inventory, pricing or upgrade decisions.

## 9. Progression
- **Hire an employee (€200):** the employee serves the queue of that shop automatically within the same time budget, so the player no longer has to click through the orders.
- **Buy the competitor (€500):** only possible if the player café already has an employee. After the acquisition the player controls the second shop: prices, ingredient purchases and upgrades. Its revenue goes to the player's balance.
- After the acquisition the player can serve only **one shop manually per day**. A shop that has neither an employee nor the player loses all its orders that day.

## 10. Win and lose conditions
- **Game over:** the balance is €0.00 or below at the end of a day.
- **Victory:** the player owns both shops and has an employee in each. Show days played and total profit.

## 11. State that must be saved
- Game: day, balance, phase (morning, selling, summary, finished), status (running, game over, victory), random seed.
- Per shop: owner, prices, upgrades bought, shop utility factor, employee hired, inventory.
- Current day: order queue, remaining preparation time, sales so far.
- History: one summary row per finished day.

## 12. Invalid actions (must be rejected)
- Spending more than the current balance (ingredients, upgrades, employee, acquisition).
- Negative or non-integer quantities, or a purchase where all quantities are 0.
- Prices of €0.00 or below, or above €10.00.
- Buying the same upgrade twice, or hiring a second employee in the same shop.
- Buying the competitor without an employee in the player café, or buying it twice.
- Planning actions outside the morning phase; selling actions outside the selling phase.
- Accepting an order when the remaining time is too short.
- Any action after game over or victory.

## 13. Open questions
- Should employees cost a daily wage? Not decided; not part of the first release.
