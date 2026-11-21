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

## v6 changes
- Morning: no automatic planning pop-up any more; the marker leads to the planning board (manager proposals still pop up).
- Staff animations: at a station the arms move (coffee, juice, pastry) and a tag with icon and progress bar shows what happens; the same for the four cleaning spots.
- Customers leave through the middle of the door (lane at 0.8 m from the door centre, the door is 3 m wide) instead of along the wall.
- FOR SALE sign: two posts behind the plate, nothing covers the letters.
- Stuck people: someone who wants to walk but hardly moved for a second may pass through others for 2.5 s, so groups never block each other.
- Upgrade dialog is wider and the status chips do not wrap.
- A sold-out product: the manager does not walk to its station, he tells the customer right away.
- Buying the competitor: you pay today, it becomes yours the next morning. Until then the old owner keeps selling (price board: "SOLD - NEW OWNER TOMORROW").
- Objective texts: while the purchase is pending and after the takeover they say that the manager runs the first café and you run the second one.
- As soon as a manager is hired, the player cannot clean any more: the manager cleans, already on the evening of the day he was hired.
- After the victory: "Keep playing (open mode)" continues the game without a goal (no second victory screen).
- The competitor's display shows croissants.
- M opens and closes the big map.

## v7 changes (campus expansion)
- Nine shops in two zones, bought in a fixed order (config "order"). Buying rule: only the next shop, and only when every shop you own has a hired manager (hired counts, he may start tomorrow).
- Everything new is data in `config.py`; the rules of each mechanic are a small class in `mechanics.py`, found by the mechanic type. `logic.py` never asks for a shop name.
- The two classic cafés keep their ids ("cafe", "rival") and their random utilities, so v4 to v6 saves load (`logic.migrate`). A v6 game that had already won continues with the new goal.
- Decisions: a visit goes to one shop. The best bundle is computed per shop (at most three products) instead of over all 27 offerings.
- Student economy: 40 campus students with €28 each (v6: 25 with €16), so nine shops find customers. Beach visitors (20, €60 each) only exist once the beach is open and stay at the beach.
- Prices of the shops and managers were tuned with the headless campaign simulation (a perfect player who buys and hires as soon as allowed): first shop around day 10, then about 5 days per shop.
- SnackBots: breakdown chance 4 % per machine and opening hour (seeded). A broken machine stays broken overnight until repaired.
- Mercado & Go: 60 shelf places, filling allowed until 10:00. Shelf goods spoil with their shortest-lived ingredient (sandwiches overnight).
- Bowl Bar: one assembly station; the set of ingredients decides the product (exact match), anything else is a "wrong bowl".
- Nova Mensa: open 11:30 to 14:30, demand factor x1.4 during the rush; customers already in the queue at 14:30 are still served.
- Surf Shack: a rental takes 2 game hours, a wetsuit then dries 1 hour; everything is back overnight. A manager plans one board per 4 rentals.
- Praia Bar: opens at the start of the "sunset" lighting phase, happy hour for the first hour (discount 0 to 50 % in steps of 5 %, demand x1.4).
- Gelado Kiosk: display portions melt 3 game hours after filling and overnight; the freezer keeps. A manager keeps the display half full.
- The beach weather (waves 1 to 5, temperature 16 to 34 °C) is seeded per day and shown in the morning (P30).
- The mechanics run on ticks every full hour (plus 11:30, 14:30, 17:30, 18:30), sent by the browser and by the simulation.

## v8 changes
- Monopoly counter: owned shops / all shops (1/9 at the start).
- Sold-out reputation: -1 per customer who goes home, -2 per customer who goes to a competitor instead, every time (v4 to v7: once per day), capped at -15 per day.
- Manager proposal: (sold + customers who found it sold out) x buffer. The summary keeps the sales of all shops (`by_shop`).
- A manager hired during the day starts the next morning; the player cleans that evening.
- SnackBots: three machines on the campus with their own stock, cash box and breakdowns. Sales go into the cash box; the player collects it and deposits it at the office (the manager does this himself).
- Shop prices about 15 % lower, the second shop €300. Measured with 10 seeds: first purchase on day 6, the last shop on day 36.
- Saving: WAL journal, synchronous FULL, a backup copy of the last good state in the same row, damaged files are moved aside. The browser sends an `autosave` event every 10 s and when the page is hidden.
- Sound is synthesised (Web Audio). Music and effects are separate switches in the pause menu, stored in localStorage (wrapped in try/catch; without storage the default is on).
- Jep: €10, high for 10 game minutes, one at a time. His look is a neutral, distinctive outfit (bucket hat, sunglasses, flower shirt); we chose not to code him by ethnicity.
- Casino: European roulette (0 to 36), bets red/black, even/odd (1:1) and dozens (2:1); bets from €10 to €1,000 and never more than your cash. The number is seeded, so tests are repeatable.
- Jep and casino money count in the day profit and the day gain next to the cash.

