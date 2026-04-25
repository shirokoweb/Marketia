"""Tests for marketia.reports — pure-Python helpers with no API dependency."""

from __future__ import annotations

import pytest

from marketia.reports import (
    append_followup_to_report,
    generate_frontmatter,
    parse_frontmatter,
    save_research_report,
    slugify,
    update_frontmatter,
)

# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_truncates_at_60():
    assert len(slugify("a" * 100)) == 60


def test_slugify_empty_string():
    assert slugify("") == ""


def test_slugify_collapses_spaces_and_underscores():
    assert slugify("foo  bar__baz") == "foo-bar-baz"


# ---------------------------------------------------------------------------
# generate_frontmatter
# ---------------------------------------------------------------------------


def test_generate_frontmatter_has_required_fields():
    fm = generate_frontmatter("My Title", tags=["tag1"])
    assert fm.startswith("---\n")
    assert "title:" in fm
    assert "tags:" in fm
    assert "date:" in fm
    assert fm.strip().endswith("---")


def test_generate_frontmatter_includes_custom_tags():
    fm = generate_frontmatter("T", tags=["market", "ai"])
    assert "market" in fm
    assert "ai" in fm


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


def test_parse_frontmatter_round_trip():
    fm = generate_frontmatter("Round Trip", tags=["a", "b"])
    full = f"{fm}body text here"
    data, body = parse_frontmatter(full)
    assert data["title"] == "Round Trip"
    assert "a" in data["tags"]
    assert body.strip() == "body text here"


def test_parse_frontmatter_no_frontmatter():
    data, body = parse_frontmatter("just a body")
    assert data == {}
    assert body == "just a body"


def test_parse_frontmatter_malformed_yaml():
    bad = "---\n: : :\n---\nbody"
    data, _ = parse_frontmatter(bad)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# update_frontmatter
# ---------------------------------------------------------------------------


def test_update_frontmatter_merges_new_key():
    fm = generate_frontmatter("T")
    full = f"{fm}body"
    updated = update_frontmatter(full, {"interaction_id": "abc123"})
    data, _ = parse_frontmatter(updated)
    assert data["interaction_id"] == "abc123"
    assert data["title"] == "T"


# ---------------------------------------------------------------------------
# save_research_report
# ---------------------------------------------------------------------------


def test_save_research_report_creates_file(tmp_path):
    path = save_research_report(
        content="report body",
        title="My Report",
        output_dir=str(tmp_path),
    )
    assert path.exists()
    assert "my-report" in path.name


def test_save_research_report_collision_handling(tmp_path):
    p1 = save_research_report(content="a", title="Same Title", output_dir=str(tmp_path))
    p2 = save_research_report(content="b", title="Same Title", output_dir=str(tmp_path))
    assert p1 != p2
    assert p1.exists()
    assert p2.exists()


def test_save_research_report_invalid_dir():
    with pytest.raises(NotADirectoryError):
        save_research_report(content="x", title="T", output_dir="/nonexistent/dir/abc")


# ---------------------------------------------------------------------------
# append_followup_to_report
# ---------------------------------------------------------------------------


def test_append_followup_increments_count(tmp_path):
    path = save_research_report(content="body", title="Parent", output_dir=str(tmp_path))
    count = append_followup_to_report(path, "follow content", "What about X?")
    assert count == 1
    count2 = append_followup_to_report(path, "more", "And Y?")
    assert count2 == 2


def test_append_followup_adds_section(tmp_path):
    path = save_research_report(content="body", title="Parent", output_dir=str(tmp_path))
    append_followup_to_report(path, "answer here", "My question")
    content = path.read_text()
    assert "Follow-up 1:" in content
    assert "answer here" in content
