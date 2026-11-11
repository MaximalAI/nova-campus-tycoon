"""Headless day simulation: plays one opening day without the browser.

It sends the same events the browser sends, but every follow-up happens at an
exact scheduled game time. The real-time step only decides how events are
batched, so the outcome is the same at every speed. Used by the tests and for
balancing (`uv run python simulation.py`).
"""

from __future__ import annotations

import heapq

import logic
import mechanics
import students as st
import timeclock
from config import CONFIG

WALK_MINUTES = 3  # game minutes from deciding to arriving at a shop


def simulate_day(state: dict, speed: int = 1, real_step: float = 0.25, serve_player: bool = True,
                 fast: bool = False) -> dict:
    """Run from the current time to the end of the day. Returns the final state.

    serve_player=True: the player serves his café perfectly (accept, prepare, hand over).
    """
    T = CONFIG["time"]
    pq: list = []
    counter = 0

    def at(time, kind, **data):
        nonlocal counter
        counter += 1
        heapq.heappush(pq, (round(time, 6), counter, kind, data))

    def send(event):
        nonlocal state
        event = dict(event, t=current)
        try:
            state, result = logic.apply(state, event, inplace=fast)
        except logic.GameError:
            return None
        return result

    for mark in T["ticks"]:
        if mark >= state["time"]:
            at(mark, "tick")
    for sid, plan in state["schedule"].items():
        for arrive, leave in plan["presence"]:
            if arrive >= state["time"]:
                at(arrive, "arrive", sid=sid)
                at(leave, "leave", sid=sid)
        for d in plan["decisions"]:
            if d >= state["time"]:
                at(d, "decide", sid=sid)

    queues = {s: [] for s in CONFIG["shops"]}
    busy = {s: False for s in CONFIG["shops"]}

    def handle_decision(sid, result):
        if result and result.get("action") == "shop":
            at(current + WALK_MINUTES / 60, "reach", sid=sid, shop=result["shop"])

    def next_customer(shop):
        if busy[shop] or not queues[shop] or not state["open"]:
            return
        sid = queues[shop][0]
        if logic.is_auto(state, shop):
            items = state["students"][sid]["intent"]["items"]
            minutes = sum(CONFIG["products"][p]["prep_minutes"] for p in items)
            busy[shop] = True
            at(current + minutes / 60, "auto_done", sid=sid, shop=shop)
            return
        if not serve_player:
            return
        res = send({"type": "at_counter", "shop": shop, "student": sid})
        if res is None:
            return
        if res.get("leaves"):
            queues[shop].remove(sid)
            handle_decision(sid, res.get("decision"))
            next_customer(shop)
            return
        if mechanics.of(shop).service == "checkout":
            busy[shop] = True
            minutes = mechanics.of(shop).p["scan_minutes"] * len(res["items"])
            at(current + minutes / 60, "checkout_done", sid=sid, shop=shop)
            return
        res = send({"type": "accept", "shop": shop, "student": sid, "player_inside": True})
        if res is None:
            return
        busy[shop] = True
        minutes = sum(CONFIG["products"][p]["prep_minutes"] for p in res["order"]["items"])
        at(current + minutes / 60, "manual_done", sid=sid, shop=shop, items=res["order"]["items"])

    t = state["time"]
    current = t
    while pq:
        t_next = timeclock.advance(t, real_step, speed)
        if t_next <= t:
            break
        while pq and pq[0][0] <= t_next + 1e-9:
            when, _, kind, data = heapq.heappop(pq)
            current = when
            sid = data.get("sid")
            if kind == "tick":
                res = send({"type": "tick"})
                if res and res.get("closed"):
                    for s in queues:
                        queues[s].clear()
                        busy[s] = False
                if res and res.get("opened"):
                    for s in queues:
                        next_customer(s)
            elif kind == "arrive":
                send({"type": "student_arrive", "student": sid})
            elif kind == "leave":
                if state["students"][sid]["status"] in (st.WANDERING, st.WALKING_TO_SHOP):
                    send({"type": "student_leave", "student": sid})
                elif state["students"][sid]["status"] != st.OFF_MAP:
                    at(current + 5 / 60, "leave", sid=sid)
            elif kind == "decide":
                handle_decision(sid, send({"type": "decide", "student": sid}))
            elif kind == "reach":
                student = state["students"][sid]
                if student["status"] != st.WALKING_TO_SHOP or student["intent"]["shop"] != data["shop"]:
                    continue
                shop = data["shop"]
                if len(queues[shop]) >= CONFIG["shops"][shop]["max_queue"]:
                    handle_decision(sid, send({"type": "queue_full", "student": sid, "shop": shop}))
                    continue
                res = send({"type": "join_queue", "student": sid, "shop": shop})
                if res is None or res.get("action"):
                    handle_decision(sid, res)
                    continue
                queues[shop].append(sid)
                at(current + student["traits"]["patience"] / 60, "patience", sid=sid, shop=shop)
                next_customer(shop)
            elif kind == "patience":
                shop = data["shop"]
                if sid in queues[shop] and state["students"][sid]["status"] == st.QUEUING:
                    queues[shop].remove(sid)
                    handle_decision(sid, send({"type": "patience_expired", "student": sid, "shop": shop}))
                    next_customer(shop)
            elif kind == "auto_done":
                shop = data["shop"]
                busy[shop] = False
                if sid in queues[shop]:
                    queues[shop].remove(sid)
                    send({"type": "auto_serve", "student": sid, "shop": shop})
                next_customer(shop)
            elif kind == "checkout_done":
                shop = data["shop"]
                busy[shop] = False
                if sid in queues[shop]:
                    queues[shop].remove(sid)
                    send({"type": "checkout", "shop": shop, "student": sid, "player_inside": True})
                next_customer(shop)
            elif kind == "manual_done":
                shop = data["shop"]
                busy[shop] = False
                if state["current_order"] and state["current_order"]["student"] == sid:
                    for p in data["items"]:
                        if mechanics.of(shop).service == "assembly":
                            send({"type": "assemble", "shop": shop, "player_inside": True,
                                  "ingredients": list(CONFIG["products"][p]["uses"])})
                        else:
                            send({"type": "prepare", "shop": shop, "product": p, "player_inside": True})
                    send({"type": "handover", "shop": shop, "student": sid, "player_inside": True})
                if sid in queues[shop]:
                    queues[shop].remove(sid)
                next_customer(shop)
        t = t_next
    return state


