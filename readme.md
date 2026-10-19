# beholder

*positioning and pitching from the point of view of whoever is judging you. never marketing.*

beholder takes a project and a target (a hackathon rubric, a grant call, yc, emergent ventures, a casting partner, a customer segment) and tells you how that target will see the project: what scores, what is missing, which claims overreach, and how to say it.

the project stays the same. the eye looking at it changes.

## what you get per target

- a **fit score** per criterion, with cited evidence or a flagged gap
- a **pitch**, positioned for that reader, in the format they expect
- a **gap list** ranked by criterion weight
- **overclaim fixes**: statements that go beyond your evidence, with defensible rewrites

later: a recommendation of **which targets to pitch at**.

## status

spec set complete. the v1 backend lives in [backend/](backend/README.md): fastapi, any postgres, one model gateway, the brain as pure functions, rest-walk repo ingest, migrations from day one, 42 tests green. the mvp flow runs: project, sources, extraction, lens parse with mandatory review, scoring with gaps, pitch views with sentence binding, overclaim checks, and the honesty guard blocking export.

## read in this order

| file | what it covers |
|---|---|
| [overview.md](docs/overview.md) | the idea in two minutes |
| [product-spec.md](spec/product-spec.md) | the product spec: what it is and does |
| [about.md](docs/about.md) | why this exists, who it is for, principles |
| [features.md](spec/features.md) | every feature, grouped, with mvp / later tags |
| [how-it-works.md](docs/how-it-works.md) | the end-to-end flow |
| [lenses.md](spec/lenses.md) | the lens format, the core asset, with an example |
| [example-studiogram.md](docs/example-studiogram.md) | a worked run on a real project |
| [build-spec.md](spec/build-spec.md) | the technical spec for builders |
| [backend-stack.md](spec/backend-stack.md) | the backend stack: where each piece runs, and with which tools |
| [roadmap.md](spec/roadmap.md) | staged plan |
| [privacy.md](docs/privacy.md) | what is stored, shared, and never used |
| [faq.md](docs/faq.md) | common questions and edge cases |
| [glossary.md](docs/glossary.md) | terms |

## the name

beholder builds on the concept behind "beauty is in the eye of the beholder": there is no view of a project from nowhere. every judgment is made from somebody's eye, and the eye changes what is seen.

the phrase by itself is of little use. the analogies are what carry it: a beholder is also the many-eyed creature, one body, a dozen eyes, each eye its own lens casting its own ray. that is the product's shape in one word: one project model, many lenses, each one seeing something the others cannot.

## what beholder is not

not a marketing tool. no ad copy, social posts, scheduling, seo, brand identity, or analytics. not dependent on any other tool. output is for an application, a demo, a partner conversation, or a pitch.
