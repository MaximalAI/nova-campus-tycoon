# Architecture v2: Python decides, the browser animates

## Problem
Version 2 is a real-time 3D game with keyboard control, a running clock (up to 8x speed) and 25 moving students. Streamlit reruns the whole Python script on every interaction, so Python cannot drive animation at 60 frames per second. At the same time the course requires the rules to be Python code tested with pytest, and storage in SQLite.

## Decision
- **Python owns every rule and every decision.** `logic.py`, `students.py`, `timeclock.py` and `config.py` contain the game state, all checks, the utility model, purchases, stock and shelf life, the sales process, reputation, progression and the summary. They are pure Python and fully covered by pytest.
- **The browser only renders, animates and collects input.** The Three.js game in `game/` runs the clock, moves the figures, shows HUD and pop-ups and reports events (dialog confirmed, student reaches the counter, item prepared, clock passed 08:00 ...).
- **The bridge is a Streamlit v2 component** (`st.components.v2.component`, available since Streamlit 1.67). The browser sends batches of events with `setTriggerValue("events", {seq, events})`. The `on_events_change` callback in `app.py` passes them to `bridge.process_batch`, which calls `logic.apply` for each event, saves the new state to SQLite and returns the results and the new view with the next render. The component stays mounted between reruns, so the 3D scene keeps running.
- **Determinism:** at the start of each day Python creates the day plan (`students.make_schedule`): who is on campus when, and when each student thinks about buying. Random decisions use a generator seeded with seed, day, student and the scheduled game time, so the same day produces the same purchases at 1x and at 8x (`tests/test_students.py::test_same_purchases_at_1x_and_8x`, using the headless driver in `simulation.py`).
- **Lighting:** `timeclock.lighting_at` defines the day and night schedule; Python sends a table sampled every 10 game minutes and the browser interpolates between the samples.

## Why this is the simplest solution that animates smoothly
- One event round trip measured about 45 ms locally; Python needs about 2 ms per event. Events are batched, so even at 8x the browser only waits for decisions, never for animation.
- The alternatives were worse: running the simulation in Python per frame (Streamlit reruns are far too slow for 60 fps), or duplicating the rules in JavaScript (rules would no longer be tested with pytest and could drift apart).

## What the browser is allowed to do on its own
Only presentation: positions, walking paths, animation, the camera, the HUD, timers for progress bars and patience, and when to send an event. If Python rejects an event, the browser shows the error and changes nothing in the game state. The browser keeps a tiny copy of the clock formula (`t += dt * speed / 60`); the tested rule is `timeclock.advance`.

## Files
| File | Role |
|---|---|
| `app.py` | Streamlit page: hides Streamlit's own UI, mounts the game, handles event batches, saves |
| `bridge.py` | Runs a batch of browser events through `logic.apply` |
| `logic.py` | Game state and all event handlers (rules) |
| `students.py` | Student pool, schedule, state machine, utility decisions |
| `timeclock.py` | Clock, speeds, phases, lighting schedule |
| `config.py` | All balancing values |
| `db.py` | SQLite storage |
| `simulation.py` | Headless day driver for tests and balancing |
| `game/` | Three.js game: `game.html`, `game.css`, `js/core.js`, `world.js`, `people.js`, `ui.js`, `flow.js`, `main.js` |
