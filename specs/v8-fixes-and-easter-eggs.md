# Spec: v8 fixes, safety, sound and two easter eggs

Product rules: `docs/product-brief-v2.md`. This spec lists what v8 changes on top of v7.

## Why
Play-testing v7 showed a list of bugs and wishes: the monopoly counter started at 0/9, the statistics needed several clicks, a manager hired during the day already cleaned in the evening, customers left a sold-out shop without any effect on the reputation, and the map could not show the beach. The course also asks for a README with the deployed URL, the team and the commands. On top, the team wanted sound and two hidden easter eggs.

## What

### Fixes
- Monopoly bar shows the shops you own (1/9 at the start, the first café is yours).
- Statistics open with one click on the day gain next to the cash (pointerdown instead of click on a button whose text is rewritten 10 times a second); a small "i" shows that it is clickable.
- A manager hired during the day starts the next morning. That evening the player cleans (the cleaning objective and the café worker check `manager`, not `manager_hired`).
- A customer who finds a product sold out costs reputation every time: -1 if he goes home, -2 if he goes to a competitor instead. At most -15 per day from sold-out products, so one bad morning does not ruin the game.
- The manager's proposal counts the customers who found a product sold out (missed demand), and the summary keeps the sales of every shop, so the first plan in a bought shop knows how much it used to sell.
- After you accept the manager's proposal he walks to the wholesaler, buys (8 game minutes), walks back and stocks the shelves.
- Minimap: the Nova Mensa icon (a plate emoji drew a white circle) is now 🍛.
- Big map: drag with the mouse to look around (also the beach), wheel to zoom; the people on it move while it is open; locked buildings show in grey with a lock.
- Beach barrier: the sign has a face on each side, so it reads correctly from the campus and from the beach.
- Daily summary, tab "Competitors": a table of all eight other shops (served, sales, market share, average price, pull, price to buy, beach closed).
- Cheaper shops: the second shop costs €300 (v7: €700); the others about 15 % less (see brief 14.6). New balance target: first purchase around day 6, then about 4 days per shop.

### SnackBots on the campus
- The three machines stand on the campus near the SnackBots office (config `machines` with id, name, position). Each has its own stock, cash box and breakdown state.
- Once you own SnackBots you refill each machine (from the storage), collect its cash and bring the cash to the office (deposit). The HUD shows the cash you carry. A machine light shows the state: red broken, yellow empty, blue cash waiting, green fine.
- The manager refills all machines in the morning and collects the cash in the evening.

### Safety (saving)
- SQLite runs with `journal_mode=WAL` and `synchronous=FULL`: a crash or a power cut never leaves a half-written save.
- Every save also writes the previous good state to `backup_json`; if `state_json` cannot be read, the backup is loaded.
- A damaged database file is moved aside (`.damaged`) and a new one is started instead of crashing the app.
- The browser reports the clock every 10 seconds and when the tab is hidden or closed (`autosave` event), so at most a few seconds of play are lost.

### Sound
- Generated in the browser with the Web Audio API (no audio files): a quiet background pad with soft notes, and a short effect per activity (sale, register, brewing, pouring, cleaning, stocking, door bell, refill, breakdown, repair, purchase fanfare, end of day, roulette, ladder, lighter).
- Pause menu ("Paused & settings"): background music and sound effects can be switched off separately; the choice is kept in the browser (localStorage).

### Easter egg 1: Jep
- Every morning Jep stands at one of eight spots on the campus (seeded by game and day), with his name above his head. Look: bucket hat, round sunglasses, flower shirt.
- Talk to him (E): he sells a joint for €10. The player smokes it (joint in the hand, smoke puffs) and is high for 10 game minutes: colours drift, the camera sways, the player walks slower. A badge shows the minutes left. No second joint while high.
- The money counts in the day profit (summary row "🌿 Jep").

### Easter egg 2: the underground casino
- Behind the Bowl Bar stands a broken vending machine ("OUT OF ORDER"). Leaning against it slides it aside: a hatch with a ladder leads down.
- Underground: a mystic casino room (purple light, floating orbs, a crystal ball, a croupier) with a roulette table.
- Roulette: chips of €10, €50, €100, €500; bets on red/black and even/odd (pay 1:1) or one of the three dozens 1-12, 13-24, 25-36 (pay 2:1). The 0 makes every bet lose. Python draws the number (seeded by game, day and spin count); the wheel spins and the ball stops on that number.
- Wins and losses count in the day profit (summary row "🎰 Casino"). Leave by the ladder or by the big map.

## Out of scope
- Real audio files or music tracks.
- More casino games than roulette, single-number bets.
- Any effect of the easter eggs on the students or the reputation.

## Done when
- `uv run pytest` passes (tests/test_v8.py, tests/test_v8_safety.py and the updated older tests).
- The browser check shows: 1/9 at the start, statistics with one click, Jep with his name and the high effect, the casino with a working roulette, the sound toggles, the big map drag to the beach, the competitor table in the summary.
- The README has the deployed URL, the team with student numbers and the commands.
