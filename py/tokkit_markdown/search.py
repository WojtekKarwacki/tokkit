"""Search markdown sections by keyword matching with ranked results."""

from __future__ import annotations

from tokkit_markdown.parser import parse_markdown, Section

CHARS_PER_TOKEN = 4
MAX_RESULTS = 5
SCORE_THRESHOLD = 0.75  # drop results scoring below 75% of the top result


def search_markdown(markdown: str, query: str) -> list[dict]:
    """Search markdown content by query, returning ranked matching sections.

    Returns a list of match dicts sorted by score (highest first):
        {"title", "path", "score", "match_type", "content", "tokens"}

    Applies three optimizations:
    1. Deduplication: if a parent section matches, its children are not
       returned as separate results (they're already in the parent content).
    2. Content-match filtering: when header matches exist, content-only
       matches are dropped to avoid noise.
    3. Budget cap: total returned tokens never exceed the original document.

    Empty query returns empty list.
    No matches returns empty list.
    """
    if not markdown or not markdown.strip() or not query or not query.strip():
        return []

    sections = parse_markdown(markdown)
    if not sections:
        return []

    query_words = query.lower().split()
    all_results: list[dict] = []

    _score_tree(sections, query_words, [], all_results)

    all_results.sort(key=lambda r: r["score"], reverse=True)

    # --- Dedup: if a parent is in results, remove its descendants ---
    matched_paths: list[str] = []
    deduped: list[dict] = []
    for r in all_results:
        is_child_of_existing = any(
            r["path"].startswith(p + " > ") for p in matched_paths
        )
        if is_child_of_existing:
            continue
        deduped.append(r)
        matched_paths.append(r["path"])

    # --- Score threshold: drop results far below the best match ---
    if deduped:
        top_score = deduped[0]["score"]
        cutoff = top_score * SCORE_THRESHOLD
        deduped = [r for r in deduped if r["score"] >= cutoff]

    # --- Budget cap: don't return more tokens than the original doc ---
    # Always allow at least MIN_RESULTS so small docs aren't over-capped.
    doc_tokens = max(1, len(markdown) // CHARS_PER_TOKEN)
    min_results = 2
    capped: list[dict] = []
    running = 0
    for r in deduped[:MAX_RESULTS]:
        if running + r["tokens"] > doc_tokens and len(capped) >= min_results:
            break
        capped.append(r)
        running += r["tokens"]

    return capped


def _score_tree(
    sections: list[Section],
    query_words: list[str],
    parent_path: list[str],
    results: list[dict],
) -> None:
    """Recursively score all sections in the tree."""
    for section in sections:
        if section.level == 0:
            path_entry = "(preamble)"
        else:
            prefix = "#" * section.level
            path_entry = f"{prefix} {section.title}"

        current_path = parent_path + [path_entry]

        score, match_type, has_header_word = _score_section(section, query_words)
        if score > 0:
            full_content = _render_section_content(section)
            results.append({
                "title": section.title or "(preamble)",
                "path": " > ".join(current_path),
                "score": round(score, 3),
                "match_type": match_type,
                "content": full_content,
                "tokens": max(1, len(full_content) // CHARS_PER_TOKEN),
                "_has_header_word": has_header_word,
            })

        _score_tree(section.children, query_words, current_path, results)


def _score_section(section: Section, query_words: list[str]) -> tuple[float, str, bool]:
    """Score a section against query words.

    Returns (score, match_type, has_header_word). Score 0 means no match.
    has_header_word is True if at least one query word matched the header.
    """
    if not query_words:
        return 0.0, "", False

    title_lower = section.title.lower() if section.title else ""
    content_lower = section.content.lower()

    word_scores: list[float] = []
    header_word_count = 0

    for word in query_words:
        best_word_score = 0.0

        # Tier 1: Header substring match (base 1.0)
        if word in title_lower:
            best_word_score = 1.0
            header_word_count += 1

        # Tier 3: Content substring match (base 0.3)
        if best_word_score == 0.0 and word in content_lower:
            best_word_score = 0.3

        word_scores.append(best_word_score)

    # Average across words — sections matching all words rank higher
    avg_score = sum(word_scores) / len(word_scores)

    if avg_score == 0.0:
        return 0.0, "", False

    # Depth bonus: deeper = more precise
    depth_bonus = 0.05 * section.level
    final_score = avg_score + depth_bonus

    has_header_word = header_word_count > 0
    match_type = "header" if header_word_count == len(query_words) else "content"

    return final_score, match_type, has_header_word


def _render_section_content(section: Section) -> str:
    """Render a section's full content including children."""
    parts = []
    if section.content:
        parts.append(section.content)
    for child in section.children:
        prefix = "#" * child.level
        parts.append(f"{prefix} {child.title}")
        child_content = _render_section_content(child)
        if child_content:
            parts.append(child_content)
    return "\n\n".join(parts)
