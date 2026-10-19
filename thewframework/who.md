# who

dimension: target audience and personas. product management function: user
research and segmentation.

## what beholder extracts

- **audience facts**: who the project says it is for, from growth docs,
  positioning pages, readme language, and icp notes. example: "the readme's
  positioning names made-to-order jewelers as the first segment."
- **segmentation evidence**: named segments, beachheads, and the order they
  are pursued, when a source states an order rather than a list.
- **user-stated audience**: what you say in the fact editor. provenance type
  `user`, shown as such, lower default trust, and it never outranks a
  documented fact until you confirm it.

## how beholder addresses it

- lens criteria about audience fit score against audience facts only; a lens
  that cares about "clearly named first users" reads the audience facts and
  nothing else.
- the one-liner and problem sections are written from the reader's eye, so
  who is defined per lens: the same project's "who" reads differently to a
  consumer segment, an enterprise buyer, and a hackathon judge.
- the lens's `vocabulary` field tunes the language of every audience-facing
  sentence to the segment that reader cares about.

## what beholder never does

- it never invents a persona. a target audience nobody wrote down is a gap
  with a suggestion, not a fictional user.
- it never widens a named segment for you. "developers" is not inferred from
  "python developers in growth-stage teams" unless a source says so.
