# Game logic: how every feature works (v15)

This document explains the rules of Nova Campus Tycoon feature by feature, as they are implemented in v15. It is written so that a reader who never opens the code knows what the game does, why, and where the rule lives. All numbers come from `config.py` (money is in cents there; this document shows euros). The tests that prove each rule are listed in `docs/testing.md`.

Related documents:
- `docs/architecture.md`: how the program is built (Python rules, browser rendering, storage, hosting).
- `docs/product-brief-v2.md`: the original product decisions and the design principles.
- `specs/`: one task spec per version, with the reasons for every change.

## Contents
1. The goal and the game loop
2. Time and the day phases
3. Planning, the wholesaler and stock
4. Prices and how students decide (the utility model)
5. Serving customers
6. Reputation
7. Money, profit and the daily summary
8. Managers
9. The monopoly race: buying shops, victory and game over
10. The nine shops and their mechanics
11. The beach zone and the weather
12. Cleaning
13. Upgrades
14. Easter eggs: Jep and the casino
15. Accounts, saving and continuing
16. Guidance: objectives, markers and pop-ups

---

## 1. The goal and the game loop

The player owns one café on the Nova SBE campus (Carcavelos) and wants a **monopoly**: own all nine shops of the campus and the beach, each run by a manager. Every game day follows the same loop:

1. **05:00 Plan** the day at the planning board of the shop you run yourself (what and how much to sell).
2. **Shop** at the wholesaler: take the products from the stands, pay at the checkout.
3. **Stock** the goods in your shop and **set prices** at the counter.
4. **08:00 to 20:00 Sell**: students queue, you accept orders, prepare them at the stations and hand them over.
5. **20:00 Close and clean**, then read the **daily summary**.
6. **Evening**: buy upgrades, hire a manager, buy the next shop, start the next day.

You win when all nine shops are yours and each has a manager. You lose when your cash is €0 or less at the end of a day, or when you are stuck (no stock, nothing to sell and too little money to buy anything, see section 9).

## 2. Time and the day phases

Rules: `timeclock.py`, `config.py["time"]`. Tests: `tests/test_time.py`.

| Time | What happens |
|---|---|
| 05:00 | Day starts (dark, street lamps on). Morning pop-up and planning board. |
| 07:00 | Managers buy their supplies if you did not confirm their proposal earlier. From now on you may open early. |
| 08:00 | Shops open (if not opened earlier). Students start buying. |
| 19:45 | Last customers: no new customers join a queue. |
| 20:00 | Shops close; waiting customers leave, an unfinished order is cancelled. Cleaning starts. |
| 21:00 | Day ends: spoilage, statistics, summary, game over check. |

- **Speed:** at 1x one game hour lasts one real minute. The player can switch to 2x, 4x or 8x; the browser runs the clock (`t += dt * speed / 60`), Python's tested rule is `timeclock.advance`.
- **Ticks:** the browser reports fixed times (07:00, 08:00, 09:00, ... 21:00) to Python as `tick` events. Python opens and closes shops, lets managers buy, runs shop mechanics (machines that break, ice cream that melts) and ends the day on these ticks.
- **Phases:** a table of phases (night, morning, lectures, lunch, afternoon, evening) sets how many students are on campus and how likely they are to buy.
- **Lighting:** `timeclock.lighting_at` interpolates sky colour, sun angle and lamps between keyframes (dawn, sunrise, daylight, sunset, dusk). Python sends a table sampled every 10 game minutes; the browser blends between the samples. The Praia Bar opens when the sunset phase starts.
- **⏩ Start the day:** after shopping and pricing you may jump to 08:00 instead of waiting.

## 3. Planning, the wholesaler and stock

Rules: `logic.py` (`_ev_confirm_plan`, `_ev_set_cart_item`, `_ev_pay`, `_ev_stock_goods`, `shopping_list`), `config.py["wholesale_items"]`, `config.py["products"]`. Tests: `tests/test_economy.py`, `tests/test_v9.py`, `tests/test_v10.py`.

