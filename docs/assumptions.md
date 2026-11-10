# Assumptions made while building v2

Decisions that the brief left open or that came up during implementation. Change them in `config.py` or tell the team.

## Rules and balancing
- Student utilities are drawn between €0.30 and €3.00 (brief default was €0.20-2.00). With €2.00 nobody ever bought orange juice at €2.50; the headless simulation showed it.
- Competitor prices: coffee €1.00, tea €1.20, croissant €1.50; competitor factor 1.2.
- Reputation: correct order +2 (+1 if handed over within 12 game minutes after accepting), wrong order -4, lost customer -1, unfinished cleaning -5. The first version used -2 per lost customer; a day without serving dropped reputation from 50 to 10, which felt too harsh.
- Patience starts counting when the café opens (08:00), also if the player is not there. Students who arrive before 08:00 wait in front of the door without losing patience.
- After accepting an order the student's patience is reset once.
- Money is credited at handover (brief 7.3). Only the correctly delivered items are paid; extra items are wasted.
- The day planning is pre-filled on day 1 (20 coffee, 4 orange juice, 10 pastéis de nata) so the first shopping list is not empty.
- The cart is pre-filled from the shopping list only on the first visit after planning.
- Prices can only be changed before opening, in steps of €0.10, between €0.10 and €10.00.
- The café can be opened manually from 07:00; it opens automatically at 08:00.
- The wholesaler is open until 20:00, so the player can restock during the day.
- Only the player's first café has cleaning spots. After buying the competitor, its stock and prices are managed through its own counter and storage shelf.
- The wholesaler sells tea (pack of 20 bags, €2.40, unlimited shelf life) and croissants (€0.50 each, 1 day) only after the competitor is bought.
- Students walk 1.9-2.6 m per real second at 1x so they reach the cafés during the morning rush.

## Time and controls
- At 20:00 the speed switches back to 1x, otherwise there is no time to clean at 8x.
- Cleaning that is still running after 21:00 completes; the clock stays at 21:00.
- The player's own walking speed is not multiplied by the game speed (brief 5).
- Camera (v3/v4): one third-person follow camera everywhere, GTA style. Click the game to capture the mouse (pointer lock), the mouse turns the camera, W walks in the camera direction, Shift runs, the wheel zooms. Inside buildings the camera moves closer and higher, and walls or roofs between camera and player fade out, so the player is never hidden behind the counter. The v2 fixed counter camera was removed because it sat behind the stations.
- Movement (v3): acceleration and smooth turning; movement is split into small sub-steps so fast running cannot pass through walls.

## Saving
- The game is saved after every batch of events. "Continue" resumes at the saved game time. Students who were in a queue or on their way to a shop start again on campus, and an order in progress is cancelled (event `resume`).

## Visuals
- Pictures of items and products are emoji icons instead of PNG files (brief 9.2 mentions `img/*.png`). They can be replaced later.
- 3D models are built from simple shapes in code (no external assets). Three.js is loaded from a CDN, so the game needs an internet connection.

## Version 1 tests
- The v1 tests (`test_first_feature.py`, `test_rules.py`, `test_demand.py`, `test_selling.py`, `test_app.py`, `test_setup.py`) were replaced by v2 tests because the rules changed by design (units and shelf life, new prices, sales process, students over the day). The same kinds of rules are covered again in `tests/test_economy.py`, `test_sales.py`, `test_students.py` and `test_progression.py`.

## v3 changes
- Language: the whole game is English (menus, buttons, dialogs, tutorial, product names, notifications, minimap). Money is shown as "€12.34".
- Wholesaler: the leave check only runs after the player was really inside. In v2 it fired right after "Enter" because the player still stood at the door, which closed the gate again.
- Competitor café: when the player buys it, its barista stays (`staff`). The barista serves automatically like the bot did, so customers get their products, pay and leave happy. Revenue goes to the player.
- Barista restock: right after the purchase and every morning the barista refills the competitor café up to `rival_restock_plan` (config.py), paid from the player's cash and limited by it. The cost counts as purchases in the daily summary and is shown in the morning dialog.
- Automatic serving (bot, barista or manager) freezes the customer's patience while the order is made, so nobody leaves during service.
- Minimap with legend: your café (green), competitor (red, green once owned), wholesaler (blue), you (arrow with view cone), students (dots), next goal (ring).
- Old v2 saves are migrated on load (`logic.migrate`): missing `staff`, `cart_prefilled` and `restock` keys get defaults.

