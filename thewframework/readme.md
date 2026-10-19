# the nine w's framework

beholder extracts positioning from whatever you give it. the nine w's are the
map of what it looks for: nine dimensions that together describe a project as
a strategic object, not just a codebase. every dimension names what beholder
aims to extract, which fact kinds carry it, and how the product addresses it:
through lens criteria, scoring, pitch view sections, and the honesty guard.

the framework is an extraction and explanation layer, not a marketing
framework. beholder reads the nine w's out of your sources; it never writes
ads, posts, or campaigns.

## the dimensions

| dimension | core strategic focus | product management function |
|---|---|---|
| [who](who.md) | target audience and personas | user research and segmentation |
| [what](what.md) | product features and core value | solution design and capabilities |
| [when](when.md) | timing, triggers and lifecycle | engagement strategy and retention |
| [where](where.md) | channels and deployment | distribution and ux environment |
| [why](why.md) | the problem statement | pain point identification and root cause |
| [why not](why-not.md) | barriers, friction and objections | risk mitigation and onboarding design |
| [world](world.md) | market landscape and competitors | competitive intelligence and positioning |
| [way](way.md) | roadmap, horizons and scope guard | release planning and scope management |
| [wire](wire.md) | messaging, social layer and virality | growth engineering and community loops |

## how beholder maps each dimension

| dimension | fact kinds extracted | lens fields | pitch view sections | guard rails |
|---|---|---|---|---|
| who | audience | criteria about fit, vocabulary | one-liner, problem as they see it | a persona with no evidence is a gap |
| what | capability, mechanic, differentiator, pricing, metric | criteria, strong answers | what is different, proof | described-but-not-wired features stay unverified |
| when | maturity, metric | deadlines, staleness | proof, gaps | no invented traction, no fake recency |
| where | platform, constraint | alternatives frame | category frame | deployment claims cite files or docs |
| why | constraint, user-stated problem | required questions | problem as they see it | an unsupported problem statement is user-stated |
| why not | alternative, constraint | objection seeds, red flags | objections and honest answers, gaps | overclaim finder, honesty guard |
| world | alternative, differentiator | alternatives frame, vocabulary | alternatives, what not to lead with | competitor claims need cited sources |
| way | maturity, roadmap statements | criteria on scope and staging | what not to lead with | the future is a plan, never a fact |
| wire | metric, audience, user-stated | vocabulary | one-liner, category frame | positioning only, never marketing |

## two rules that hold across all nine

1. **evidence or a gap.** every extraction binds to provenance: a repo path
   and lines, a document page, a url, or the label user-stated. a dimension
   with no evidence is not guessed into existence; it appears as a gap, with
   what would close it.
2. **the eye changes the answer.** the same nine-dimension picture is
   re-weighted per lens. what "when" means for a hackathon judge (a demo on
   time) differs from what it means for a casting partner (a delivery
   roadmap). the extraction is shared; the reading is per target.

read the dimension pages in order, or start from whichever one your sources
actually speak to. a source that says nothing about a dimension is itself
information: beholder records the silence in the gap list.

## grounding coverage in the backend

the framework is not only documentation. the backend implements the coverage
check: `get /projects/{id}/grounding` reports each dimension as grounded
(a confirmed fact, or one at or above the confidence bar), partial (facts
exist, none reach the bar), or silent (nothing speaks to it), with what would
close each silent dimension. the `plan` fact kind exists for the way
dimension: stated roadmap and future statements are stored as plans, and a
plan is never a capability.
