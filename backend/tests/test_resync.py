"""repo re-sync: change summaries between two walks of the same repo. the
pure summary is unit-tested directly; the service is tested with a fake
walk, because the walk itself is covered by test_forges."""

import pytest

from app.ingest.changes import summarize_chunk_changes


def _chunks(*specs):
    # (path, text) pairs; a file may appear twice, like walk slices
    return [{"path": p, "text": t, "lines_start": 1, "lines_end": len(t.splitlines())} for p, t in specs]


def test_no_changes_when_walks_match():
    old = _chunks(("readme.md", "hello"), ("app.py", "print()"))
    new = _chunks(("app.py", "print()"), ("readme.md", "hello"))
    d = summarize_chunk_changes(old, new)
    assert d["files_added"] == []
    assert d["files_removed"] == []
    assert d["files_changed"] == []
    assert d["files_unchanged"] == 2


def test_added_removed_changed_files():
    old = _chunks(("readme.md", "old readme"), ("app.py", "print()"), ("gone.py", "x = 1"))
    new = _chunks(("readme.md", "new readme"), ("app.py", "print()"), ("fresh.py", "y = 2"))
    d = summarize_chunk_changes(old, new)
    assert d["files_added"] == ["fresh.py"]
    assert d["files_removed"] == ["gone.py"]
    assert d["files_changed"] == ["readme.md"]
    assert d["files_unchanged"] == 1
    assert d["files_before"] == 3
    assert d["files_after"] == 3


def test_reslicing_is_not_churn():
    """the walk may slice the same file into more chunks as it grows. the
    summary speaks files, not chunks, so no spurious change."""
    old = _chunks(("app.py", "a\nb"))
    new = _chunks(("app.py", "a"), ("app.py", "b"))
    d = summarize_chunk_changes(old, new)
    assert d["files_changed"] == []
    assert d["files_unchanged"] == 1


@pytest.mark.asyncio
async def test_resync_repo_source_records_change_summary(db_session, monkeypatch):
    """the service re-walks, inserts a new source (history is insert-only),
    and stores what changed in meta.change_summary."""
    from app.models import Project, Source, SourceChunk
    from app import service

    project = Project(name="p")
    db_session.add(project)
    await db_session.flush()
    first = Source(project_id=project.id, kind="repo", forge="github", ref="main", url="https://github.com/o/r", content_hash="h1")
    db_session.add(first)
    await db_session.flush()
    db_session.add(SourceChunk(source_id=first.id, idx=0, path="readme.md", lines_start=1, lines_end=2, text="old readme"))
    db_session.add(SourceChunk(source_id=first.id, idx=1, path="app.py", lines_start=1, lines_end=1, text="print()"))
    await db_session.flush()

    walks = [
        {"chunks": [
            {"path": "readme.md", "lines_start": 1, "lines_end": 2, "text": "new readme"},
            {"path": "app.py", "lines_start": 1, "lines_end": 1, "text": "print()"},
        ], "report": {"commit_sha": "abc", "fetched": 2}},
    ]
    calls = []

    def fake_walk(repo_url, ref, forge=None):
        calls.append((repo_url, ref))
        return walks[0]

    monkeypatch.setattr(service.walk_mod, "walk_repo", fake_walk)
    new_source, summary = await service.resync_repo_source(db_session, first.id)
    assert calls == [("https://github.com/o/r", "main")]  # same repo, same ref
    assert new_source.id != first.id  # insert-only: history keeps the old walk
    assert summary["files_changed"] == ["readme.md"]
    assert summary["files_unchanged"] == 1
    assert new_source.meta["change_summary"] == summary
    assert new_source.commit_sha == "abc"


@pytest.mark.asyncio
async def test_resync_rejects_non_repo_source(db_session):
    from app.models import Project, Source

    project = Project(name="p")
    db_session.add(project)
    await db_session.flush()
    doc = Source(project_id=project.id, kind="doc", content_hash="h")
    db_session.add(doc)
    await db_session.flush()
    from app.service import resync_repo_source

    with pytest.raises(ValueError, match="not a repo source"):
        await resync_repo_source(db_session, doc.id)