## v4 changes
- Mouse look: the game runs inside a shadow DOM (Streamlit component). There `document.pointerLockElement` is the shadow host, not the canvas, so v3 never noticed that the mouse was captured. v4 asks the canvas' own root. With the mouse captured the figure always faces the view direction (Minecraft style); without it, it turns towards the walking direction (GTA style). If the browser refuses the capture, dragging with the mouse turns the camera.
- Stock card left of the reputation: portions each owned shop can still sell, updated live (red = 0, orange = 3 or less).
- Minimap without legend; the building icons on the map are enough.
- Wholesaler card: shopping list next to the cart (missing / done), cart total, cash.
- "Start the day" button: after shopping and stocking, before 08:00, jumps the clock to 08:00 and opens the café.
- Preparation is faster: coffee 2, juice 3, tea 2 game minutes.
- Mistakes while serving: Cancel stops a product that is being made (nothing is used). A wrong product on the tray can be thrown away (ingredients lost). An order can be cancelled (customer leaves, reputation -3).
- Sold out: crossed-out emojis were unclear. Bubbles and the order dialog now say "sold out".
- What reputation brings: more customers (factor 0.7 to 1.3 for the day), more patience (x0.75 to x1.35), tips for correct orders (5 % from 60, 10 % from 75, 15 % from 90). The reputation card shows the current effect.
- Reputation goes down visibly: waited too long -3, sold out and left -1 (once per student and day, otherwise one empty shelf would ruin the day), turned away -1, cancelled order -3, wrong order -4. Every change shows a toast.
- Cheaper: upgrades €30 / €60 / €100, manager €100, competitor €300.
- Daily summary with four tabs: today (incl. tips, sold out, thrown away), stock movements per item (start, in, used, spoiled, end, change), the competitor (customers, sales, market share, prices of the day), the last 7 days.
- Saving: the start screen offers "Continue" first (Enter) and shows day and cash of the save. A new game asks first and replaces the save (`db.abandon_running`). Continuing inside the wholesaler puts unpaid goods back.
- Pause menu: "New game" (with confirmation) to start over.
- Storage shelf: was a solid block with boxes stuck inside it. Now an open shelf whose crates show the real stock.
- Clock edge case: the browser clock is a float, so 20.9999999 now counts as 21:00 (before, the day could get stuck in "closing").

## v5 changes
- The clock keeps running while a pop-up is open (only the pause menu stops it). Leaving the browser tab opens the pause menu.
- The dirty floor spot in the café only shows after closing (it was visible from day 1).
- Minimap: click it for a big map; clicking a place teleports you to its door. Not possible while unpaid goods are in your cart.
- Wholesaler: the cart starts empty. You take each product at its stand (shopping list as reference, more or less is fine) and pay at the checkout. During the day the list is hidden; only the cart shows.
- Demand: lectures and the evening have more students and a higher café probability, and students have €16 a day (was €10, the afternoon dried up because budgets were spent). Measured with the simulation: about 8 to 19 customers per hour for both cafés during lectures.
- The patience bar runs in game time (checked: 4x speed drops 4x faster). The bar in the order pop-up now updates live.
- The register is only usable before opening (prices are fixed during the day).
- Camera inside buildings may go lower and further back (walls fade), so you see the door and arriving customers.
- Order bubbles: emojis centred, bubble as wide as the order (the "being served" tag used to stretch it).
- People do not overlap: they push each other apart, someone standing in the queue stays put, the player is pushed out. Customers leave along a side lane instead of walking through the queue. Legs stop swinging at once when someone stops.
- Sold out: the utility model compares the rest of the order with the other café and with keeping the money. That is why some customers still take the other product and some leave. The toast now says why.
- Tray: each product has its own ✕, and "Throw away extras" removes only what the order does not need.
- Manager: starts the next day. Every morning he proposes plan and prices (yesterday's sales +20 %, +50 % if sold out, at least 8; price +€0.10 if sold out, -€0.10 if nobody bought). You accept or change it, otherwise he buys at 07:00. He walks to the stations for every product and cleans the four spots after closing. Happy customers of the manager give +1 reputation (before: only losses, so reputation never recovered).
- Day gain next to the cash (sales + tips - purchases - spending today); click it for statistics with charts over all days (market share, sales and profit, reputation, customers, cash). The daily summary has a Charts tab too.
- Price boards in front of both cafés ("-" until today's prices are set or the café opens); a "FOR SALE" sign at the competitor once you hired a manager.
- After buying the competitor: no barista any more. It opens the next day and you run it yourself (plan, shop, serve) while the manager runs the first café; the day starts in front of the new shop. A manager there too means victory. Old saves with the v3/v4 barista are migrated to this rule.