- **Products and items.** A product is what a customer buys (coffee, pastel de nata, poke bowl). An item is what you buy at the wholesaler (coffee beans, nata, rice). Every product lists the items it uses (`uses`), for example one coffee uses 1 unit of beans.
- **Planning board.** You choose how many portions of each product you want to sell today. The game turns the plan into a shopping list: for every item the number of packs needed (`shopping_list`), taking the stock you still have into account.
- **Wholesaler.** One stand per item. At a stand you choose how many packs go into the cart (the amount starts at 0; "Take the list amount" fills in the shopping list amount). At the checkout you pay; the goods go into your bag. The shopping list is only a guide: you can buy more or less.
- **Stocking.** In your shop you put the bag into the storage. Each pack becomes a batch with an age.
- **Shelf life.** Every item has `shelf_days` (beans keep forever, oranges 3 days, nata 1 day). At the end of each day every batch gets one day older; batches that reach their shelf life spoil and their value appears as "spoiled goods" in the summary.
- **Portions.** The number of portions a shop can still sell is the minimum over the product's items of (units in stock / units per portion). Products sold from a front (vending machine, shelf, display) only count what is in the front.
- **Oldest first.** Selling always uses the oldest batch first.

## 4. Prices and how students decide (the utility model)

Rules: `students.py`, `logic._decide`, `logic.shop_factor`. Tests: `tests/test_students.py`, `tests/test_v7_model.py`, `tests/test_v5.py`.

**The pool.** 40 students live on the campus (20 extra beach visitors once the beach is open). Every morning each student gets a budget (€28 campus, €60 beach), a patience (30 to 60 game minutes), a walking speed and, for every product of every shop, a random **utility**: how much the product is worth to this student today (€0.30 to €3.00). The random numbers come from a generator seeded with the game seed, the day and the student, so a day is reproducible.

**The schedule.** At the start of each day Python creates the day plan (`make_schedule`): who arrives and leaves when, and at which times each student thinks about buying something (every 20 to 45 minutes). The phase table sets how many students are on campus at each time (crowded at lunch, quiet during lectures).

**A decision.** When a student thinks about buying (`decide` event), Python checks every shop of the student's zone that is open now:
- **Value of a product** at a shop = shop factor x utility - price.
- **Best bundle per shop:** the set of at most three of the shop's products with the highest total value, within the budget, only products with a positive value and not sold out.
- **Choice:** the shop with the highest bundle value wins; if no bundle has a positive value, the student buys nothing and keeps walking.

**The shop factor** (`shop_factor`) is how attractive a shop is:
- base factor of the shop (1.0 for most shops),
- plus the bonus of every upgrade bought there (+0.15, +0.20, +0.25),
- times the **reputation factor** for shops you own (0.7 at reputation 0 to 1.3 at 100),
- times a mechanic factor (good waves at the Surf Shack, heat at the Gelado Kiosk, lunch rush at the Mensa).

So a high price lowers the value of a product for everybody, a good reputation and upgrades raise it. Shops you do not own keep their own fixed prices; they compete through the same formula.

**Calm sea (v13).** On a calm day fewer people go surfing: only the wave factor's share of the beach visitors (40 % on a 1-star day) considers the Surf Shack at all, decided once per student and day.

## 5. Serving customers

Rules: `logic.py` (`_ev_join_queue`, `_ev_at_counter`, `_counter_check`, `_ev_accept`, `_ev_prepare`, `_ev_handover`, `_ev_patience_expired`, `_ev_auto_serve`), `students.py` (state machine). Tests: `tests/test_sales.py`, `tests/test_v4.py`, `tests/test_v14_sold_out_orders.py`, `tests/test_v15.py`.

**Student states** (`students.transition`): wandering, walking to a shop, queuing, being served, served, leaving. Python rejects any event that does not fit the current state, so the browser cannot cheat.

