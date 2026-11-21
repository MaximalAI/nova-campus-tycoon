# Spec: v15 flicker fix, reputation, SnackBots guidance, game over and full documentation

Product rules: `docs/product-brief-v2.md`; the current rules in detail: `docs/game-logic.md`. This spec lists what v15 changes on top of v14.

## Why
Maxi's bug and extension list for v15 after playing v14: the screen still turned dark and flickered now and then, advanced games lost reputation every day until it reached 0, SnackBots was confusing, a few pop-ups and messages were wrong or in the wrong order, NPCs got stuck in groups, the casino showed the result early, the day summary seemed to sell more than planned, there was no game over when the player could not do anything any more, and the documentation was not complete enough for a reader who only reads GitHub.

## What
1. **No more flicker.** Streamlit fades an element to 33 % opacity when Python takes longer than 0.5 s ("stale" element). The whole game is one element, so a slow server answer laid a dark blue film over the game, which jumped back when the answer came. `app.py` keeps stale elements at 100 % opacity. Reproduced with a deliberately slow server: before 0.33 opacity during the answer, after 1.0.
2. **One reputation rule for every customer.** Served customers raise the reputation, unserved ones lower it, in your own shop and in shops run by a manager (a manager's happy customer now counts +2 like yours, it was +1). All customer changes (served, partly served, sold out, waited too long, broken machine, wrong order, turned away, cancelled) share one daily budget of +-15 net. Before, sold-out losses had their own -15 cap next to the +15 cap of the gains, so a large business could only sink. Four simulated campaigns: reputation never below 20, at most 15 per day, victory on days 34 to 35.
3. **Partly served customers.** A customer who got only part of his order (something sold out) costs -1 at the counter and brings no plus at the handover; the toast says "Partly happy customer (... was sold out)" and the summary counts them separately.
4. **Why the reputation changed.** Every change is booked with its reason; the daily summary shows them ("+27 served customers, -3 waited too long, -26 sold out").
5. **SnackBots guidance.** The first time you run SnackBots a pop-up (P46) explains the machines. Every machine that needs you (broken, cash inside or not full) has an orange ring and a tag above it with its stock and cash. The objective names the three machines.
6. **Broken machine message.** A customer at a broken machine leaves with the toast "the machine ... is broken" and -2 reputation (it said "the machine is empty").
7. **Cash to bring back.** Collected cash is shown in a pulsing line under your money ("You carry €4.20 - bring it to the SnackBots office"), in the objective and in the collect toast ("not in your account yet").
8. **Stock "i".** A small "i" next to "Stock" opens P47 with the whole stock of every shop (storage with best-before days, shelves, machines, bag, carried cash).
9. **Settings (P20).** Shows the account you are logged in with and a "Log out" button.
10. **Pause first.** Leaving the browser tab while a pop-up is open (shopping list, casino ...) shows the pause menu on top; after "Resume" the pop-up comes back (it was the other way round).
11. **Shop price only when entering.** The "for sale" pop-up of a shop you do not own (for example Nova Mensa) appears when you walk up to its door from outside, not when you come out.
12. **Order bubbles in a queue.** Bubbles do not cover each other any more: the first in line keeps his place and is drawn on top, the others move up; every bubble shows the place in the queue (1, 2, 3).
13. **NPCs do not get stuck in groups.** Walking people slide past each other sideways instead of pushing head-on; someone who is stuck three times in a row finds a new way.
14. **Casino.** During a roulette or slot spin the cash shown stays at "before minus the stake" until the result is shown.
15. **Summary chart.** "Sold vs. what you had": grey = what you had that day (plan, leftovers from yesterday and extra purchases), green = sold, dashed line = plan. Selling more than planned is possible (you bought more or had leftovers), selling more than you had is not; the chart now shows both, so it can be checked.
16. **Game over when stuck.** At the end of a day: no portion left in any of your shops, nothing in the bag or the cart, no cash in a machine or in your pocket, and less money than the cheapest wholesale item your shops can use: game over ("out of money and stock"). Before, the player could stay in an endless loop with €0.57.
17. **Self-service fix.** If everything a Mercado customer wanted sold out while he waited, the checkout lets him leave instead of failing.
18. **Simulation cleans.** The headless player now cleans after closing like a real player (before it always lost 15 reputation per day, which hid the reputation drift in the balance runs).
19. **Documentation.** New `docs/game-logic.md` (every feature and its rules), rewritten `docs/architecture.md` (request lifecycle, modules, events, storage, security, performance, hosting), new `docs/testing.md` (every test file and what it proves, the balance simulation), new `specs/README.md`, rewritten `README.md` with a reading order.

## Out of scope
- Moving the server closer to Lisbon (Render cannot move an existing service; it needs a new service in Frankfurt).
- "Sold old pastel de nata" when a customer did not get his orange juice: we could not reproduce it; with item 3 a missing product now always shows as "Partly happy customer (... was sold out)". A screenshot of the exact message would help.

## Done when
- `uv run pytest` passes (355 tests), including `tests/test_v15.py`.
- Four full simulated campaigns are won and the reputation never drifts to 0.
- In the browser: no fade while the server answers; P20 shows the account and "Log out"; the pause menu comes before an open pop-up; P47 lists the stock; at SnackBots P46, the machine tags and the orange rings show; the summary chart shows what you had; no console errors.
