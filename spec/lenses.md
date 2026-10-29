# lenses

a lens defines how one target judges. lenses are the core asset of beholder: the quality of the library decides whether outputs feel sharp or generic.

## lens types

| type | source | example |
|---|---|---|
| rubric | user uploads a rubric, judging sheet, or call for proposals | a hackathon main track, a sponsor track, a grant call |
| preset | maintained by beholder from public criteria and writing | yc, emergent ventures |
| custom | user pastes a brief or describes the reader | "a marketplace seller burned by image-compliance sweeps" |

## lens fields

| field | meaning |
|---|---|
| id, name, type | identity |
| criteria | list of name, weight, description, and what a strong answer looks like |
| required_questions | fields the target requires the applicant to answer |
| impresses | what stands out to this reader |
| red_flags | what costs credibility |
| alternatives_frame | what this reader compares against, including "do nothing" |
| trusted_evidence | evidence kinds ranked by how much this reader trusts them |
| objection_seeds | questions this reader usually raises |
| vocabulary | words and framings this reader uses |
| required_artifacts | eligibility gates and deliverables. not scored: they pass or disqualify | # implied by rubric wording
| output_formats | formats the target expects |
| sources | where the lens came from, with urls or upload ids |
| last_verified | date the lens was last checked against its sources |
| version | lens version |

## example lens (rubric type)

```yaml
id: rubric/example-hackathon-main-track
type: rubric
name: example hackathon, main track
sources:
  - type: upload
    ref: judging-sheet.pdf
last_verified: 2026-10-19
version: 1

criteria:
  - name: technical depth
    weight: 0.30
    description: non-trivial engineering, not a thin wrapper
    strong_answer: a working core that would take weeks to rebuild
  - name: demo quality
    weight: 0.30
    description: a working, end-to-end demo judges can see
    strong_answer: live or recorded demo of the full flow
  - name: originality
    weight: 0.20
    description: a new angle on a known problem
    subjective: true
  - name: impact
    weight: 0.20
    description: who benefits and how many

required_questions:
  - what problem does it solve?
  - what did you build during the event?

impresses:
  - a working demo with real data
  - a clear explanation of what was built in the event window
red_flags:
  - features described but not demonstrated
  - claims about scale with no evidence
alternatives_frame: existing tools plus doing nothing
trusted_evidence: [live demo, public repo with recent commits, user quotes]
objection_seeds:
  - what exactly was built during the event?
  - why not use an existing tool?
output_formats: [30-second pitch, application answers]
```

## how a rubric becomes a lens

1. user uploads pdf, doc, or a url
2. beholder extracts criteria, weights, required questions, and stated priorities
3. if weights are not stated, beholder proposes weights and marks them as inferred
4. user reviews and edits the parse. editing a draft is the edit half of the review: a weight the human changes stops being marked inferred, because the marker records where the number came from. only drafts are editable: a confirmed lens has scores resting on it, and edits to it are a re-parse into a new lens
5. the user confirms the parse. confirmation is the read half of the review: the client echoes every criterion back, name and weight each, and the echo must match the lens. an echo that does not match is a reject, never a silent confirm. a confirm button that never showed the numbers is not a review
6. the lens is saved to the user's private library

the review step matters: a wrong weight silently skews every score, so the review is enforced, not requested: a draft lens never scores, and confirmation must prove the reviewer read the weights.

## subjective criteria

for criteria like "originality" or "innovation," beholder shows a score range and the reasoning, not a point estimate, and says which evidence would move it.

## sponsor tracks

each sponsor track is its own lens. beholder shows a comparison of which track the project fits best, based on scores.

## preset lens rules

- built only from public criteria and writing, with sources cited
- every preset shows its last-verified date
- presets older than their staleness threshold show a warning and are never presented as current
- presets describe what a target has said it values; they do not claim to predict decisions

## the shared library

public rubrics a user uploads can be contributed to the shared library with opt-in. confidential or private materials are never contributed. contributed lenses are reviewed before they become presets.

the rules the code enforces, not just states:

- contribution needs an explicit assertion that the rubric is public. no assertion, no contribution, and the api says why
- only a confirmed lens can be contributed: an unconfirmed parse is the model's reading, not the user's
- only uploaded rubrics. custom lenses are the user's own framing and stay private
- submitting does not publish. a submitted lens is visible to reviewers only, and the shelf never shows it
- the reviewer is a deployment role, an email allowlist in configuration. no reviewers configured means nothing is approved, and the api says so instead of pretending a review happened
- a contributor never reviews their own contribution, even if they are on the allowlist
- approval is what makes a lens shared. the shelf shows the sources and the last-verified date, so a reader can judge the lens before trusting it

