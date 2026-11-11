"""v7 step 1: data model, buying order, migration of old saves (brief section 14)."""

import json
import pathlib
import re

import pytest

import logic
import simulation as sim
import students as st
from config import CONFIG
from logic import GameError

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
NEW_SHOPS = [s for s in CONFIG["shops"] if s not in ("cafe", "rival")]


def go(state, t=6.0, **event):
    return logic.apply(state, dict(event, t=t))


def next_day(state):
    state, _ = go(state, t=21.0, type="tick")
    state, _ = go(state, t=21.0, type="next_day")
    return state


# --- config -----------------------------------------------------------------------------


def test_every_shop_is_complete_data():
    orders = []
    for shop, spec in CONFIG["shops"].items():
        for key in ("name", "products", "order", "zone", "start_prices", "manager_cost", "max_queue", "mechanic"):
            assert key in spec, (shop, key)
        assert spec["zone"] in CONFIG["zones"]
        assert set(spec["start_prices"]) == set(spec["products"])
        assert len(spec["products"]) == 3
        orders.append(spec["order"])
        for product in spec["products"]:
            for item in CONFIG["products"][product]["uses"]:
                assert item in CONFIG["wholesale_items"], (product, item)
    assert sorted(orders) == list(range(1, len(orders) + 1))


def test_acquisition_prices_rise_from_shop_to_shop():
    prices = [logic.acquisition_cost(s) for s in logic.SHOP_ORDER[1:]]
    assert prices == sorted(prices) and len(set(prices)) == len(prices)


def test_logic_has_no_if_chains_on_new_shop_names():
    source = (pathlib.Path(logic.__file__)).read_text()
    for shop in NEW_SHOPS:
        assert not re.search(rf"[\"']{shop}[\"']", source), shop


def test_config_is_json_for_the_browser():
    assert json.loads(json.dumps(CONFIG))["shops"].keys() == CONFIG["shops"].keys()


# --- buying order -----------------------------------------------------------------------


@pytest.fixture
def rich():
    state = logic.new_game(seed=11)
    state["money"] = 5_000_000
    return state


