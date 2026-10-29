# how it works

## flow

```
project input ──► extraction ──► project model (facts + provenance)
                                        │
target input ──► lens (criteria, weights, trusted evidence, red flags)
                                        │
                                        ▼
                         score · gaps · overclaims
                                        │
                                        ▼
                           pitch view (9 sections)
                                        │
                                        ▼
                    export (30s pitch, application answers, brief)
```

## step by step

1. **add the project.** connect a repo (github, gitlab, bitbucket, gitea; one or several), paste text, upload docs, or point at a doc site. nothing is required except something that describes the project.
2. **review the model.** beholder lists the facts it found, each with evidence. confirm, reject, edit, or add facts. facts you add are labeled user-stated. for a repo, evidence pins the exact commit it was read at, so a score can always be traced to the code that produced it.
3. **choose targets.** upload a rubric or call for proposals, pick a preset (yc, emergent ventures), or paste a custom brief. for a rubric, the parse is a draft you can edit, and confirming it means the weights were shown to you: a draft lens never scores, and weights beholder proposed stay marked inferred even after you confirm them.
4. **score.** for each target, every criterion gets a score, the reasoning, the facts supporting it, and what would raise it.
5. **find gaps and overclaims.** gaps are criteria with no supporting facts, ranked by weight. if you pasted your own pitch, beholder checks each claim against the facts and rewrites the ones that overreach.
6. **render the pitch view.** the same nine sections for every target. only facts that matter to that reader lead. true-but-distracting facts go under "what not to lead with."
7. **compare.** put two to four targets side by side.
8. **export.** pick the format the target expects. exports are generated from the view and cannot contain unsupported claims unless you confirmed them.

## the honesty rules

- every sentence binds to a fact about the project, or to a criterion in the lens (for sentences about the audience, such as objections)
- a sentence with no binding fails and is regenerated or dropped
- low-confidence unconfirmed facts are marked in the view and need confirmation before export
- beholder never fills a gap with invented evidence; it lists the gap and what would close it

## what an edit does

- **annotation:** changes wording or emphasis in one view only
- **fact edit:** changes the model, and every view using that fact updates

there is no third kind of edit. this is what keeps pitches consistent across targets.
