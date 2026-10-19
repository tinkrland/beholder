"""the brain: extraction, lens building, scoring, claims, projection, honesty.
pure functions over pydantic models, every check unit-testable with canned
model outputs and no api calls."""

from . import claims, consistency, extraction, grounding, honesty, lens_builder, presets, projector, retrieval, scorer  # noqa: F401
