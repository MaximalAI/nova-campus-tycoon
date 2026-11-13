# Spec: v9 fixes, wholesaler stands and a bigger casino

Product rules: `docs/product-brief-v2.md`. This spec lists what v9 changes on top of v8.

## Why
Play-testing v8 showed display bugs (casino chips behind order icons and in the upgrade dialog, an empty info circle), geometry bugs (a shelf in the SnackBots wall, floating benches, open walls above the doors) and gaps in the second shop (day planning, upgrades of all shops in one dialog, no evening cleaning). The team also wanted managers who really shop at the wholesaler, a wholesaler with every product, quieter sounds from far away and more to do in the casino.

## What

### Display fixes
- The roulette chips used the CSS class `chip`, which the order and upgrade dialogs use too. They are now `rchip`; the sound switches are `snd-toggle` (the wholesaler's toggle chips were affected as well).
- The info circle next to the day gain is green (red when negative) with a white "i".
- Beach barrier: a big two-line sign on two posts ("BEACH / opens when the campus is yours"), readable from both sides.
- Signs shrink their text until it fits (`textTexture`); the casino name sign is wider.

### World
- SnackBots office: the storage shelf stands along the side wall like in the vending layout (it was rotated into the left wall).
- Benches have legs and back posts. Every building has a wall above the door (above the awning it was open).
- The casino room and its people are only drawn while the player is inside, so it is not visible at the edge of the map.

### Second shop and managers
- Every owned shop's day plan board can be opened. In the shop you run it opens the planning for that shop; elsewhere it shows that shop's plan (manager's plan, opens tomorrow, or where you work today).
- Upgrades & staff shows only the shop of the board (the office of SnackBots opens its own).
- Every manager with a counter cleans his shop after closing (stations, counter, floor). Only the café has cleaning spots in the rules; for the other shops this is the evening routine you see.
- After you accept a manager's proposal he walks to the wholesaler, goes to the stand of every product he bought (aisle by aisle, through the free column next to the checkout), waits in line until the checkout is free, pays and walks back. Managers who start together leave a few minutes apart and use different spots at the stands.

### Wholesaler
- One stand per product (28), grouped by shop under a sign: the café, Café da Esquina, SnackBots and Mercado & Go along the north wall, Bowl Bar, Nova Mensa and Gelado along the south wall, Praia Bar and Surf Shack on an island in the middle that can be used from both sides.
- Products of shops you do not own yet are shown with a lock; using them says which shop you need. A test checks that every base product of every shop is sold at the wholesaler.

### Sound
- The cleaning sound plays with the cleaning animation (a swish every 1.8 s while someone cleans).
- Effects of a shop, a machine or a worker get quieter with distance (full within 8 m, silent from 30 m). Campus sounds are not heard in the casino and the other way round.

### Casino
- The machine over the hatch can be pushed back (and aside again) once you know the secret.
- Roulette: the stake drops onto the field you bet on, the croupier works the wheel; after the spin the chips go to you (with the winnings) or to the croupier.
- Bar da Sorte along the east wall with a barkeeper, two guests at the bar and one guest watching the roulette. Drinks (beer €4, port €6, caipirinha €8) make you tipsy for 10 game minutes: blurred, swaying view, walking drifts sideways. No second drink while tipsy.
- Three one-armed bandits along the west wall. Coins of €1, €5 or €10; three equal symbols pay 5x to 100x, two cherries give the coin back. About 89 % of the stakes come back over time (`slot_return_rate`). Reels are seeded by game, day and pull count.
- Bar spending and slot results count in the day profit (summary rows "🍸 Casino bar" and "🎰 Casino").

## Out of scope
- Cleaning rules (reputation) for shops other than the café.
- More casino games, NPCs who play.

## Done when
- `uv run pytest` passes, including `tests/test_v9.py` (bar, slots, wholesaler coverage).
- The browser check shows the fixes above: white order chips, the "i", the bigger beach sign, the office shelf, bench legs, the wholesaler stands from both sides of the island, managers shopping stand by stand and queueing at the checkout, the rival manager cleaning, the push-back of the casino machine, chips on the roulette table, the bar and the slot machines.
