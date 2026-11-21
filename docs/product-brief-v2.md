# Nova Campus Tycoon v2: Product Brief

Status: 21.11.2026 (updated for v15). Source of truth for the product ideas since version 2. Replaces `docs/product-brief.md` wherever the two differ. Section 14 describes the v7 campus expansion and section 15 the changes of v8 to v15; newer sections win where they differ from older ones. The current rules with all numbers are described feature by feature in `docs/game-logic.md`.

## 0. How the ideas were unified

Version 2 merges four inputs: the team's game design for the daily café cycle, the sales process notes, the movement-and-time prompt, and the rules of version 1. Where they contradicted each other, this brief decides as follows:

| Topic | Conflict | Decision in v2 |
|---|---|---|
| Camera | "first-person" vs. "Third Person" | Third person everywhere, plus a fixed counter camera while the player stands behind the counter. |
| Day length | 07:30-19:30 vs. 05:00-21:00 | Game day 05:00-21:00; café open 08:00-20:00. At 1x, 1 game hour = 1 real minute. |
| Customers | arrival rate + order weights + price elasticity vs. utility model | Utility model of v1 stays (25 students, €10 budget, daily random utilities, shop factor). The phase table controls how many students are on campus. |
| Reputation | affects customer count vs. utility model unchanged | Reputation (0-100) scales the café's shop utility factor for the next day (±20 %). The utility formula itself is unchanged. |
| Payment | at the register vs. when the order is finished | Money is credited at handover, when the order is finished. No refunds needed. |
| Closing | queue still served vs. waiting customers leave | At 20:00 waiting customers leave and an unfinished order is cancelled. Then cleaning. |
| Stock | everything spoils daily vs. shelf life per item | Shelf life per item: coffee beans unlimited, oranges 3 days, pastéis de nata 1 day. |
| Competitor | price-gap rule vs. utility model | Utility model decides between the cafés. The NPC shop keeps fixed prices and fixed shop factor. |
| Progression | not in the design doc | Unchanged from v1: upgrades, manager (= employee), buying the competitor, victory and game over. |
| Data on screen | Streamlit tables vs. "only the 3D world" | The page shows only the game. Everything (menus, HUD, dialogs, statistics) is drawn inside the 3D view. |

Open points are listed in section 13.

## 1. Vision and principles

The player runs a café on a university campus and plays every day the same loop: plan, shop at the wholesaler, set prices, serve students, close and clean up. The long-term goal is the monopoly: buy every shop on the map, one after another, and put a manager into each (since v7: nine shops in two zones, see section 14).

Three principles apply to every feature:
1. **Only the 3D world.** No tables, sidebars or Streamlit widgets outside the game. Title screen, HUD, dialogs and the daily summary are part of the 3D view and share one visual style.
2. **Always guided.** Every action of the player opens a pop-up, and the HUD always shows the next objective. The player never has to guess what to do next.
3. **A living campus.** Students arrive, wander, go to lectures, crowd at lunch and react to prices, queues and the player's service.

## 2. Technical frame

- Stack stays as in the course: Python, Streamlit, SQLite, pytest, uv.
- Game rules and decisions (clock, phases, lighting schedule, students, utility, stock, serving, progression) are Python in `logic.py` (or new logic modules) and are covered by pytest. Storage stays in `db.py`.
- Three.js rendering, input, animation, HUD and pop-ups run in the browser. JavaScript only renders, animates and collects input. It does not decide game rules.
- Recommended bridge: Python decides, the browser animates. At the start of each day Python creates the day plan (student pool, utilities, schedule). The browser runs the clock and sends events at decision points (dialog confirmed, student reaches the counter, order accepted, item prepared, order handed over, phase change). Python validates each event with `logic.py`, updates the state, saves it and returns the result.
- The Streamlit page shows only the game, full window. Streamlit header, sidebar and footer are hidden.
- All balancing values live in one configuration (see section 11), never hard-coded in several places.
- A seedable random generator makes every day reproducible for tests.

## 3. World

The campus has three places, connected by walkable paths.

| Place | Run by | Purpose | Interaction points |
|---|---|---|---|
| Café | Player | Start of every day, sales | Planning board, upgrade board, storage, counter, coffee machine, juice press, display case (pastel de nata), four cleaning spots, door sign |
| Wholesaler | Game | Buying supplies | Entrance zone, one stand per item with picture sign, checkout with NPC cashier, exit |
| Competitor café | NPC (bot) | Competition for students, can be bought later | Entrance zone with info pop-up (prices, buy offer) |
| Seven more NPC shops (v7) | NPC (bot) until bought | Campus zone and beach zone, see section 14 | Entrance zone with P17, shop-specific stations |
| Campus paths | - | Walking between places | Ground marker to the next objective, entrance zones as triggers |

- Walking from the café to the wholesaler takes 30-45 real seconds.
- The competitor café lies visibly on that path, so the player sees it every day.
- Students enter and leave over different map edges, never all from one corner.
- Buildings block movement. Players and students walk on walkable areas only.

## 4. Controls and camera

