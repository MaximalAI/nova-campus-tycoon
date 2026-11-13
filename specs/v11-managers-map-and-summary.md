# Spec: v11 managers, map, shop fixes and the day summary

Product rules: `docs/product-brief-v2.md`. This spec lists what v11 changes on top of v10.

## Why
Play-testing v10 showed managers bumping into each other on their way to the wholesaler, a vending manager who only stood in his office, a map with paths running under buildings and benches facing away from the fountain, two shops that could not be used (Bowl Bar assembly, Praia Bar happy hour), Surf Shack prices without a margin and a day summary that was hard to read (plan always 0 for manager shops, investments counted as a loss, unclear charts).

## What

### Managers
- "Start the day" is greyed out while a manager is still on his way to or from the wholesaler (or about to leave). The objective and the P08 dialog say why. It turns green once all managers are back.
- Managers no longer walk through each other: a walking manager steps aside of one who stands, two walking ones both give way. Every manager has his own waiting spot in front of the wholesaler, they go through the door one after the other and use different spots at the stands.
- The player starts a bit to the right of the café door (out of the way of managers leaving the café).
- SnackBots manager: after shopping he walks from machine to machine. At each machine he repairs it (if broken), refills it from the storage and takes the cash out; the cash goes straight into the balance (toast "+€X"). During opening hours he goes round about every 90 game minutes, sooner when a machine breaks down or runs low; in the evening he collects the cash. New event `manager_service {shop, machine}`.
- Without a browser (headless simulation, tab closed) Python does a full round half an hour after opening and then every two hours without a round. Breakdowns are no longer repaired by magic.
- Beach managers walk through the gate on the path, not through the fence (the fence is now part of the walking grid).

### Map
- More seating (tables with four chairs and a parasol), more trees, bins, bike racks and flower beds on the campus; loungers, a lifeguard tower and a volleyball net on the beach. Nothing stands on a path or in front of a door.
- Paths no longer run under buildings: the main path goes from the café door to the wholesaler door (the two pieces behind the café are gone).
- The beach (sand, surf, fence) spans the whole width of the map, also on the maps.
- All benches around the plaza face the fountain.
- The "Surf & Sun" board on the promenade stands on two posts instead of floating.

### Shops
- Bowl Bar: the "Assemble" button turns green as soon as an ingredient is picked; ingredient names are dark on white (they were white in dark mode).
- Surf Shack: a rental costs the board or wetsuit spread over 40 rentals (`lifetime_uses`), not the whole board. Start prices €15 / €8 / €25 (with a margin). The price buttons step by €0.10 below €6, €0.50 up to €20, €1 above.
- Praia Bar: prices and the happy hour can be set at the register until the bar opens at sunset.
- Reputation rules are the same at the beach as on the campus (sold out, part of the order missing, waited too long, cleaning). A missing part of an order in a manager's shop is now also shown as a toast.
- A shop that was yours to clean and stays dirty costs 15 reputation (was 5).

### Other
- The music and all sounds stop while the browser tab is hidden and come back when you return.
- Bug found while testing: an event of the previous evening (autosave at 21:00) that reached Python after "next_day" set the new morning to 21:00, so the new day ended at its first tick. Events now carry their day; an old one no longer moves the clock.

### Day summary
- Sold vs. plan uses the plan of every shop you ran: your own plan and your managers' accepted proposals (also per shop in `by_shop`). The chart grows with its labels and wraps with many products, so it no longer runs into the text.
- The customers chart names its lines: green = served, red = lost (waited too long or sold out).
- Profit is without investments: buying shops, upgrades and hiring managers are listed as "Investments" and do not lower the day's profit (they still come out of the cash).
- Market share says what it counts: "campus only" until the beach opens, then "campus + beach". Bot shops in a closed zone never count.

## Out of scope
- New shops or products.
- Changing the campaign balance targets.

## Done when
- `uv run pytest` passes, including `tests/test_v11.py`.
- The browser check shows: the start button greyed out until all managers are back, no two managers standing in each other at the wholesaler, the vending manager's rounds with cash toasts, the new decoration with no object on a path, the full-width beach, benches facing the fountain, the Bowl Bar assembly, the Praia Bar happy hour during the day, the summary with plans and the market share label, and the audio pausing in a hidden tab.
