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
- Camera: third-person follow camera; right mouse drag rotates, the mouse wheel zooms. Behind the counter during opening hours a fixed counter camera is used.

## Saving
- The game is saved after every batch of events. "Fortsetzen" resumes at the saved game time. Students who were in a queue or on their way to a shop start again on campus, and an order in progress is cancelled (event `resume`).

## Visuals
- Pictures of items and products are emoji icons instead of PNG files (brief 9.2 mentions `img/*.png`). They can be replaced later.
- 3D models are built from simple shapes in code (no external assets). Three.js is loaded from a CDN, so the game needs an internet connection.

## Version 1 tests
- The v1 tests (`test_first_feature.py`, `test_rules.py`, `test_demand.py`, `test_selling.py`, `test_app.py`, `test_setup.py`) were replaced by v2 tests because the rules changed by design (units and shelf life, new prices, sales process, students over the day). The same kinds of rules are covered again in `tests/test_economy.py`, `test_sales.py`, `test_students.py` and `test_progression.py`.
