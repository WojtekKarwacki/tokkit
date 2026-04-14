"""Tests for chain splitting and primary command detection."""

import pytest
from tokkit_hook.chain import split_chain, find_primary


class TestSplitChain:
    def test_single_command(self):
        assert split_chain("git diff") == ["git diff"]

    def test_and_chain(self):
        result = split_chain("git add . && git commit -m 'fix'")
        assert result == ["git add .", "git commit -m 'fix'"]

    def test_semicolon_chain(self):
        result = split_chain("cd src; pytest")
        assert result == ["cd src", "pytest"]

    def test_respects_single_quotes(self):
        result = split_chain("echo 'hello && world'")
        assert result == ["echo 'hello && world'"]

    def test_respects_double_quotes(self):
        result = split_chain('echo "cd src && run"')
        assert result == ['echo "cd src && run"']

    def test_mixed_chain(self):
        result = split_chain("cd src && pytest; echo done")
        assert len(result) == 3

    def test_empty_string(self):
        assert split_chain("") == []

    def test_whitespace_only(self):
        assert split_chain("   ") == []


class TestFindPrimary:
    def test_find_primary_cd_then_pytest(self):
        commands = ["cd src", "pytest"]
        assert find_primary(commands) == "pytest"

    def test_find_primary_git_add_then_commit(self):
        commands = ["git add .", "git commit -m 'fix'"]
        assert find_primary(commands) == "git commit -m 'fix'"

    def test_find_primary_all_silent(self):
        commands = ["cd src", "mkdir -p out"]
        # Returns last when all are silent
        assert find_primary(commands) == "mkdir -p out"

    def test_find_primary_single(self):
        assert find_primary(["git diff"]) == "git diff"

    def test_find_primary_export_then_pytest(self):
        commands = ["export FOO=bar", "pytest"]
        assert find_primary(commands) == "pytest"

    def test_find_primary_git_stash_push_then_run(self):
        commands = ["git stash push", "cargo test"]
        assert find_primary(commands) == "cargo test"
