# beholder product spec (v2)

*positioning and pitching from the point of view of whoever is judging you. never marketing.*

## 1. summary

beholder takes a project and a target, and tells you how that target will see it. the target might be a hackathon rubric, a grant call, yc, emergent ventures, a casting partner, or a customer segment. the project stays the same; the eye looking at it changes.

for each target, beholder produces:

- **a fit score** per criterion, with cited evidence or a flagged gap
- **the pitch**, positioned for that reader, in the format they expect
- **a gap list**: what the target will want that the project cannot yet show, ranked by weight
- **claims to fix**: statements that overreach the evidence, with defensible rewrites

later, it also recommends **which targets to pitch at all**.

the name comes from "beauty is in the eye of the beholder."

**who it is for:** anyone pitching one project to several audiences: hackathon builders, early founders, grant applicants, solo creators. v1 is for projects with code, full or half written; pre-build projects with just specs are the v2 horizon.

**how it runs:** a hosted service, self-hostable. the source is available; open-sourcing depends.

## 2. pitching, not marketing

| beholder does | beholder does not do |
|---|---|
| decides what the project *is* to a given reader | write ad copy, social posts, or campaigns |
| scores the project against that reader's criteria | schedule, publish, or distribute anything |
| names the alternatives that reader compares it to | run seo, ads, or growth experiments |
| picks the strengths that matter to that reader, with evidence | manage brand identity or tone of voice |
| surfaces objections, gaps, and overclaims | measure reach, clicks, or conversions |

the output is for an application, a demo, a partner conversation, or a pitch. it is event-based: a target, a deadline, one shot.

beholder is a standalone product. it does not depend on tin or any other tool.

## 3. core concepts

- **project model:** a structured, evidence-linked picture of the project. single source of truth.
- **fact:** one statement about the project (for example "every design is checked server-side before release"). every fact links to evidence or is marked unsupported.
- **target:** the specific thing being pitched at. **the target is the unit of the product**, not a generic audience type. "yc" and "emergent ventures" are different targets. a hackathon main track and a sponsor track are different targets.
- **lens:** the structured definition of how a target judges: criteria and weights, what impresses, red flags, trusted evidence, vocabulary, and expected format.
- **pitch view:** the project model reframed through one lens. same structure for every target so views compare side by side.
- **gap:** a criterion in the lens with no supporting fact.
- **overclaim:** a statement in the user's own pitch that goes beyond what the facts support.

## 4. inputs

the project can come from any of these, alone or combined:

- repos (read-only) from github, gitlab, bitbucket, and gitea: public via url, private via a connected account or url plus token. a project can span several repos and branches
- doc-site urls: gitbook, quartz, and similar wikis
- live url
- readme, deck, or one-pager
- uploaded docs and notes: pdf, docx, md, txt, json
- pasted description

repos are the primary input for v1. pasted text and uploaded documents sit alongside them, not behind them. every fact carries provenance: file and lines, document and page, or "user-stated." user-stated facts are always labeled as such and are lower-trust by default.

## 5. targets and lenses

### 5.1 rubric targets (hackathons, grants)

the user uploads a rubric, judging sheet, or call for proposals (pdf, doc, or url). beholder parses criteria, weights, required questions, and stated priorities into a lens, and the user reviews the parse before the first render. this is the core flow and the first thing built.

sponsor tracks are handled as separate targets, with a comparison showing which track fits the project best.

### 5.2 preset targets (investors, programs)

yc, emergent ventures, and similar are maintained as structured lenses built from each target's public criteria and writing. every preset shows its sources and a **last verified** date. stale presets are flagged in the ui.

### 5.3 custom targets

the user pastes a fund thesis, partner requirements, a customer interview, or a plain-language description ("a skeptical casting partner who has had cracked pieces before"). beholder drafts a lens and the user edits it.

### 5.4 lens fields

- criteria with weights
- what impresses this reader
- red flags
- what they compare against (including "do nothing")
- evidence they trust, ranked (demo, revenue, letters, benchmarks)
- objections they typically raise
- vocabulary
- expected output format
- source and last verified date

the lens library is the long-term asset. quality of lenses decides whether outputs feel sharp or generic. see [lenses.md](lenses.md).

## 6. the pitch view

every target produces the same sections:

1. **one-liner:** what the project is, in this reader's words
2. **category frame:** the category this reader would put it in
3. **the problem as they see it**
4. **alternatives they compare against**
5. **what is different, and why they care:** only strengths relevant to this reader
6. **proof:** facts ranked by how much this reader trusts that kind of evidence
7. **likely objections and honest answers**
8. **what not to lead with:** true things that would hurt or distract with this reader
9. **gaps:** what this reader will want that the project cannot yet show

### formats

the view can be rendered into the format the target expects:

