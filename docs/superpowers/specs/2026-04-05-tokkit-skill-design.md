# Tokkit Code Intelligence Skill — Design Spec

A Claude Code skill that teaches agents to use tokkit's graph tools for token-efficient codebase exploration.

## Deliverables

1. `tokkit/skill/SKILL.md` — the skill file
2. `tokkit/skill/references/tool-guide.md` — detailed tool usage guide
3. CLAUDE.md entry pointing to the skill

## Skill Metadata

- **name:** tokkit-code-intelligence
- **description:** Triggers on codebase exploration, code understanding, symbol lookup, call tracing, architecture overview for Python/JS/TS repos. Teaches the agent to use tokkit MCP tools instead of reading raw files.
- **Trigger phrases:** "find where X is defined", "how does Y work", "show me the auth flow", "what calls this function", "explore the codebase", "project architecture", "trace the call chain"

## SKILL.md Content (~1,500 words)

Covers:
1. **When to use:** Codebase exploration tasks on Python/JS/TS repos
2. **Workflow:** Index → query graph → read only what's needed
3. **Tool selection guide:** Which tool for which task
4. **Qualified name format:** `project::file::Scope.name`
5. **Confidence interpretation:** 0.95/0.90/0.75/0.55 meaning
6. **Edge types beyond CALLS:** TESTS, CO_CHANGED, SIMILAR_TO, HANDLES
7. **Limitations:** search_code stubbed, max_depth defaults, route detection heuristic
8. **Token stats:** Check savings at end of exploration

## references/tool-guide.md Content

Detailed reference for each tool:
- Exact parameter names and types
- Example calls with realistic arguments
- Expected response format
- Common patterns (find callers, map a feature, find untested code)

## CLAUDE.md Entry

```markdown
@skill/SKILL.md — Use tokkit tools for code exploration instead of reading raw files
```

## What This Does NOT Include

- No hooks (too brittle)
- No plugin scaffolding (skill is standalone)
- No scripts (no programmatic validation needed)
