"""Streamlit screens for Nova Campus Tycoon (UI only).

This module only renders screens and reacts to clicks. Game rules live in
logic.py, storage lives in db.py, the 3D view lives in campus3d.py.
Every action is: call a logic function, save the new state, rerun.

Run with: uv run streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import campus3d
import db
import logic
from logic import CONFIG, GameError, format_money

st.set_page_config(page_title="Nova Campus Tycoon", page_icon="☕", layout="wide")

PHASE_LABELS = {
    logic.MORNING: "🌅 Morning planning",
    logic.SELLING: "☕ Selling day",
    logic.SUMMARY: "📊 End of day",
    logic.FINISHED: "🏁 Finished",
}

conn = db.connect(db.DEFAULT_DB_PATH)
ss = st.session_state
ss.setdefault("game_id", None)
ss.setdefault("flash", [])
ss.setdefault("nonce", 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def shop_name(shop_id: str) -> str:
    return CONFIG["shops"][shop_id]["name"]


def product_name(product: str) -> str:
    return CONFIG["products"][product]["name"]


def ingredient_name(ingredient: str) -> str:
    return CONFIG["ingredients"][ingredient]["name"]


def act(action, *args, success: str | None = None) -> None:
    """Run a logic action on the current game, save it and rerun."""
    game = db.load_game(conn, ss.game_id)
    try:
        new = action(game, *args)
    except GameError as error:
        ss.flash.append(("error", str(error)))
    else:
        db.save_game(conn, new)
        if success:
            ss.flash.append(("success", success))
        ss.nonce += 1  # resets input widgets after a successful action
    st.rerun()


def show_flash() -> None:
    for kind, message in ss.flash:
        (st.error if kind == "error" else st.success)(message)
    ss.flash = []


def header(game: logic.Game) -> None:
    left, middle, right = st.columns([3, 1.6, 1.2], vertical_alignment="center")
    left.markdown("## ☕ Nova Campus Tycoon")
    middle.markdown(f"**Day {game.day}**  \n{PHASE_LABELS[game.phase]}")
    right.metric("Balance", format_money(game.balance_cents))


def sidebar(game: logic.Game) -> None:
    with st.sidebar:
        st.subheader("Your shops")
        for shop_id in logic.SHOP_IDS:
            shop = game.shops[shop_id]
            owner = "✅ yours" if shop.owner == "player" else "🤖 competitor bot"
            st.markdown(f"**{shop_name(shop_id)}** ({owner})")
            st.caption(
                f"Utility factor {logic.shop_factor(shop):.2f}"
                + (" · 👩‍🍳 employee" if shop.has_employee else "")
            )
            if shop.owner == "player":
                st.dataframe(
                    pd.DataFrame(
                        {"Ingredient": [ingredient_name(i) for i in shop.inventory],
                         "Stock": list(shop.inventory.values())}
                    ),
                    hide_index=True,
                    width="stretch",
                )
        st.divider()
        if st.button("💾 Save & quit", width="stretch"):
            ss.game_id = None
            st.rerun()
        st.caption("Your game is saved after every action.")


def campus_view(game: logic.Game) -> None:
    with st.expander("🌳 3D campus view", expanded=True):
        st.iframe(campus3d.campus_html(game, 380), height=390)
        st.caption("Drag to rotate, scroll to zoom. Green roof = your shop, red roof = competitor.")


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


def start_screen() -> None:
    st.title("☕ Nova Campus Tycoon")
    st.markdown(
        "You own a small café on campus. Buy ingredients, set your prices, serve students "
        "and grow until you own **every shop on campus**. You start with **€100.00**; "
        "if your balance is €0.00 or below at the end of a day, the game is over."
    )
    show_flash()
    latest = db.latest_game_id(conn)
    col1, col2, _ = st.columns([1, 1, 3])
    if col1.button("🆕 New game", type="primary", width="stretch"):
        ss.game_id = db.save_game(conn, logic.new_game())
        st.rerun()
    if latest is not None:
        if col2.button("▶️ Continue", width="stretch"):
            ss.game_id = latest
            st.rerun()


def wholesaler_tab(game: logic.Game) -> None:
    st.markdown("Ingredients spoil at the end of the day. One unit makes one product.")
    for shop_id in logic.player_shops(game):
        st.markdown(f"#### For {shop_name(shop_id)}")
        cols = st.columns(len(logic.shop_ingredients(shop_id)) + 1)
        quantities = {}
        for col, ingredient in zip(cols, logic.shop_ingredients(shop_id)):
            cost = CONFIG["ingredients"][ingredient]["cost"]
            quantities[ingredient] = int(
                col.number_input(
                    f"{ingredient_name(ingredient)} ({format_money(cost)})",
                    min_value=0, step=1, value=0,
                    key=f"buy-{shop_id}-{ingredient}-{ss.nonce}",
                )
            )
        total = logic.purchase_cost(quantities)
        cols[-1].metric("Total cost", format_money(total))
        if cols[-1].button("Buy", key=f"buy-{shop_id}", type="primary"):
            act(logic.buy_ingredients, quantities, shop_id,
                success=f"Bought ingredients for {format_money(total)}.")


def prices_tab(game: logic.Game) -> None:
    st.markdown(f"Prices between €0.01 and {format_money(CONFIG['max_price'])}.")
    for shop_id in logic.player_shops(game):
        shop = game.shops[shop_id]
        st.markdown(f"#### {shop_name(shop_id)}")
        cols = st.columns(len(shop.prices) + 1)
        new_prices = {}
        for col, (product, price) in zip(cols, shop.prices.items()):
            euros = col.number_input(
                product_name(product), min_value=0.0, max_value=10.0, step=0.10,
                value=price / 100, format="%.2f", key=f"price-{shop_id}-{product}-{ss.nonce}",
            )
            new_prices[product] = int(round(euros * 100))
        if cols[-1].button("Save prices", key=f"prices-{shop_id}"):
            act(logic.set_prices, shop_id, new_prices, success="Prices saved.")
    if game.shops["competitor"].owner == "bot":
        bot = game.shops["competitor"]
        st.caption(
            "Competitor prices (fixed): "
            + ", ".join(f"{product_name(p)} {format_money(c)}" for p, c in bot.prices.items())
        )


def growth_tab(game: logic.Game) -> None:
    for shop_id in logic.player_shops(game):
        shop = game.shops[shop_id]
        st.markdown(f"#### {shop_name(shop_id)} · utility factor {logic.shop_factor(shop):.2f}")
        cols = st.columns(4)
        for col, (upgrade, spec) in zip(cols, CONFIG["upgrades"].items()):
            col.markdown(f"**{spec['name']}**  \n+{spec['factor_bonus']:.2f} · {format_money(spec['cost'])}")
            if upgrade in shop.upgrades:
                col.success("Bought")
            elif col.button("Buy upgrade", key=f"up-{shop_id}-{upgrade}"):
                act(logic.buy_upgrade, shop_id, upgrade, success=f"{spec['name']} bought.")
        with cols[3]:
            st.markdown(f"**Employee**  \nServes automatically · {format_money(CONFIG['employee_cost'])}")
            if shop.has_employee:
                st.success("Hired")
            elif st.button("Hire employee", key=f"hire-{shop_id}"):
                act(logic.hire_employee, shop_id, success="Employee hired.")

    if game.shops["competitor"].owner == "bot":
        st.markdown("#### 🏢 Buy the competitor")
        st.markdown(
            f"Costs {format_money(CONFIG['acquisition_cost'])}. "
            "Requires an employee in your café. You then control its prices, ingredients and upgrades."
        )
        if st.button("Buy competitor café", type="primary"):
            act(logic.buy_competitor, success="You now own the competitor café!")


def morning_screen(game: logic.Game) -> None:
    tabs = st.tabs(["🏪 Wholesaler", "💶 Prices", "⭐ Upgrades & staff"])
    with tabs[0]:
        wholesaler_tab(game)
    with tabs[1]:
        prices_tab(game)
    with tabs[2]:
        growth_tab(game)

    st.divider()
    owned = logic.player_shops(game)
    unstaffed = [s for s in owned if not game.shops[s].has_employee]
    if len(owned) > 1 and unstaffed:
        current = game.manual_shop if game.manual_shop in owned else owned[0]
        choice = st.radio(
            "Which shop do you serve in person today?", owned,
            index=owned.index(current), format_func=shop_name, horizontal=True,
            key=f"manual-{ss.nonce}",
        )
        if choice != game.manual_shop:
            act(logic.set_manual_shop, choice)
        for shop_id in unstaffed:
            if shop_id != choice:
                st.warning(f"Nobody works in the {shop_name(shop_id)} today: its customers will leave.")
    if st.button("🔔 Open shop", type="primary", width="stretch"):
        act(logic.open_shop)


def order_text(order: logic.Order, shop: logic.Shop) -> str:
    items = ", ".join(product_name(i) for i in order.items)
    value = sum(shop.prices[i] for i in order.items)
    return f"Student {order.student + 1}: {items} ({format_money(value)})"


def selling_screen(game: logic.Game) -> None:
    budget = CONFIG["day_time_budget"]
    cols = st.columns(2)
    for col, shop_id in zip(cols, logic.SHOP_IDS):
        shop = game.shops[shop_id]
        stats = game.stats[shop_id]
        queue = game.queues[shop_id]
        with col:
            st.markdown(f"### {shop_name(shop_id)}")
            if shop.owner == "bot":
                st.info(f"🤖 The competitor served {stats.served} customers "
                        f"and earned {format_money(stats.revenue)}.")
                continue
            st.progress(max(stats.time_left, 0) / budget,
                        text=f"⏱️ Preparation time left: {stats.time_left} s of {budget} s")
            st.caption(f"Served {stats.served} · lost {stats.lost} · revenue {format_money(stats.revenue)}")
            if shop.has_employee:
                st.success("👩‍🍳 Your employee served this shop's customers.")
            elif shop_id != game.manual_shop:
                st.warning("Closed today: nobody worked here.")
            elif queue:
                nxt = queue[0]
                need = logic.order_prep_time(shop, nxt)
                st.markdown(f"**Next:** {order_text(nxt, shop)} · needs {need} s")
                missing = [
                    product_name(i) for i in nxt.items
                    if shop.inventory.get(CONFIG["products"][i]["ingredient"], 0) == 0
                ]
                if missing:
                    st.caption("Out of stock: " + ", ".join(missing))
                if st.button("✅ Accept next order", type="primary", key=f"accept-{shop_id}"):
                    act(logic.accept_next_order, shop_id)
                if len(queue) > 1:
                    st.markdown("**Waiting:**")
                    for order in queue[1:]:
                        st.markdown(f"- {order_text(order, shop)}")
            else:
                st.success("No customers waiting.")
    st.divider()
    if st.button("🌙 End day", width="stretch"):
        act(logic.end_day)


def summary_tables(summary: dict) -> None:
    rows = []
    for shop_id, s in summary["shops"].items():
        if s["owner"] != "player":
            continue
        rows.append({
            "Shop": shop_name(shop_id),
            "Customers served": s["served"],
            "Customers lost": s["lost"],
            "Revenue": format_money(s["revenue"]),
            "Ingredient cost": format_money(s["ingredient_cost"]),
            "Spoiled": format_money(s["spoiled_value"]),
            "Upgrades & staff": format_money(s["spending"]),
            "Profit": format_money(s["profit"]),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    sold = {}
    for shop_id, s in summary["shops"].items():
        who = "You" if s["owner"] == "player" else "Competitor"
        for product, count in s["sold"].items():
            sold.setdefault(product_name(product), {})[who] = count
    if sold:
        st.markdown("**Units sold per product**")
        st.bar_chart(pd.DataFrame(sold).T.fillna(0), stack=False)


def summary_screen(game: logic.Game) -> None:
    summary = game.history[-1]
    c1, c2, c3 = st.columns(3)
    c1.metric("Profit today", format_money(summary["profit"]))
    c2.metric("Balance", format_money(summary["balance"]))
    c3.metric("Your market share", f"{summary['market_share'] * 100:.0f}%")
    summary_tables(summary)
    if len(game.history) > 1:
        st.markdown("**Balance over time**")
        st.line_chart(pd.DataFrame(
            {"Balance (€)": [h["balance"] / 100 for h in game.history]},
            index=[h["day"] for h in game.history],
        ))
    if st.button("☀️ Next day", type="primary", width="stretch"):
        act(logic.next_day)


def finished_screen(game: logic.Game) -> None:
    if game.status == logic.VICTORY:
        st.balloons()
        st.success(
            f"🏆 Monopoly! You own every shop on campus after {game.day} days "
            f"with a total profit of {format_money(game.total_profit)}."
        )
    else:
        st.error(f"💸 Game over on day {game.day}: your balance dropped to {format_money(game.balance_cents)}.")
    if game.history:
        summary_tables(game.history[-1])
    if st.button("🆕 New game", type="primary"):
        ss.game_id = db.save_game(conn, logic.new_game())
        st.rerun()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

game = db.load_game(conn, ss.game_id) if ss.game_id is not None else None
if game is None:
    ss.game_id = None
    start_screen()
else:
    header(game)
    show_flash()
    sidebar(game)
    campus_view(game)
    screens = {
        logic.MORNING: morning_screen,
        logic.SELLING: selling_screen,
        logic.SUMMARY: summary_screen,
        logic.FINISHED: finished_screen,
    }
    screens[game.phase](game)
