# Spec: v13 playtest bug fixes

Product rules: `docs/product-brief-v2.md`. This spec lists what v13 changes on top of v12.

## Why
A full playtest (day 1 in the browser, a day-31 save with eight shops, six headless campaigns) found eight bugs. The owner confirmed seven of them for fixing; the missing station marker while preparing an order (bug 6) stays as it is.

## What
1. **Manager plans no longer explode after a sold-out day.** Customers who found a product sold out count only half (`manager.missed_weight` 0.5), and a plan is at most 1.5x the best day the shop ever sold (`manager.max_vs_best_day`). Before, one bad day could make the Bowl Bar plan 173 poke bowls.
2. **Managers share the money and buy complete portions.** If the cash is not enough for a plan, the whole plan is scaled down until its shopping list fits, so every product can still be made. At 07:00 and with "Accept all" (new event `confirm_all_manager_plans`) every manager gets a share of the cash in proportion to his plan; before, the last shop in the buying order got nothing or only rice. A toast says how much of the plan a manager could buy, and the "Accept all" pop-up warns before buying when the cash is short.
3. **Reputation no longer swings 96 to 0 to 100.** Customers who waited too long (-3 each) and happy customers of your managers (+1 each) share one daily budget: together they change the reputation by at most +-15 per day, net (`reputation.customer_daily_cap`). The owner first chose separate caps (-15 / +10); in test campaigns that let the reputation sink to 0 for weeks and made the game last 49-57 days, so he chose the shared net cap (31-32 days, never stuck at 0).
4. **Buying a shop warns when the managers will lack money.** The view has `manager_cost_estimate` (what the managers spent this morning, or their current proposal if they have not bought yet). The buy pop-up warns when the cash left after the purchase is below it. The purchase stays allowed.
5. **Flat sea means fewer surfers, not zero surfers.** The wave factor below 1 now lowers the share of beach visitors who consider the Surf Shack at all (fixed per student and day), instead of lowering what everybody would pay (which meant nobody rented on a 1-star day, -100 % instead of the -60 % in the forecast). Good waves still raise what people pay. The Surf Shack manager plans with today's waves against the waves of the day his plan is based on.
6. (not fixed, owner's decision) No marker while preparing an order.
7. **After "Prices saved" the objective moves on.** It says "Prices set - press ⏩ Start the day" (or that the managers are still at the wholesaler), and the marker no longer points at the register.
8. **Welcome text.** "Your café is right behind you (☕ on the minimap)" instead of "on the left".

## Done when
- `uv run pytest` passes, including `tests/test_v13_bug_fixes.py`.
- Headless campaigns are still won, without long stretches at reputation 0.
- In the browser: the welcome text, the objective after saving prices, the "Accept all" warning and the buy warning show as described.
