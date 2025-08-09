"""Unit tests for JSON compaction."""

from tokkit_json.schema_conv import to_schema_csv
from tokkit_json import compact_json


# ---------------------------------------------------------------------------
# Schema-based conversion
# ---------------------------------------------------------------------------

def test_flat_array_of_objects():
    obj = [{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;age]"
    assert lines[1] == "alice;30"
    assert lines[2] == "bob;25"


def test_single_object():
    obj = {"name": "alice", "age": 30}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;age]"
    assert lines[1] == "alice;30"


def test_nested_array_of_objects():
    obj = {
        "id": "user1",
        "name": "bob",
        "projects": [
            {"id": "p1", "name": "super project"},
            {"id": "p2", "name": "another project"},
        ],
    }
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[id;name;projects:[{id;name}]]"
    assert "user1;bob;[{p1;super project};{p2;another project}]" == lines[1]


def test_deeply_nested():
    obj = {
        "id": "user1",
        "name": "bob",
        "surname": "kowalski",
        "projects": [
            {
                "id": "project1",
                "name": "super project",
                "tasks": [
                    {"id": "task1", "title": "my task"},
                    {"id": "task2", "title": "another task"},
                ],
            },
            {
                "id": "project2",
                "name": "another project",
                "tasks": [
                    {"id": "task3", "title": "only one task"},
                ],
            },
        ],
    }
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[id;name;surname;projects:[{id;name;tasks:[{id;title}]}]]"
    expected_data = (
        "user1;bob;kowalski;"
        "[{project1;super project;[{task1;my task};{task2;another task}]};"
        "{project2;another project;[{task3;only one task}]}]"
    )
    assert lines[1] == expected_data


def test_nested_object_not_in_array():
    obj = {"name": "alice", "address": {"city": "NYC", "zip": "10001"}}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;address:{city;zip}]"
    assert lines[1] == "alice;{NYC;10001}"


def test_scalar_list():
    obj = {"name": "alice", "tags": ["admin", "active"]}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;tags]"
    assert lines[1] == "alice;[admin;active]"


def test_empty_list():
    obj = {"name": "alice", "items": []}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;items]"
    assert lines[1] == "alice;[]"


def test_none_values():
    obj = {"name": "alice", "bio": None, "age": 30}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[1] == "alice;;30"


def test_bool_values():
    obj = {"name": "alice", "active": True, "banned": False}
    result = to_schema_csv(obj)
    assert "true" in result
    assert "false" in result


def test_semicolon_in_value_quoted():
    obj = {"text": "hello;world"}
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert '"hello;world"' in lines[1]


def test_missing_keys_across_rows():
    obj = [{"name": "alice", "age": 30}, {"name": "bob", "role": "pm"}]
    result = to_schema_csv(obj)
    lines = result.split("\n")
    assert lines[0] == "[name;age;role]"
    assert lines[1] == "alice;30;"  # missing role
    assert lines[2] == "bob;;pm"    # missing age


def test_top_level_primitive_array():
    obj = [1, 2, 3]
    result = to_schema_csv(obj)
    assert result == "[1;2;3]"


def test_empty_array():
    assert to_schema_csv([]) == "[]"


# ---------------------------------------------------------------------------
# compact_json integration
# ---------------------------------------------------------------------------

def test_compact_json_array_of_objects():
    json_str = '[{"name": "alice", "age": 30}, {"name": "bob", "age": 25}]'
    result = compact_json(json_str)
    lines = result.split("\n")
    assert lines[0] == "[name;age]"
    assert "alice" in lines[1]
    assert "bob" in lines[2]


def test_compact_json_nested():
    json_str = '{"users": [{"name": "alice"}, {"name": "bob"}]}'
    result = compact_json(json_str)
    lines = result.split("\n")
    assert lines[0] == "[users:[{name}]]"
    assert "[{alice};{bob}]" in lines[1]


def test_compact_json_empty_input():
    assert compact_json("") == ""
    assert compact_json("   ") == ""


def test_compact_json_invalid_json():
    import pytest
    with pytest.raises(ValueError, match="Invalid JSON"):
        compact_json("{not valid json")


def test_compact_json_scalar_input():
    result = compact_json('"hello"')
    assert result == "hello"


def test_compact_json_number_input():
    result = compact_json("42")
    assert result == "42"
