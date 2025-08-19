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


# ---------------------------------------------------------------------------
# Sparse fixture fidelity
# ---------------------------------------------------------------------------

class TestSparseDataFidelity:
    """Verify sparse fixture data survives compaction (especially nulls)."""

    def test_all_ids_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            assert record["id"] in sparse_compacted

    def test_non_null_names_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["name"] is not None:
                assert record["name"] in sparse_compacted, (
                    f"Name '{record['name']}' for {record['id']} missing"
                )

    def test_non_null_cities_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["city"] is not None:
                assert record["city"] in sparse_compacted

    def test_non_null_salaries_preserved(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["salary"] is not None:
                assert str(record["salary"]) in sparse_compacted

    def test_skills_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            for skill in record["skills"]:
                assert skill in sparse_compacted, (
                    f"Skill '{skill}' for {record['id']} missing"
                )

    def test_schema_header_has_all_fields(self, sparse_compacted):
        first_line = sparse_compacted.split("\n")[0]
        for field in ["id", "name", "email", "city", "state", "age", "role", "skills", "salary"]:
            assert field in first_line, f"Field '{field}' missing from schema header"


# ---------------------------------------------------------------------------
# Tricky values fixture fidelity
# ---------------------------------------------------------------------------

class TestTrickyDataFidelity:
    """Verify tricky values survive compaction (escaping edge cases)."""

    def test_all_ids_present(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            assert record["id"] in tricky_compacted

    def test_semicolon_names_present(self, tricky_compacted, tricky_data):
        """Names with semicolons should be quoted in output."""
        for record in tricky_data:
            if ";" in (record["name"] or ""):
                # The name should appear somewhere in the output (possibly quoted)
                assert record["name"].replace(";", "") in tricky_compacted.replace(";", "") or \
                    record["name"] in tricky_compacted, (
                    f"Name '{record['name']}' for {record['id']} missing"
                )

    def test_unicode_preserved(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            if any(ord(c) > 127 for c in (record["name"] or "")):
                assert record["name"] in tricky_compacted

    def test_all_codes_preserved(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            assert str(record["code"]) in tricky_compacted

    def test_empty_string_vs_null(self, tricky_compacted, tricky_data):
        """T11 has empty string name, not null — both should not lose the record."""
        assert "T11" in tricky_compacted


# ---------------------------------------------------------------------------
# Large orders fixture fidelity
# ---------------------------------------------------------------------------

class TestLargeDataFidelity:
    """Verify large-scale fixture data survives compaction."""

    def test_all_order_ids_present(self, large_compacted, large_data):
        for order in large_data:
            assert order["order_id"] in large_compacted, (
                f"Order '{order['order_id']}' missing"
            )

    def test_order_count(self, large_data):
        assert len(large_data) == 120

    def test_all_states_present(self, large_compacted, large_data):
        states = {o["shipping"]["address"]["state"] for o in large_data}
        for state in states:
            assert state in large_compacted

    def test_refund_amounts_preserved(self, large_compacted, large_data):
        for order in large_data:
            for ret in order.get("returns", []):
                assert str(ret["refund_amount"]) in large_compacted