| Action | Input |
|---|---|
| Walk | Arrow keys, alternatively WASD |
| Interact with object or person | E within range, or left click on it |
| Choose in a pop-up (item, quantity, price) | Mouse |
| Confirm pop-up | Enter or primary button |
| Close / cancel pop-up | Esc or secondary button |
| Show shopping list and stock (optional) | Tab |
| Rotate camera (optional) | Mouse with right button held |
| Pause menu | P or pause button |

Camera:
- Outside and in the wholesaler: third-person follow camera, about 4-5 m behind and 2-3 m above the figure, smoothed.
- Behind the café counter: fixed camera behind the player, looking over the counter to the entrance, so customers, counter and stations are visible at once. Walking away from the counter switches back to the follow camera.

Interaction:
- Every interactive object has a range of about 2 m. In range, a hint appears above it (for example "[E] Kasse benutzen") and the object gets an outline.
- Mouse clicks are checked by raycast. A click out of range shows the toast "Geh näher heran".
- While a dialog pop-up is open, walking is locked.

## 5. Time system

- At 1x speed, 1 game hour = 1 real minute.
- A game day runs from 05:00 to 21:00. The night from 21:00 to 05:00 is skipped with a fade.

| Phase | Game time | Real time at 1x | Content |
|---|---|---|---|
| 1 Morning & planning | 05:00-05:30 | 0:30 | Spawn in front of the café, day planning |
| 2 Wholesaler | 05:30-07:00 | 1:30 | Walk there, choose items, pay |
| 3 Preparation | 07:00-08:00 | 1:00 | Walk back, stock the storage, set prices |
| 4 Opening hours | 08:00-20:00 | 12:00 | Serve students |
| 5 Closing | 20:00-21:00 | 1:00 | Clean up |
| 6 Summary & night | 21:00-05:00 | skipped | Daily summary pop-up, then fade to the next morning |

Rules:
- In phases 1-3 the clock pauses while a dialog pop-up is open. During opening hours it always runs, so customers create real time pressure.
- If the player is not in the café at 08:00, the café opens anyway. Students queue in front of the counter and their patience is already running.
- From 19:45 no new customers come. At 20:00 the café closes (see 7.6).

Speed control:
- Buttons 1x, 2x, 4x, 8x next to the clock. The active speed is highlighted. Each day starts at 1x.
- The multiplier applies equally to everything time-based: clock, student movement and decisions, patience, preparation times, cleaning, the competitor's serving. At 8x a day plays exactly like at 1x, only faster. The player's own walking speed is not multiplied.
- Switching speed mid-day continues from the current game time without jumps.
- The pause button stops everything (clock, all NPCs, progress bars) at every speed. After unpausing, the previous speed continues.

## 6. Daily flow step by step

Pop-up IDs refer to the catalog in section 10.

### Step 1: Spawn and day planning (05:00)
1. The figure spawns in front of the café. P01 "Guten Morgen, Tag X" shows balance, stock (with days until spoilage) and yesterday's sales.
2. At the planning board in the café, P02 "Tagesplanung": per product the player sets how many portions he wants to sell today (plus/minus).
3. P02 calculates the shopping list: planned portions minus usable stock, converted into wholesale units, plus estimated cost.
4. Confirming saves the shopping list. T01 appears and a ground marker shows the way to the wholesaler.

### Step 2: Way to the wholesaler
1. The player walks himself. The shopping list is visible in the HUD.
2. Passing the competitor's entrance zone opens P17 "Konkurrenz" with the current NPC prices.
3. At the wholesaler's entrance zone, P03 "Großhandel betreten?" with [Betreten] and [Später].

### Step 3: Choosing items
1. Each item has its own stand with a picture sign.
2. A stand opens P04 "Ware: Name": picture, name, description, unit price, pack size, shelf life and quantity, pre-filled from the shopping list.
3. [In den Warenkorb] adds the quantity, T02. Opening the same stand again changes or removes the item.
4. If the cart exceeds the balance, P04 shows the total in red with "Nicht genug Geld".

