"""Unit tests for the markdown section tree parser."""

from tokkit_markdown.parser import parse_markdown, Section


def test_single_header():
    md = "# Title\n\nSome content here."
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].level == 1
    assert sections[0].title == "Title"
    assert "Some content here." in sections[0].content


def test_nested_headers():
    md = """# Top
Intro text.

## Child One
Child one content.

## Child Two
Child two content.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Top"
    assert "Intro text." in sections[0].content
    assert len(sections[0].children) == 2
    assert sections[0].children[0].title == "Child One"
    assert sections[0].children[1].title == "Child Two"


def test_deeply_nested():
    md = """# H1
## H2
### H3
#### H4
##### H5
###### H6
Deepest content.
"""
    sections = parse_markdown(md)
    assert sections[0].title == "H1"
    node = sections[0]
    for i in range(2, 7):
        assert len(node.children) == 1
        node = node.children[0]
        assert node.level == i
    assert "Deepest content." in node.content


def test_skipped_levels():
    md = """# Top
## Sub
#### Skipped H3
Content under h4.
"""
    sections = parse_markdown(md)
    h1 = sections[0]
    h2 = h1.children[0]
    # h4 becomes child of h2 even though h3 was skipped
    assert len(h2.children) == 1
    assert h2.children[0].level == 4
    assert h2.children[0].title == "Skipped H3"


def test_multiple_top_level():
    md = """# First
Content one.

# Second
Content two.

# Third
Content three.
"""
    sections = parse_markdown(md)
    assert len(sections) == 3
    assert sections[0].title == "First"
    assert sections[1].title == "Second"
    assert sections[2].title == "Third"


def test_content_before_first_header():
    md = """Preamble text here.

# First Header
Content.
"""
    sections = parse_markdown(md)
    # Preamble becomes a level-0 section
    assert sections[0].level == 0
    assert "Preamble text here." in sections[0].content
    assert sections[1].title == "First Header"


def test_empty_sections():
    md = """# Empty One
# Empty Two
# Has Content
Some text.
"""
    sections = parse_markdown(md)
    assert len(sections) == 3
    assert sections[0].content.strip() == ""
    assert sections[1].content.strip() == ""
    assert "Some text." in sections[2].content


def test_header_with_inline_formatting():
    md = """# **Bold** Header
## `Code` in *Heading*
Content.
"""
    sections = parse_markdown(md)
    assert sections[0].title == "**Bold** Header"
    assert sections[0].children[0].title == "`Code` in *Heading*"


def test_hash_in_code_block_not_parsed_as_header():
    md = """# Real Header
Content before code.

```python
# This is a comment, not a header
## Also not a header
def foo():
    pass
```

More content after code.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Real Header"
    assert "# This is a comment" in sections[0].content
    assert "More content after code." in sections[0].content


def test_hash_in_indented_code_block():
    md = """# Real Header

    # indented code line
    ## also indented

After indented block.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert "# indented code line" in sections[0].content


def test_no_headers():
    md = "Just plain text.\nAnother line."
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].level == 0
    assert "Just plain text." in sections[0].content


def test_empty_document():
    sections = parse_markdown("")
    assert sections == []


def test_whitespace_only():
    sections = parse_markdown("   \n\n   ")
    assert sections == []


def test_char_count_includes_children():
    md = """# Parent
Parent text.

## Child
Child text is longer than parent text for testing.
"""
    sections = parse_markdown(md)
    parent = sections[0]
    child = parent.children[0]
    # Parent char_count should include child's content
    assert parent.char_count > child.char_count
    assert parent.char_count >= len("Parent text.") + child.char_count


def test_large_document_many_sections():
    parts = []
    for i in range(50):
        parts.append(f"## Section {i}\nContent for section {i}.\n")
    md = "# Main\n" + "\n".join(parts)
    sections = parse_markdown(md)
    assert sections[0].title == "Main"
    assert len(sections[0].children) == 50


def test_hash_in_tilde_code_block():
    md = """# Real Header

~~~
# Not a header
## Also not
~~~

After tilde block.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Real Header"
    assert "# Not a header" in sections[0].content
    assert "After tilde block." in sections[0].content


def test_setext_headers_ignored():
    """ATX headers only — setext-style (underline) not treated as headers."""
    md = """# Real Header

Setext Header
==============

Also Setext
-----------

Content.
"""
    sections = parse_markdown(md)
    assert len(sections) == 1
    assert sections[0].title == "Real Header"
    assert "Setext Header" in sections[0].content
