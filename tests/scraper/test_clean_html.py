"""Unit tests for the HTML stripping pipeline."""

from tokkit_scraper.pipeline import strip_noise


def test_removes_script_tags():
    html = "<html><body><p>Hello</p><script>alert('x')</script></body></html>"
    result = strip_noise(html)
    assert "alert" not in result
    assert "Hello" in result


def test_removes_style_tags():
    html = "<html><body><p>Hello</p><style>.x { color: red; }</style></body></html>"
    result = strip_noise(html)
    assert "color" not in result
    assert "Hello" in result


def test_removes_head():
    html = "<html><head><title>Page</title><meta charset='utf-8'></head><body><p>Content</p></body></html>"
    result = strip_noise(html)
    assert "<title>" not in result
    assert "<meta" not in result
    assert "Content" in result


def test_removes_nav_footer_aside():
    html = """<html><body>
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
        <main><p>Article content here</p></main>
        <footer><p>Copyright 2024</p></footer>
        <aside><p>Related links</p></aside>
    </body></html>"""
    result = strip_noise(html)
    assert "Article content here" in result
    assert "Home" not in result
    assert "Copyright" not in result
    assert "Related links" not in result


def test_removes_noise_by_class_id():
    html = """<html><body>
        <div class="cookie-banner">Accept cookies</div>
        <div id="gdpr-consent">GDPR stuff</div>
        <div class="sidebar-nav">Menu</div>
        <div class="ad-container">Buy now</div>
        <p>Real content</p>
    </body></html>"""
    result = strip_noise(html)
    assert "Accept cookies" not in result
    assert "GDPR stuff" not in result
    assert "Menu" not in result
    assert "Buy now" not in result
    assert "Real content" in result


def test_strips_attributes():
    html = '<html><body><p class="intro" data-id="5" style="color:red">Hello</p><a href="/page" class="link" onclick="go()">Click</a></body></html>'
    result = strip_noise(html)
    assert 'class=' not in result
    assert 'data-id' not in result
    assert 'style=' not in result
    assert 'onclick=' not in result
    assert 'href="/page"' in result
    assert "Hello" in result
    assert "Click" in result


def test_collapses_whitespace():
    html = "<html><body><p>Hello    world</p><p>   </p><p>Next</p></body></html>"
    result = strip_noise(html)
    assert "Hello    world" not in result
    assert "Hello" in result
    assert "world" in result
    assert "Next" in result


from tokkit_scraper.markdown import html_to_markdown


def test_markdown_headings():
    html = "<h1>Title</h1><h2>Subtitle</h2><h3>Section</h3>"
    result = html_to_markdown(html)
    assert "# Title" in result
    assert "## Subtitle" in result
    assert "### Section" in result


def test_markdown_links():
    html = '<p>Visit <a href="https://example.com">Example</a> for more.</p>'
    result = html_to_markdown(html)
    assert "[Example](https://example.com)" in result


def test_markdown_lists():
    html = "<ul><li>One</li><li>Two</li></ul><ol><li>First</li><li>Second</li></ol>"
    result = html_to_markdown(html)
    assert "- One" in result
    assert "- Two" in result
    assert "1. First" in result
    assert "2. Second" in result


def test_markdown_tables():
    html = "<table><tr><th>Name</th><th>Age</th></tr><tr><td>Alice</td><td>30</td></tr></table>"
    result = html_to_markdown(html)
    assert "| Name | Age |" in result
    assert "| --- | --- |" in result
    assert "| Alice | 30 |" in result


def test_markdown_code_blocks():
    html = "<pre><code>def hello():\n    print('hi')</code></pre>"
    result = html_to_markdown(html)
    assert "```" in result
    assert "def hello():" in result


def test_markdown_emphasis():
    html = "<p><strong>Bold</strong> and <em>italic</em> and <b>also bold</b> and <i>also italic</i></p>"
    result = html_to_markdown(html)
    assert "**Bold**" in result
    assert "*italic*" in result
    assert "**also bold**" in result
    assert "*also italic*" in result


def test_markdown_blockquotes():
    html = "<blockquote><p>A wise quote</p></blockquote>"
    result = html_to_markdown(html)
    assert "> A wise quote" in result


def test_markdown_images():
    html = '<img alt="A cat" src="https://example.com/cat.jpg">'
    result = html_to_markdown(html)
    assert "![A cat](https://example.com/cat.jpg)" in result


from tokkit_scraper import clean_html


def test_text_mode():
    html = "<html><body><h1>Title</h1><p>Hello <strong>world</strong></p></body></html>"
    result = clean_html(html, mode="text")
    assert "Title" in result
    assert "Hello" in result
    assert "world" in result
    assert "#" not in result
    assert "**" not in result
    assert "<" not in result


def test_minimal_mode():
    html = """<html><body>
        <script>alert('x')</script>
        <style>.x{}</style>
        <nav><a href="/">Home</a></nav>
        <p class="intro">Content</p>
    </body></html>"""
    result = clean_html(html, mode="minimal")
    assert "alert" not in result
    assert ".x{}" not in result
    assert "Home" in result
    assert "Content" in result


def test_empty_input():
    assert clean_html("") == ""
    assert clean_html("   ") == ""


def test_invalid_mode_raises():
    import pytest
    with pytest.raises(ValueError, match="mode"):
        clean_html("<p>Hi</p>", mode="invalid")


def test_markdown_mode_default():
    html = "<html><body><h1>Title</h1><p>Paragraph</p></body></html>"
    result = clean_html(html)
    assert "# Title" in result
    assert "Paragraph" in result


def test_full_pipeline_markdown():
    html = """<html>
    <head><title>Page</title></head>
    <body>
        <nav><a href="/">Home</a></nav>
        <script>tracking()</script>
        <main>
            <h1>Article</h1>
            <p>Read <a href="/more">more here</a>.</p>
        </main>
        <footer>Copyright</footer>
    </body></html>"""
    result = clean_html(html, mode="markdown")
    assert "# Article" in result
    assert "[more here](/more)" in result
    assert "Home" not in result
    assert "tracking" not in result
    assert "Copyright" not in result
