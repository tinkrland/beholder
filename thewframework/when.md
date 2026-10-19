# when

dimension: timing, triggers and lifecycle. product management function:
engagement strategy and retention.

## what beholder extracts

- **maturity facts**: where the project is in its lifecycle, read from what
  the repo shows: tests, ci, changelogs, release tags, migration history.
  observed, not verified, and confident only to that extent.
- **metric facts**: retention, usage, and engagement numbers a source states,
  each with its citation. a metric nobody wrote down does not exist here.
- **timing statements**: dates, deadlines, and launch plans from roadmap docs
  and changelogs, stored as statements about sources, not as predictions.

## how beholder addresses it

- every target carries a deadline; scoring and views know what "on time"
  means for that reader.
- preset lenses carry `last_verified` and `staleness_days`: a lens past its
  threshold is excluded from recommended and flagged, because a stale
  picture of a target is worse than none.
- the proof section orders evidence the reader trusts at this moment of the
  project's life: a judge at a demo day and a partner in month six need
  different "when" answers from the same facts.

## what beholder never does

- it never invents traction, momentum, or recency. "actively maintained" is
  only claimed when a dated source backs it.
- it never predicts. timing analysis says what is and what is documented, and
  the rest is a gap.