### Step 4: Checkout
1. At the checkout the NPC cashier greets the player. P05 "Kasse Großhandel": each item with quantity, unit price and sum, plus balance before and after. Buttons [Bezahlen] and [Zurück zum Einkauf].
2. [Bezahlen] deducts the money and puts the goods into the shopping bag (the figure's inventory), T03.
3. If the money is not enough, [Bezahlen] is disabled until items are removed.
4. With unpaid items in the cart, the exit does not let the player through and shows a hint.

### Step 5: Back to the café and stocking
1. The player walks back. Entering the café with a full bag opens P06 "Waren einräumen". [Einräumen] moves everything into the café storage, T04.

### Step 6: Setting prices
1. The counter before 08:00 opens P07 "Preise festlegen": per product the selling price in steps of €0.10, cost per portion and margin. Yesterday's prices are pre-filled.
2. A hint explains the effect: higher prices lower the chance that students buy (utility model, section 8).
3. Then P08 "Laden öffnen?". [Öffnen] opens before 08:00 if the player wants; at 08:00 the café opens automatically. T05.

### Step 7: Serving customers (08:00-20:00), see section 7

### Step 8: Closing and cleaning (20:00-21:00)
1. At 19:45 T09 "Letzte Kunden"; afterwards nobody new comes.
2. At 20:00 P14 "Ladenschluss". The door sign switches to "Geschlossen". Waiting customers leave; an unfinished order is cancelled without revenue.
3. Four cleaning spots light up: wipe the counter, clean the coffee machine, clear the tables, sweep the floor. Each opens P15 "Aufräumen: Ort" with a progress bar of about 3 s, then T10.
4. When all four are done, the day is finished. At 21:00 the day also ends if cleaning is unfinished; unfinished cleaning costs reputation.

### Step 9: Daily summary and next day
1. P16 "Tagesbilanz": revenue, purchase cost, spoiled goods, profit, sold vs. planned per product, customers served and lost, reputation and market share against the competitor.
2. Goods past their shelf life spoil overnight and are shown as a loss.
3. Game over check: balance €0.00 or below means P19 "Spielende".
4. [Nächster Tag] fades out, skips the night, and the player spawns at 05:00 in front of the café.

## 7. Sales process

### 7.1 Where serving happens
- During opening hours the player moves freely.
- Students can only be served in person while the player is inside his own café.
- If the player leaves the café, no new orders are accepted, an order in progress pauses until he returns, and T12 appears. Students' patience keeps running.
- With a manager hired, the manager serves automatically with the same preparation times and the player is free.

### 7.2 Queue and thought bubbles
- Students enter the café, line up at the counter (at most 4 in the queue) and move forward when the order in front is finished.
- A thought bubble above each queuing student shows icons of the products they want (for example a coffee cup).
- Each student has a patience bar (green, yellow, red). Patience starts when the student joins the queue.
- If the queue is full, an arriving student re-decides with the utility logic (other café, later, or nothing).

### 7.3 One order at a time
1. **New order:** when a student reaches the counter, P09 "Neue Bestellung" opens with the student's picture, the ordered items and the patience bar. [Annehmen] or [Ablehnen].
2. **Reject:** the student leaves the café and re-decides with the utility logic: competitor café or no purchase.
3. **Prepare:** after accepting, the player prepares each item at its station. Every station has a fixed preparation time with a progress bar:
   - Coffee: coffee machine, P10 "Kaffee zubereiten", 5 s.
   - Orange juice: juice press, P11 "Orangensaft pressen", uses 3 oranges, 6 s.
   - Pastel de nata: display case, P12 "Pastel de Nata nehmen", 1 s.
   - Each finished item goes onto the tray (HUD bar), T06.
4. **Hand over:** clicking the student opens P13 "Bestellung übergeben": tray against order with check marks and crosses. [Übergeben] credits the sale and finishes the order, T07. The next student moves up.
5. Only one order can be in progress. While it runs, no further order can be accepted.

### 7.4 Error cases
- **Wrong item handed over:** the student is unhappy and reputation drops.
- **Patience runs out:** the student leaves without buying, T08, reputation drops slightly.
- **Sold out:** P09 shows the item greyed out. The student re-decides with the utility logic, excluding the sold-out item: another item in this café, the competitor, or nothing.

### 7.5 Reputation
- Scale 0-100, start 50. Fast and correct service raises it; wrong items, lost customers and unfinished cleaning lower it.
- The reputation at the end of a day scales the café's shop utility factor for the next day: factor × (0.8 + 0.4 × reputation / 100), which is ±20 %.

### 7.6 Closing time
- At 20:00 no new customers or orders are allowed, waiting customers leave, and an order in progress is not continued beyond closing.
- The day's revenue is recorded in the daily summary.

## 8. Students and NPCs

### 8.1 Utility model (unchanged from v1)
- Every student gets a budget of €10.00 at the start of each day.
- Every student draws a random utility for every product, new every day.
- Utility of a product = shop utility factor × product utility. Unspent money also gives utility (budget minus total spent).
- A student buys the bundle that maximizes utility within the remaining budget, at most one coffee per visit.

### 8.2 Student pool and phases
- Each day has a fixed pool of 25 students. Never more than 25 exist or are on the map at the same time.
- A student keeps budget and utilities for the whole day, also when leaving for a lecture and coming back.
- The number of students on the map follows a configurable phase table. Students arrive and leave over the map edges, so the count moves gradually towards the target.

| Game time | Real time at 1x | Phase | Students on map (start value) | Café probability |
|---|---|---|---|---|
| 05:00-07:30 | 0:00-2:30 | Night | 0 | - |
| 07:30-08:00 | 2:30-3:00 | Early morning | ~3 (wait in front of the café) | high |
| 08:00-09:00 | 3:00-4:00 | Morning rush | ~18 | high |
| 09:00-12:00 | 4:00-7:00 | Morning lectures | ~6 | low |
| 12:00-13:30 | 7:00-8:30 | Lunch break | 25 (all) | very high |
| 13:30-16:00 | 8:30-11:00 | Afternoon lectures | ~4 | low |
| 16:00-18:00 | 11:00-13:00 | Late afternoon | ~10 | medium |
| 18:00-20:00 | 13:00-15:00 | Evening | ~2 | low |
| 20:00-21:00 | 15:00-16:00 | Closed | 0 (everyone leaves) | - |

### 8.3 Student behaviour (state machine per student)
States: `off_map → arriving → wandering → deciding → walking_to_shop → queuing → being_served → wandering → leaving → off_map` (and back later the same day).
- **Deciding** uses the utility model with the remaining budget to choose the café and the order. The walk follows from that decision.
- A student can buy several times per day (for example a snack in the morning and lunch) as long as budget is left and buying still increases utility. Otherwise the student only wanders.
- Individual traits: walking speed, how often they change their mind, patience in the queue.
- Wandering means walking to random walkable points, sometimes pausing.
- Leaving for a lecture is random per student and more likely at phase changes.

### 8.4 Competitor café (NPC)
- Sells coffee, tea and croissant with fixed prices and a fixed shop utility factor, and has no stock decisions.
- Serves its own queue automatically with fixed preparation times.
- Its entrance zone opens P17 "Konkurrenz" with its prices. Once the player is allowed to buy it, P17 also shows the offer.

### 8.5 Wholesaler
- Run by the game; the cashier is an NPC with no logic beyond the checkout.
- Optional: purchase prices vary daily by ±10 %.

## 9. Products, items, upgrades and progression

### 9.1 Wholesale items

| Item | Unit | Price | Base units per unit | Shelf life | Description (in-game) |
|---|---|---|---|---|---|
| Kaffeebohnen | Packung 250 g | €4.00 | 25 portions | unlimited | "Frisch geröstete Arabica-Bohnen. Eine Packung reicht für 25 Tassen." |
| Orangen | Netz mit 6 Stück | €2.00 | 6 oranges | 3 days | "Saftige Orangen von der Algarve. Für ein Glas Saft brauchst du drei." |
| Pastel de Nata | Stück | €0.60 | 1 piece | 1 day | "Heute früh gebacken. Verdirbt über Nacht - kauf nur, was du verkaufst." |

Storage counts base units with their age, so spoilage per batch is exact.

### 9.2 Café products

| Product | Uses | Station | Prep time | Cost per portion | Start price | Description (in-game) |
|---|---|---|---|---|---|---|
| Kaffee (Bica) | 1 portion of beans | coffee machine | 5 s | €0.16 | €0.90 | "Ein kräftiger portugiesischer Espresso." |
| Orangensaft (0,25 l) | 3 oranges | juice press | 6 s | €1.00 | €2.50 | "Frisch gepresst, ohne Zucker." |
| Pastel de Nata | 1 pastel | display case | 1 s | €0.60 | €1.30 | "Knuspriger Blätterteig mit Puddingfüllung, mit Zimt." |

Each item and product needs a picture (for example `img/kaffeebohnen.png`), used in pop-ups and thought bubbles.

### 9.3 Upgrades, manager and acquisition (v1 rules; extended to nine shops in section 14)
- At the upgrade board in the café, P18 "Ausbau & Personal" offers three one-time upgrades that raise the shop utility factor (+0.15 for €60, +0.20 for €120, +0.25 for €200) and hiring a manager for €200.
- Buying the competitor (€500) requires a manager in the player's café and is offered in P17.
- After the purchase the player controls the competitor's prices, stock and upgrades; the wholesaler then also sells tea and croissants. Without a manager there, the player serves it in person with the same sales process.
- Victory: the player owns both cafés and both have a manager. Game over: balance €0.00 or below at the end of a day. Both open P19 "Spielende".

## 10. Pop-up system and catalog

### 10.1 Rules
- **Dialog pop-up (modal):** for every decision. Locks walking. Closes with the primary button, the secondary button or Esc.
- **Toast:** feedback after an action or an event. Does not lock anything. Closes after 2-3 s. At most three stacked at the bottom center.
- At most one dialog is open; further dialogs wait in a queue.
- One template for all dialogs: title (place and action), picture, 1-3 short sentences of description, values (price, stock, quantity stepper, subtotal), one green primary button and one secondary button.
- Entrance zones open a small dialog instead of a toast, so walking past does not spam windows.
- Texts, pictures and prices come from the product data, not from the pop-up.
- In-game language: English (since v3). Money format in the game: "€34.50".

### 10.2 Dialog pop-ups

| ID | Title | Trigger | Content | Buttons | Result |
|---|---|---|---|---|---|
| P00 | Nova Campus Tycoon | Game start | Title screen in the 3D campus | [Neues Spiel] [Fortsetzen] | Day 1 or saved game |
| P01 | Guten Morgen, Tag X | Spawn at 05:00 | Balance, stock with shelf life, yesterday's sales | [Los geht's] | Player can walk |
| P02 | Tagesplanung | Planning board | Planned portions per product, shopping list, cost | [Einkaufszettel speichern] [Abbrechen] | T01, ground marker |
| P03 | Großhandel betreten? | Wholesaler entrance zone | Short text, shopping list | [Betreten] [Später] | Player inside |
| P04 | Ware: Name | Item stand | Picture, description, price, unit, shelf life, quantity, subtotal | [In den Warenkorb] [Abbrechen] | T02 |
| P05 | Kasse Großhandel | Wholesaler checkout | Cart list, total, balance before/after | [Bezahlen] [Zurück zum Einkauf] | T03, goods in bag |
| P06 | Waren einräumen | Entering the café with goods | Content of the bag | [Einräumen] | T04, storage updated |
| P07 | Preise festlegen | Counter before 08:00 | Price, cost per portion, margin per product | [Preise übernehmen] [Abbrechen] | P08 |
| P08 | Laden öffnen? | After P07 or door sign | Time, hint about waiting students | [Öffnen] [Noch nicht] | T05 |
| P09 | Neue Bestellung | Student reaches the counter | Student picture, items (sold out greyed), patience | [Annehmen] [Ablehnen] | Order in progress or student re-decides |
| P10 | Kaffee zubereiten | Coffee machine | Picture, steps, progress bar | [Starten] [Abbrechen] | T06, coffee on tray |
| P11 | Orangensaft pressen | Juice press | Picture, oranges used, progress bar | [Pressen] [Abbrechen] | T06, juice on tray |
| P12 | Pastel de Nata nehmen | Display case | Picture, stock | [Nehmen] [Abbrechen] | T06, pastel on tray |
| P13 | Bestellung übergeben | Click on the student | Order against tray with check marks | [Übergeben] [Abbrechen] | T07, money credited, student leaves |
| P14 | Ladenschluss | Clock reaches 20:00 | Hint, list of cleaning spots | [Aufräumen] | Cleaning spots light up |
| P15 | Aufräumen: Ort | Cleaning spot | Picture, progress bar | [Starten] | T10 |
| P16 | Tagesbilanz | All cleaning done or 21:00 | Revenue, costs, spoilage, profit, plan vs. sales, customers, reputation, market share | [Nächster Tag] | Fade, P01 |
| P17 | Konkurrenz | Competitor entrance zone | NPC prices; buy offer when allowed | [OK] / [Café kaufen] | Info or acquisition |
| P18 | Ausbau & Personal | Upgrade board | Upgrades, manager, shop factor | [Kaufen] [Schließen] | Upgrade or manager |
| P19 | Spielende | Victory or game over | Result, days played, total profit | [Neues Spiel] | P00 |
| P20 | Pause | Pause button or P | Speed, save state | [Weiter] [Speichern & beenden] | Game continues or P00 |
| P21 | Start a new game? | "New game" with a running save | Warning that the save is replaced | [New game] [Cancel] | P00 or back |
| P22 | Cancel this order? | Cancel button during an order | Reputation cost | [Cancel order] [Keep it] | Order cancelled |
| P23 | Manager's proposal | Morning, shop with a working manager | Plan, prices, cost | [Confirm] [Change] | Manager buys |
| P24 | Statistics | Click on the day gain | Charts and day figures | [Close] | - |
| P25-P35 | v7 pop-ups | see section 14.7 | | | |

