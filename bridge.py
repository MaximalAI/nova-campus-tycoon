"""Bridge between the browser game and the game rules.

The browser sends batches of events: {"seq": 7, "events": [{"cid": 1, "type": ..., "t": 8.25, ...}]}.
Every event is checked by logic.apply. A rejected event returns its error
message and changes nothing; the following events of the batch still run.
"""

from __future__ import annotations

import logic


def process_batch(state: dict, events: list[dict]) -> tuple[dict, list[dict]]:
    results = []
    logic.migrate(state)  # saves from older versions keep working
    for event in events:
        cid = event.get("cid")
        try:
            state, result = logic.apply(state, event)
        except logic.GameError as error:
            results.append({"cid": cid, "ok": False, "error": str(error)})
        else:
            results.append({"cid": cid, "ok": True, "result": result})
    return state, results
