# beholder

*positioning and pitching from the point of view of whoever is judging you. never marketing.*

beholder takes a project and a target (a hackathon rubric, a grant call, yc, emergent ventures, a casting partner, a customer segment) and tells you how that target will see the project: what scores, what is missing, which claims overreach, and how to say it.

the project stays the same. the eye looking at it changes.

## what you get per target

- a **fit score** per criterion, with cited evidence or a flagged gap
- a **pitch**, positioned for that reader, in the format they expect
- a **gap list** ranked by criterion weight
- **overclaim fixes**: statements that go beyond your evidence, with defensible rewrites

which targets to pitch at, from the scores already on the table.

and once something happens: **what actually happened**, recorded so a lens can be checked against outcomes instead of assumed good.

## status

spec set complete and the whole mvp is built behind an api. the nine w's framework, beholder's extraction map, lives in [thewframework/](thewframework/readme.md). the backend lives in [backend/](backend/README.md): fastapi, any postgres, one model gateway, the brain as pure functions, rest-walk repo ingest that pins every citation to a commit, migrations from day one, 161 tests green, no network in the suite.

what runs today, end to end:

- **projects and evidence**: pasted text, documents, doc sites, and repos over the rest api of github, gitlab, bitbucket, or gitea. every fact cites file and lines, document and page, or the user who stated it. repo citations name the commit they were read at, and a re-sync reports what changed since the last walk
- **the lens**: a rubric parsed into criteria and weights, with a mandatory review step. authored presets for hackathons, grants, yc, and partner tracks, each with its last-verified date
- **scoring and pitch**, with gaps ranked by weight, sentence-bound views, overclaim checks, and the honesty guard that blocks an export resting on unsupported facts
- **exports**: markdown, demo script, deck outline, partner one-pager. the same guarded sentences rearranged for a different reader, never rewritten
- **the shared library**: a public rubric can be contributed with an explicit public assertion, reviewed by the deployment, and only then becomes visible with its sources
- **outcomes and calibration**: what happened to a target is recorded as history, and a lens can be checked against those outcomes. below three per group it says too few to say anything, which is the honest answer
- **pre-build mode**: a project that exists only as specs. no structural pass, every fact labeled a claim, exports that say so

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
| [thewframework/](thewframework/readme.md) | the nine w's: what beholder extracts from what you give it, per dimension |
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