### 10.3 Toasts

| ID | Text | Trigger |
|---|---|---|
| T01 | "Einkaufszettel erstellt - ab zum Großhandel!" | P02 confirmed |
| T02 | "3x Kaffeebohnen im Warenkorb" | P04 confirmed |
| T03 | "Einkauf bezahlt: 34,50 €" | P05 confirmed |
| T04 | "Waren eingeräumt" | P06 confirmed |
| T05 | "Geöffnet - die ersten Kunden kommen" | Café opened |
| T06 | "Kaffee fertig" | Item prepared |
| T07 | "Kunde zufrieden: +2,20 €" | P13 confirmed |
| T08 | "Kunde ist gegangen" | Patience ran out |
| T09 | "Letzte Kunden" | 19:45 |
| T10 | "Erledigt" | Cleaning spot finished |
| T11 | "Geh näher heran" | Click out of range |
| T12 | "Bestellung pausiert - du hast das Café verlassen" | Player leaves the café with an order in progress |
| T13-T20 | v7 toasts | see section 14.7 |

## 11. HUD and look

HUD (overlay inside the 3D view, same style as the pop-ups):
- Top right: digital clock (HH:MM), day, speed buttons 1x/2x/4x/8x, pause button, balance.
- Top center: current objective, for example "Nächstes Ziel: Zum Großhandel".
- Top left: reputation.
- Top left, below the reputation (v7): monopoly progress bar "Monopoly 3/9" (shops owned with a hired manager out of all shops). Clicking it opens P35.
- Bottom: tray during opening hours; toasts above it.
- Tab: shopping list and stock.

