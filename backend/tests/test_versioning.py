"""model version diff: what changed between two extractions. pure brain
function tested on canned fact sets; identity is the content hash."""

from app.brain import versioning


def _fact(h, statement, status="inferred", kind="capability"):
    return {"content_hash": h, "statement": statement, "kind": kind, "status": status}


def test_no_changes_between_identical_sets():
    d = versioning.diff_versions("v1", "v2", [_fact("a", "a statement")], [_fact("a", "a statement")], ["s1"], ["s1"])
    assert d.facts_added == []
    assert d.facts_removed == []
    assert d.status_changes == []
    assert d.sources_added == []
    assert d.sources_removed == []


def test_added_removed_and_sources():
    d = versioning.diff_versions(
        "v1",
        "v2",
        [_fact("a", "fact a"), _fact("b", "fact b")],
        [_fact("b", "fact b"), _fact("c", "fact c")],
        ["s1", "s2"],
        ["s2", "s3"],
    )
    assert [c.statement for c in d.facts_added] == ["fact c"]
    assert [c.statement for c in d.facts_removed] == ["fact a"]
    assert d.sources_added == ["s3"]
    assert d.sources_removed == ["s1"]


def test_status_change_is_not_a_content_change():
    """confirming or rejecting is a review action: same hash, new status."""
    d = versioning.diff_versions(
        "v1",
        "v2",
        [_fact("a", "fact a", status="inferred")],
        [_fact("a", "fact a", status="confirmed")],
        [],
        [],
    )
    assert d.facts_added == []
    assert d.facts_removed == []
    assert len(d.status_changes) == 1
    assert d.status_changes[0].from_status == "inferred"
    assert d.status_changes[0].to_status == "confirmed"


def test_reworded_fact_is_remove_plus_add():
    """the content hash covers the statement: a rewording is a new fact, not
    a change to the old one. the diff says so honestly."""
    d = versioning.diff_versions("v1", "v2", [_fact("a", "old wording")], [_fact("b", "new wording")], [], [])
    assert [c.statement for c in d.facts_removed] == ["old wording"]
    assert [c.statement for c in d.facts_added] == ["new wording"]


def test_diff_against_empty_from_version():
    d = versioning.diff_versions("", "v2", [], [_fact("a", "fact a")], [], ["s1"])
    assert d.from_version == ""
    assert len(d.facts_added) == 1
