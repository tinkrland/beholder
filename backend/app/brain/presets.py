"""preset lens pure functions: staleness and drift. a preset lens carries
last_verified and staleness_days; a lens past its threshold is flagged, never
silently trusted. drift checking is deliberately dumb: the preset names
phrases its sources must still contain. if a source drops them, a human looks,
not a model."""

from datetime import date


def is_stale(lens: dict, today: date | None = None) -> bool:
    """staleness rules: no staleness_days means never stale (custom lenses);
    staleness_days with no last_verified means stale on arrival; otherwise
    stale when (today - last_verified) exceeds the threshold."""
    if not lens.get("staleness_days"):
        return False
    verified = lens.get("last_verified")
    if verified is None:
        return True
    if isinstance(verified, str):
        verified = date.fromisoformat(verified)
    today = today or date.today()
    return (today - verified).days > lens["staleness_days"]


def drift_check(preset: dict, source_texts: list[str]) -> dict:
    """which drift keywords the fetched sources still contain. found keywords
    mean the source still reads the way the preset author read it; missing
    ones mean the source moved and a human should re-read it. no keywords or
    no sources means nothing to check, which is itself reported."""
    keywords = preset.get("drift_keywords", [])
    if not keywords or not source_texts:
        return {"keywords_found": [], "keywords_missing": [], "checkable": False, "drifted": False}
    blob = " ".join(source_texts).lower()
    found = [k for k in keywords if k.lower() in blob]
    missing = [k for k in keywords if k.lower() not in blob]
    return {"keywords_found": found, "keywords_missing": missing, "checkable": True, "drifted": bool(missing)}


def preset_summary(preset: dict, lens_row: dict | None, today: date | None = None) -> dict:
    """one row for the presets listing: what it is, whether it is installed,
    and its staleness state. staleness is computed from the installed row,
    not the authored file: verification is a property of the running system."""
    out = {
        "key": preset["key"],
        "name": preset["name"],
        "description": preset["description"],
        "staleness_days": preset["staleness_days"],
        "criteria_count": len(preset["criteria"]),
        "installed": lens_row is not None,
        "lens_id": lens_row["id"] if lens_row else None,
        "version": lens_row["version"] if lens_row else None,
        "last_verified": str(lens_row["last_verified"]) if lens_row and lens_row.get("last_verified") else None,
        "stale": False,
    }
    if lens_row:
        out["stale"] = is_stale({**lens_row, "staleness_days": preset["staleness_days"]}, today)
    return out