def purchases(state: dict) -> list[tuple]:
    return sorted(
        (sid, p["shop"], tuple(p["items"]), round(p["time"], 4))
        for sid, s in state["students"].items() for p in s["purchases"]
    )


def morning_setup(state: dict) -> dict:
    """Plan, buy and stock a typical day so a simulation can start at 08:00."""
    def go(ev, t):
        nonlocal state
        state, _ = logic.apply(state, dict(ev, t=t))
    go({"type": "confirm_plan", "plan": {"coffee": 25, "orange_juice": 6, "pastel_de_nata": 12}}, 5.2)
    go({"type": "enter_wholesaler"}, 5.6)
    for i, item in enumerate(state["shopping_list"]):  # take each item from its stand
        go({"type": "set_cart_item", "item": item, "qty": state["shopping_list"][item]}, 5.7 + i * 0.05)
    go({"type": "pay"}, 6.0)
    go({"type": "stock_goods", "shop": "cafe"}, 6.6)
    return state


def play_morning(state: dict) -> dict:
    """A good player's morning in the shop he runs: plan like a manager would, buy, stock, fill."""
    shop = logic.work_shop(state)
    if shop is None:
        return state

    def go(ev, t):
        nonlocal state
        try:
            state, _ = logic.apply(state, dict(ev, t=t))
        except logic.GameError:
            pass

    plan = logic.manager_proposal(state, shop)["plan"]
    go({"type": "confirm_plan", "plan": plan}, 5.2)
    go({"type": "enter_wholesaler"}, 5.6)
    budget = state["money"]
    for i, (item, packs) in enumerate(state["shopping_list"].items()):
        n = min(packs, budget // CONFIG["wholesale_items"][item]["price"])
        budget -= n * CONFIG["wholesale_items"][item]["price"]
        if n:
            go({"type": "set_cart_item", "item": item, "qty": n}, 5.7 + i * 0.02)
    if state["cart"]:
        go({"type": "pay"}, 6.0)
    go({"type": "leave_wholesaler"}, 6.1)
    if state["bag"]:
        go({"type": "stock_goods", "shop": shop}, 6.6)
    if mechanics.of(shop).front_products():
        go({"type": "fill_front", "shop": shop}, 6.8)
    go({"type": "set_prices", "shop": shop, "prices": dict(state["shops"][shop]["prices"])}, 6.9)
    return state


def play_evening(state: dict, reserve: int) -> tuple[dict, list[tuple]]:
    """Hire a manager as soon as possible, buy the next shop as soon as allowed."""
    done = []

    def go(ev):
        nonlocal state
        state, _ = logic.apply(state, dict(ev, t=state["time"]))
        done.append((state["day"], ev["type"], ev.get("shop")))

    for shop in logic.owned_shops(state):
        if not state["shops"][shop]["manager_hired"] and state["money"] - logic.manager_cost(shop) >= reserve:
            go({"type": "hire_manager", "shop": shop})
    target = logic.next_target(state)
    if target and logic.buy_blocker(state, target) is None and state["money"] - logic.acquisition_cost(target) >= reserve:
        go({"type": "buy_shop", "shop": target})
    return state, done


def simulate_campaign(seed: int, max_days: int = 80, reserve: int = 4_000, speed: int = 8) -> dict:
    """Play whole games with the simple strategy of the balance target (brief 14.6).

    Returns the day each shop was bought and the day of the victory (None if not reached)."""
    state = logic.new_game(seed=seed)
    bought: dict[str, int] = {}
    hired: dict[str, int] = {}
    while state["day"] <= max_days and state["status"] == logic.RUNNING:
        state = play_morning(state)
        state = simulate_day(state, speed=speed, fast=True)
        if state["status"] != logic.RUNNING:
            break
        state, actions = play_evening(state, reserve)
        for day, kind, shop in actions:
            (bought if kind == "buy_shop" else hired)[shop] = day
        if state["status"] != logic.RUNNING:
            break
        state, _ = logic.apply(state, {"type": "next_day", "t": 21.0})
    return {"seed": seed, "bought": bought, "hired": hired, "status": state["status"], "days": state["day"],
            "money": state["money"]}


if __name__ == "__main__":
    import statistics
    import sys

    if "--campaign" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1]) if "--seeds" in sys.argv else 10
        days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 60
        runs = [simulate_campaign(seed, max_days=days) for seed in range(1, seeds + 1)]
        target = CONFIG["balance_target"]
        print("shop            median day  min  max   target")
        for k, shop in enumerate(logic.SHOP_ORDER[1:]):
            got = [r["bought"][shop] for r in runs if shop in r["bought"]]
            want = target["first_purchase_day"] + k * target["days_per_further_shop"]
            if got:
                print(f"{shop:15} {statistics.median(got):10} {min(got):4} {max(got):4}   {want}   ({len(got)}/{len(runs)} runs)")
            else:
                print(f"{shop:15}          -              {want}   (0/{len(runs)} runs)")
        print("victories:", sum(r["status"] == logic.VICTORY for r in runs), "of", len(runs))
        sys.exit(0)

    for seed in (1, 2, 3):
        s = simulate_day(morning_setup(logic.new_game(seed=seed)), speed=8)
        print(seed, s["summary"]["revenue"], s["summary"]["profit"], s["summary"]["served"],
              s["summary"]["lost"], s["summary"]["market_share"], s["summary"]["spoiled_value"])