## worked example: a real rubric, parsed end to end

source: cgu hacks, the ethical ai hackathon at claremont graduate university. a public judging rubric with stated weights, five criteria at 20 percent each, and a 1-to-5 score guide. this is what the lens builder produces from it, before the user's review.

what is stated versus drafted:

- criteria names, descriptions, and weights: stated in the rubric, taken verbatim, no weight is inferred
- `strong_answer` for each criterion: drafted from the rubric's own "what to assess" text
- everything else (`impresses`, `red_flags`, `trusted_evidence`, `objection_seeds`, `alternatives_frame`, `vocabulary`, `output_formats`): drafted, marked inferred, and the user reviews them before the first render
- `required_questions` is empty because the rubric states none
- the event's own scale is 1 to 5. beholder scores 0 to 5, so that "nothing to score" exists

```yaml
id: rubric/cgu-hacks-ethical-ai
type: rubric
name: cgu hacks, ethical ai hackathon
sources:
  - type: url
    ref: https://research.cgu.edu/hackathon/home/judging-rubric/
last_verified: 2026-10-19
version: 1

criteria:
  - name: socially responsible impact in innovation
    weight: 0.20
    description: addresses a problem that impacts real people; specifies responsible intent across target end users; serves people traditionally forgotten, marginalized, or blocked by this kind of technology
    strong_answer: names the affected group explicitly and shows the design choices made for them
  - name: ease of use, transparency, and explainability
    weight: 0.20
    description: clear, insightful visual outputs (user interface, maps); accessible to end users; users can follow the reasoning behind ai-provided answers
    strong_answer: every ai answer can be traced to its reasoning in the ui
  - name: use of innovative technology and intelligent adaptation
    weight: 0.20
    description: ai system design is original and adaptable to realistic use cases; prompted or pre-trained models have high impact on the described problem; pre-trained geoai models use spatial or contextual analysis correctly
    strong_answer: model choices justified by the problem, with the adaptation to real use shown
  - name: user safety and trust
    weight: 0.20
    description: trust and safety centered throughout; explicit disclosures of ethical risks, unintended consequences, and misuse; tested handling of user information
    strong_answer: a working disclosure in the product and a test that shows how information is handled
  - name: presentation and storytelling
    weight: 0.20
    description: clear vision, project structure, and design logic; engaging storytelling; presenters demonstrate ethical thinking
    strong_answer: a story that carries the ethical reasoning, not a feature tour

required_questions: []   # the rubric states none

impresses:               # inferred, review before first render
  - a named, specific affected group
  - reasoning traces shown in the ui
  - explicit disclosures of what the ai can get wrong
red_flags:               # inferred
  - "ai for good" claims with no named beneficiary
  - black-box model behavior
  - no disclosure of risks or misuse
alternatives_frame: doing nothing, or existing tools with the same ai behind them   # inferred
trusted_evidence: [live demo, working ui the judge can click, disclosure text in the product]   # inferred from what the criteria ask to see
objection_seeds:         # inferred
  - who exactly is the affected group you named?
  - how does a user see why the model answered that way?
  - what happens when the model is wrong?
  - what data do you keep, and where does it go?
vocabulary: [responsible ai, explainability, disclosure, end users, geoai, spatial analysis]
output_formats: [3-minute pitch, live demo]   # inferred from the presentation criterion
```

the review step on this lens is light where the rubric was explicit and heavy where it was silent. the criteria and weights are trusted because the source states them; the drafted fields are where the user's judgment goes. a project scored through this lens would surface its gaps fast: nothing about revenue, no market questions, so investor framings die here, and any project whose strength is technical novelty alone will show a hole on the safety and impact criteria.

this lens took minutes to parse because the source is clean. the same parse on a rubric with unstated weights would propose weights, mark them inferred, and require the user to confirm them before the first score, per the flow above.

## worked example: one event, many lenses

source: ethglobal's agentic ethereum hackathon. the same event publishes a main judging rubric and a separate set of partner prize criteria, each with its own requirements. one event, several targets, several lenses. this is the case the whole product rests on.

what the material splits into:

- the main track: five stated categories, no stated weights, two rounds (async screening on the demo video, then live judging), same criteria both rounds
- each partner prize: its own stated criteria, its own qualification requirements, its own examples of what the partner likes
- even one partner's sub-tracks are different lenses: autonome's best defai agent cites griffain and heyanon as its reference points; best social agent cites luna and aixbt. same criteria list, different eye

main track lens:

