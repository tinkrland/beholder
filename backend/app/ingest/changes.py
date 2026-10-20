"""repo re-sync change summaries: what changed between two walks of the
same repo. pure, no io.

files are the unit, not chunks: a chunk is a slice of a file, and the
walk may slice differently as files grow or shrink. comparing at the
chunk level would report spurious churn; comparing the joined text per
path says honestly what a reader of the repo would see."""

import hashlib


def _path_text(chunks: list[dict]) -> dict[str, str]:
    """join chunk text per path, in walk order."""
    joined: dict[str, list[str]] = {}
    for c in chunks:
        joined.setdefault(c["path"], []).append(c["text"])
    return {p: "\n".join(parts) for p, parts in joined.items()}


def summarize_chunk_changes(old_chunks: list[dict], new_chunks: list[dict]) -> dict:
    """files added, files removed, files changed between two chunk sets."""
    old_by_path = _path_text(old_chunks)
    new_by_path = _path_text(new_chunks)
    old_hashes = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in old_by_path.items()}
    new_hashes = {p: hashlib.sha256(t.encode()).hexdigest() for p, t in new_by_path.items()}

    return {
        "files_added": sorted(p for p in new_hashes if p not in old_hashes),
        "files_removed": sorted(p for p in old_hashes if p not in new_hashes),
        "files_changed": sorted(p for p in new_hashes if p in old_hashes and new_hashes[p] != old_hashes[p]),
        "files_unchanged": sum(1 for p in new_hashes if p in old_hashes and new_hashes[p] == old_hashes[p]),
        "files_before": len(old_hashes),
        "files_after": len(new_hashes),
    }