Day and night lighting (configurable times, smooth interpolation):
- 05:00-07:00 dawn: dark blue turning orange, street lamps on.
- 07:00-08:30 sunrise: warm orange light, low sun, long shadows.
- 08:30-17:30 daylight: bright neutral light, the sun moves and shadows change direction and length.
- 17:30-19:30 sunset: warm orange/pink light, long shadows.
- 19:30-21:00 dusk: dark blue sky, street lamps and café lights on.
- Sky colour, sun direction, light intensity and colour always change together.

Look:
- Stylized low-poly 3D: café with interior and stations, wholesaler with stands and cashier, competitor café, paths, trees, lamps.
- Students: roughly human proportions, varied clothing and hair colours, small shadow, walking animation whose speed follows the game speed.
- Interactive objects show an outline and a hint in range.
- Performance: smooth with all 25 students on the map at 8x speed.

## 12. Configuration and state

All balancing values live in one configuration. Starting values:

```json
{
  "config": {
    "realSecondsPerGameHourAt1x": 60,
    "speeds": [1, 2, 4, 8],
    "dayStartHour": 5,
    "openHour": 8,
    "lastCustomerHour": 19.75,
    "closeHour": 20,
    "summaryHour": 21,
    "startMoney": 50.00,
    "studentPoolSize": 25,
    "studentBudget": 10.00,
    "maxQueue": 4,
    "patienceSec": [30, 60],
    "reputationStart": 50,
    "reputationFactorRange": [0.8, 1.2],
    "pauseClockInDialogsBeforeOpening": true,
    "managerCost": 200.00,
    "acquisitionCost": 500.00
  }
}
```

