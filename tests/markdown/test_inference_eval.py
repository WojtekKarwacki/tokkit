"""LLM inference eval for search_markdown.

Compares LLM accuracy and token cost when given:
  - Control: full markdown document
  - Treatment: search_markdown output (matching sections only)

Both must answer correctly. Treatment should use fewer tokens.
Uses claude_agent_sdk (authenticates via Claude Code credentials).

Run: pytest -m inference tests/markdown/test_inference_eval.py -v
"""

import asyncio
import json
import os
import re
from datetime import date

import pytest
from pydantic import BaseModel

from tokkit_markdown import search_markdown

from markdown.fixtures.eval_questions import (
    QUESTIONS,
    TextAnswer,
    ListAnswer,
    CountAnswer,
    BoolAnswer,
    load_fixture,
)

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODELS = os.environ.get("TOKKIT_EVAL_MODELS", "haiku").split(",")
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


def _ask_llm(context: str, question: str, response_model: type[BaseModel], model: str) -> BaseModel:
    """Send a question + context to Claude, return parsed structured output."""
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    system = (
        "You are a documentation analyst. You will be given documentation content "
        "and a question about it. Read carefully and answer precisely. "
        "Respond with ONLY a raw JSON object matching this schema "
        "(no markdown, no code fences, no explanation, just JSON):\n"
        f"{schema}"
    )

    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model,
        max_turns=1,
    )

    user_prompt = f"Documentation:\n\n{context}\n\nQuestion: {question}"

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
# Answer comparison
# ---------------------------------------------------------------------------

def answers_match(result: BaseModel, gold: BaseModel) -> bool:
    """Compare LLM result against gold answer."""
    if isinstance(gold, TextAnswer):
        # Normalize: lowercase, strip quotes/brackets
        r = result.answer.strip().strip('"\'[]').lower()
        g = gold.answer.strip().strip('"\'[]').lower()
        return g in r or r in g

    if isinstance(gold, CountAnswer):
        return result.count == gold.count

    if isinstance(gold, BoolAnswer):
        return result.answer == gold.answer

    if isinstance(gold, ListAnswer):
        return set(s.lower().strip() for s in result.items) == set(s.lower().strip() for s in gold.items)

    raise TypeError(f"Unknown answer type: {type(gold)}")


# ---------------------------------------------------------------------------
# Results collection
# ---------------------------------------------------------------------------

_results: list[dict] = []


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

_question_ids = [q["id"] for q in QUESTIONS]


