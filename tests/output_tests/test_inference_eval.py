"""LLM inference accuracy eval for compact_output.

Run: pytest -m inference tests/output_tests/test_inference_eval.py -v
"""

import asyncio
import json
import os
import re
from datetime import date

import pytest
from pydantic import BaseModel

from tokkit_output import compact_output
from output_tests.fixtures.eval_fixtures import QUESTIONS, FIXTURES, CountAnswer, ListAnswer, FileLineAnswer, StatusAnswer

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

EVAL_MODEL = os.environ.get("TOKKIT_EVAL_MODEL", "haiku")
CHARS_PER_TOKEN = 4


def _extract_json(text: str) -> dict:
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1)
    return json.loads(text.strip())


def _ask_llm(data_str: str, question: str, response_model: type[BaseModel], model: str) -> BaseModel:
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    system = (
        "You are a data analyst. You will be given command output and a question. "
        "Analyze the output carefully and answer the question. "
        "Respond with ONLY a raw JSON object matching this schema "
        "(no markdown, no code fences, no explanation, just JSON):\n"
        f"{schema}"
    )
    options = ClaudeAgentOptions(system_prompt=system, model=model, max_turns=1)
    user_prompt = f"Given the following command output:\n\n{data_str}\n\nAnswer this question: {question}"

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


def _answers_match(result: BaseModel, gold: BaseModel) -> bool:
    if isinstance(gold, CountAnswer):
        return result.count == gold.count
    if isinstance(gold, ListAnswer):
        return set(s.lower() for s in result.items) == set(s.lower() for s in gold.items)
    if isinstance(gold, FileLineAnswer):
        return result.file == gold.file and result.line == gold.line
    if isinstance(gold, StatusAnswer):
        return result.status.lower() == gold.status.lower()
    raise TypeError(f"Unknown type: {type(gold)}")


_results: list[dict] = []
_question_ids = [q["id"] for q in QUESTIONS]


@pytest.mark.inference
class TestOutputInferenceEval:

    @pytest.mark.parametrize("q_id", _question_ids)
    def test_question(self, q_id):
        q = next(q for q in QUESTIONS if q["id"] == q_id)
        raw = FIXTURES[q["fixture_name"]]
        compacted = compact_output(raw, hint=q["fixture_name"])
        gold = q["gold"]

        control = _ask_llm(raw, q["question"], q["model"], EVAL_MODEL)
        treatment = _ask_llm(compacted, q["question"], q["model"], EVAL_MODEL)

        _results.append({
            "id": q_id,
            "fixture": q["fixture_name"],
            "question": q["question"],
            "control_correct": _answers_match(control, gold),
            "treatment_correct": _answers_match(treatment, gold),
            "raw_tokens": len(raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(compacted) // CHARS_PER_TOKEN,
        })

        assert _answers_match(treatment, gold), (
            f"{q_id} treatment wrong: got {treatment.model_dump()}, expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        if len(_results) < len(_question_ids):
            pytest.skip("Not all results collected")

        ctrl_ok = sum(1 for r in _results if r["control_correct"])
        treat_ok = sum(1 for r in _results if r["treatment_correct"])
        total = len(_results)

        lines = [
            "# compact_output Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Model:** {EVAL_MODEL}",
            f"**Questions:** {total}",
            "",
            "| # | Fixture | Question | Control | Treatment | Savings |",
            "|---|---------|----------|---------|-----------|---------|",
        ]

        for r in _results:
            savings = (1 - r["compact_tokens"] / r["raw_tokens"]) * 100 if r["raw_tokens"] > 0 else 0
            ctrl = "PASS" if r["control_correct"] else "FAIL"
            treat = "PASS" if r["treatment_correct"] else "FAIL"
            lines.append(f"| {r['id']} | {r['fixture']} | {r['question'][:40]} | {ctrl} | {treat} | {savings:.0f}% |")

        lines.extend([
            "",
            f"**Control:** {ctrl_ok}/{total} ({ctrl_ok/total*100:.0f}%)",
            f"**Treatment:** {treat_ok}/{total} ({treat_ok/total*100:.0f}%)",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "OUTPUT_INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\n\n{report}")