Wholesale items, products, upgrades, the phase table and the lighting schedule are part of the same configuration (values as in sections 5, 8, 9 and 11).

Saved state (SQLite) includes at least: day, game time, phase, money, reputation, stock with batch age, plan, cart, bag, prices, tray, order in progress, upgrades, manager per café, competitor owner, the day's student pool (budgets, utilities, positions) and daily statistics. The game saves at every confirmed dialog, every finished order and every phase change. "Fortsetzen" resumes at the last save.

## 13. Open decisions (defaults apply until the team decides)

- [ ] Utility range and competitor prices must be rebalanced to the lower v2 prices. Default: utilities €0.20-2.00, competitor coffee €1.00, tea €1.20, croissant €1.50, competitor factor 1.2.
- [ ] Start money €50 vs. manager €200 and acquisition €500: check after the first test game.
- [ ] Pop-up density: should tiny actions (taking a pastel) be a toast instead of a dialog? Default: dialog, as in the catalog.
- [ ] Reputation effect on the shop factor (±20 %): keep or drop.
- [ ] Daily price fluctuation at the wholesaler (±10 %): default off.

- [x] v7 time target: first shop around day 10, then about 5 days per shop (decided 11.11.2026).
- [x] v7: all campus NPC shops trade from day 1 (decided 11.11.2026).

## 14. Version 7: campus monopoly

### 14.1 Goal
The one-competitor game becomes a campus-wide monopoly race. Every new shop is an NPC competitor that the player can buy, and every shop adds one new gameplay mechanic, not only new products. The campus zone comes first; the beach zone towards Carcavelos beach unlocks once every campus shop is owned.

### 14.2 Shops and zones
Nine shops in unlock order. Ingredients in brackets.

| # | Shop | Zone | Products [ingredients] | Mechanic |
|---|---|---|---|---|
| 1 | Your Café | Campus | Bica [Coffee beans], Orange juice [Oranges], Pastel de nata [Pastel de nata] | Owned from the start. Unchanged. |
| 2 | Café da Esquina | Campus | Coffee [Coffee beans], Tea [Tea leaves], Croissant [Croissants] | First acquisition target. Unchanged. |
| 3 | SnackBots | Campus | Water [Water bottles], Coke Zero [Coke Zero cans], Protein bar [Protein bars] | Vending machines |
| 4 | Mercado & Go | Campus | Sandwich [Bread, Cheese], Iced tea [Iced tea cans], Apple [Apples] | Limited shelf space |
| 5 | Bowl Bar | Campus | Poke bowl [Rice, Salmon], Açaí bowl [Açaí purée], Smoothie [Fruit mix] | Assembly station |
| 6 | Nova Mensa | Campus | Chicken with fries [Chicken, Fries], Pizza slice [Frozen pizza], Pudding [Pudding cups] | Lunch rush |
| 7 | Surf Shack | Beach | Surfboard rental [Surfboards], Wetsuit rental [Wetsuits], Surf class [Surf instructor] | Rentals and waves |
| 8 | Praia Bar | Beach | Beer [Draught beer], Sangria [Red wine, Fruit mix], Burger [Burger patties] | Sunset opening, happy hour |
| 9 | Gelado Kiosk | Beach | Ice cream scoop [Ice cream], Ice lolly [Ice lollies], Iced coffee [Coffee beans, Ice cream] | Melting and temperature |

Every NPC shop sells with fixed prices and a fixed shop factor while it belongs to the bot, like Café da Esquina today. Every new shop has its own low-poly building in the current style, an entrance zone with P17, a price board, a "FOR SALE" sign while it is the next shop you may buy, and an icon on the minimap and the big map.

### 14.3 The seven new mechanics

**SnackBots (vending machines).** Three machines (one per product) and a small office of the vending company. No staff, no queue at a counter, no preparation time: a student buys at the machine instantly if it has stock. The player refills the machines from the bag (P25); a machine holds a limited number of items. Each machine can break down at random during opening hours (chance per game hour in config). A broken machine sells nothing; the player repairs it on the spot for a fee (P26) or loses its sales until it is fixed. In the office the player can hire the SnackBots manager (P27); from the next day he refills every morning and repairs breakdowns automatically (the repair fee is still paid).

**Mercado & Go (limited shelf space).** The shop has a fixed number of shelf slots (for example 60 items). Every morning the player decides in P28 how many of each product go onto the shelves; the rest stays in the storage room. Students can only buy what is on the shelves. Sandwiches are put together while stocking the shelves (one bread and one cheese each). Students pay at the register; scanning takes a short fixed time.