**In a shop you run yourself:**
1. The student walks to the shop and joins the queue (at most `max_queue`, 3 to 8 depending on the shop; a full queue sends him on).
2. **At the counter** Python checks whether every wanted product can still be made. If something sold out, the student decides again without it: he keeps the rest of the order, or goes to another shop, or goes home. Either way the sold-out product costs reputation (section 6).
3. **Order pop-up (P09):** you accept or turn him away. If a product sold out while he waited (for example the last croissant went into the order before him), the pop-up is not shown with it; the student shows it as sold out instead (v14).
4. **Prepare** each product at its station (coffee machine, juice press, display case ...). Each takes some game minutes.
5. **Hand over** the tray. The money is credited only now. The order is checked:
   - complete and correct: happy customer, reputation plus, tip (if the reputation is high enough),
   - complete, but something he wanted was sold out at the counter: **partly happy customer** (v15), no reputation plus, shown separately in the summary,
   - wrong or incomplete: wrong order, reputation minus (he still pays for what he got).
6. **Patience:** while queuing, each customer's patience runs down (longer at a good reputation). At 0 he leaves unhappy (reputation minus) and decides again without your shop.
7. You can throw away extra products from the tray or cancel an order (reputation minus).

**In a shop with a manager or a bot owner** the order is served automatically after the preparation time (`auto_serve`). The same reputation rules apply to your managed shops (section 6).

**Self-service shops:** at Mercado & Go customers take products from the shelves and you scan them at the register (`checkout`); at SnackBots they buy from the machines (section 10).

## 6. Reputation

Rules: `logic._customer_reputation`, `logic._change_reputation`, `logic._sold_out_penalty`, `config.py["reputation"]`. Tests: `tests/test_v4.py`, `tests/test_v13_bug_fixes.py`, `tests/test_v15.py`.

Reputation is a number from 0 to 100 (start 50). It is shared by all your shops.

**What it brings** (applied to the next customers and the next day):
- Demand: the reputation factor scales the shop factor of your shops from 0.7 (reputation 0) to 1.3 (reputation 100).
- Patience: customers wait 0.75 to 1.35 times as long.
- Tips: from reputation 60 happy customers tip 5 %, from 75 10 %, from 90 15 % of the bill.

**One rule for every customer (v15).** Every customer of every shop you own changes the reputation, whether you serve him yourself or your manager does:

| Customer | Change |
|---|---|
| Served completely and correctly | +2 (+1 more if you served him yourself within 12 game minutes) |
| Partly served (something he wanted was sold out, he took the rest) | -1 at the counter, no plus at the handover |
| Left because everything he wanted was sold out | -1 (went home) or -2 (went to a competitor) |
| Waited too long and left | -3 |
| Wanted to buy at a broken vending machine | -2 |
| Wrong order | -4 |
| Turned away | -1 |
| Order cancelled | -3 |

**The daily budget.** All customer changes of one day share one budget of **+-15 net**: a gain first makes up for the day's losses and the other way round. So the reputation follows the balance of happy and unhappy customers, but one day cannot crash it to 0 or push it to 100.

Why: before v15, sold-out losses had their own -15 cap while the gains of managed shops were capped at +15. A large business with many managed shops (where some products always sell out) could therefore only lose reputation and drifted towards 0. In four simulated campaigns with the v15 rule the reputation never fell below 20 and changed by at most 15 per day.

**Outside the budget:** a shop you had to clean and left dirty costs -15 (per shop) at the end of the day.

**Shown to the player:** every change appears as a small toast with its reason, and the daily summary lists today's reputation changes by reason (for example "+27 served customers, -3 waited too long, -26 sold out").

## 7. Money, profit and the daily summary

Rules: `logic._end_day`, `logic._sell`. Tests: `tests/test_sales.py::test_summary_numbers_add_up`, `tests/test_v11.py`.