## v9 changes
- Upgrades & staff and the day plan board belong to one shop each. The board of a shop you do not run today shows its plan read-only.
- Managers of shops with a counter clean after closing. This is shown, it has no rule effect (the café's four cleaning spots stay the only cleaning rule).
- The managers' wholesaler walk is shown in the browser only; the purchase itself happens in Python when you accept the proposal (as before).
- Wholesaler layout: one stand per product. A product used by several shops stands with the first shop that needs it (coffee beans with the café, fruit mix with the Bowl Bar).
- Sound distance: full volume within 8 m, silent from 30 m. Alerts (breakdowns, end of day, purchases) are heard everywhere.
- Casino bar: drinks €4 to €8, tipsy for 10 game minutes, one at a time. Slot machines: coins €1, €5, €10; return rate about 89 %.

## v10 changes
- Upgrades: three per shop, themed; prices and bonuses equal the café's tiers (€30 +0.15, €60 +0.20, €100 +0.25). v9 upgrades map to the same tier.
- Cleaning: every owned shop with staff that was open today; the player cleans the one he ran, managers clean theirs. Missed cleaning costs reputation once per shop that was the player's job. The vending shop has no cleaning.
- SnackBots manager: plans capacity x machines per product; refilling shares the goods out evenly (emptiest machine first).
- Mercado & Go: shelves can be filled until closing; the fill_until value is 20:00. A partly sold-out order costs 1 reputation point (inside the daily sold-out cap of 15).
- Managers wait outside the wholesaler while the player is inside (only shown in the browser; the purchase happens in Python when the proposal is accepted).

## v11 changes
- "Start the day" waits for every manager who is on (or about to start) his wholesaler walk. The purchase itself still happens in Python when the proposal is accepted; the walk is shown in the browser.
- Managers avoid each other in the browser only (a walking one gives way); this has no rule effect.
- SnackBots manager rounds: one `manager_service` event per machine (repair if the money is there, refill from the storage while open, take the cash into the balance). Browser rounds about every 90 game minutes, at once after a breakdown. Python fallback: half an hour after opening, then every two hours without a round. The evening cash is collected on the last round or at the end of the day.
- Reusable rental items last 40 rentals (`lifetime_uses`). Their cost per rental is used in the price dialog and by managers; the purchase price is still paid once when buying.
- Shops with their own opening hours (Praia Bar) can be priced until they open.
- Missed cleaning: -15 reputation per shop that was the player's job (v10: -5).
- Investments (shops, upgrades, managers) are kept in `stats.investments`, shown in the summary and not taken off the day profit. `spending` now only holds running costs (machine repairs).
- Market share: your sales / (your sales + bot shops in open zones).
- The beach fence blocks the walking grid except at the gate (thin colliders used to be ignored by the grid).
- The browser stamps every event with its day. An event of the previous day that arrives after "next_day" (for example an autosave sent at 21:00 while the new day loads) is still applied but does not move the clock; before, it could set the new morning to 21:00 and end the new day at its first tick.

## v12 changes
- Accounts: e-mail (stored lower case, unique) and a password of at least 8 characters, stored as a PBKDF2-SHA256 hash with a random salt. No e-mail confirmation and no password reset (no mail service).
- A login is kept for 30 days through a random token in the browser's local storage; the server keeps only its hash.
- Every save belongs to one account. Saves from before v12 go to the first account created on that database.
- The deployed game needs a persistent disk (`NCT_DB_PATH`), otherwise accounts and saves are lost at every deploy.

## v13 changes
- Manager plans: sold-out customers count half; a plan is at most 1.5x the shop's best day ever (per product, at least the minimum of 8).
- Managers scale the whole plan down when the cash is short, so they always buy complete portions. When several managers buy together (07:00 or "Accept all"), each gets a share of the cash in proportion to the cost of his plan.
- Waiting customers (-3) and manager-served customers (+1) change the reputation by at most +-15 per day together, net. Other reputation changes (orders, sold-out, cleaning) keep their own rules.
- The cost estimate in the buy pop-up is what the managers paid this morning, or their current proposal if they have not bought yet. It is a warning only.
- Waves below 3 stars: only the wave factor's share of beach visitors (for example 40 % on a 1-star day) considers the Surf Shack that day. Waves above 3 stars still raise what people pay, as before.

## v14 changes
- The walking grid treats every collider up to 20 m as an obstacle; the sea and the beach fence keep their own rules.
- Render quality: pixel ratio at most 1.25, PCF shadows, 60 frames per second at most (30 when idle). The sun angle is rounded to 0.5° and the shadow centre to 8 m steps.
- The browser gets the config and the lighting table once per Streamlit session; a fresh browser view without them asks with the event `need_static`.
- The view's `history` holds only the fields of the summary table (day, revenue, tips, profit, served, lost, reputation, money, competitor revenue and served).
- A sold-out product found at "Accept" is handled like one found at the counter (take the rest or leave, sold-out reputation loss), never as an error.
- The legal notice names Maximilian Kienzle as contact; it is a student project notice, not reviewed by a lawyer.

## v15 changes
- Every customer of every owned shop counts in one daily reputation budget of +-15 net: served (+2, +1 fast when you serve yourself), partly served (-1 at the counter, no plus at the handover), sold out (-1 home, -2 to a competitor), waited too long (-3), broken machine (-2), wrong order (-4), turned away (-1), cancelled (-3). Cleaning (-15 per dirty shop) stays outside the budget.
- A manager's happy customer counts like the player's (+2) but never gets the fast bonus.
- "What you had" in the summary chart is sold + portions left before the overnight spoilage, summed over your shops. For products sold from a front (machines, shelves, display) only the front counts.
- Game over "stuck" is checked at the end of the day with the cheapest wholesale item that one of your shops can use (one piece of it already makes a sellable portion).
- The SnackBots explanation (P46) is shown once per browser (kept in the browser's local storage).
- The headless simulation cleans after closing like a real player.

## v16 changes
- Overlapping order bubbles are accepted: a fixed height above every customer reads better than bubbles that move up and build a tower in a long queue. The drawing order (first in line on top) keeps the next order readable.