def test_only_the_next_shop_is_for_sale(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    assert logic.next_target(state) == "rival"
    with pytest.raises(GameError, match="first"):
        go(state, type="buy_shop", shop=NEW_SHOPS[0])
    state, res = go(state, type="buy_shop", shop="rival")
    assert res["bought"] == "rival"
    state = next_day(state)
    assert logic.next_target(state) == NEW_SHOPS[0]


def test_every_owned_shop_needs_a_hired_manager_before_buying(rich):
    with pytest.raises(GameError, match="manager in every shop"):
        go(rich, type="buy_shop")
    state, _ = go(rich, type="hire_manager", shop="cafe")
    state, _ = go(state, type="buy_shop")
    state = next_day(state)
    view = logic.view(state)
    assert view["for_sale"] is None and "Café da Esquina" in view["buy_blocker"]
    state, _ = go(state, type="hire_manager", shop="rival")  # hired counts, he starts tomorrow
    assert logic.view(state)["for_sale"] == NEW_SHOPS[0]
    state, _ = go(state, type="buy_shop")
    assert state["shops"][NEW_SHOPS[0]]["sold"] and state["shops"][NEW_SHOPS[0]]["owner"] == "bot"
    state = next_day(state)
    assert state["shops"][NEW_SHOPS[0]]["owner"] == "player"
    assert logic.work_shop(state) == NEW_SHOPS[0]


def test_prices_and_managers_cost_what_the_config_says(rich):
    state, _ = go(rich, type="hire_manager", shop="cafe")
    money = state["money"]
    state, _ = go(state, type="buy_shop")
    assert money - state["money"] == CONFIG["shops"]["rival"]["acquisition_cost"]
    state = next_day(state)
    money = state["money"]
    state, _ = go(state, type="hire_manager", shop="rival")
    assert money - state["money"] == CONFIG["shops"]["rival"]["manager_cost"]


def test_wholesaler_sells_new_items_once_you_own_the_shop(rich):
    shop = NEW_SHOPS[0]
    item = next(iter(CONFIG["products"][CONFIG["shops"][shop]["products"][0]]["uses"]))
    assert not logic.item_available(rich, item)
    rich["shops"][shop]["owner"] = "player"
    assert logic.item_available(rich, item)
    # coffee beans are always there (your café)
    assert logic.item_available(rich, "coffee_beans")


def test_new_shops_trade_from_day_one_as_bots():
    state, _ = go(logic.new_game(seed=4), t=8.0, type="tick")
    for shop in NEW_SHOPS:
        assert logic.is_auto(state, shop) and logic.shop_operating(state, shop)
    s = state["students"]["s3"]
    product = CONFIG["shops"][NEW_SHOPS[0]]["products"][0]
    s["status"], s["intent"] = st.QUEUING, {"shop": NEW_SHOPS[0], "items": [product]}
    state, res = go(state, t=8.2, type="auto_serve", shop=NEW_SHOPS[0], student="s3")
    assert res["items"] == [product] and state["money"] == CONFIG["start_money"]
    assert state["stats"]["shops"][NEW_SHOPS[0]]["revenue"] == CONFIG["shops"][NEW_SHOPS[0]]["start_prices"][product]


def test_a_simulated_day_sells_in_the_new_shops():
    state = sim.simulate_day(sim.morning_setup(logic.new_game(seed=3)), speed=8)
    sold = {s: state["stats"]["shops"][s]["served"] for s in NEW_SHOPS}
    assert all(n > 0 for n in sold.values()), sold
    assert state["summary"]["served"] > 0  # your café still has customers


# --- students ---------------------------------------------------------------------------


def test_old_cafes_keep_their_random_utilities():
    """A seed gives the same utilities in the two classic cafés as in v6."""
    old = json.loads((FIXTURES / "save_v6.json").read_text())
    pool = st.make_pool(old["seed"], old["day"])
    for sid, s in old["students"].items():
        for key, u in s["utilities"].items():
            assert pool[sid]["utilities"][key] == pytest.approx(u)


def test_a_visit_goes_to_one_shop_with_the_best_bundle():
    student = {"id": "x", "budget": 1_000, "utilities": {
        st.offering_key(s, p): 1.0 for s, p in st.all_offerings()}}
    best = NEW_SHOPS[0]
    for p in CONFIG["shops"][best]["products"]:
        student["utilities"][st.offering_key(best, p)] = 500.0
    prices = {st.offering_key(s, p): 100 for s, p in st.all_offerings()}
    factors = {s: 1.0 for s in CONFIG["shops"]}
    shop, items = st.choose_order(student, prices, factors, list(CONFIG["shops"]))
    assert shop == best and sorted(items) == sorted(CONFIG["shops"][best]["products"])


# --- migration --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["save_v4.json", "save_v6.json"])
def test_old_saves_load_and_play_a_day(name):
    state = logic.migrate(json.loads((FIXTURES / name).read_text()))
    assert set(state["shops"]) == set(CONFIG["shops"])
    for shop in NEW_SHOPS:
        assert state["shops"][shop]["owner"] == "bot"
    assert state["shops"]["cafe"]["manager_hired"]
    logic.view(state)
    if logic.work_shop(state):
        state = sim.morning_setup(state)
    state = sim.simulate_day(state, speed=8)
    assert state["day_state"] == logic.DAY_SUMMARY
    state, _ = go(state, t=21.0, type="next_day")
    assert len(state["students"]) == CONFIG["students"]["pool_size"]


def test_a_won_v6_game_continues_with_the_new_goal():
    state = logic.migrate(json.loads((FIXTURES / "save_v6_victory.json").read_text()))
    assert state["status"] == logic.RUNNING
    assert state["shops"]["rival"]["owner"] == "player"
    assert logic.next_target(state) == NEW_SHOPS[0]
    assert logic.view(state)["for_sale"] == NEW_SHOPS[0]
