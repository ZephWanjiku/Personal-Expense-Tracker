"""
seed_demo_data.py
Creates a demo user (username: demo, password: Demo1234) and populates their
account with a few months of realistic sample transactions and budgets, so the
Dashboard and Budgets pages have something to show right away.

Run with:
    python seed_demo_data.py
"""

import random
from datetime import date
import database as db

db.init_db()

random.seed(42)

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo1234"

EXPENSE_PLAN = {
    "Food": (250, 420),
    "Rent": (900, 900),
    "Transport": (60, 140),
    "Utilities": (80, 160),
    "Entertainment": (30, 150),
    "Health": (0, 200),
    "Shopping": (40, 300),
}

INCOME_PLAN = {
    "Salary": (3200, 3200),
    "Freelance": (0, 600),
}

MONTHS = ["2026-06", "2026-07", "2026-08"]


def random_day(month: str) -> str:
    year, mon = map(int, month.split("-"))
    day = random.randint(1, 27)
    return date(year, mon, day).isoformat()


existing = db.authenticate_user(DEMO_USERNAME, DEMO_PASSWORD)
if existing:
    user_id = existing["id"]
    print(f"Using existing demo user (id={user_id}).")
else:
    user_id = db.create_user(DEMO_USERNAME, DEMO_PASSWORD)
    print(f"Created demo user '{DEMO_USERNAME}' / '{DEMO_PASSWORD}' (id={user_id}).")

categories = {c["name"]: c["id"] for c in db.get_categories(user_id)}

for month in MONTHS:
    for cat_name, (lo, hi) in EXPENSE_PLAN.items():
        amount = round(random.uniform(lo, hi), 2)
        if amount > 0:
            db.add_transaction(user_id, random_day(month), "expense", categories[cat_name], amount, f"{cat_name} - {month}")

    for cat_name, (lo, hi) in INCOME_PLAN.items():
        amount = round(random.uniform(lo, hi), 2)
        if amount > 0:
            db.add_transaction(user_id, random_day(month), "income", categories[cat_name], amount, f"{cat_name} - {month}")

    # Set a budget for a couple of categories
    db.set_budget(user_id, categories["Food"], month, 350)
    db.set_budget(user_id, categories["Entertainment"], month, 100)

print("Seeded demo data across", MONTHS)
print(f"\nLog in with username '{DEMO_USERNAME}' and password '{DEMO_PASSWORD}' to see it.")