**Bowl Bar (assembly).** The first products with two ingredients. One assembly station opens P29, where the player chooses the ingredients for the bowl (rice, salmon, açaí purée, fruit mix). The chosen set decides what lands on the tray: rice + salmon is a poke bowl, açaí purée alone is an açaí bowl, fruit mix alone is a smoothie; any other set is a "Wrong bowl" (T20) and still uses up the ingredients. Handing over a wrong bowl counts as a wrong order (existing reputation penalty). A manager always assembles correctly.

**Nova Mensa (lunch rush).** The Mensa is only open from 11:30 to 14:30. During the lunch rush (12:00 to 14:00) many more students are on campus, the Mensa queue holds up to 8 students, preparation is fast and prices are low. Volume, not margin, makes the money. T14 announces the rush.

**Surf Shack (rentals and waves).** Surfboards and wetsuits are bought once at the wholesaler and are reusable. A rental takes one free board or wetsuit, which comes back after some game hours (T15). A returned wetsuit first dries for a while before it can be rented again (T16). A surf class needs a booked instructor (bought per day, a few classes each). Every day has a wave rating from 1 to 5 stars (seeded), shown in P30 in the morning; it multiplies the demand for all three products.

**Praia Bar (sunset and happy hour).** The bar opens when the sunset lighting phase starts (17:30, from the lighting table) and closes at 20:00 like every shop. The first hour is happy hour (T17): prices are lower by a discount the player chooses in P32, and more students want to come. Sangria shares the fruit mix with the Bowl Bar.

**Gelado Kiosk (melting and temperature).** Ice cream and ice lollies wait in the freezer (no melting). The player moves portions into the display (P33); the display melts its content after a few game hours (T18 shows the loss). Every day has a temperature (seeded, for example 16 to 34 °C), shown in P30, which scales the kiosk's demand. Iced coffee uses coffee beans and ice cream.

### 14.4 Students in two zones
- Campus: the student pool grows from 25 to 40 (configurable), so nine shops still find enough customers. The lunch phase has a higher target so the Mensa rush is real.
- Beach: a second pool of 20 beach visitors with a higher budget (€60). They only appear once the beach zone is unlocked and only walk in the beach zone. Campus students do not walk to the beach.
- A student visits one shop per decision. To keep the decision fast with 27 products, the student computes the best bundle per open shop (at most 3 products each) and picks the shop with the highest utility. This gives the same result as before for one-shop bundles, which is what the game already sells.
- Shops with opening hours (Mensa, Praia Bar) are only offered to students while open.

### 14.5 Progression, buying rule and victory
1. Start: you own Your Café; all campus NPC shops already trade as competitors.
2. Campus zone: Café da Esquina, SnackBots, Mercado & Go, Bowl Bar and Nova Mensa become buyable one after another.
3. Beach zone: unlocks (T19, P34) once you own every campus shop; then Surf Shack, Praia Bar and Gelado Kiosk become buyable in this order.
4. Victory: you own all nine shops and every shop has a hired manager. P19 as before, with "Keep playing (open mode)".

Buying rule: only the next shop in the unlock order is for sale, and only when every shop you already own has a hired manager. Hired counts (the manager may start tomorrow), so you can hire in the evening and buy the next morning. As since v6, you pay at once and the shop becomes yours the next morning; until then the bot keeps selling. You then run the new shop yourself until you hire its manager.

HUD: a monopoly progress bar shows owned shops with a hired manager out of nine. P35 lists all shops with owner, manager, price and what is needed for the next purchase.

### 14.6 Prices and balance (starting values, calibrated by the headless simulation)

Values after the calibration with the headless simulation (`uv run python simulation.py --campaign --seeds 10`: 10 of 10 games won, the last shop around day 36).
The manager of Your Café costs €100. v8 (team decision 12.11.2026): the shops are cheaper, the second shop costs €300 instead of €700.

| # | Shop | Acquisition (v8) | v7 | Manager | Simulated purchase day (median) | Target |
|---|---|---|---|---|---|---|
| 2 | Café da Esquina | €300 | €700 | €120 | 6 | 6 |
| 3 | SnackBots | €600 | €750 | €120 | 8.5 | 10 |
| 4 | Mercado & Go | €1,200 | €1,400 | €200 | 12 | 14 |
| 5 | Bowl Bar | €1,700 | €2,000 | €250 | 16.5 | 18 |
| 6 | Nova Mensa | €2,200 | €2,600 | €300 | 20.5 | 22 |
| 7 | Surf Shack | €3,000 | €3,400 | €350 | 24 | 26 |
| 8 | Praia Bar | €3,600 | €4,200 | €400 | 31 | 30 |
| 9 | Gelado Kiosk | €4,300 | €5,000 | €400 | 36 | 34 |

Other balance values of v7: the campus pool has 40 students with €28 each per day (v6: 25 with €16), the lunch phase lasts until 14:00, and the beach has 20 visitors with €60 each. Expensive beach products have their own price limit (a surf class can cost up to €60).

Balance target (team decision 11.11.2026, updated 12.11.2026 for v8): a good player buys Café da Esquina around day 6 and every further shop about 4 days after the previous one, so the campus zone is complete around day 22 and the beach around day 34. The headless simulation plays many seeds with a simple strategy (buy as soon as allowed, hire as soon as possible) and reports the day each shop was bought; prices are adjusted until the median hits the target. Wholesale items, products, start prices and all mechanic parameters live in `config.py`.