```yaml
id: rubric/ethglobal-agentic-ethereum-main
type: rubric
name: ethglobal agentic ethereum, main track
sources:
  - type: url
    ref: https://ethglobal.com/events/agents/info/details
last_verified: 2026-10-19
version: 1

criteria:   # five stated categories, no weights stated. equal weights proposed, marked inferred
  - name: technicality
    weight: 0.20   # inferred
    description: how complex is the problem, how sophisticated is the solution
    strong_answer: a non-trivial problem solved with a working, sophisticated build
  - name: originality
    weight: 0.20   # inferred
    description: a new idea or a creative solve of an existing problem
    subjective: true
  - name: practicality
    weight: 0.20   # inferred
    description: complete and functional; usable by its target audience today
    strong_answer: something the target user could run today, not a promise of completeness
  - name: usability (ui/ux/dx)
    weight: 0.20   # inferred
    description: intuitive; easy to interact with
  - name: wow factor
    weight: 0.20   # inferred
    description: lasting impression; the catch-all for anything impressive that fits nowhere else
    subjective: true

required_questions: []   # none stated
required_artifacts:
  - demo video, 2 to 4 minutes, or the submission is cut
trusted_evidence: [demo video, live walkthrough, public repo]   # first round is judged on the video alone
output_formats: [demo video script, 30-second pitch]
```

the rounds differ in evidence, not criteria. the async round sees only the video, the live round sees the project itself. same lens, two proof burdens.

