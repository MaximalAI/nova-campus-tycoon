"""All balancing values for Nova Campus Tycoon in one place.

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
        # Before this hour the clock pauses while a dialog is open (v5: never, the clock keeps running).
        "dialogs_pause_clock_before": 5.0,
        # A manager buys the goods he proposed at this time if you did not confirm the proposal.
        "manager_buys_at": 7.0,
        "earliest_manual_open": 7.0,
        "fast_service_minutes": 12,
    },
    "start_money": 5_000,
    # Suggested portions in the first day planning (the player changes them).
    "start_plan": {"coffee": 20, "orange_juice": 4, "pastel_de_nata": 10},
    "students": {
        "pool_size": 40,  # v7: 25 -> 40, so nine shops still find customers
        "budget": 2_800,  # v7: 1_600 -> 2_800, more shops to spend it in
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
            # v7: the campus pool grew from 25 to 40
            "Gonçalo", "Mariana", "Ben", "Leonor", "Duarte", "Laura", "Afonso", "Matilde",
            "Paul", "Francisca", "Henrique", "Sara", "Max", "Joana", "Vasco",
        ],
    },
    "max_queue": 4,  # default; every shop has its own "max_queue"
    "reputation": {
        "start": 50,
        # What a good reputation brings (v4): more customers choose your café,
        # customers wait longer and happy customers leave a tip.
        "factor_range": [0.7, 1.3],  # demand factor at reputation 0 and 100
        "patience_range": [0.75, 1.35],  # patience multiplier at reputation 0 and 100
        "tips": [[60, 0.05], [75, 0.10], [90, 0.15]],  # from this reputation on: share of the bill
        "correct_order": 2,
        "staff_served": 1,  # a happy customer served by your manager
        "fast_bonus": 1,
        "wrong_order": -4,
        "customer_lost": -3,  # waited too long and left
        "sold_out_left": -1,  # found the shelves empty and left (once per student and day)
        "order_cancelled": -3,  # you cancelled an accepted order
        "rejected": -1,  # you turned the customer away
        "cleaning_missed": -5,
    },
    # Daily phases: how many students are on campus and how likely they visit a café.
    "phases": [
        {"name": "Night", "from": 5.0, "to": 7.5, "target": 0, "cafe_probability": 0.0},
        {"name": "Early morning", "from": 7.5, "to": 8.0, "target": 3, "cafe_probability": 0.9},
        {"name": "Morning rush", "from": 8.0, "to": 9.0, "target": 24, "cafe_probability": 0.8},
        # v5: a few students also come during lectures, so there is never a long empty wait
        {"name": "Morning lectures", "from": 9.0, "to": 12.0, "target": 16, "cafe_probability": 0.85},
        # v7: the lunch rush (12:00 to 14:00) brings everybody to campus
        {"name": "Lunch break", "from": 12.0, "to": 14.0, "target": 40, "cafe_probability": 0.9},
        {"name": "Afternoon lectures", "from": 14.0, "to": 16.0, "target": 14, "cafe_probability": 0.85},
        {"name": "Late afternoon", "from": 16.0, "to": 18.0, "target": 18, "cafe_probability": 0.75},
        {"name": "Evening", "from": 18.0, "to": 20.0, "target": 10, "cafe_probability": 0.8},
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
            "base_units": 25, "base_name": "portions", "shelf_days": None,
            "description": "Freshly roasted Arabica beans. One pack makes 25 cups.",
        },
        "oranges": {
            "name": "Oranges", "icon": "🍊", "unit": "net of 6", "price": 200,
            "base_units": 6, "base_name": "oranges", "shelf_days": 3,
            "description": "Juicy oranges from the Algarve. One glass of juice takes three.",
        },
        "nata": {
            "name": "Pastel de nata", "icon": "🥧", "unit": "piece", "price": 60,
            "base_units": 1, "base_name": "pieces", "shelf_days": 1,
            "description": "Baked this morning. Spoils overnight, so only buy what you can sell.",
        },
        "tea_leaves": {
            "name": "Tea", "icon": "🌿", "unit": "box of 20 bags", "price": 240,
            "base_units": 20, "base_name": "bags", "shelf_days": None,
            "description": "Green and black tea for your second café.",
        },
        "croissant_dough": {
            "name": "Croissant", "icon": "🥐", "unit": "piece", "price": 50,
            "base_units": 1, "base_name": "pieces", "shelf_days": 1,
            "description": "Butter croissant, ready to bake. Spoils overnight.",
        },
        # v7: an item is sold at the wholesaler once you own a shop whose products use it.
        # SnackBots
        "water": {
            "name": "Water bottles", "icon": "💧", "unit": "pack of 12", "price": 300,
            "base_units": 12, "base_name": "bottles", "shelf_days": None,
            "description": "Still water, 0.5 l bottles for the vending machine.",
        },
        "coke_zero": {
            "name": "Coke Zero cans", "icon": "🥤", "unit": "pack of 12", "price": 480,
            "base_units": 12, "base_name": "cans", "shelf_days": None,
            "description": "Cold drinks sell best in the afternoon.",
        },
        "protein_bars": {
            "name": "Protein bars", "icon": "🍫", "unit": "box of 10", "price": 600,
            "base_units": 10, "base_name": "bars", "shelf_days": None,
            "description": "For students who go to the gym after lectures.",
        },
        # Mercado & Go
        "bread": {
            "name": "Bread", "icon": "🥖", "unit": "bag of 10 rolls", "price": 200,
            "base_units": 10, "base_name": "rolls", "shelf_days": 1,
            "description": "Fresh rolls for sandwiches. Spoil overnight.",
        },
        "cheese": {
            "name": "Cheese", "icon": "🧀", "unit": "pack of 20 slices", "price": 300,
            "base_units": 20, "base_name": "slices", "shelf_days": 5,
            "description": "Queijo flamengo. One slice per sandwich.",
        },
        "iced_tea": {
            "name": "Iced tea cans", "icon": "🧋", "unit": "pack of 12", "price": 420,
            "base_units": 12, "base_name": "cans", "shelf_days": None,
            "description": "Lemon iced tea in cans.",
        },
        "apples": {
            "name": "Apples", "icon": "🍎", "unit": "bag of 8", "price": 240,
            "base_units": 8, "base_name": "apples", "shelf_days": 5,
            "description": "Crunchy apples from Alcobaça.",
        },
        # Bowl Bar
        "rice": {
            "name": "Rice", "icon": "🍚", "unit": "5 kg bag", "price": 600,
            "base_units": 25, "base_name": "portions", "shelf_days": None,
            "description": "Sushi rice. One bag makes 25 bowls.",
        },
        "salmon": {
            "name": "Salmon", "icon": "🐟", "unit": "1 kg tray", "price": 1_400,
            "base_units": 8, "base_name": "portions", "shelf_days": 2,
            "description": "Fresh salmon for poke bowls. Keeps two days.",
        },
        "acai": {
            "name": "Açaí purée", "icon": "🫐", "unit": "box of 10 packs", "price": 900,
            "base_units": 10, "base_name": "packs", "shelf_days": None,
            "description": "Frozen açaí purée, one pack per bowl.",
        },
        "fruit_mix": {
            "name": "Fruit mix", "icon": "🍓", "unit": "1 kg bag", "price": 400,
            "base_units": 8, "base_name": "portions", "shelf_days": 2,
            "description": "Cut strawberries, banana and mango.",
        },
        # Nova Mensa
        "chicken": {
            "name": "Chicken", "icon": "🍗", "unit": "box of 10 portions", "price": 1_200,
            "base_units": 10, "base_name": "portions", "shelf_days": 2,
            "description": "Grilled chicken legs for the lunch menu.",
        },
        "fries": {
            "name": "Fries", "icon": "🍟", "unit": "2.5 kg frozen bag", "price": 500,
            "base_units": 20, "base_name": "portions", "shelf_days": None,
            "description": "Frozen fries, 20 portions.",
        },
        "frozen_pizza": {
            "name": "Frozen pizza", "icon": "🍕", "unit": "box of 2 pizzas", "price": 400,
            "base_units": 8, "base_name": "slices", "shelf_days": None,
            "description": "Two pizzas, four slices each.",
        },
        "pudding_cups": {
            "name": "Pudding cups", "icon": "🍮", "unit": "pack of 12", "price": 480,
            "base_units": 12, "base_name": "cups", "shelf_days": 4,
            "description": "Pudim flan in cups.",
        },
    },
    "products": {
        "coffee": {
            "name": "Coffee (bica)", "icon": "☕", "uses": {"coffee_beans": 1},
            "station": "coffee_machine", "prep_minutes": 2,
            "description": "A strong Portuguese espresso.",
        },
        "orange_juice": {
            "name": "Orange juice (0.25 l)", "icon": "🧃", "uses": {"oranges": 3},
            "station": "juicer", "prep_minutes": 3,
            "description": "Freshly squeezed, no sugar.",
        },
        "pastel_de_nata": {
            "name": "Pastel de nata", "icon": "🥧", "uses": {"nata": 1},
            "station": "display_case", "prep_minutes": 1,
            "description": "Crispy puff pastry with custard and cinnamon.",
        },
        "tea": {
            "name": "Tea", "icon": "🍵", "uses": {"tea_leaves": 1},
            "station": "kettle", "prep_minutes": 2,
            "description": "Hot tea of your choice.",
        },
        "croissant": {
            "name": "Croissant", "icon": "🥐", "uses": {"croissant_dough": 1},
            "station": "display_case", "prep_minutes": 1,
            "description": "Warm and buttery.",
        },
        # v7. "utility": [min, max] in cents overrides the students' default utility range,
        # so expensive products (a poke bowl) still find buyers.
        "water": {
            "name": "Water", "icon": "💧", "uses": {"water": 1},
            "station": "machine", "prep_minutes": 0, "description": "Still water, 0.5 l.",
        },
        "coke_zero": {
            "name": "Coke Zero", "icon": "🥤", "uses": {"coke_zero": 1},
            "station": "machine", "prep_minutes": 0, "description": "Ice cold, no sugar.",
        },
        "protein_bar": {
            "name": "Protein bar", "icon": "🍫", "uses": {"protein_bars": 1},
            "station": "machine", "prep_minutes": 0, "description": "20 g of protein.", "utility": [60, 340],
        },
        "sandwich": {
            "name": "Sandwich", "icon": "🥪", "uses": {"bread": 1, "cheese": 2},
            "station": None, "prep_minutes": 0, "description": "Cheese sandwich, made this morning.",
            "utility": [80, 420],
        },
        "iced_tea": {
            "name": "Iced tea", "icon": "🧋", "uses": {"iced_tea": 1},
            "station": None, "prep_minutes": 0, "description": "Lemon iced tea.",
        },
        "apple": {
            "name": "Apple", "icon": "🍎", "uses": {"apples": 1},
            "station": None, "prep_minutes": 0, "description": "One apple a day.",
        },
        "poke_bowl": {
            "name": "Poke bowl", "icon": "🍣", "uses": {"rice": 1, "salmon": 1},
            "station": "assembly", "prep_minutes": 3, "description": "Rice and fresh salmon.",
            "utility": [250, 1_000],
        },
        "acai_bowl": {
            "name": "Açaí bowl", "icon": "🫐", "uses": {"acai": 1},
            "station": "assembly", "prep_minutes": 2, "description": "Cold açaí purée.",
            "utility": [180, 720],
        },
        "smoothie": {
            "name": "Smoothie", "icon": "🥤", "uses": {"fruit_mix": 1},
            "station": "assembly", "prep_minutes": 2, "description": "Blended fresh fruit.",
            "utility": [120, 480],
        },
        # What lands on the tray when the ingredients of a bowl do not match any product.
        "wrong_bowl": {
            "name": "Wrong bowl", "icon": "🥣", "uses": {}, "station": None, "prep_minutes": 0,
            "description": "This is not what anybody ordered.", "hidden": True,
        },
        "chicken_fries": {
            "name": "Chicken with fries", "icon": "🍗", "uses": {"chicken": 1, "fries": 1},
            "station": "grill", "prep_minutes": 1, "description": "The Mensa classic.",
            "utility": [200, 650],
        },
        "pizza": {
            "name": "Pizza slice", "icon": "🍕", "uses": {"frozen_pizza": 1},
            "station": "oven", "prep_minutes": 1, "description": "Hot from the oven.",
            "utility": [100, 400],
        },
        "pudding": {
            "name": "Pudding", "icon": "🍮", "uses": {"pudding_cups": 1},
            "station": "fridge", "prep_minutes": 1, "description": "Pudim flan.",
        },
    },
    # v7: the monopoly race. Shops are bought in "order"; a zone opens when every shop of the
    # zone named in "unlock_after" is yours. Money in cents. "building" is the layout the
    # browser draws for the new shops (the first two cafés have hand-built interiors).
    "zones": {
        "campus": {"name": "Campus", "unlock_after": None},
    },
    "shops": {
        "cafe": {
            "name": "Your Café", "products": ["coffee", "orange_juice", "pastel_de_nata"],
            "base_factor": 1.0, "start_owner": "player", "order": 1, "zone": "campus",
            "start_prices": {"coffee": 90, "orange_juice": 250, "pastel_de_nata": 130},
            "acquisition_cost": None, "manager_cost": 10_000, "max_queue": 4, "open_hours": None,
            "mechanic": {"type": "counter"}, "icon": "☕",
        },
        "rival": {
            "name": "Café da Esquina", "products": ["coffee", "tea", "croissant"],
            "base_factor": 1.2, "start_owner": "bot", "order": 2, "zone": "campus",
            "start_prices": {"coffee": 100, "tea": 120, "croissant": 150},
            "acquisition_cost": 30_000, "manager_cost": 10_000, "max_queue": 4, "open_hours": None,
            "mechanic": {"type": "counter"}, "icon": "🏪",
        },
        "snackbots": {
            "name": "SnackBots", "products": ["water", "coke_zero", "protein_bar"],
            "base_factor": 1.0, "start_owner": "bot", "order": 3, "zone": "campus",
            "start_prices": {"water": 100, "coke_zero": 150, "protein_bar": 200},
            "acquisition_cost": 35_000, "manager_cost": 8_000, "max_queue": 3, "open_hours": None,
            "mechanic": {"type": "vending"}, "icon": "🤖",
            "building": {"x0": 7, "x1": 15, "z0": 13, "z1": 21, "door": "west", "wall": 0xe3f2fd,
                         "trim": 0x1565c0, "roof": 0x1e88e5, "sign": "SNACKBOTS", "interior": "vending"},
        },
        "mercado": {
            "name": "Mercado & Go", "products": ["sandwich", "iced_tea", "apple"],
            "base_factor": 1.0, "start_owner": "bot", "order": 4, "zone": "campus",
            "start_prices": {"sandwich": 300, "iced_tea": 150, "apple": 80},
            "acquisition_cost": 45_000, "manager_cost": 10_000, "max_queue": 4, "open_hours": None,
            "mechanic": {"type": "counter"}, "icon": "🛒",
            "building": {"x0": 12, "x1": 24, "z0": -31, "z1": -20, "door": "south", "wall": 0xf1f8e9,
                         "trim": 0x558b2f, "roof": 0xf9a825, "sign": "MERCADO & GO", "interior": "market"},
        },
        "bowl_bar": {
            "name": "Bowl Bar", "products": ["poke_bowl", "acai_bowl", "smoothie"],
            "base_factor": 1.1, "start_owner": "bot", "order": 5, "zone": "campus",
            "start_prices": {"poke_bowl": 750, "acai_bowl": 550, "smoothie": 350},
            "acquisition_cost": 55_000, "manager_cost": 12_000, "max_queue": 4, "open_hours": None,
            "mechanic": {"type": "counter"}, "icon": "🥗",
            "building": {"x0": -22, "x1": -12, "z0": 11, "z1": 21, "door": "east", "wall": 0xfff3e0,
                         "trim": 0xef6c00, "roof": 0x6a1b9a, "sign": "BOWL BAR", "interior": "counter"},
        },
        "mensa": {
            "name": "Nova Mensa", "products": ["chicken_fries", "pizza", "pudding"],
            "base_factor": 1.0, "start_owner": "bot", "order": 6, "zone": "campus",
            "start_prices": {"chicken_fries": 450, "pizza": 250, "pudding": 120},
            "acquisition_cost": 65_000, "manager_cost": 14_000, "max_queue": 8, "open_hours": None,
            "mechanic": {"type": "counter"}, "icon": "🍽️",
            "building": {"x0": -26, "x1": -10, "z0": -34, "z1": -20, "door": "south", "wall": 0xeceff1,
                         "trim": 0x37474f, "roof": 0x455a64, "sign": "NOVA MENSA", "interior": "counter"},
        },
    },
    # Headless balance run (simulation.py --campaign): the target days for each purchase.
    "balance_target": {"first_purchase_day": 10, "days_per_further_shop": 5},
    "price_step": 10,
    "max_price": 1_000,
    "upgrades": {
        "coffee_machine": {"name": "Better coffee machine", "icon": "⚙️", "factor_bonus": 0.15, "cost": 3_000},
        "seating": {"name": "Seating & decor", "icon": "🪴", "factor_bonus": 0.20, "cost": 6_000},
        "branding": {"name": "Sign & branding", "icon": "🪧", "factor_bonus": 0.25, "cost": 10_000},
    },
    "manager_cost": 10_000,
    # After you buy the competitor, its barista keeps selling automatically and
    # orders supplies every morning (and right after the purchase) for this plan.
    # Manager proposals (v5): yesterday's sales plus a buffer, at least this many portions.
    "manager": {"buffer": 1.2, "sold_out_buffer": 1.5, "min_portions": 8},
    "acquisition_cost": 30_000,
    "cleaning_spots": {
        "counter": {"name": "Wipe the counter", "minutes": 3},
        "coffee_machine": {"name": "Clean the coffee machine", "minutes": 3},
        "tables": {"name": "Clear the tables", "minutes": 3},
        "floor": {"name": "Sweep the floor", "minutes": 3},
    },
}