### 14.7 New pop-ups and toasts

| ID | Title | Trigger | Content | Buttons |
|---|---|---|---|---|
| P25 | Refill: machine | SnackBots machine | Items in machine and bag, capacity | [Refill] [Cancel] |
| P26 | Machine broken | Broken machine | What broke, repair fee, sales lost so far | [Repair for €X] [Later] |
| P27 | Vending company office | Office desk | Manager offer for SnackBots | [Hire] [Close] |
| P28 | Stock the shelves | Mercado shelves, morning | Shelf slots used, per product: storage and amount for the shelf | [Fill shelves] [Cancel] |
| P29 | Assemble a bowl | Bowl Bar station | Ingredient toggles, preview of the result, stock | [Assemble] [Cancel] |
| P30 | Beach forecast | Morning (beach zone unlocked) or forecast board | Temperature and wave rating with their effect on demand | [OK] |
| P31 | Rentals | Surf Shack rack | Boards and wetsuits: free, rented (back at), drying (dry at) | [Close] |
| P32 | Happy hour | Praia Bar register | Discount for the first hour | [Save] [Cancel] |
| P33 | Fill the display | Gelado freezer | Freezer stock, display content and melting time | [Fill] [Cancel] |
| P34 | Beach zone unlocked | Last campus shop bought | Short text, map of the beach | [Show me] |
| P35 | Monopoly | Click on the progress bar | All shops: owner, manager, price, next step | [Close] |

| ID | Text | Trigger |
|---|---|---|
| T13 | "Machine broken: Coke Zero" | A vending machine breaks |
| T14 | "Lunch rush at the Mensa!" | 12:00 while you own or run the Mensa |
| T15 | "1x Surfboard returned" | A rental comes back |
| T16 | "1x Wetsuit dry again" | Drying finished |
| T17 | "Happy hour at Praia Bar!" | Bar opens |
| T18 | "3 portions of ice cream melted" | Display melted |
| T19 | "Beach zone unlocked" | All campus shops owned |
| T20 | "Wrong bowl" | Assembly with a wrong set of ingredients |

### 14.8 Technical rules for v7
- Everything new is data in `config.py`: zones, shops (order, zone, products, stations, opening hours, queue size, acquisition and manager cost, mechanic type and parameters), wholesale items (which shop unlocks them) and products. `logic.py` contains no if/else chains on shop names; mechanics are looked up by their type.
- `logic.migrate()` loads v4, v5 and v6 saves: missing shops are added as bots, the old competitor statistics move to the new per-shop fields. A v6 save that had already won continues as a running game with the new goal.
- Performance stays smooth at 8x with all students of both zones on the map: static scenery is merged into a few meshes by colour, and every person is drawn with five meshes (body, two arms, two legs) that share geometry and material.
- At the wholesaler, every new shop has one aisle (P04 lists its items). With several managers, their morning proposals come as one summary (P23, "Accept all" or "One by one").

## 15. Changes from v8 to v15 (current state)

The ideas of sections 1 to 14 still hold. These versions changed or added rules; each has its own spec in `specs/`, and `docs/game-logic.md` describes the resulting rules in full.

| Version | Change of the product |
|---|---|
| v8 | Saves are crash-safe (full sync, backup of the previous state). Sound and music. Two easter eggs: Jep and the hidden casino with roulette. Every customer who leaves because of a sold-out product costs reputation. |
| v9 | One wholesaler stand per item; the casino gets a bar and slot machines. |
| v10 | Upgrades and cleaning spots per shop; the SnackBots manager fills every machine; Mercado & Go objectives; partly missing orders cost reputation. |
| v11 | Managers go round the machines, a dirty shop costs 15 reputation, investments are shown outside the day's profit, the day summary has five tabs, the big map. |
| v12 | Landing page and accounts (e-mail and password, one account per address, saves per player); the game is hosted at www.novacampustycoon.com. |
| v13 | Manager plans are capped (sold-out customers count half, at most 1.5x the best day); short cash is shared between managers who buy complete portions; the buy pop-up warns about tomorrow's manager costs; a calm sea means fewer surfers. |
| v14 | People avoid all obstacles; beach props fixed; legal notice; a product that sells out while a customer waits is shown as sold out instead of an error; lighter rendering and faster server answers. |
| v15 | No dimming flicker while the server answers; one reputation rule for every customer of every owned shop with one daily budget of +-15; partly served customers; SnackBots guidance (explanation, rings and tags on every machine, carried cash); stock overview; account and log out in the settings; game over when the player is stuck without stock and money. |

**Reputation (replaces the numbers in section 7 where they differ):** served +2 (+1 fast when you serve yourself), partly served -1, sold out -1 or -2, waited too long -3, broken machine -2, wrong order -4, turned away -1, cancelled -3; all customers of one day move the reputation by at most 15 (net). A dirty shop costs 15 more.

**Game over (extends section 9):** besides bankruptcy (cash at or below €0 at the end of a day), the game ends when the player is stuck: no stock in any shop, nothing in the bag or cart, no cash in a machine or in his pocket, and less money than the cheapest wholesale item his shops can use.