- 30-second pitch
- 2-minute demo script
- written application answers, mapped to the rubric's own fields
- deck outline
- one-pager (partners)

formats are projections of the view. they are never edited separately, so they stay consistent.

## 7. checks

- **rubric score:** per-criterion score with reasoning and what would raise it.
- **gap finder:** ranked by criterion weight. example: "judges weight demo polish at 30 percent and there is no demo link."
- **overclaim finder:** compares the user's own pitch language against the facts. example: "'never gets flagged by the platforms' has no supporting evidence; try 'renders the exact product mesh; no diffusion model touches the product.'"
- **honesty guard:** no sentence in a view may rest on an unsupported fact. unsupported facts can be confirmed by the user, and they then show as user-stated. beholder never invents traction, metrics, or proof to fit a lens.
- **consistency check:** finds framings across targets that contradict each other or would look bad if one reader saw another's version. example: "free forever" in the user view versus "monetizes heavily" in the investor view. suggests a framing that holds across all targets.

## 8. worked example: studiogram

see [example-studiogram.md](../docs/example-studiogram.md). in short: the same facts become a photo-before-the-cast pitch for made-to-order jewelers; a no-generation-risk framing for sellers burned by ai-label sweeps, honestly routed to answer pages until a mesh onramp exists; and a many-crops, byte-identical pitch for preorder brands. beholder flags "won't get flagged" (the repo's own research pass marks it needs-full-read) and "an ai studio" (contradicts the deterministic architecture).

the value is the flags and rewrites, not the fluent copy.

## 9. matching (later)

beholder recommends which targets to pitch at: which hackathons, grants, funds, or partners fit this project, and why.

this needs a live database of open calls, deadlines, and eligibility, which is an ongoing data job. the staged approach:

1. **rank what the user brings:** the user uploads the targets they are considering and beholder ranks them by fit.
2. **suggest from the library:** once lens coverage is large enough, recommend targets from it.
3. **discovery:** surface newly opened calls that fit.

## 10. privacy and trust

see [privacy.md](../docs/privacy.md). in short:

- projects are never used to train models
- uploaded rubrics and applications are private to the user by default
- if a rubric is public, the user can opt in to contributing it to the shared lens library; confidential materials are never contributed
- repo access is read-only, and users can exclude files
- source code is never quoted in outputs unless the user asks
- data is deleted when the project is disconnected or deleted

## 11. mvp scope

**in:**
- project input from pasted text, uploads, or a repo
- project model with facts and provenance, editable by the user
- rubric upload that becomes a lens, with a parse review step
- a handful of preset lenses (for example yc and emergent ventures)
- custom lens from plain language
- pitch view with the nine sections
- rubric score, gap finder, overclaim finder, honesty guard
- side-by-side comparison of two to four targets
- exports: 30-second pitch, application answers mapped to rubric fields, markdown and pdf

**later:**
- consistency check across all targets, richer diff mode
- target matching and discovery
- repo webhook re-sync and change summaries
- iteration loop: edit a fact and see scores update
- deck outline and demo script formats
- shared lens library and community contributions
- viewport simulation ("ask the investor lens a question"), if it stays within pitching

**explicitly out:** ad copy, posting, scheduling, seo, brand identity, tin integration.

## 12. build order

1. project input, fact extraction with provenance, fact editor
2. rubric upload and parsing into lenses, with a review step
3. scoring against a lens, plus gap finder
4. pitch view generation and exports
5. honesty guard and overclaim finder
6. preset lenses and custom lenses
7. side-by-side comparison and consistency check
8. iteration loop and repo re-sync
9. matching

rubric first, because it has the tightest feedback loop: the rubric is explicit, so anyone can check whether the scoring makes sense. full technical detail in [build-spec.md](build-spec.md).

## 13. invariants

- one project model per project. views are projections, never sources.
- every fact has provenance or is labeled user-stated.
- every sentence in a view binds to at least one fact about the project, or to a criterion in the lens (for sentences about the audience, such as objections or what they compare against).
- view edits are either annotations (wording and emphasis in one view) or fact edits (which propagate to every view). nothing else.
- beholder never invents evidence to close a gap.
- positioning and pitching only.

## 14. success measures

- time from input to first scored pitch view (target: under five minutes)
- rubric parse accuracy as judged by users (share of criteria and weights accepted without edit)
- overclaims and gaps found per project, and how many the user fixes
- exports used in a real application, hackathon, or pitch
- outcomes the user reports (advanced, funded, accepted)
- targets scored per project

## 15. open questions

- pricing: per project, per target, or subscription
- how to keep preset lenses current as programs change their criteria
- how much of a lens should be shared across users versus private
- how to score fairly when a rubric has subjective criteria ("originality")
- whether viewport simulation stays within pitching
- how to handle targets that publish no criteria at all
