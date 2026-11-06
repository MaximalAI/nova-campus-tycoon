# Version 2: The campus game in 3D

Source of truth: `docs/product-brief-v2.md`. Section numbers below refer to that brief.

## Why
Version 1 is a Streamlit management screen with a 3D picture on top. Version 2 turns it into a game: the player only sees the 3D campus, walks with the keyboard, is guided by pop-ups through every step of the day, and the campus feels alive because students behave like real students over a school day.

## What
1. **Only the 3D world** (brief 1, 2): full-window game, Streamlit chrome hidden, title screen, HUD, pop-ups and summary inside the 3D view.
2. **World** (brief 3): café with interior and stations, wholesaler with stands and cashier, competitor café on the way, paths, collision with buildings.
3. **Controls and camera** (brief 4): arrow keys/WASD, E or click to interact, outline and hint in range, third-person follow camera, fixed counter camera.
4. **Time system** (brief 5): 05:00-21:00, 1 game hour = 1 real minute at 1x, phases 1-6, speed 1x/2x/4x/8x, pause, clock pausing in morning dialogs.
5. **Daily flow** (brief 6): planning board and shopping list, wholesaler with cart and checkout, bag, stocking, prices, opening, closing with cleaning, daily summary, next day.
6. **Sales process** (brief 7): queue of up to 4 with thought bubbles and patience, accept/reject, one order at a time, stations with progress bars, tray, handover with payment, pause when the player leaves the café, manager, error cases, reputation, closing rules.
7. **Students** (brief 8): pool of 25, budget and utilities kept all day, phase table, arriving and leaving over map edges, state machine, several purchases per day, re-deciding with the utility model, competitor serving automatically.
8. **Products and progression** (brief 9): wholesale units and shelf life per batch, products with stations, upgrades and manager at the upgrade board, buying the competitor in P17, victory and game over.
9. **Pop-ups** (brief 10): one dialog template, dialog queue, toasts, the full catalog P00-P20 and T01-T12.
10. **HUD and look** (brief 11): HUD layout, current objective and ground marker, day and night lighting, low-poly look, walking animation.
11. **Configuration and saving** (brief 12): one configuration for all balancing values, SQLite save at every confirmed dialog, finished order and phase change, "Fortsetzen" resumes there.

## Existing rules that must not change
- Utility model of brief 8.1: €10 budget per student and day, daily random utilities, shop factor × utility, unspent money as utility, existing bundle logic.
- The competitor has fixed prices, a fixed shop factor and no stock decisions.
- Upgrade, manager, acquisition, victory and game-over rules of brief 9.3.
- The pause button stops everything at every speed.

## Out of scope
- Changing the utility formula (only the reputation modifier of brief 7.5 is new).
- Weather, seasons, different sunrise times per day.
- Multiplayer, accounts, payments, external APIs, LLM features.
- Sound and music.
- Pathfinding beyond what is needed to avoid buildings.

## Done when

Logic (pytest):
- Clock: at 1x one real minute = one game hour; at 2x, 4x and 8x the same day takes half, a quarter and an eighth of the time; switching speed mid-day continues without jumps; pause stops all time-based progress.
- With a fixed seed, the same day produces the same purchases at 1x and at 8x.
- The clock pauses during dialogs in phases 1-3 and never during opening hours.
- Phase, target student count and café probability are correct at 07:45, 08:30, 10:00, 12:30, 14:00, 16:30, 18:30, 20:30 and at every boundary.
- The lighting function returns the correct state at 06:00, 07:45, 12:00, 18:00, 20:00 and at the boundaries, and values change smoothly.
- Never more than 25 students on the map, also when the phase table asks for more; with a fixed seed the count stays close to each target and is clearly higher at 12:30 than at 10:00 and 14:00.
- A student who leaves and returns keeps remaining budget and utilities; students never spend more than their remaining budget.
- State transitions: a student only buys after reaching the counter, being accepted and receiving the order; a rejected or sold-out student re-decides with the utility model; a student leaving for a lecture ends off-map.
- Shopping list = planned portions minus usable stock, in wholesale units; cart above balance blocks payment; unpaid cart blocks the exit.
- Unit conversion and shelf life: beans never spoil, oranges after 3 days, pastéis overnight; spoilage is reported per batch.
- Sales: one order at a time; money is credited only at handover; leaving the café pauses the order; patience running out loses the customer; wrong items lower reputation; at 20:00 waiting customers leave and an unfinished order is cancelled.
- The manager serves with the same preparation times; reputation scales the next day's shop factor by ±20 %.
- Daily summary numbers add up (revenue - purchase cost = profit; spoilage reported separately).
- Saving and "Fortsetzen" restore the state of the last save point.
- All existing tests still pass or are replaced by v2 tests for the same rule, with the reason noted in the commit message.

In the running game:
- The page shows only the game. A full day can be played with keyboard and mouse only, guided by pop-ups and the current objective, from P01 to P16.
- At 8x a full day shows the running clock, dawn, sunrise, daylight, sunset and dusk, the morning rush, quiet lecture times, the lunch peak with 25 students, queues with thought bubbles, and students walking on and off the map.
- The game stays smooth with 25 students at 8x.

## How to work
Implement directly, without waiting for approval, on a branch named `v2-campus-game`. Work in steps; each step gets its tests first, then the implementation, then its own commit:
1. **Architecture:** check how v1 renders the 3D world and how Python and the browser can communicate. Choose the simplest solution that keeps all rules in tested Python and animates smoothly (brief 2 recommends "Python decides, the browser animates"). Write the decision and the reason into `docs/architecture.md`.
2. **Core logic:** configuration, clock, speed, phases, lighting schedule, wholesale units, shelf life, planning, cart, checkout, bag, stocking, prices, reputation (logic only, fully tested).
3. **Students and sales logic:** student pool, state machine, decisions with the utility model, queue, accept/reject, stations, tray, handover, patience, manager, competitor serving, closing, summary (logic only, fully tested).
4. **Game shell:** full-window page, bridge between Python and browser, title screen, saving and loading, HUD with clock, speed, pause and balance, pop-up template, dialog queue and toasts.
5. **World and controls:** campus, café interior with stations, wholesaler, competitor café, collision, keyboard movement, E/click interaction with outline and hint, both cameras, ground marker.
6. **Morning loop in the game:** P00-P08 with T01-T05, end to end.
7. **Opening hours in the game:** students moving, arriving and leaving over map edges, queues, thought bubbles, P09-P13, manager, competitor serving.
8. **Evening, progression and look:** P14-P20, cleaning, summary, fade to next day, upgrades and acquisition, day and night lighting, student look and walking animation.

Rules:
- Tests come before the implementation in each step. Do not weaken, skip or delete tests to get green output.
- If something is unclear, make a reasonable assumption, write it into `docs/assumptions.md` and continue.
- At the end: run all tests, show the output, list the changed files per step, and tell us how to verify a full game day in the running game.