- **Start money:** €50.
- **Income:** sales and tips (credited at the handover; vending machine sales go into the machine's cash box first, see SnackBots).
- **Costs of the day:** purchases at the wholesaler (yours and your managers'), repairs, money spent at Jep and in the casino bar, casino wins and losses.
- **Profit of the day** = sales + tips - purchases - repairs - Jep + casino - bar. **Investments** (shops, upgrades, managers) are paid from the cash but shown separately, not as part of the day's profit.
- **The daily summary (P16)** has five tabs:
  - *Today:* money (sales, tips, purchases, profit, spoiled goods, cash tonight), customers (served, partly happy, lost, of them sold out, wrong orders, thrown away, reputation, market share), today's reputation changes by reason, and the chart **"Sold vs. what you had"**: per product a grey bar for what you had (plan, leftovers from yesterday and extra purchases), a green bar for what you sold, and a dashed line for the plan. You can sell more than you planned, but never more than you had.
  - *Stock:* per shop and item the opening stock, goods in, used, spoiled and closing stock.
  - *Competitors:* every shop you do not own yet with its prices and sales.
  - *Last days:* revenue, profit, customers and reputation of the last seven days.
  - *Charts:* the same over time.
- **Market share** = your revenue / (your revenue + the revenue of the shops you do not own) in the open zones.

## 8. Managers

Rules: `logic.manager_proposal`, `logic._manager_buys`, `logic._managers_buy_all`, `logic._affordable_plan`, `logic.manager_cost_estimate`, `config.py["manager"]`. Tests: `tests/test_progression.py`, `tests/test_v8.py`, `tests/test_v13_bug_fixes.py`.

- **Hiring:** each shop has its own manager price (€100 to €400). A hired manager starts the next morning. From then on the shop runs without you: he plans, buys, sets prices, serves, cleans.
- **The proposal (05:00):** for every product the manager plans yesterday's sales plus half of the customers who found it sold out, times a buffer (1.2, or 1.5 if it sold out), at least 8 portions, and at most 1.5 times the best day this shop ever had (v13: so one bad day cannot blow up the plan). The Surf Shack manager also plans with today's waves. Prices: +€0.10 for products that sold out, -€0.10 for products nobody bought (never below cost + €0.10).
- **Buying:** you can accept the proposals (one by one or "Accept all"), change them, or let the managers buy on their own at 07:00. The managers then walk to the wholesaler, buy, come back and stock the shop.
- **Short of cash (v13):** if the money is not enough for every plan, each manager gets a share of the cash in proportion to his plan and scales his whole plan down, so he still buys complete portions (rice and salmon for a poke bowl, not just rice). A toast says how much of the plan he could buy; the "Accept all" pop-up warns before.
- **Buying a shop (v13):** the buy pop-up shows what your managers will roughly need for tomorrow's supplies and warns if the purchase leaves less than that.

## 9. The monopoly race: buying shops, victory and game over

Rules: `logic.next_target`, `logic.buy_blocker`, `logic._ev_buy_shop`, `logic.is_stuck`, `logic._end_day`. Tests: `tests/test_v7_model.py`, `tests/test_v7_victory.py`, `tests/test_v6.py`, `tests/test_v15.py`.

- **Buying order:** the shops are bought one after another in a fixed order (table in section 10). The HUD bar "Monopoly 3/9" shows the progress.
- **Condition:** the next shop is for sale only when every shop you own has a manager. Walking to its door shows its price and its sales (P17). This pop-up appears only when you walk up to the door from outside, not when you come out of the shop (v15).
- **After buying:** the shop becomes yours the next morning; you run it yourself until you hire its manager. The beach zone opens once every campus shop is yours.
- **Victory:** all nine shops are yours and each has a manager. You can keep playing without a goal (open mode).
- **Game over, bankrupt:** your cash is €0.00 or less at the end of a day.
- **Game over, stuck (v15):** at the end of a day you have no portion left in any shop (storage, shelves, machines), nothing in the bag or the cart, no cash in a vending machine or in your pocket, and less money than the cheapest wholesale item your shops can use. Then no day could bring money again, so the game ends instead of leaving you in an endless loop.
- **Balance target:** the first shop is bought around day 6 and each further shop takes about 4 days (`config.py["balance_target"]`, checked by `tests/test_v7_victory.py` with the headless simulation). In the v15 test campaigns the monopoly was reached on days 34 to 35.

## 10. The nine shops and their mechanics

Rules: `mechanics.py` (one class per mechanic), `config.py["shops"]`. Tests: `tests/test_v7_snackbots_mercado.py`, `tests/test_v7_bowlbar_mensa.py`, `tests/test_v7_beach.py`, `tests/test_v10.py`, `tests/test_v11.py`.

Every shop has a **mechanic**: a small class that changes how the shop sells. All mechanics share one interface (`Mechanic`: availability, price, demand factor, objective text, start and end of day, ...), so `logic.py` never needs `if shop == ...` branches.

| # | Shop | Zone | Price | Manager | Products | Mechanic |
|---|---|---|---|---|---|---|
| 1 | Your Café | campus | start | €100 | coffee, orange juice, pastel de nata | counter: prepare at stations, hand over |
| 2 | Café da Esquina | campus | €300 | €120 | coffee, tea, croissant | counter |
| 3 | SnackBots | campus | €600 | €120 | water, Coke Zero, protein bar | vending machines |
| 4 | Mercado & Go | campus | €1,200 | €200 | sandwich, iced tea, apple | shelves and checkout |
| 5 | Bowl Bar | campus | €1,700 | €250 | poke bowl, açaí bowl, smoothie | assembly from ingredients |
| 6 | Nova Mensa | campus | €2,200 | €300 | chicken & fries, pizza, pudding | lunch rush 11:30 to 14:30 |
| 7 | Surf Shack | beach | €3,000 | €350 | board rental, wetsuit rental, surf class | rental (gear comes back), waves |
| 8 | Praia Bar | beach | €3,600 | €400 | beer, sangria, burger | opens at sunset, happy hour |
| 9 | Gelado Kiosk | beach | €4,300 | €400 | ice cream scoop, lolly, iced coffee | melting display, temperature |

**Counter (Your Café, Café da Esquina).** Customers order at the counter, you prepare each product at its station and hand over the tray (section 5).

**SnackBots (vending machines).** There is no counter. Students buy from **three snack machines** spread over the campus; a customer walks to the machine with the most of what he wants and queues there. Each machine has a stock per product (capacity per product) and a cash box.
- You fill your bag at the office storage, walk to each machine and refill it (press E).
- Every sale goes into the machine's cash box. You take the cash out at the machine; it is then in your pocket, **not in your account**, until you bring it to the board in the SnackBots office.
- Machines can break down (a chance per game hour). A broken machine sells nothing; a customer who wanted to buy there leaves (-2 reputation, toast "the machine is broken", v15). You repair it for a fee.
- Guidance (v15): the first time you run SnackBots a pop-up (P46) explains these steps. Every machine that needs you has an orange ring and a tag with its stock and cash; a broken one says "broken". The cash you carry is shown in a pulsing line under your money and in the objective.
- The SnackBots manager fills all machines in the morning, goes round them during the day (repair, refill, cash) and brings the cash in the evening.

**Mercado & Go (shelves).** The shelves hold a limited number of each product. You move goods from the storage to the shelves (any time during the day); customers take what is on the shelves and you scan their shopping at the register. An empty shelf is a sold-out product.

**Bowl Bar (assembly).** Each bowl is put together from two ingredients in a pop-up; a wrong combination is a wrong order.

**Nova Mensa (lunch rush).** Open only 11:30 to 14:30, with a rush (higher demand) from 12:00 to 14:00 and a queue of up to 8.

**Surf Shack (rental).** Boards and wetsuits are bought once and come back after each rental (wetsuits have to dry first); their cost is spread over 40 rentals. Instructors are booked per day. Demand follows the daily wave rating (section 11).

**Praia Bar (sunset bar).** Opens when the sunset lighting phase starts (17:30) and closes at 20:00. You can set a happy hour with a discount at the register.

**Gelado Kiosk (melting).** Ice cream waits in the freezer; what is in the display melts over the day. Demand follows the temperature.

## 11. The beach zone and the weather

Rules: `logic.weather_for`, `mechanics.weather_factor`, `config.py["weather"]`, `config.py["beach_visitors"]`. Tests: `tests/test_v7_beach.py`, `tests/test_v13_bug_fixes.py`.

- The beach opens when every campus shop is yours (a gate south of the campus).
- 20 beach visitors with more money (€60) and their own day: a quiet morning, a busy midday and a crowd at sunset.
- **Weather, new every day (seeded):** waves 1 to 5 stars and a temperature of 16 to 34 °C. A forecast board shows both.
- **Waves (Surf Shack):** factor 0.4 / 0.7 / 1.0 / 1.3 / 1.6 for 1 to 5 stars. Below 1 it is the share of visitors who consider surfing at all; above 1 it raises what people are willing to pay.
- **Temperature (Gelado Kiosk):** demand factor from 0.5 (coldest) to 1.6 (hottest).

## 12. Cleaning

Rules: `logic._ev_clean`, `logic._end_day`, `config.py["cleaning_spots"]`. Tests: `tests/test_v10.py`, `tests/test_v11.py`.

After closing, the shop you ran yourself has to be cleaned: each shop has its own spots (counter, coffee machine, tables, floor ...), each takes a few game minutes. The marker leads you from spot to spot. A shop left dirty costs -15 reputation at the end of the day. Managers clean their own shops. Vending machines need no cleaning.

## 13. Upgrades

Rules: `logic.upgrade_catalogue`, `logic._ev_buy_upgrade`. Tests: `tests/test_progression.py`, `tests/test_v10.py`.

Every shop has three themed upgrades at its upgrade board (for the café: better coffee machine €30, seating & decor €60, sign & branding €100). Each raises that shop's factor (+0.15, +0.20, +0.25) and is visible in the 3D world.

## 14. Easter eggs: Jep and the casino

Rules: `easter_eggs.py`, `logic._ev_buy_from_jep`, `_ev_roulette`, `_ev_slot`, `_ev_buy_drink`. Tests: `tests/test_v8.py`, `tests/test_v9.py`. Details for graders: `specs/v8-fixes-and-easter-eggs.md`, `specs/v9-fixes-and-casino.md`.

- **Jep** turns up somewhere on the campus every morning (a seeded spot) and sells a few odd things; his effects are visual and temporary.
- **The casino** is hidden below the campus. Roulette (red/black and even/odd pay 1:1, each dozen 2:1, on 0 every bet loses), slot machines and a bar. Outcomes are decided in Python with a seeded generator. While the wheel or the reels spin, the cash shown stays at "before the spin minus the stake" until the result is shown (v15), so the HUD never gives the result away early.
- Casino wins and losses and bar spending are part of the day's profit.

## 15. Accounts, saving and continuing

Rules: `auth.py`, `db.py`, `app.py`. Tests: `tests/test_v12_accounts.py`, `tests/test_persistence.py`, `tests/test_v8_safety.py`.

- **Landing page:** create an account with e-mail and password, or log in. One account per e-mail address (case does not matter). Passwords need 8 to 128 characters and are stored only as a PBKDF2-SHA256 hash with a random salt (200,000 rounds); nobody can read them back. A login token is kept in the browser so you stay logged in.
- **Saves:** every account has its own saved games. The game is saved after every batch of actions, every 10 seconds, and when the tab is hidden or closed. SQLite runs with full sync and keeps a backup copy of the previous state, so a crash costs at most a few seconds.
- **Continue:** "Continue" on the title screen loads your last game. Customers who were in a queue start fresh on the campus.
- **Settings (P20, pause):** music and sound effects, the account you are logged in with and "Log out" (v15), "Save & quit", "New game". Leaving the browser tab pauses the game; the pause menu appears on top of any open pop-up, and the pop-up comes back after "Resume" (v15).
- **Legal notice:** the landing page footer and the title menu open the legal notice (Impressum) with the team and a disclaimer.

## 16. Guidance: objectives, markers and pop-ups

Rules: `logic.objective`, `mechanics.*.objective`, `game/js/flow.js` (`objectiveText`, `objectiveTarget`). Tests: `tests/test_v6.py`, `tests/test_v13_bug_fixes.py`.

- The HUD always shows the next objective (Python writes it from the state; a shop mechanic can replace it, for example SnackBots reminds you of the cash you carry).
- A yellow ring on the ground and an arrow next to the player point to the next place (planning board, wholesaler stand, storage, counter, cleaning spot). At SnackBots every machine that needs you gets an extra orange ring.
- Every action opens a numbered pop-up (P01 to P47). Only one pop-up is shown at a time; others wait in a queue. The "E ..." hint never covers an order bubble, and customers in a queue show their place (1, 2, 3 ...) in their order bubble, the first in line drawn on top (v15).
- The "i" next to the stock (v15) opens the full stock list of every shop (storage with best-before days, shelves, vending machines, bag, carried cash); the "i" next to the day gain opens the statistics.