sponsor lens (one of autonome's three):

```yaml
id: rubric/ethglobal-agentic-ethereum-autonome-defai
type: rubric
name: ethglobal agentic ethereum, autonome best defai agent
sources:
  - type: url
    ref: https://ethglobal.com/events/agents/prizes
last_verified: 2026-10-19
version: 1

criteria:   # five stated, no weights stated. equal weights proposed, marked inferred
  - name: technical execution
    weight: 0.20   # inferred
    description: the project functions as pitched and the implementation is robust
  - name: usability
    weight: 0.20   # inferred
    description: the ux is intuitive and easy to use
  - name: impact
    weight: 0.20   # inferred
    description: large impact on the intended users
  - name: innovative
    weight: 0.20   # inferred
    description: a fresh perspective on the problem statement
  - name: presentation
    weight: 0.20   # inferred
    description: concise demo video within the time limit

required_artifacts:
  - agent launched on the autonome platform
  - user-facing interface open-sourced on github
  - demo video, max 5 minutes
impresses:   # stated by the partner as its reference projects
  - griffain, heyanon, almanak
vocabulary: [defai, autonomous agent, altlayer, tee, eliza, agentkit]
trusted_evidence: [live agent on the platform, open-source interface, demo video]
objection_seeds:
  - why is this an agent and not a script?
  - what does robust mean beyond the demo path?
```

what this example hardens:

- **eligibility is not a criterion.** a project that never launched on autonome is not scored 1 on the sponsor lens, it is out. lenses carry weights and gates separately, and beholder shows a failed gate as a reason, not a low score. the main lens has no such gate beyond the video length.
- **the same project meets different proof burdens per lens.** the main track's async round judges a 3-minute video; the sponsor track demands platform artifacts and open source. the projector ranks proof per lens, so the same fact lands differently.
- **weights can be inferred in both lenses and still be wrong in both.** equal weights are proposed because nothing is stated; the user confirms or edits before the first score. if a team knows judges care most about technicality, that edit is the highest-leverage ten seconds in the product.
- **one event is many targets.** the event's own docs say the majority of prizes go to projects that do not advance to live judging, and the first round has no impact on partner prize eligibility. the same project can lose the main track and win a sponsor track, or the reverse. that is beholder's thesis, stated by a real event's own documentation: fit is per target, not overall rank.
- **lenses multiply from one source.** this one page of prizes yields more than a dozen lenses. the lens library grows with events, not with new rubric formats.

## worked example: one project, different fronts

the two lenses above are real rubrics. this run puts one project through them. the project is studiogram (see [example-studiogram.md](../docs/example-studiogram.md)), extracted from its real repository, and the project model does not change between fronts. only the eye changes. that is the whole product in one example.

the project model, unchanged in every front below:

- studiogram renders the exact product mesh on posable subjects; no diffusion model ever touches the product
- everything visible in a frame is a number in saved scene state; the same state reproduces the same frame byte for byte, and retakes are byte-identical
- the only model in the loop (sam 3d) segments props; a prop is geometry in the scene, not a denoised guess
- a provenance gate refuses to load an asset whose hash fails, and licenses travel with every use
- pre-launch: buyer segments are hypotheses until a live surface measures anything

### front 1: cgu hacks, ethical ai hackathon (main rubric)

| criterion | weight | score | what the facts support |
|---|---|---|---|
| socially responsible impact in innovation | 0.20 | 2 | sellers hurt by the 2026 ai-label sweeps are a real, nameable group, and the repo names them. but no document states responsible intent toward them, and the icp doc explicitly routes this segment to answer pages, not the product. the group is served by research, not by a shipped system. |
| ease of use, transparency, and explainability | 0.20 | 4 | explainability is architectural: every visible thing in a frame is a number in inspectable scene state, and the studio keeps separate roles (subject, set, light, camera) instead of folding them into one opaque prompt. the frame is auditable by construction. |
| use of innovative technology and intelligent adaptation | 0.20 | 3 | deterministic rendering plus a bounded segmentation model is original and adapted to a real use case. but the rubric rewards ai-system design, and this product's design choice is to use as little model as possible. honest fit, modest score. |
| user safety and trust | 0.20 | 4 | a trust architecture exists: hash-verified assets, traveling licenses, a provenance gate, immutable capture records. gap: no disclosure of what the bounded prop model can get wrong. |
| presentation and storytelling | 0.20 | 1 | captures export as png and video, so demo material exists, but there is no narrated demo and no live surface. |

weighted total: about 2.8 of 5. the top gaps by weight times missing score: no stated responsible intent for the named group, no prop-model disclosures, then no narrated demo.

the one honest angle this lens surfaces: **the render cannot misrepresent the product.** to these judges that is the rarest kind of ai story: no melted logos, no five-finger hands, retakes byte-identical, and an asset that fails its hash does not load. the same fact the jeweler hears as "the photo precedes the cast" lands here as "the system cannot hallucinate what it is selling."

the overclaim this lens tempts is subtler than usual, because a model IS in the loop: the pitch wants "an ai studio." the honesty guard blocks it, and the rewrite is the boundary itself: "a deterministic renderer; the only model in the loop segments props, and it never touches the product."

### front 2: ethglobal agentic ethereum, main track

same project model, different front:

| criterion | weight | score | what the facts support |
|---|---|---|---|
| technicality | 0.20 | 3 | the deterministic render composite and the scene-state system are genuinely non-trivial. |
| originality | 0.20 | 2 | roles-not-a-prompt is a fresh angle for this room, but freshness in a vacuum is not what this criterion means. |
| practicality | 0.20 | 2 | the artifact works and exports, but there is no live commercial surface: the segments are hypotheses until measured. |
| usability | 0.20 | 3 | the no-cad studio carries over. |
| wow factor | 0.20 | 1 | nothing here lands with an ethereum audience. |

weighted total: about 2.0 of 5, and the vocabulary mismatch is the real signal: the project model contains zero web3 facts. not weak facts. none.

the overclaim this lens tempts: captures carry provenance records, so the pitch wants to stretch that into "on-chain provenance." there is no chain anywhere in the project model. the honesty guard blocks it: a provenance record is not a blockchain.

beholder's verdict on this front is not a pitch. it is the recommendation the matching stage will one day make automatically: **do not pitch here.** the honest fix is not better wording, it is building the thing the target wants to see, which is a different project decision, not a positioning one.

### front 3: autonome best defai agent (sponsor track)

no scores. the eligibility gates fail before scoring begins: there is no agent launched on autonome and no open-source interface. beholder shows the failed gates as reasons, not as zeros. this front is out, in one line, and that is the correct output.

### the three fronts, side by side

| front | fit | the one honest angle | the honesty guard blocked | gate |
|---|---|---|---|---|
| cgu ethical ai | moderate | the render cannot misrepresent the product, and a failed hash does not load | "an ai studio" written on a deterministic renderer | demo video, 2 to 4 minutes |
| ethglobal main track | poor | none that survives contact with the facts | "immutable" stretched to "on-chain" | demo video, 2 to 4 minutes |
| autonome defai agent | out | not reached | not reached | agent on autonome, open-source interface |

what this run hardens:

- **the project model never changed.** every score, gap, and angle above comes from the same ten facts. the eye changed, nothing else. that is the unit: one model, many views.
- **each lens tempts its own overclaim, and a bounded model in the loop makes the temptation subtle.** the ai rubric wants "an ai studio" written on a renderer whose design choice is minimal model use. the web3 event wants "on-chain" written on "provenance records." the temptation comes from the target, and the honesty guard is what stops beholder from becoming a marketing tool under that pressure.
- **weak fit is a valid output.** "do not pitch here, and here is why in facts" is as valuable as a pitch, and it is the seed of the matching stage.
- **gaps differ per front, so the to-do list differs per front.** for cgu: state responsible intent for the named group, disclose the prop model's limits, narrate a demo. for ethglobal: nothing to do but build a different feature. the same project, two different gap lists, ranked by what each reader weights.
