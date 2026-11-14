# Spec: v12 landing page and player accounts

Product rules: `docs/product-brief-v2.md`. This spec lists what v12 changes on top of v11.

## Why
The game is now public at www.novacampustycoon.com. Before v12 there was one saved game for everybody: "Continue" loaded the latest game in the database, whoever played it. Every visitor needs their own account and their own saved game, and the site needs a front page that says what the game is.

## What
- Landing page (first screen, over the 3D campus): title, tagline, three cards (run your café, buy the competition, take the beach), a login box with the tabs "Log in" and "Create account", and a footer line.
- Create account with e-mail and password (password twice). Rules: a valid e-mail address, a password of 8 to 128 characters. One account per e-mail address: the address is stored in lower case and the column is UNIQUE (case does not matter), a second account with the same address is refused with "There is already an account with this e-mail address. Please log in."
- Log in with e-mail and password. A wrong address or password gives one message for both ("Wrong e-mail address or password.") and waits half a second.
- Passwords are stored only as salted PBKDF2-SHA256 hashes (200,000 rounds). A login gives the browser a random token (kept in the browser's local storage for 30 days); the database keeps only the token's SHA-256 hash. Reloading the page logs in again with this token.
- The title menu shows the account and a "Log out" button. Logging out ends the token on the server and in the browser.
- Saves belong to accounts (`saves.user_id`). "Continue" offers only your own running game; "New game" replaces only your own. Game events are refused unless the loaded game belongs to the logged-in account.
- Old databases get the new column automatically. The first account created on a database keeps the games saved before v12 (locally that is your own old save).
- Deployment on Render: persistent disk at `/var/data`, `NCT_DB_PATH=/var/data/game.db`; `www.novacampustycoon.com` is the primary domain.

## Out of scope
- Password reset by e-mail (needs a mail service).
- Changing the e-mail address or deleting an account in the game.
- Leaderboards or playing together in one game.

## Done when
- `uv run pytest` passes, including `tests/test_v12_accounts.py`.
- In the browser: the landing page appears first; creating an account opens the title menu; the same address (in other case or with spaces) is refused; a wrong password is refused; a second account does not see the first account's save; a reload keeps you logged in; "Log out" returns to the landing page.
