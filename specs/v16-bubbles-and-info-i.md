# Spec: v16 order bubbles and the stock "i"

Product rules: `docs/product-brief-v2.md`; the current rules in detail: `docs/game-logic.md`. This spec lists what v16 changes on top of v15.

## Why
Maxi's list after playing v15: the queue numbers in the order bubbles were not needed, a long queue built a tower of bubbles because every bubble moved up until it was free, and the "i" next to "Stock" looked different from the "i" on the day gain button.

## What
1. **Only the products in the bubble.** Order bubbles show the products (and "sold out" items), no queue number any more.
2. **Every bubble at the same height.** A bubble always sits at the same height above its customer; bubbles are no longer pushed up to avoid each other, so a long queue no longer builds a tower. Where bubbles overlap, the first in line is drawn on top, then the customers nearest to the player.
3. **One "i" style.** The stock "i" uses the same look as the day gain "i": white italic serif "i" on a dark green circle. The Stock heading is uppercase with letter spacing, which turned the old "i" into an "I"; the button switches both off.

## Out of scope
- Game rules, balance and the Python side are unchanged.
