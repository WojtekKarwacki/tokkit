# JSON Compaction Inference Eval — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether `compact_json` output preserves enough information for an LLM to perform accurate inference on deeply nested data, compared to raw JSON.

**Architecture:** Two test layers — deterministic data fidelity tests (no LLM, default pytest) and LLM-backed inference eval (claude-agent-sdk, `pytest -m inference`). Both share a common fixtures module with question definitions, gold answer computation, and Pydantic response models.

**Tech Stack:** Python, pytest, claude-agent-sdk, pydantic, tokkit_json

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tests/json_tests/fixtures/__init__.py` | Create | Package marker |
| `tests/json_tests/fixtures/ecommerce_orders.json` | Create | E-commerce fixture (15 orders, nested line items/shipping/returns) |
| `tests/json_tests/fixtures/eval_questions.py` | Create | Question definitions, Pydantic response models, gold answer computation |
| `tests/json_tests/test_data_fidelity.py` | Create | Deterministic data preservation tests |
| `tests/json_tests/test_inference_eval.py` | Create | LLM-backed inference accuracy eval |
| `tests/json_tests/conftest.py` | Create | Shared fixtures (load JSON, compact JSON) |
| `pyproject.toml` | Modify | Add `inference` marker |

Existing files referenced (read-only):
- `tests/e2e/benchmark/fixtures/json/nested_complex.json` — org fixture
- `py/tokkit_json/__init__.py` — `compact_json()` function
- `py/tokkit_json/schema_conv.py` — `to_schema_csv()` implementation

---

### Task 1: E-commerce Orders Fixture

**Files:**
- Create: `tests/json_tests/fixtures/__init__.py`
- Create: `tests/json_tests/fixtures/ecommerce_orders.json`

- [ ] **Step 1: Create fixture package**

```python
# tests/json_tests/fixtures/__init__.py
# (empty)
```

- [ ] **Step 2: Create e-commerce orders fixture**

Create `tests/json_tests/fixtures/ecommerce_orders.json` with 15 orders. The fixture must have:
- 4 nesting levels: order → line_items → (each with category), shipping → tracking_events, returns (optional)
- Heterogeneous records: some orders have returns, some don't
- Enough data to make aggregation/filtering questions non-trivial
- Realistic values that allow deterministic gold answers

```json
[
  {
    "order_id": "ORD-001",
    "customer": "alice johnson",
    "date": "2024-11-15",
    "status": "delivered",
    "line_items": [
      {"product": "Laptop Pro 15", "quantity": 1, "unit_price": 1299.99, "category": "electronics"},
      {"product": "USB-C Hub", "quantity": 2, "unit_price": 49.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "123 Oak St", "city": "San Francisco", "state": "CA", "zip": "94102"},
      "carrier": "FedEx",
      "tracking_events": [
        {"timestamp": "2024-11-15T10:00:00Z", "status": "shipped", "location": "San Francisco, CA"},
        {"timestamp": "2024-11-17T14:30:00Z", "status": "delivered", "location": "San Francisco, CA"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-002",
    "customer": "bob smith",
    "date": "2024-11-16",
    "status": "delivered",
    "line_items": [
      {"product": "Ergonomic Chair", "quantity": 1, "unit_price": 599.00, "category": "furniture"},
      {"product": "Desk Lamp", "quantity": 1, "unit_price": 79.99, "category": "furniture"}
    ],
    "shipping": {
      "address": {"street": "456 Elm Ave", "city": "Los Angeles", "state": "CA", "zip": "90001"},
      "carrier": "UPS",
      "tracking_events": [
        {"timestamp": "2024-11-16T09:00:00Z", "status": "shipped", "location": "Los Angeles, CA"},
        {"timestamp": "2024-11-18T11:00:00Z", "status": "delivered", "location": "Los Angeles, CA"}
      ]
    },
    "returns": [
      {"item": "Desk Lamp", "reason": "defective", "status": "refunded", "refund_amount": 79.99}
    ]
  },
  {
    "order_id": "ORD-003",
    "customer": "carol davis",
    "date": "2024-11-17",
    "status": "shipped",
    "line_items": [
      {"product": "Running Shoes", "quantity": 1, "unit_price": 129.99, "category": "apparel"},
      {"product": "Sports Watch", "quantity": 1, "unit_price": 249.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "789 Pine Rd", "city": "Chicago", "state": "IL", "zip": "60601"},
      "carrier": "USPS",
      "tracking_events": [
        {"timestamp": "2024-11-17T08:00:00Z", "status": "shipped", "location": "Chicago, IL"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-004",
    "customer": "dave wilson",
    "date": "2024-11-18",
    "status": "delivered",
    "line_items": [
      {"product": "Cookbook Collection", "quantity": 3, "unit_price": 24.99, "category": "books"},
      {"product": "Kitchen Scale", "quantity": 1, "unit_price": 34.99, "category": "kitchen"}
    ],
    "shipping": {
      "address": {"street": "321 Maple Dr", "city": "Austin", "state": "TX", "zip": "73301"},
      "carrier": "FedEx",
      "tracking_events": [
        {"timestamp": "2024-11-18T07:00:00Z", "status": "shipped", "location": "Austin, TX"},
        {"timestamp": "2024-11-20T16:00:00Z", "status": "delivered", "location": "Austin, TX"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-005",
    "customer": "eve martinez",
    "date": "2024-11-19",
    "status": "delivered",
    "line_items": [
      {"product": "Wireless Headphones", "quantity": 1, "unit_price": 199.99, "category": "electronics"},
      {"product": "Phone Case", "quantity": 2, "unit_price": 19.99, "category": "electronics"},
      {"product": "Screen Protector", "quantity": 3, "unit_price": 9.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "654 Cedar Ln", "city": "Seattle", "state": "WA", "zip": "98101"},
      "carrier": "UPS",
      "tracking_events": [
        {"timestamp": "2024-11-19T12:00:00Z", "status": "shipped", "location": "Seattle, WA"},
        {"timestamp": "2024-11-21T10:00:00Z", "status": "delivered", "location": "Seattle, WA"}
      ]
    },
    "returns": [
      {"item": "Phone Case", "reason": "wrong color", "status": "refunded", "refund_amount": 19.99}
    ]
  },
  {
    "order_id": "ORD-006",
    "customer": "frank lee",
    "date": "2024-11-20",
    "status": "delivered",
    "line_items": [
      {"product": "Yoga Mat", "quantity": 1, "unit_price": 49.99, "category": "fitness"},
      {"product": "Resistance Bands", "quantity": 1, "unit_price": 29.99, "category": "fitness"},
      {"product": "Water Bottle", "quantity": 2, "unit_price": 14.99, "category": "fitness"}
    ],
    "shipping": {
      "address": {"street": "987 Birch St", "city": "Portland", "state": "OR", "zip": "97201"},
      "carrier": "USPS",
      "tracking_events": [
        {"timestamp": "2024-11-20T11:00:00Z", "status": "shipped", "location": "Portland, OR"},
        {"timestamp": "2024-11-22T09:00:00Z", "status": "delivered", "location": "Portland, OR"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-007",
    "customer": "grace kim",
    "date": "2024-11-21",
    "status": "processing",
    "line_items": [
      {"product": "4K Monitor", "quantity": 1, "unit_price": 449.99, "category": "electronics"},
      {"product": "Monitor Arm", "quantity": 1, "unit_price": 89.99, "category": "furniture"}
    ],
    "shipping": {
      "address": {"street": "147 Walnut Ave", "city": "San Jose", "state": "CA", "zip": "95101"},
      "carrier": "FedEx",
      "tracking_events": []
    },
    "returns": []
  },
  {
    "order_id": "ORD-008",
    "customer": "hank brown",
    "date": "2024-11-22",
    "status": "delivered",
    "line_items": [
      {"product": "Coffee Maker", "quantity": 1, "unit_price": 149.99, "category": "kitchen"},
      {"product": "Coffee Beans 1kg", "quantity": 2, "unit_price": 18.99, "category": "grocery"},
      {"product": "Travel Mug", "quantity": 1, "unit_price": 24.99, "category": "kitchen"}
    ],
    "shipping": {
      "address": {"street": "258 Spruce Ct", "city": "Denver", "state": "CO", "zip": "80201"},
      "carrier": "UPS",
      "tracking_events": [
        {"timestamp": "2024-11-22T14:00:00Z", "status": "shipped", "location": "Denver, CO"},
        {"timestamp": "2024-11-24T08:00:00Z", "status": "out_for_delivery", "location": "Denver, CO"},
        {"timestamp": "2024-11-24T15:00:00Z", "status": "delivered", "location": "Denver, CO"}
      ]
    },
    "returns": [
      {"item": "Coffee Maker", "reason": "not as described", "status": "refunded", "refund_amount": 149.99}
    ]
  },
  {
    "order_id": "ORD-009",
    "customer": "iris chen",
    "date": "2024-11-23",
    "status": "shipped",
    "line_items": [
      {"product": "Winter Jacket", "quantity": 1, "unit_price": 189.99, "category": "apparel"},
      {"product": "Wool Scarf", "quantity": 1, "unit_price": 39.99, "category": "apparel"},
      {"product": "Gloves", "quantity": 1, "unit_price": 29.99, "category": "apparel"}
    ],
    "shipping": {
      "address": {"street": "369 Ash Blvd", "city": "Boston", "state": "MA", "zip": "02101"},
      "carrier": "FedEx",
      "tracking_events": [
        {"timestamp": "2024-11-23T10:00:00Z", "status": "shipped", "location": "Boston, MA"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-010",
    "customer": "jack taylor",
    "date": "2024-11-24",
    "status": "delivered",
    "line_items": [
      {"product": "Bluetooth Speaker", "quantity": 1, "unit_price": 79.99, "category": "electronics"},
      {"product": "Aux Cable", "quantity": 1, "unit_price": 9.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "741 Oak Pl", "city": "Sacramento", "state": "CA", "zip": "95814"},
      "carrier": "USPS",
      "tracking_events": [
        {"timestamp": "2024-11-24T13:00:00Z", "status": "shipped", "location": "Sacramento, CA"},
        {"timestamp": "2024-11-26T17:00:00Z", "status": "delivered", "location": "Sacramento, CA"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-011",
    "customer": "kate nguyen",
    "date": "2024-11-25",
    "status": "cancelled",
    "line_items": [
      {"product": "Standing Desk", "quantity": 1, "unit_price": 699.99, "category": "furniture"},
      {"product": "Cable Management Kit", "quantity": 1, "unit_price": 19.99, "category": "furniture"}
    ],
    "shipping": {
      "address": {"street": "852 Elm Way", "city": "Phoenix", "state": "AZ", "zip": "85001"},
      "carrier": "UPS",
      "tracking_events": []
    },
    "returns": []
  },
  {
    "order_id": "ORD-012",
    "customer": "leo garcia",
    "date": "2024-11-26",
    "status": "delivered",
    "line_items": [
      {"product": "Python Crash Course", "quantity": 1, "unit_price": 39.99, "category": "books"},
      {"product": "Mechanical Keyboard", "quantity": 1, "unit_price": 159.99, "category": "electronics"},
      {"product": "Mouse Pad XL", "quantity": 1, "unit_price": 19.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "963 Ivy Rd", "city": "Miami", "state": "FL", "zip": "33101"},
      "carrier": "FedEx",
      "tracking_events": [
        {"timestamp": "2024-11-26T09:00:00Z", "status": "shipped", "location": "Miami, FL"},
        {"timestamp": "2024-11-28T12:00:00Z", "status": "delivered", "location": "Miami, FL"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-013",
    "customer": "mia patel",
    "date": "2024-11-27",
    "status": "delivered",
    "line_items": [
      {"product": "Tablet 10 inch", "quantity": 1, "unit_price": 349.99, "category": "electronics"},
      {"product": "Tablet Case", "quantity": 1, "unit_price": 29.99, "category": "electronics"},
      {"product": "Stylus Pen", "quantity": 1, "unit_price": 59.99, "category": "electronics"}
    ],
    "shipping": {
      "address": {"street": "159 Fern Dr", "city": "Oakland", "state": "CA", "zip": "94601"},
      "carrier": "UPS",
      "tracking_events": [
        {"timestamp": "2024-11-27T08:00:00Z", "status": "shipped", "location": "Oakland, CA"},
        {"timestamp": "2024-11-29T14:00:00Z", "status": "delivered", "location": "Oakland, CA"}
      ]
    },
    "returns": [
      {"item": "Stylus Pen", "reason": "not compatible", "status": "refunded", "refund_amount": 59.99}
    ]
  },
  {
    "order_id": "ORD-014",
    "customer": "noah white",
    "date": "2024-11-28",
    "status": "delivered",
    "line_items": [
      {"product": "Cast Iron Skillet", "quantity": 1, "unit_price": 44.99, "category": "kitchen"},
      {"product": "Cutting Board Set", "quantity": 1, "unit_price": 34.99, "category": "kitchen"},
      {"product": "Chef Knife", "quantity": 1, "unit_price": 89.99, "category": "kitchen"},
      {"product": "Apron", "quantity": 1, "unit_price": 19.99, "category": "apparel"}
    ],
    "shipping": {
      "address": {"street": "753 Sage Ave", "city": "San Diego", "state": "CA", "zip": "92101"},
      "carrier": "FedEx",
      "tracking_events": [
        {"timestamp": "2024-11-28T07:00:00Z", "status": "shipped", "location": "San Diego, CA"},
        {"timestamp": "2024-11-30T11:00:00Z", "status": "delivered", "location": "San Diego, CA"}
      ]
    },
    "returns": []
  },
  {
    "order_id": "ORD-015",
    "customer": "olivia reed",
    "date": "2024-11-29",
    "status": "shipped",
    "line_items": [
      {"product": "Wireless Mouse", "quantity": 1, "unit_price": 59.99, "category": "electronics"},
      {"product": "Notebook 5-Pack", "quantity": 1, "unit_price": 12.99, "category": "office"},
      {"product": "Pen Set", "quantity": 1, "unit_price": 8.99, "category": "office"}
    ],
    "shipping": {
      "address": {"street": "246 Moss Ln", "city": "Atlanta", "state": "GA", "zip": "30301"},
      "carrier": "USPS",
      "tracking_events": [
        {"timestamp": "2024-11-29T15:00:00Z", "status": "shipped", "location": "Atlanta, GA"}
      ]
    },
    "returns": []
  }
]
```

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/fixtures/__init__.py tests/json_tests/fixtures/ecommerce_orders.json
git commit -m "test: add e-commerce orders fixture for inference eval"
```

---

### Task 2: Pydantic Response Models & Question Definitions

**Files:**
- Create: `tests/json_tests/fixtures/eval_questions.py`

This module defines all response models, questions, and gold-answer computation functions. Both test files import from it.

- [ ] **Step 1: Create the eval_questions module with response models**

```python
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
    """Q5: Trace carol's position: team, department, org."""
    for dept in data["departments"]:
        for team in dept["teams"]:
            for member in team["members"]:
                if member["name"] == "carol":
                    return PathAnswer(path=[team["name"], dept["name"], data["organization"]])
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
]
```

- [ ] **Step 2: Run a quick sanity check that gold answers compute without errors**

```bash
cd /home/edge/code/tokkit && python -c "
import sys; sys.path.insert(0, 'tests')
from json_tests.fixtures.eval_questions import *
org = load_org()
eco = load_ecommerce()
print('Q1:', gold_q1_python_skill_count(org))
print('Q2:', gold_q2_leads_fewer_yoe(org))
print('Q3:', gold_q3_budget_per_person(org))
print('Q4:', gold_q4_team_classification(org))
print('Q5:', gold_q5_carol_path(org))
print('Q6:', gold_q6_total_refunds(eco))
print('Q7:', gold_q7_ca_no_tracking(eco))
print('Q8:', gold_q8_avg_order_value(eco))
print('Q9:', gold_q9_order_classification(eco))
print('All gold answers computed OK')
"
```

Expected: all 9 lines print without errors.

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/fixtures/eval_questions.py
git commit -m "test: add eval question definitions and gold answer computation"
```

---

### Task 3: Shared Test Fixtures (conftest)

**Files:**
- Create: `tests/json_tests/conftest.py`

- [ ] **Step 1: Create conftest with fixture loaders**

```python
"""Shared fixtures for JSON inference eval tests."""

import json
import os
import pytest

from tokkit_json import compact_json


@pytest.fixture
def org_raw_json() -> str:
    """Load org fixture as raw JSON string."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "e2e", "benchmark", "fixtures", "json", "nested_complex.json"
    )
    with open(path) as f:
        return f.read()


@pytest.fixture
def org_data(org_raw_json) -> dict:
    """Parse org fixture."""
    return json.loads(org_raw_json)


@pytest.fixture
def org_compacted(org_raw_json) -> str:
    """Compact org fixture."""
    return compact_json(org_raw_json)


@pytest.fixture
def ecommerce_raw_json() -> str:
    """Load e-commerce fixture as raw JSON string."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "ecommerce_orders.json")
    with open(path) as f:
        return f.read()


@pytest.fixture
def ecommerce_data(ecommerce_raw_json) -> list[dict]:
    """Parse e-commerce fixture."""
    return json.loads(ecommerce_raw_json)


@pytest.fixture
def ecommerce_compacted(ecommerce_raw_json) -> str:
    """Compact e-commerce fixture."""
    return compact_json(ecommerce_raw_json)
```

- [ ] **Step 2: Verify fixtures load**

```bash
cd /home/edge/code/tokkit && python -c "
import json, os
# Org fixture
with open('tests/e2e/benchmark/fixtures/json/nested_complex.json') as f:
    org = json.load(f)
print(f'Org: {len(org[\"departments\"])} departments')
# E-commerce fixture
with open('tests/json_tests/fixtures/ecommerce_orders.json') as f:
    eco = json.load(f)
print(f'Ecommerce: {len(eco)} orders')
from tokkit_json import compact_json
org_c = compact_json(json.dumps(org))
eco_c = compact_json(json.dumps(eco))
print(f'Org compacted: {len(org_c)} chars (from {len(json.dumps(org))})')
print(f'Eco compacted: {len(eco_c)} chars (from {len(json.dumps(eco))})')
"
```

Expected: prints counts and char lengths without errors.

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/conftest.py
git commit -m "test: add shared conftest for inference eval fixtures"
```

---

### Task 4: Deterministic Data Fidelity Tests

**Files:**
- Create: `tests/json_tests/test_data_fidelity.py`

These tests verify that `compact_json` output preserves all values needed for inference. No LLM calls. Runs in default `pytest`.

- [ ] **Step 1: Write all data fidelity tests**

```python
"""Deterministic data fidelity tests for compact_json.

Verifies that compacted output preserves all values needed for LLM inference.
No LLM calls — runs in default pytest.
"""

import json

from json_tests.fixtures.eval_questions import load_org, load_ecommerce


# ---------------------------------------------------------------------------
# Org fixture fidelity
# ---------------------------------------------------------------------------

class TestOrgDataFidelity:
    """Verify org fixture data survives compaction."""

    def test_all_member_names_present(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            for team in dept["teams"]:
                for member in team["members"]:
                    assert member["name"] in org_compacted, (
                        f"Member '{member['name']}' missing from compacted output"
                    )

    def test_all_team_names_present(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            for team in dept["teams"]:
                assert team["name"] in org_compacted, (
                    f"Team '{team['name']}' missing from compacted output"
                )

    def test_all_department_names_present(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            assert dept["name"] in org_compacted

    def test_organization_name_present(self, org_compacted, org_data):
        assert org_data["organization"] in org_compacted

    def test_numeric_values_preserved(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            assert str(dept["budget"]) in org_compacted, (
                f"Budget {dept['budget']} for {dept['name']} missing"
            )
            assert str(dept["headcount"]) in org_compacted, (
                f"Headcount {dept['headcount']} for {dept['name']} missing"
            )

    def test_yoe_values_preserved(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            for team in dept["teams"]:
                for member in team["members"]:
                    assert str(member["yoe"]) in org_compacted

    def test_all_skills_present(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            for team in dept["teams"]:
                for member in team["members"]:
                    for skill in member["skills"]:
                        assert skill in org_compacted, (
                            f"Skill '{skill}' for {member['name']} missing"
                        )

    def test_schema_header_reflects_nesting(self, org_compacted):
        first_line = org_compacted.split("\n")[0]
        # Must contain nested schema markers
        assert "departments" in first_line
        assert "[{" in first_line or "{" in first_line, (
            "Schema header doesn't reflect nested structure"
        )

    def test_lead_names_present(self, org_compacted, org_data):
        for dept in org_data["departments"]:
            for team in dept["teams"]:
                if "lead" in team:
                    assert team["lead"] in org_compacted


# ---------------------------------------------------------------------------
# E-commerce fixture fidelity
# ---------------------------------------------------------------------------

class TestEcommerceDataFidelity:
    """Verify e-commerce fixture data survives compaction."""

    def test_all_order_ids_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            assert order["order_id"] in ecommerce_compacted

    def test_all_customer_names_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            assert order["customer"] in ecommerce_compacted

    def test_all_product_names_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for item in order["line_items"]:
                assert item["product"] in ecommerce_compacted, (
                    f"Product '{item['product']}' missing"
                )

    def test_all_prices_preserved(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for item in order["line_items"]:
                assert str(item["unit_price"]) in ecommerce_compacted, (
                    f"Price {item['unit_price']} for {item['product']} missing"
                )

    def test_all_quantities_preserved(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for item in order["line_items"]:
                assert str(item["quantity"]) in ecommerce_compacted

    def test_all_categories_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for item in order["line_items"]:
                assert item["category"] in ecommerce_compacted

    def test_all_states_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            state = order["shipping"]["address"]["state"]
            assert state in ecommerce_compacted

    def test_refund_amounts_preserved(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for ret in order.get("returns", []):
                assert str(ret["refund_amount"]) in ecommerce_compacted, (
                    f"Refund {ret['refund_amount']} missing"
                )

    def test_tracking_event_statuses_present(self, ecommerce_compacted, ecommerce_data):
        for order in ecommerce_data:
            for event in order["shipping"]["tracking_events"]:
                assert event["status"] in ecommerce_compacted

    def test_schema_header_reflects_nesting(self, ecommerce_compacted):
        first_line = ecommerce_compacted.split("\n")[0]
        assert "line_items" in first_line
        assert "shipping" in first_line
```

- [ ] **Step 2: Run data fidelity tests**

```bash
cd /home/edge/code/tokkit && pytest tests/json_tests/test_data_fidelity.py -v
```

Expected: all tests PASS. If any fail, it reveals a real compaction bug — investigate before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/test_data_fidelity.py
git commit -m "test: add deterministic data fidelity tests for compact_json"
```

---

### Task 5: LLM Inference Eval Tests

**Files:**
- Create: `tests/json_tests/test_inference_eval.py`
- Modify: `pyproject.toml:41-43` (add marker)

- [ ] **Step 1: Register the inference marker in pyproject.toml**

Add to the existing `[tool.pytest.ini_options]` section:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib"
markers = [
    "inference: LLM-backed inference accuracy eval (requires ANTHROPIC_API_KEY)",
]
```

- [ ] **Step 2: Write the inference eval test file**

```python
"""LLM inference accuracy eval for compact_json.

Compares LLM accuracy on raw JSON vs compacted JSON against gold answers.
Requires ANTHROPIC_API_KEY environment variable.

Run: pytest -m inference tests/json_tests/test_inference_eval.py -v
"""

import asyncio
import json
import os
from datetime import date

import pytest
from pydantic import BaseModel

from tokkit_json import compact_json

from json_tests.fixtures.eval_questions import (
    QUESTIONS,
    CountAnswer,
    NumericAnswer,
    ListAnswer,
    RankedAnswer,
    ClassificationAnswer,
    PathAnswer,
    load_org,
    load_ecommerce,
)

# ---------------------------------------------------------------------------
# SDK workaround (same as jakglosuja)
# ---------------------------------------------------------------------------

import claude_agent_sdk._internal.message_parser as _mp

_original_parse = _mp.parse_message


def _tolerant_parse(data):
    try:
        return _original_parse(data)
    except _mp.MessageParseError as e:
        if "Unknown message type" in str(e):
            return None
        raise


_mp.parse_message = _tolerant_parse

import sys
for _name, _mod in list(sys.modules.items()):
    if _name.startswith("claude_agent_sdk") and _mod is not None:
        if getattr(_mod, "parse_message", None) is _original_parse:
            _mod.parse_message = _tolerant_parse

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, AssistantMessage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EVAL_MODEL = os.environ.get("TOKKIT_EVAL_MODEL", "sonnet")
CHARS_PER_TOKEN = 4
LLM_TIMEOUT = 120  # seconds per call

SYSTEM_PROMPT = (
    "You are a data analyst. You will be given a dataset and a question. "
    "Analyze the data carefully and answer the question. "
    "Respond ONLY with valid JSON matching the required schema."
)


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------

def _json_schema_for(model: type[BaseModel]) -> dict:
    return model.model_json_schema()


async def _ask_llm(data_str: str, question: str, response_model: type[BaseModel]) -> BaseModel:
    """Send a question + data to Claude, return parsed structured output."""
    options = ClaudeAgentOptions(
        system_prompt=SYSTEM_PROMPT,
        model=EVAL_MODEL,
        output_format={
            "type": "json_schema",
            "schema": _json_schema_for(response_model),
        },
        max_turns=1,
    )

    user_prompt = f"Given the following data:\n\n{data_str}\n\nAnswer this question: {question}"

    result_msg = None
    structured_output_fallback = None

    async with asyncio.timeout(LLM_TIMEOUT):
        async for message in query(prompt=user_prompt, options=options):
            if isinstance(message, ResultMessage):
                result_msg = message
            elif isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "name") and block.name == "StructuredOutput":
                        structured_output_fallback = block.input

    if result_msg is None:
        raise RuntimeError("No result message from Claude")

    if result_msg.is_error:
        raise RuntimeError(f"Claude error: {result_msg.result}")

    raw = None
    if result_msg.structured_output is not None:
        raw = result_msg.structured_output
    elif result_msg.result:
        raw = json.loads(result_msg.result)
    elif structured_output_fallback is not None:
        raw = structured_output_fallback
    else:
        raise RuntimeError("No output from Claude")

    if isinstance(raw, str):
        raw = json.loads(raw)

    return response_model.model_validate(raw)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def answers_match(result: BaseModel, gold: BaseModel) -> bool:
    """Compare LLM result against gold answer based on model type."""
    if isinstance(gold, CountAnswer):
        return result.count == gold.count

    if isinstance(gold, NumericAnswer):
        return abs(result.value - gold.value) < 0.01

    if isinstance(gold, ListAnswer):
        return set(s.lower() for s in result.items) == set(s.lower() for s in gold.items)

    if isinstance(gold, RankedAnswer):
        if len(result.rankings) != len(gold.rankings):
            return False
        for r, g in zip(result.rankings, gold.rankings):
            if r.name.lower() != g.name.lower():
                return False
            if abs(r.value - g.value) > 0.01:
                return False
        return True

    if isinstance(gold, ClassificationAnswer):
        result_set = {(c.name.lower(), c.category.lower()) for c in result.classifications}
        gold_set = {(c.name.lower(), c.category.lower()) for c in gold.classifications}
        return result_set == gold_set

    if isinstance(gold, PathAnswer):
        return [s.lower() for s in result.path] == [s.lower() for s in gold.path]

    raise TypeError(f"Unknown answer type: {type(gold)}")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def org_raw() -> str:
    return json.dumps(load_org(), indent=2)


@pytest.fixture(scope="module")
def ecommerce_raw() -> str:
    return json.dumps(load_ecommerce(), indent=2)


@pytest.fixture(scope="module")
def org_compact(org_raw) -> str:
    return compact_json(org_raw)


@pytest.fixture(scope="module")
def ecommerce_compact(ecommerce_raw) -> str:
    return compact_json(ecommerce_raw)


# ---------------------------------------------------------------------------
# Results collection
# ---------------------------------------------------------------------------

_results: list[dict] = []


# ---------------------------------------------------------------------------
# Tests — one per question
# ---------------------------------------------------------------------------

def _run(coro):
    """Run async coroutine in sync test."""
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.mark.inference
class TestInferenceEval:

    def test_q1_aggregation(self, org_raw, org_compact, org_data):
        q = QUESTIONS[0]
        gold = q["gold_fn"](org_data)
        control = _run(_ask_llm(org_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(org_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(org_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(org_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q2_cross_reference(self, org_raw, org_compact, org_data):
        q = QUESTIONS[1]
        gold = q["gold_fn"](org_data)
        control = _run(_ask_llm(org_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(org_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(org_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(org_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q3_ranking(self, org_raw, org_compact, org_data):
        q = QUESTIONS[2]
        gold = q["gold_fn"](org_data)
        control = _run(_ask_llm(org_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(org_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(org_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(org_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q4_categorization(self, org_raw, org_compact, org_data):
        q = QUESTIONS[3]
        gold = q["gold_fn"](org_data)
        control = _run(_ask_llm(org_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(org_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(org_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(org_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q5_path_traversal(self, org_raw, org_compact, org_data):
        q = QUESTIONS[4]
        gold = q["gold_fn"](org_data)
        control = _run(_ask_llm(org_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(org_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(org_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(org_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q6_total_refunds(self, ecommerce_raw, ecommerce_compact, ecommerce_data):
        q = QUESTIONS[5]
        gold = q["gold_fn"](ecommerce_data)
        control = _run(_ask_llm(ecommerce_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(ecommerce_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(ecommerce_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(ecommerce_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q7_ca_no_tracking(self, ecommerce_raw, ecommerce_compact, ecommerce_data):
        q = QUESTIONS[6]
        gold = q["gold_fn"](ecommerce_data)
        control = _run(_ask_llm(ecommerce_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(ecommerce_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(ecommerce_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(ecommerce_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q8_avg_order_value(self, ecommerce_raw, ecommerce_compact, ecommerce_data):
        q = QUESTIONS[7]
        gold = q["gold_fn"](ecommerce_data)
        control = _run(_ask_llm(ecommerce_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(ecommerce_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(ecommerce_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(ecommerce_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_q9_order_classification(self, ecommerce_raw, ecommerce_compact, ecommerce_data):
        q = QUESTIONS[8]
        gold = q["gold_fn"](ecommerce_data)
        control = _run(_ask_llm(ecommerce_raw, q["question"], q["model"]))
        treatment = _run(_ask_llm(ecommerce_compact, q["question"], q["model"]))
        _results.append({
            "id": q["id"], "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(ecommerce_raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(ecommerce_compact) // CHARS_PER_TOKEN,
        })
        assert answers_match(treatment, gold), (
            f"Treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        """Generate markdown report after all questions."""
        if len(_results) < 9:
            pytest.skip("Not all questions completed")

        control_correct = sum(1 for r in _results if r["control_correct"])
        treatment_correct = sum(1 for r in _results if r["treatment_correct"])
        total = len(_results)

        lines = [
            "# JSON Compaction Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Model:** {EVAL_MODEL}",
            f"**Questions:** {total}",
            "",
            "## Results",
            "",
            "| # | Question | Control | Treatment | Gold | Raw Tokens | Compact Tokens | Savings |",
            "|---|----------|---------|-----------|------|------------|----------------|---------|",
        ]

        for r in _results:
            savings = (1 - r["compact_tokens"] / r["raw_tokens"]) * 100 if r["raw_tokens"] > 0 else 0
            ctrl = "PASS" if r["control_correct"] else "FAIL"
            treat = "PASS" if r["treatment_correct"] else "FAIL"
            lines.append(
                f"| {r['id']} | {r['question']} | {ctrl} | {treat} "
                f"| {r['gold_answer']} | {r['raw_tokens']:,} | {r['compact_tokens']:,} | {savings:.1f}% |"
            )

        lines.extend([
            "",
            "## Summary",
            "",
            f"- **Control accuracy:** {control_correct}/{total} ({control_correct/total*100:.0f}%)",
            f"- **Treatment accuracy:** {treatment_correct}/{total} ({treatment_correct/total*100:.0f}%)",
            f"- **Accuracy delta:** {(treatment_correct - control_correct)}/{total}",
            "",
        ])

        # Add detail for any failures
        failures = [r for r in _results if not r["treatment_correct"]]
        if failures:
            lines.append("## Treatment Failures")
            lines.append("")
            for r in failures:
                lines.append(f"### {r['id']}: {r['question']}")
                lines.append(f"- **Gold:** `{r['gold_answer']}`")
                lines.append(f"- **Treatment got:** `{r['treatment_answer']}`")
                lines.append(f"- **Control got:** `{r['control_answer']}`")
                ctrl_ok = "correct" if r["control_correct"] else "also wrong"
                lines.append(f"- **Control was:** {ctrl_ok}")
                lines.append("")

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
```

- [ ] **Step 3: Run data fidelity tests to make sure nothing broke**

```bash
cd /home/edge/code/tokkit && pytest tests/json_tests/test_data_fidelity.py -v
```

Expected: all PASS.

- [ ] **Step 4: Verify inference tests are collected but skipped without marker**

```bash
cd /home/edge/code/tokkit && pytest tests/json_tests/test_inference_eval.py --collect-only 2>&1 | head -20
```

Expected: tests collected, but if you run without `-m inference` they'll be included (they have the marker but aren't excluded by default — this is fine since they just need the API key).

- [ ] **Step 5: Commit**

```bash
git add tests/json_tests/test_inference_eval.py pyproject.toml
git commit -m "test: add LLM inference eval for compact_json accuracy"
```

---

### Task 6: Run the Full Eval

- [ ] **Step 1: Run deterministic tests**

```bash
cd /home/edge/code/tokkit && pytest tests/json_tests/test_data_fidelity.py tests/json_tests/test_compact_json.py -v
```

Expected: all PASS.

- [ ] **Step 2: Run inference eval**

```bash
cd /home/edge/code/tokkit && pytest -m inference tests/json_tests/test_inference_eval.py -v --timeout=300
```

Expected: 10 tests run (9 questions + 1 report). Review `tests/INFERENCE_EVAL_RESULTS.md` for accuracy comparison.

- [ ] **Step 3: Review results and commit report**

Read `tests/INFERENCE_EVAL_RESULTS.md`. If any treatment tests failed:
- Check if control also failed (question too hard, not a compaction issue)
- Check if it's a compaction bug (data fidelity test should have caught it)
- Check if it's a prompt issue (compacted format confuses the LLM on this question type)

```bash
git add tests/INFERENCE_EVAL_RESULTS.md
git commit -m "test: add inference eval results"
```
