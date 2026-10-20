"""version diff: what changed between two model versions. pure, no io.

facts are identified by content hash, not row id: re-extraction creates
new rows for the same fact, and the hash is what makes them the same
fact. a status change is not a content change: it is reported as its
own kind of change, because confirming or rejecting is a review action,
not a rewording."""

from app.schemas import BaseModel  # re-exported for symmetry


class FactChange(BaseModel):
    content_hash: str
    kind: str
    statement: str


class StatusChange(BaseModel):
    content_hash: str
    statement: str
    from_status: str
    to_status: str


class VersionDiff(BaseModel):
    from_version: str
    to_version: str
    facts_added: list[FactChange]
    facts_removed: list[FactChange]
    status_changes: list[StatusChange]
    sources_added: list[str]
    sources_removed: list[str]


def diff_versions(
    from_version: str,
    to_version: str,
    from_facts: list[dict],
    to_facts: list[dict],
    from_sources: list[str],
    to_sources: list[str],
) -> VersionDiff:
    """from_facts/to_facts: rows with content_hash, statement, status.
    from_sources/to_sources: source content hashes."""
    by_hash_from = {f["content_hash"]: f for f in from_facts}
    by_hash_to = {f["content_hash"]: f for f in to_facts}

    added = [
        FactChange(content_hash=h, kind=f["kind"], statement=f["statement"]) for h, f in by_hash_to.items() if h not in by_hash_from
    ]
    removed = [
        FactChange(content_hash=h, kind=f["kind"], statement=f["statement"]) for h, f in by_hash_from.items() if h not in by_hash_to
    ]
    status_changes = [
        StatusChange(
            content_hash=h,
            statement=f["statement"],
            from_status=by_hash_from[h]["status"],
            to_status=f["status"],
        )
        for h, f in by_hash_to.items()
        if h in by_hash_from and by_hash_from[h]["status"] != f["status"]
    ]
    return VersionDiff(
        from_version=from_version,
        to_version=to_version,
        facts_added=sorted(added, key=lambda c: c.statement),
        facts_removed=sorted(removed, key=lambda c: c.statement),
        status_changes=sorted(status_changes, key=lambda c: c.statement),
        sources_added=sorted(set(to_sources) - set(from_sources)),
        sources_removed=sorted(set(from_sources) - set(to_sources)),
    )
