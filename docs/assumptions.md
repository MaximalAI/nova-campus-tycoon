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
- Camera (v3): one third-person follow camera everywhere, GTA style. Click the game to capture the mouse (pointer lock), the mouse turns the camera, W walks in the camera direction, Shift runs, the wheel zooms. Inside buildings the camera moves closer and higher, and walls or roofs between camera and player fade out, so the player is never hidden behind the counter. The v2 fixed counter camera was removed because it sat behind the stations.
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
