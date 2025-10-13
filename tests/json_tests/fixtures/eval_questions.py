"""Inference eval: questions, response models, and gold answer computation."""

import json
import os
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class CountAnswer(BaseModel):
    count: int


class NumericAnswer(BaseModel):
    value: float


class ListAnswer(BaseModel):
    items: list[str]


class RankEntry(BaseModel):
    name: str
    value: float


class RankedAnswer(BaseModel):
    rankings: list[RankEntry]


class Classification(BaseModel):
    name: str
    category: str


class ClassificationAnswer(BaseModel):
    classifications: list[Classification]


class PathAnswer(BaseModel):
    path: list[str]


# ---------------------------------------------------------------------------
# Fixture loading
# ---------------------------------------------------------------------------

FIXTURES_DIR = os.path.join(os.path.dirname(__file__))
ORG_FIXTURE = os.path.join(
    os.path.dirname(__file__), "..", "..", "e2e", "benchmark", "fixtures", "json", "nested_complex.json"
)
ECOMMERCE_FIXTURE = os.path.join(FIXTURES_DIR, "ecommerce_orders.json")


def load_org() -> dict:
    with open(ORG_FIXTURE) as f:
        return json.load(f)


def load_ecommerce() -> list[dict]:
    with open(ECOMMERCE_FIXTURE) as f:
        return json.load(f)


def load_sparse() -> list[dict]:
    path = os.path.join(FIXTURES_DIR, "sparse_records.json")
    with open(path) as f:
        return json.load(f)


def load_tricky() -> list[dict]:
    path = os.path.join(FIXTURES_DIR, "tricky_values.json")
    with open(path) as f:
        return json.load(f)


def generate_large_orders(n: int = 120, seed: int = 42) -> list[dict]:
    """Generate n deterministic e-commerce orders for large-scale testing."""
    import random
    rng = random.Random(seed)

    states = ["CA", "CA", "CA", "TX", "NY", "IL", "WA", "FL", "CO", "MA"]
    cities = {
        "CA": "San Francisco", "TX": "Austin", "NY": "New York",
        "IL": "Chicago", "WA": "Seattle", "FL": "Miami",
        "CO": "Denver", "MA": "Boston",
    }
    carriers = ["FedEx", "UPS", "USPS"]
    categories = ["electronics", "furniture", "apparel", "books", "kitchen", "fitness", "office", "grocery"]
    products = {
        "electronics": ["Laptop", "Monitor", "Keyboard", "Mouse", "Headphones", "Speaker", "Tablet", "Cable"],
        "furniture": ["Chair", "Desk", "Lamp", "Shelf", "Cabinet"],
        "apparel": ["Jacket", "Shoes", "Hat", "Scarf", "Gloves"],
        "books": ["Novel", "Textbook", "Cookbook", "Guide", "Manual"],
        "kitchen": ["Blender", "Toaster", "Pan", "Knife Set", "Scale"],
        "fitness": ["Yoga Mat", "Dumbbells", "Band Set", "Jump Rope"],
        "office": ["Notebook", "Pen Set", "Stapler", "Folder Set"],
        "grocery": ["Coffee Beans", "Tea Box", "Olive Oil", "Spice Set"],
    }
    statuses_weights = [("delivered", 0.4), ("shipped", 0.25), ("processing", 0.2), ("cancelled", 0.15)]
    statuses = [s for s, _ in statuses_weights]
    weights = [w for _, w in statuses_weights]

    orders = []
    for i in range(1, n + 1):
        state = rng.choice(states)
        city = cities[state]
        status = rng.choices(statuses, weights=weights, k=1)[0]
        n_items = rng.randint(1, 5)
        line_items = []
        for _ in range(n_items):
            cat = rng.choice(categories)
            product = rng.choice(products[cat])
            line_items.append({
                "product": product,
                "quantity": rng.randint(1, 4),
                "unit_price": round(rng.uniform(5.99, 999.99), 2),
                "category": cat,
            })

        has_tracking = status in ("delivered", "shipped")
        n_events = rng.randint(1, 3) if has_tracking else 0
        tracking = []
        for j in range(n_events):
            tracking.append({
                "timestamp": f"2024-12-{i % 28 + 1:02d}T{8 + j * 4:02d}:00:00Z",
                "status": ["shipped", "in_transit", "delivered"][min(j, 2)],
                "location": f"{city}, {state}",
            })

        has_return = rng.random() < 0.2 and status == "delivered"
        returns = []
        if has_return and line_items:
            ret_item = rng.choice(line_items)
            returns.append({
                "item": ret_item["product"],
                "reason": rng.choice(["defective", "wrong item", "not as described", "changed mind"]),
                "status": "refunded",
                "refund_amount": ret_item["unit_price"],
            })

        orders.append({
            "order_id": f"ORD-L{i:03d}",
            "customer": f"customer_{i}",
            "date": f"2024-12-{i % 28 + 1:02d}",
            "status": status,
            "line_items": line_items,
            "shipping": {
                "address": {
                    "street": f"{100 + i} Main St",
                    "city": city,
                    "state": state,
                    "zip": f"{10000 + i}",
                },
                "carrier": rng.choice(carriers),
                "tracking_events": tracking,
            },
            "returns": returns,
        })
    return orders


