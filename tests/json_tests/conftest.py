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


@pytest.fixture
def sparse_raw_json() -> str:
    """Load sparse fixture as raw JSON string."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sparse_records.json")
    with open(path) as f:
        return f.read()


@pytest.fixture
def sparse_data(sparse_raw_json) -> list[dict]:
    """Parse sparse fixture."""
    return json.loads(sparse_raw_json)


@pytest.fixture
def sparse_compacted(sparse_raw_json) -> str:
    """Compact sparse fixture."""
    return compact_json(sparse_raw_json)


@pytest.fixture
def tricky_raw_json() -> str:
    """Load tricky values fixture as raw JSON string."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "tricky_values.json")
    with open(path) as f:
        return f.read()


@pytest.fixture
def tricky_data(tricky_raw_json) -> list[dict]:
    """Parse tricky values fixture."""
    return json.loads(tricky_raw_json)


@pytest.fixture
def tricky_compacted(tricky_raw_json) -> str:
    """Compact tricky values fixture."""
    return compact_json(tricky_raw_json)


@pytest.fixture
def large_raw_json() -> str:
    """Generate large orders fixture as raw JSON string."""
    from json_tests.fixtures.eval_questions import generate_large_orders
    return json.dumps(generate_large_orders(), indent=2)


@pytest.fixture
def large_data(large_raw_json) -> list[dict]:
    """Parse large orders fixture."""
    return json.loads(large_raw_json)


@pytest.fixture
def large_compacted(large_raw_json) -> str:
    """Compact large orders fixture."""
    return compact_json(large_raw_json)
