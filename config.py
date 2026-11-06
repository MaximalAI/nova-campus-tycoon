"""All balancing values for Nova Campus Tycoon v2 in one place.

Money is in cents. Game time is in hours (5.5 = 05:30). Durations of actions
are in game minutes; at 1x speed one game minute lasts one real second.
The whole dict is JSON-compatible and is also sent to the browser.
"""

CONFIG = {
    "time": {
        "day_start": 5.0,
        "open": 8.0,
        "last_customer": 19.75,
        "close": 20.0,
        "day_end": 21.0,
        "real_seconds_per_game_hour": 60,
        "speeds": [1, 2, 4, 8],
        # Before this hour the clock pauses while a dialog is open.
        "dialogs_pause_clock_before": 8.0,
        "earliest_manual_open": 7.0,
        "fast_service_minutes": 12,
    },
    "start_money": 5_000,
    # Suggested portions in the first day planning (the player changes them).
    "start_plan": {"coffee": 20, "orange_juice": 4, "pastel_de_nata": 10},
    "students": {
        "pool_size": 25,
        "budget": 1_000,
        "utility_min": 30,
        "utility_max": 300,
        "patience_minutes": [30, 60],
        "walk_speed": [1.9, 2.6],  # metres per real second at 1x
        "fickleness": [0.7, 1.3],  # multiplies the café probability
        "decide_every_minutes": [20, 45],
        "schedule_step_minutes": 5,
        "max_change_per_step": 4,
        "names": [
            "Ana", "João", "Mia", "Lukas", "Inês", "Tiago", "Sofia", "Leon", "Beatriz",
            "Noah", "Marta", "Rui", "Emma", "Diogo", "Clara", "Pedro", "Lea", "Tomás",
            "Hannah", "Miguel", "Rita", "Felix", "Carolina", "Jonas", "Luísa",
        ],
    },
    "max_queue": 4,
    "reputation": {
        "start": 50,
        "factor_range": [0.8, 1.2],
        "correct_order": 2,
        "fast_bonus": 1,
        "wrong_order": -4,
        "customer_lost": -1,
        "cleaning_missed": -5,
    },
    # Daily phases: how many students are on campus and how likely they visit a café.
    "phases": [
        {"name": "Night", "from": 5.0, "to": 7.5, "target": 0, "cafe_probability": 0.0},
        {"name": "Early morning", "from": 7.5, "to": 8.0, "target": 3, "cafe_probability": 0.9},
        {"name": "Morning rush", "from": 8.0, "to": 9.0, "target": 18, "cafe_probability": 0.8},
        {"name": "Morning lectures", "from": 9.0, "to": 12.0, "target": 6, "cafe_probability": 0.15},
        {"name": "Lunch break", "from": 12.0, "to": 13.5, "target": 25, "cafe_probability": 0.9},
        {"name": "Afternoon lectures", "from": 13.5, "to": 16.0, "target": 4, "cafe_probability": 0.15},
        {"name": "Late afternoon", "from": 16.0, "to": 18.0, "target": 10, "cafe_probability": 0.4},
        {"name": "Evening", "from": 18.0, "to": 20.0, "target": 2, "cafe_probability": 0.2},
        {"name": "Closed", "from": 20.0, "to": 21.0, "target": 0, "cafe_probability": 0.0},
    ],
    # Lighting keyframes; values in between are interpolated smoothly.
    "lighting": [
        {"t": 5.0, "name": "dawn", "sky": [0.05, 0.07, 0.18], "sun_color": [0.55, 0.6, 0.9], "sun": 0.08, "ambient": 0.28, "elevation": 4, "azimuth": 80, "lamps": 1.0},
        {"t": 7.0, "name": "sunrise", "sky": [0.98, 0.62, 0.42], "sun_color": [1.0, 0.62, 0.38], "sun": 0.7, "ambient": 0.45, "elevation": 6, "azimuth": 90, "lamps": 0.5},
        {"t": 8.5, "name": "daylight", "sky": [0.62, 0.8, 1.0], "sun_color": [1.0, 0.93, 0.8], "sun": 1.25, "ambient": 0.62, "elevation": 28, "azimuth": 115, "lamps": 0.0},
        {"t": 13.0, "name": "daylight", "sky": [0.55, 0.78, 1.0], "sun_color": [1.0, 1.0, 0.96], "sun": 1.55, "ambient": 0.72, "elevation": 66, "azimuth": 185, "lamps": 0.0},
        {"t": 17.5, "name": "sunset", "sky": [0.62, 0.78, 0.98], "sun_color": [1.0, 0.9, 0.75], "sun": 1.2, "ambient": 0.6, "elevation": 24, "azimuth": 250, "lamps": 0.0},
        {"t": 19.5, "name": "dusk", "sky": [0.96, 0.5, 0.46], "sun_color": [1.0, 0.5, 0.42], "sun": 0.5, "ambient": 0.4, "elevation": 3, "azimuth": 275, "lamps": 0.8},
        {"t": 21.0, "name": "dusk", "sky": [0.06, 0.08, 0.22], "sun_color": [0.55, 0.6, 0.9], "sun": 0.08, "ambient": 0.28, "elevation": 4, "azimuth": 285, "lamps": 1.0},
    ],
    "wholesale_items": {
        "coffee_beans": {
            "name": "Coffee beans", "icon": "🫘", "unit": "250 g pack", "price": 400,
            "base_units": 25, "base_name": "portions", "shelf_days": None, "needs_rival": False,
            "description": "Freshly roasted Arabica beans. One pack makes 25 cups.",
        },
        "oranges": {
            "name": "Oranges", "icon": "🍊", "unit": "net of 6", "price": 200,
            "base_units": 6, "base_name": "oranges", "shelf_days": 3, "needs_rival": False,
            "description": "Juicy oranges from the Algarve. One glass of juice takes three.",
        },
        "nata": {
            "name": "Pastel de nata", "icon": "🥧", "unit": "piece", "price": 60,
            "base_units": 1, "base_name": "pieces", "shelf_days": 1, "needs_rival": False,
            "description": "Baked this morning. Spoils overnight, so only buy what you can sell.",
        },
        "tea_leaves": {
            "name": "Tea", "icon": "🌿", "unit": "box of 20 bags", "price": 240,
            "base_units": 20, "base_name": "bags", "shelf_days": None, "needs_rival": True,
            "description": "Green and black tea for your second café.",
        },
        "croissant_dough": {
            "name": "Croissant", "icon": "🥐", "unit": "piece", "price": 50,
            "base_units": 1, "base_name": "pieces", "shelf_days": 1, "needs_rival": True,
            "description": "Butter croissant, ready to bake. Spoils overnight.",
        },
    },
    "products": {
        "coffee": {
            "name": "Coffee (bica)", "icon": "☕", "uses": {"coffee_beans": 1},
            "station": "coffee_machine", "prep_minutes": 5,
            "description": "A strong Portuguese espresso.",
        },
        "orange_juice": {
            "name": "Orange juice (0.25 l)", "icon": "🧃", "uses": {"oranges": 3},
            "station": "juicer", "prep_minutes": 6,
            "description": "Freshly squeezed, no sugar.",
        },
        "pastel_de_nata": {
            "name": "Pastel de nata", "icon": "🥧", "uses": {"nata": 1},
            "station": "display_case", "prep_minutes": 1,
            "description": "Crispy puff pastry with custard and cinnamon.",
        },
        "tea": {
            "name": "Tea", "icon": "🍵", "uses": {"tea_leaves": 1},
            "station": "kettle", "prep_minutes": 4,
            "description": "Hot tea of your choice.",
        },
        "croissant": {
            "name": "Croissant", "icon": "🥐", "uses": {"croissant_dough": 1},
            "station": "display_case", "prep_minutes": 1,
            "description": "Warm and buttery.",
        },
    },
    "shops": {
        "cafe": {
            "name": "Your Café", "products": ["coffee", "orange_juice", "pastel_de_nata"],
            "base_factor": 1.0, "start_owner": "player",
            "start_prices": {"coffee": 90, "orange_juice": 250, "pastel_de_nata": 130},
        },
        "rival": {
            "name": "Café da Esquina", "products": ["coffee", "tea", "croissant"],
            "base_factor": 1.2, "start_owner": "bot",
            "start_prices": {"coffee": 100, "tea": 120, "croissant": 150},
        },
    },
    "price_step": 10,
    "max_price": 1_000,
    "upgrades": {
        "coffee_machine": {"name": "Better coffee machine", "icon": "⚙️", "factor_bonus": 0.15, "cost": 6_000},
        "seating": {"name": "Seating & decor", "icon": "🪴", "factor_bonus": 0.20, "cost": 12_000},
        "branding": {"name": "Sign & branding", "icon": "🪧", "factor_bonus": 0.25, "cost": 20_000},
    },
    "manager_cost": 20_000,
    # After you buy the competitor, its barista keeps selling automatically and
    # orders supplies every morning (and right after the purchase) for this plan.
    "rival_restock_plan": {"coffee": 20, "tea": 15, "croissant": 15},
    "acquisition_cost": 50_000,
    "cleaning_spots": {
        "counter": {"name": "Wipe the counter", "minutes": 3},
        "coffee_machine": {"name": "Clean the coffee machine", "minutes": 3},
        "tables": {"name": "Clear the tables", "minutes": 3},
        "floor": {"name": "Sweep the floor", "minutes": 3},
    },
}