def load_large_orders() -> list[dict]:
    return generate_large_orders()


# ---------------------------------------------------------------------------
# Gold answer computation — org fixture
# ---------------------------------------------------------------------------

def gold_q1_python_skill_count(data: dict) -> CountAnswer:
    """Q1: How many people across all teams have 'python' as a skill?"""
    count = 0
    for dept in data["departments"]:
        for team in dept["teams"]:
            for member in team["members"]:
                if "python" in member.get("skills", []):
                    count += 1
    return CountAnswer(count=count)


def gold_q2_leads_fewer_yoe(data: dict) -> ListAnswer:
    """Q2: Which team leads have fewer YOE than at least one of their members?"""
    leads = []
    for dept in data["departments"]:
        for team in dept["teams"]:
            lead_name = team.get("lead")
            if not lead_name:
                continue
            lead_yoe = None
            max_member_yoe = 0
            for member in team["members"]:
                if member["name"] == lead_name:
                    lead_yoe = member["yoe"]
                else:
                    max_member_yoe = max(max_member_yoe, member["yoe"])
            if lead_yoe is not None and lead_yoe < max_member_yoe:
                leads.append(lead_name)
    return ListAnswer(items=leads)


def gold_q3_budget_per_person(data: dict) -> RankedAnswer:
    """Q3: Rank departments by budget-per-person (budget/headcount)."""
    entries = []
    for dept in data["departments"]:
        ratio = round(dept["budget"] / dept["headcount"], 2)
        entries.append(RankEntry(name=dept["name"], value=ratio))
    entries.sort(key=lambda e: e.value, reverse=True)
    return RankedAnswer(rankings=entries)


def gold_q4_team_classification(data: dict) -> ClassificationAnswer:
    """Q4: Classify each Engineering team as 'data', 'infra', or 'app'."""
    # Hand-labeled based on stack:
    # Backend: python, go, postgres, redis -> app
    # Frontend: react, typescript, tailwind -> app
    # Infrastructure: terraform, k8s, aws -> infra
    # Data: python, spark, airflow -> data
    eng = None
    for dept in data["departments"]:
        if dept["name"] == "Engineering":
            eng = dept
            break
    classifications = []
    label_map = {
        "Backend": "app",
        "Frontend": "app",
        "Infrastructure": "infra",
        "Data": "data",
    }
    for team in eng["teams"]:
        category = label_map.get(team["name"], "app")
        classifications.append(Classification(name=team["name"], category=category))
    return ClassificationAnswer(classifications=classifications)


def gold_q5_carol_path(data: dict) -> PathAnswer:
    """Q5: Trace carol's position: carol, team, department, org."""
    for dept in data["departments"]:
        for team in dept["teams"]:
            for member in team["members"]:
                if member["name"] == "carol":
                    return PathAnswer(path=["carol", team["name"], dept["name"], data["organization"]])
    raise ValueError("carol not found in fixture")


# ---------------------------------------------------------------------------
# Gold answer computation — e-commerce fixture
# ---------------------------------------------------------------------------

def gold_q6_total_refunds(data: list[dict]) -> NumericAnswer:
    """Q6: Total refund amount across all returned orders."""
    total = 0.0
    for order in data:
        for ret in order.get("returns", []):
            total += ret["refund_amount"]
    return NumericAnswer(value=round(total, 2))


