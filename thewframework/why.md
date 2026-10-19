# why

dimension: the problem statement. product management function: pain point
identification and root cause.

## what beholder extracts

- **problem statements**: what the project says the problem is, from readme,
  docs, pitch text, and pasted sources. the semantic pass reads these as
  claims about the world, each with its citation.
- **constraint facts**: stated technical and market constraints that explain
  why the problem persists.
- **user-stated problem**: what you say the problem is. provenance type
  `user`, lower default trust, upgradeable by confirmation. your framing of
  the problem is evidence about your intent, not about the world.

## how beholder addresses it

- "the problem as they see it" is a fixed section of every pitch view: the
  same project's problem is restated in the reader's frame. a rubric that
  scores "clear problem articulation" reads the problem facts through the
  lens's own required questions.
- the gap finder names a missing problem statement explicitly: many projects
  describe what they built and never say what hurts.
- the lens's `required_questions` are the reader's version of why; scoring
  checks whether any fact answers them.

## what beholder never does

- it never improves your problem statement into a market claim. the
  overclaim finder checks "why" language like any other: a problem bigger
  than its evidence gets rewritten smaller.
- it never invents a root cause. analysis stops at what sources say; the
  rest is a gap with a suggested source that would close it.