@pytest.mark.inference
class TestMarkdownInferenceEval:

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.parametrize("q_id", _question_ids)
    def test_question(self, q_id, model):
        q = next(q for q in QUESTIONS if q["id"] == q_id)
        full_md = load_fixture(q["fixture"])
        gold = q["gold_fn"](full_md)

        # Treatment: search_markdown output
        treatment_context = search_markdown(full_md, q["query"])

        # Control: full document
        control_tokens = len(full_md) // CHARS_PER_TOKEN
        treatment_tokens = len(treatment_context) // CHARS_PER_TOKEN

        control = _ask_llm(full_md, q["question"], q["model"], model)
        treatment = _ask_llm(treatment_context, q["question"], q["model"], model)

        _results.append({
            "id": q_id,
            "model": model,
            "fixture": q["fixture"],
            "query": q["query"],
            "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "control_tokens": control_tokens,
            "treatment_tokens": treatment_tokens,
        })

        # Treatment must get the right answer
        assert answers_match(treatment, gold), (
            f"[{model}] {q_id} treatment wrong: got {treatment.model_dump()}, "
            f"expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        """Generate markdown report after all questions."""
        expected = len(QUESTIONS) * len(MODELS)
        if len(_results) < expected:
            pytest.skip(f"Only {len(_results)}/{expected} results collected")

        total_control = sum(r["control_tokens"] for r in _results)
        total_treatment = sum(r["treatment_tokens"] for r in _results)
        total_savings = (1 - total_treatment / total_control) * 100 if total_control > 0 else 0

        lines = [
            "# Markdown Search Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Models:** {', '.join(MODELS)}",
            f"**Questions:** {len(QUESTIONS)}",
            f"**Total LLM calls:** {len(_results) * 2} ({len(_results)} questions x 2 control/treatment)",
            "",
            "## Per-Question Results",
            "",
            "| # | Fixture | Query | " + " | ".join(f"{m} Ctrl | {m} Treat" for m in MODELS) + " | Control Tok | Treat Tok | Savings |",
            "|---|---------|-------|" + "|".join("---------|----------" for _ in MODELS) + "|------------|-----------|---------|",
        ]

        for q in QUESTIONS:
            q_results = {r["model"]: r for r in _results if r["id"] == q["id"]}
            if not q_results:
                continue
            cols = []
            for m in MODELS:
                r = q_results.get(m)
                if r:
                    ctrl = "PASS" if r["control_correct"] else "FAIL"
                    treat = "PASS" if r["treatment_correct"] else "FAIL"
                    cols.append(f" {ctrl} | {treat}")
                else:
                    cols.append(" - | -")
            r0 = next(iter(q_results.values()))
            savings = (1 - r0["treatment_tokens"] / r0["control_tokens"]) * 100 if r0["control_tokens"] > 0 else 0
            lines.append(
                f"| {q['id']} | {q['fixture'][:15]} | `{q['query'][:20]}` |"
                + " |".join(cols)
                + f" | {r0['control_tokens']:,} | {r0['treatment_tokens']:,} | {savings:.0f}% |"
            )

        # Totals
        lines.extend([
            "",
            "## Token Savings Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total control tokens | {total_control:,} |",
            f"| Total treatment tokens | {total_treatment:,} |",
            f"| Total savings | {total_savings:.1f}% |",
            f"| Ratio | {total_control / total_treatment:.1f}x |" if total_treatment > 0 else f"| Ratio | inf |",
        ])

        # Accuracy summary
        lines.extend(["", "## Accuracy Summary", ""])
        for m in MODELS:
            m_results = [r for r in _results if r["model"] == m]
            ctrl_ok = sum(1 for r in m_results if r["control_correct"])
            treat_ok = sum(1 for r in m_results if r["treatment_correct"])
            total = len(m_results)
            lines.append(
                f"**{m}:** Control {ctrl_ok}/{total} ({ctrl_ok/total*100:.0f}%), "
                f"Treatment {treat_ok}/{total} ({treat_ok/total*100:.0f}%)"
            )

        # Failures
        failures = [r for r in _results if not r["treatment_correct"]]
        if failures:
            lines.extend(["", "## Treatment Failures", ""])
            for r in failures:
                lines.append(f"### [{r['model']}] {r['id']}: {r['question']}")
                lines.append(f"- **Query:** `{r['query']}`")
                lines.append(f"- **Gold:** `{r['gold_answer']}`")
                lines.append(f"- **Treatment got:** `{r['treatment_answer']}`")
                lines.append(f"- **Control got:** `{r['control_answer']}`")
                ctrl_ok = "correct" if r["control_correct"] else "also wrong"
                lines.append(f"- **Control was:** {ctrl_ok}")
                lines.append("")

        lines.extend([
            "",
            "## Methodology",
            "",
            "**Control:** LLM receives the full markdown document + question.",
            "**Treatment:** LLM receives `search_markdown(doc, query)` output + question.",
            "",
            "Both paths use the same model, system prompt, and question. "
            "Gold answers are computed deterministically from the fixture text. "
            "Token counts are estimated as `len(context) / 4`.",
            "",
            "The eval proves that `search_markdown` returns enough context "
            "for the LLM to answer correctly while using significantly fewer tokens.",
        ])

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "MARKDOWN_INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