def gold_q7_ca_no_tracking(data: list[dict]) -> ListAnswer:
    """Q7: Orders shipped to California with no tracking events."""
    result = []
    for order in data:
        state = order["shipping"]["address"]["state"]
        events = order["shipping"]["tracking_events"]
        if state == "CA" and len(events) == 0:
            result.append(order["order_id"])
    return ListAnswer(items=result)


def gold_q8_avg_order_value(data: list[dict]) -> NumericAnswer:
    """Q8: Average order value (sum of qty * unit_price per order, averaged)."""
    totals = []
    for order in data:
        order_total = sum(
            item["quantity"] * item["unit_price"] for item in order["line_items"]
        )
        totals.append(order_total)
    avg = round(sum(totals) / len(totals), 2)
    return NumericAnswer(value=avg)


def gold_q9_order_classification(data: list[dict]) -> ClassificationAnswer:
    """Q9: Classify orders as 'electronics', 'mixed', or 'non-electronics'."""
    classifications = []
    for order in data:
        categories = {item["category"] for item in order["line_items"]}
        has_electronics = "electronics" in categories
        all_electronics = categories == {"electronics"}
        if all_electronics:
            label = "electronics"
        elif has_electronics:
            label = "mixed"
        else:
            label = "non-electronics"
        classifications.append(Classification(name=order["order_id"], category=label))
    return ClassificationAnswer(classifications=classifications)


# ---------------------------------------------------------------------------
# Gold answer computation — sparse fixture
# ---------------------------------------------------------------------------

def gold_q10_non_null_city(data: list[dict]) -> CountAnswer:
    """Q10: How many records have a non-null city?"""
    count = sum(1 for r in data if r["city"] is not None)
    return CountAnswer(count=count)


def gold_q11_has_skills(data: list[dict]) -> ListAnswer:
    """Q11: Which people (by id) have at least one skill?"""
    ids = [r["id"] for r in data if r["skills"]]
    return ListAnswer(items=ids)


def gold_q12_avg_salary(data: list[dict]) -> NumericAnswer:
    """Q12: Average salary of records with non-null salary."""
    salaries = [r["salary"] for r in data if r["salary"] is not None]
    avg = round(sum(salaries) / len(salaries), 2)
    return NumericAnswer(value=avg)


# ---------------------------------------------------------------------------
# Gold answer computation — large orders fixture
# ---------------------------------------------------------------------------

def gold_q13_total_revenue(data: list[dict]) -> NumericAnswer:
    """Q13: Total revenue across all line items in all orders."""
    total = sum(
        item["quantity"] * item["unit_price"]
        for order in data
        for item in order["line_items"]
    )
    return NumericAnswer(value=round(total, 2))


def gold_q14_ca_count(data: list[dict]) -> CountAnswer:
    """Q14: How many orders shipped to CA?"""
    count = sum(1 for o in data if o["shipping"]["address"]["state"] == "CA")
    return CountAnswer(count=count)


def gold_q15_ca_refunds(data: list[dict]) -> NumericAnswer:
    """Q15: Total refund amount for orders shipped to CA."""
    total = 0.0
    for order in data:
        if order["shipping"]["address"]["state"] == "CA":
            for ret in order.get("returns", []):
                total += ret["refund_amount"]
    return NumericAnswer(value=round(total, 2))


# ---------------------------------------------------------------------------
# Gold answer computation — tricky values fixture
# ---------------------------------------------------------------------------

def gold_q16_name_by_id(data: list[dict]) -> ListAnswer:
    """Q16: Name of record with id T03 (has semicolons)."""
    for r in data:
        if r["id"] == "T03":
            return ListAnswer(items=[r["name"]])
    raise ValueError("T03 not found")


def gold_q17_code_404(data: list[dict]) -> ListAnswer:
    """Q17: IDs of records where code == 404."""
    ids = [r["id"] for r in data if r["code"] == 404]
    return ListAnswer(items=ids)


def gold_q18_tags_for_t07(data: list[dict]) -> ListAnswer:
    """Q18: Tags for record T07."""
    for r in data:
        if r["id"] == "T07":
            return ListAnswer(items=r["tags"])
    raise ValueError("T07 not found")


# ---------------------------------------------------------------------------
# Question registry
# ---------------------------------------------------------------------------

