# Spec: v14 world fixes, legal notice, sold-out orders and performance

Product rules: `docs/product-brief-v2.md`. This spec lists what v14 changes on top of v13.

## Why
Maxi's playtest list for v13: people walked through flower beds, some beach props looked wrong, the view flickered, the laptop got warm, the server felt slow, the site had no legal notice, and a sold-out product could still be ordered.

## What
- **People avoid all obstacles.** The walking grid of the students and managers now counts every obstacle up to 20 m (flower beds, terraces, bike racks, loungers); before only obstacles under 2 m counted.
- **Beach props.** Loungers stand on four legs. The lifeguard tower stairs go up to the platform (they sloped the wrong way) and have steps.
- **Start café.** The white sign left of the door is gone (the café opens at 08:00, at the register or with ⏩).
- **No more flicker.** The sun angle moves in 0.5° steps and the shadow area in 8 m steps, so shadow edges no longer shimmer while you walk.
- **Lighter on the laptop.** At most 1.25 render pixels per screen pixel (Retina screens rendered 4x the pixels), the cheaper PCF shadow filter, at most 60 frames per second (30 while nothing moves: title screen or a pop-up with the clock stopped).
- **Faster server answers.** The full database check runs once per server process, not on every request. The state handled in a request is not loaded and migrated a second time. The config and the lighting table (about 55 KB) go to the browser once per session; the view sends only the summary fields of the last days (about 40 KB less per answer).
- **Legal notice (Impressum).** On the landing page (footer link) and in the title menu: the team with student IDs, Maximilian Kienzle as contact (address and e-mail) and a disclaimer.
- **Wholesaler.** An item starts at 0 (or what is already in the cart); "Take the list amount" fills in the list amount.
- **No overlapping text.** The "E ..." hint moves above a customer's order bubble if they would overlap; the key help at the bottom left hides while the order bar is shown.
- **Sold-out orders.** If a product sells out while a customer waits at the counter, the order pop-up is not shown with it: the customer shows it as sold out and takes the rest or leaves. If it happens at "Accept", Python does the same instead of an error, and the sold-out product always costs reputation (before, a partly sold-out order was accepted without any reputation loss).

## Out of scope
- Moving the server to a region closer to Lisbon (Render cannot change the region of an existing service; it needs a new service).

## Done when
- `uv run pytest` passes, including `tests/test_v14_sold_out_orders.py`.
- In the browser: 400 sampled walking paths never cross a flower bed; loungers, stairs and the café front look right; the legal notice opens from the landing page and the title menu; no console errors.
