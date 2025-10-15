"""LLM inference accuracy eval for compact_json.

Compares LLM accuracy on raw JSON vs compacted JSON against gold answers.
Uses claude_agent_sdk (authenticates via Claude Code credentials).

Run: pytest -m inference tests/json_tests/test_inference_eval.py -v
"""

import asyncio
import json
import os
import re
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
    load_sparse,
    load_tricky,
    load_large_orders,
)

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

EVAL_MODEL = os.environ.get("TOKKIT_EVAL_MODEL", "haiku")
SKIP_QUESTIONS = {"q1", "q6"}  # redundant: Q10/Q14 supersede Q1, Q13/Q15 supersede Q6
CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1)
    return json.loads(text.strip())


def _ask_llm(data_str: str, question: str, response_model: type[BaseModel], model: str) -> BaseModel:
    """Send a question + data to Claude, return parsed structured output."""
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    system = (
        "You are a data analyst. You will be given a dataset and a question. "
        "Analyze the data carefully and answer the question. "
        "Respond with ONLY a raw JSON object matching this schema "
        "(no markdown, no code fences, no explanation, just JSON):\n"
        f"{schema}"
    )

    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model,
        max_turns=1,
    )

    user_prompt = f"Given the following data:\n\n{data_str}\n\nAnswer this question: {question}"

    result_text = None

    async def _run():
        nonlocal result_text
        async for msg in query(prompt=user_prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_text = msg.result

    asyncio.get_event_loop().run_until_complete(_run())

    if not result_text:
        raise RuntimeError("No result from Claude")

    raw = _extract_json(result_text)
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
# Fixture data loaders (cached at module level)
# ---------------------------------------------------------------------------

_fixture_cache: dict[str, tuple] = {}


def _get_fixture(fixture_name: str) -> tuple[str, str, object]:
    """Return (raw_json, compacted, parsed_data) for a fixture. Cached."""
    if fixture_name not in _fixture_cache:
        if fixture_name == "org":
            data = load_org()
        elif fixture_name == "ecommerce":
            data = load_ecommerce()
        elif fixture_name == "sparse":
            data = load_sparse()
        elif fixture_name == "tricky":
            data = load_tricky()
        elif fixture_name == "large":
            data = load_large_orders()
        else:
            raise ValueError(f"Unknown fixture: {fixture_name}")
        raw = json.dumps(data, indent=2)
        compacted = compact_json(raw)
        _fixture_cache[fixture_name] = (raw, compacted, data)
    return _fixture_cache[fixture_name]


# ---------------------------------------------------------------------------
# Results collection
# ---------------------------------------------------------------------------

_results: list[dict] = []


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

_question_ids = [q["id"] for q in QUESTIONS if q["id"] not in SKIP_QUESTIONS]


@pytest.mark.inference
class TestInferenceEval:

    @pytest.mark.parametrize("q_id", _question_ids)
    def test_question(self, q_id):
        q = next(q for q in QUESTIONS if q["id"] == q_id)
        raw, compacted, data = _get_fixture(q["fixture"])
        gold = q["gold_fn"](data)

        control = _ask_llm(raw, q["question"], q["model"], EVAL_MODEL)
        treatment = _ask_llm(compacted, q["question"], q["model"], EVAL_MODEL)

        _results.append({
            "id": q_id,
            "model": EVAL_MODEL,
            "fixture": q["fixture"],
            "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(compacted) // CHARS_PER_TOKEN,
        })

        assert answers_match(treatment, gold), (
            f"[{EVAL_MODEL}] {q_id} treatment wrong: got {treatment.model_dump()}, "
            f"expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        """Generate markdown report after all questions."""
        expected = len(_question_ids)
        if len(_results) < expected:
            pytest.skip(f"Only {len(_results)}/{expected} results collected")

        ctrl_ok = sum(1 for r in _results if r["control_correct"])
        treat_ok = sum(1 for r in _results if r["treatment_correct"])
        total = len(_results)

        lines = [
            "# JSON Compaction Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Model:** {EVAL_MODEL}",
            f"**Questions:** {total}",
            f"**LLM calls:** {total * 2} ({total} x 2 control/treatment)",
            "",
            "## Results",
            "",
            "| # | Fixture | Question | Control | Treatment | Savings |",
            "|---|---------|----------|---------|-----------|---------|",
        ]

        for r in _results:
            savings = (1 - r["compact_tokens"] / r["raw_tokens"]) * 100 if r["raw_tokens"] > 0 else 0
            ctrl = "PASS" if r["control_correct"] else "FAIL"
            treat = "PASS" if r["treatment_correct"] else "FAIL"
            lines.append(
                f"| {r['id']} | {r['fixture']} | {r['question'][:50]} "
                f"| {ctrl} | {treat} | {savings:.0f}% |"
            )

        lines.extend([
            "",
            "## Summary",
            "",
            f"- **Control accuracy:** {ctrl_ok}/{total} ({ctrl_ok/total*100:.0f}%)",
            f"- **Treatment accuracy:** {treat_ok}/{total} ({treat_ok/total*100:.0f}%)",
            f"- **Accuracy delta:** {treat_ok - ctrl_ok}",
            "",
        ])

        # Per fixture type
        lines.append("## By Fixture Type")
        lines.append("")
        fixture_types = list(dict.fromkeys(r["fixture"] for r in _results))
        for ft in fixture_types:
            ft_results = [r for r in _results if r["fixture"] == ft]
            ft_ctrl = sum(1 for r in ft_results if r["control_correct"])
            ft_treat = sum(1 for r in ft_results if r["treatment_correct"])
            ft_total = len(ft_results)
            lines.append(f"**{ft}:** Control {ft_ctrl}/{ft_total}, Treatment {ft_treat}/{ft_total}")
        lines.append("")

        # Failures detail
        failures = [r for r in _results if not r["treatment_correct"]]
        if failures:
            lines.append("## Treatment Failures")
            lines.append("")
            for r in failures:
                lines.append(f"### {r['id']}: {r['question']}")
                lines.append(f"- **Gold:** `{r['gold_answer']}`")
                lines.append(f"- **Treatment got:** `{r['treatment_answer']}`")
                lines.append(f"- **Control got:** `{r['control_answer']}`")
                ctrl_status = "correct" if r["control_correct"] else "also wrong"
                lines.append(f"- **Control was:** {ctrl_status}")
                lines.append("")

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