QUESTIONS = [
    {
        "id": "q1",
        "fixture": "org",
        "question": "How many people across all teams have 'python' listed as one of their skills? Return just the count.",
        "model": CountAnswer,
        "gold_fn": gold_q1_python_skill_count,
    },
    {
        "id": "q2",
        "fixture": "org",
        "question": "Which team leads have fewer years of experience (yoe) than at least one of their team members? Return the lead names.",
        "model": ListAnswer,
        "gold_fn": gold_q2_leads_fewer_yoe,
    },
    {
        "id": "q3",
        "fixture": "org",
        "question": "Rank the departments by budget-per-person (budget divided by headcount), from highest to lowest. Return each department name and the ratio.",
        "model": RankedAnswer,
        "gold_fn": gold_q3_budget_per_person,
    },
    {
        "id": "q4",
        "fixture": "org",
        "question": "Classify each team in the Engineering department as 'data', 'infra', or 'app' based on the team's stack and purpose. Return team name and category.",
        "model": ClassificationAnswer,
        "gold_fn": gold_q4_team_classification,
    },
    {
        "id": "q5",
        "fixture": "org",
        "question": "Trace carol's position in the organization: what team is she on, what department is that team in, and what is the organization name? Return as an ordered path from most specific to most general.",
        "model": PathAnswer,
        "gold_fn": gold_q5_carol_path,
    },
    {
        "id": "q6",
        "fixture": "ecommerce",
        "question": "What is the total refund amount in dollars across all returned items in all orders? Return the numeric value.",
        "model": NumericAnswer,
        "gold_fn": gold_q6_total_refunds,
    },
    {
        "id": "q7",
        "fixture": "ecommerce",
        "question": "Which orders were shipped to California (state CA) but have zero tracking events? Return the order IDs.",
        "model": ListAnswer,
        "gold_fn": gold_q7_ca_no_tracking,
    },
    {
        "id": "q8",
        "fixture": "ecommerce",
        "question": "What is the average order value across all orders? Calculate each order's value as the sum of (quantity * unit_price) for all its line items, then average across orders. Return the numeric value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q8_avg_order_value,
    },
    {
        "id": "q9",
        "fixture": "ecommerce",
        "question": "Classify each order as 'electronics' (all line items are electronics), 'mixed' (some electronics, some not), or 'non-electronics' (no electronics). Return order_id and category.",
        "model": ClassificationAnswer,
        "gold_fn": gold_q9_order_classification,
    },
    # --- Sparse fixture questions ---
    {
        "id": "q10",
        "fixture": "sparse",
        "question": "How many records have a non-null city value? Count only records where city is present and not null.",
        "model": CountAnswer,
        "gold_fn": gold_q10_non_null_city,
    },
    {
        "id": "q11",
        "fixture": "sparse",
        "question": "Which records (by their id field) have at least one skill in their skills list? Return the ids. Exclude records with empty skills arrays.",
        "model": ListAnswer,
        "gold_fn": gold_q11_has_skills,
    },
    {
        "id": "q12",
        "fixture": "sparse",
        "question": "What is the average salary among records that have a non-null salary? Ignore records where salary is null. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q12_avg_salary,
    },
    # --- Large orders questions ---
    {
        "id": "q13",
        "fixture": "large",
        "question": "What is the total revenue across all orders? Calculate as the sum of (quantity * unit_price) for every line item in every order. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q13_total_revenue,
    },
    {
        "id": "q14",
        "fixture": "large",
        "question": "How many orders were shipped to California (state CA)?",
        "model": CountAnswer,
        "gold_fn": gold_q14_ca_count,
    },
    {
        "id": "q15",
        "fixture": "large",
        "question": "What is the total refund amount across all orders that were shipped to California (state CA)? Sum the refund_amount from all returns in CA orders. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q15_ca_refunds,
    },
    # --- Tricky values questions ---
    {
        "id": "q16",
        "fixture": "tricky",
        "question": "What is the exact name of the record with id 'T03'? Return it as a single-item list.",
        "model": ListAnswer,
        "gold_fn": gold_q16_name_by_id,
    },
    {
        "id": "q17",
        "fixture": "tricky",
        "question": "List the ids of all records where the code field equals exactly 404 (the number four hundred and four, not numbers like 40401 that contain 404 as a substring).",
        "model": ListAnswer,
        "gold_fn": gold_q17_code_404,
    },
    {
        "id": "q18",
        "fixture": "tricky",
        "question": "What are the tags for the record with id 'T07'? Return them exactly as they appear.",
        "model": ListAnswer,
        "gold_fn": gold_q18_tags_for_t07,
    },
]
