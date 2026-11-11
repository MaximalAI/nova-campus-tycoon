# Spec: v6 fixes and polish

## Why
Playtesting v5 showed small but annoying issues around the manager, the takeover of the second café, NPC movement and a few visuals.

## What
1. No automatic planning pop-up in the morning; walk to the planning board.
2. Animations for staff while making coffee, pressing juice, taking pastry and cleaning.
3. Customers leave through the door, not half through the wall.
4. FOR SALE sign readable.
5. NPCs do not get stuck in groups.
6. Upgrade dialog chips on one line.
7. Sold-out products: the manager does not walk to the station.
8. Bought café becomes the player's property the next morning.
9. Correct objective text after the purchase (manager runs the old café, you run the new one).
10. With a manager hired the player cannot clean; the manager does it.
11. After the victory: keep playing in open mode.
12. Croissants in the competitor's display.
13. M opens the map.

## Out of scope
- New products, sound, multiplayer.

## Done when
- `uv run pytest` passes, including `tests/test_v6.py`.
- Browser test: no planning pop-up after the morning dialog; staff show an activity tag and arm movement; leaving customers cross the door line within ±1.2 m of its centre; the manager skips sold-out stations; the competitor is still a bot on the purchase day and yours the next day; the player cannot clean with a manager; victory offers open mode and the game continues; M toggles the map.
