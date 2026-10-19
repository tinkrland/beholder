"""authored preset lenses: curated targets, versioned in the repo, synced into
the lenses table at startup. authored means a human wrote them, not a model:
review_status is confirmed by authorship, and staleness is part of the format.

adding a preset is a data file here, not a code change. keep the files
honest: criteria the target actually applies, sources that actually exist."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def load_presets() -> list[dict]:
    """every json file in data/, sorted by key. the loader is dumb on
    purpose: a malformed preset should fail loudly at startup, not score."""
    presets = []
    for p in sorted(DATA_DIR.glob("*.json")):
        with open(p) as fh:
            presets.append(json.load(fh))
    required = {"key", "name", "description", "criteria", "staleness_days", "sources", "drift_keywords"}
    for preset in presets:
        missing = required - set(preset)
        if missing:
            raise ValueError(f"preset {preset.get('key', '?')} is missing {sorted(missing)}")
        weights = sum(c.get("weight", 0) for c in preset["criteria"])
        if abs(weights - 1.0) > 0.001:
            raise ValueError(f"preset {preset['key']} weights sum to {weights}, not 1.0")
    return presets


def preset_by_key(key: str) -> dict | None:
    return next((p for p in load_presets() if p["key"] == key), None)
