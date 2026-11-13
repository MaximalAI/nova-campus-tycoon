# Spec: v10 shop logic, cleaning per shop, vending and Mercado

Product rules: `docs/product-brief-v2.md`. This spec lists what v10 changes on top of v9.

## Why
v9 still had gaps in the basic loop of the bought shops: upgrades that did not fit a shop (a better coffee machine at SnackBots), no cleaning outside the café, a SnackBots manager who only filled one of three machines, and a Mercado & Go that was hard to understand. The team asked for a check of the whole loop in every shop: plan, buy, sell, clean, hire a manager, manager proposes, buys, sells and cleans.

## What

### Upgrades per shop
- Every shop has three upgrades that fit what it sells (config `shops.<shop>.upgrades`), with the same prices and bonuses as the café's three tiers (the balance stays). Example: SnackBots has card readers, LED machine fronts and branding.
- A shop only sells its own upgrades. Old saves: an upgrade bought in v9 becomes the same tier of the new list (`migrate`).

### Cleaning per shop
- Every owned shop with staff that was open today is cleaned after closing (config `shops.<shop>.cleaning`, for example Mercado & Go: register, shelves, floor). SnackBots has no shop floor to clean.
- The player cleans the shop he ran (dialog P14 lists its spots, the marker leads from spot to spot). Each manager cleans his own shop and reports every spot. The day ends as soon as everything is clean, at the latest at 21:00.
- A shop that was yours to clean and stays dirty costs reputation (once per shop). A manager's shop is never left dirty.
- After reloading the page in the evening the managers start cleaning again (before, the café stayed dirty).
- The cleaning sound is only heard when the player is in the shop that is cleaned, or cleans himself.

### SnackBots
- The manager plans enough to fill all three machines (capacity x machines) and shares the goods out evenly (before, one machine got everything).
- The manager is a visible person: he works at the office desk, walks to the wholesaler with his proposal, refills each machine in the morning and collects the cash in the evening.
- The office has the day plan board (no longer hidden behind the storage shelf), an upgrade board and a board that explains the machine lights (P45).
- Customers line up at a machine: the first one uses it, the others wait behind him and move up. Someone who waits too long walks away.

### Mercado & Go
- The objective leads through the steps: storage, shelves, prices, scanning; while open it reports an empty shelf that can be refilled. The marker points to the shelf or the register.
- The shelves can be refilled any time until closing (before: only until 10:00). The shelf dialog starts with a full suggestion, so one click fills the shelves.
- Open shelving units with a product sign and up to six goods boxes (before: a solid block that stood in the upgrade board).
- A customer who finds part of his order missing still buys the rest but costs 1 reputation point (`sold_out_partial`, also in shops run by a manager, inside the daily sold-out cap).

### Wholesaler and managers
- The objective leads the player along the shopping list: "Take 2x Oranges from its stand (1/3 done)", the marker points to the nearest stand of the next item, then to the checkout. An item of the list starts with the list amount in its dialog.
- Managers who arrive while the player is shopping wait at the door until he has left.
- A newly bought shop starts its day plan with sensible amounts instead of zero.

### Casino and beach
- After "Spin" the roulette dialog closes so the player sees the wheel and the chips; it comes back with the result.
- The word BEACH is centred on the barrier sign.

## Out of scope
- New shops or products.
- Changing the balance targets (upgrade prices and bonuses stay the same).

## Done when
- `uv run pytest` passes, including `tests/test_v10.py` (upgrades, cleaning, vending manager, Mercado).
- The browser check shows: a Mercado day from the plan to the cleaning with the managers cleaning their shops, the SnackBots manager filling all machines and doing his rounds, lines at the machines, the office boards, the guided wholesaler visit, the roulette dialog closing during the spin and the centred beach sign.
