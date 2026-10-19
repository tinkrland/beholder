# worked example: studiogram

source: the project's real repository (tinkrland/studiogram, growth branch), with the studio domains (`camera/`, `lighting/`, `setdesign/`, `customized-hands/`, `bust/`, `jewelry/`, `socmed-integration/`) and a `growth/` folder that holds positioning, buyer segments, research, and content drafts. this shows what beholder produces for one project and three targets from real files with real paths. the lens details remain illustrative.

## the project (facts extracted)

| fact | provenance |
|---|---|
| renders the exact mesh that goes to manufacturing; no diffusion model ever touches the product | readme.md, growth/growth-wiki/positioning.md |
| everything visible in a frame is a number in a saved scene state; the same state reproduces the same frame, byte for byte | readme.md |
| captures are immutable records with reproducible state: camera path, lighting deltas, snapshot; retakes are byte-identical | readme.md, growth/growth-wiki/positioning.md |
| the studio has roles, not a prompt: subject, set, lighting rig, and camera are separate systems with their own state | growth/growth-wiki/positioning.md |
| the rigged hand: 8970 vertices, 33 bones, per-joint posing, five authored pose presets, seven blend targets | readme.md |
| the bust: 210k-vert sculpt; ear seats wear studs, hoops, and labrets threaded front-to-back through the anatomy | readme.md |
| the necklace drape is deterministic: length is the only input | readme.md |
| procedural rings and bracelets attach to bones, so pieces ride posing | readme.md |
| the hand model is CC BY-SA 3.0 (DennisH2010, blendswap) and the license travels with every use; the bust is cc0 with provenance in assets/bust-provenance.md | readme.md |
| provenance gate: builds verify against a published release manifest; the bust's mesh loads only after its sha256 recomputes clean | readme.md |
| sam 3d objects by meta segments props; a prop is geometry in the scene, not a denoised guess | readme.md |
| five export framings: viewport, 1:1, 4:5, 9:16, 16:9 | readme.md |
| beachhead buyer: the made-to-order jeweler who already has the mesh; exactness is the whole value; no hallucination tolerance in fine jewelry | growth/growth-wiki/icp.md |
| the burned-seller segment converts only after a photo-to-mesh onramp or template library exists; until then they are the audience for the answer pages, not the product | growth/growth-wiki/icp.md |
| buyer segments are hypotheses until a live surface measures anything | growth/growth-wiki/icp.md |
| the growth folder is compose-only: drafts arrive as commits for review, never actions | growth/README.md |
| claims not yet verified against primary policy pages are marked "needs full read before publishing" | growth/README.md |

## target 1: the made-to-order jeweler (beachhead)

- **position:** the listing photo can precede the cast.
- **leads with:** the icp doc's own line, which needs no rewrite: lost-wax casting starts from a printed master, so the cad file exists before the product does; studiogram renders that exact geometry, so the photo can precede the object.
- **supports with:** byte-identical retakes, the provenance gate, pieces that ride posing because they are attached to bones.
- **gap:** the icp doc says segments are hypotheses until a live surface measures anything. no pilot, pricing, or jeweler conversations exist in the facts. the pitch can promise exactness, not traction.

## target 2: sellers burned by ai-image flags

- **position:** not the product. the answer pages.
- **why:** the icp doc is explicit: most of this segment has no meshes, and it converts only after a photo-to-mesh onramp or template library exists. until then they are the audience for the answer pages, not the product.
- **beholder's output here is a boundary, not a pitch:** the honest view for this target routes them to the research-backed answer pages and refuses to imply the studio serves them today. pitching the product at this segment now would cost credibility exactly where the answer pages are earning it.
- **overclaim:** "won't get flagged." the repo's own research pass is marked needs-full-read, and the deep-dive carries sources rather than promises. beholder blocks the claim until the policy pages are fully read, and the rewrite is what the facts support: "no diffusion model touches the product; captures re-render byte-identical."

## target 3: small brands running preorder or made-to-order drops

- **position:** the same piece in every crop, on a schedule.
- **supports with:** 4:5, 9:16, and 1:1 are studio presets now, and the icp doc names this segment's need: listing and social imagery on a schedule, the same piece in many crops.
- **gap:** workflow and scheduling claims beyond the presets are not in the facts. the pitch sells repeatability, not automation it cannot show.

## what beholder found on an honest repo

this repo ships its own honesty infrastructure: a provenance gate that refuses to load a mesh whose hash fails, licenses that travel with every use, byte-identical retakes, a compose-only growth folder, and needs-full-read markers on unverified claims. the overclaim finder mostly confirms the repo's own discipline and turns its qualifiers into pitch-ready language.

the interesting failure mode flips, as it does on honest repos: the pitch wants to say "an ai studio," because the market pays for ai. the architecture says the opposite, and the opposite is the stronger claim in a segment the repo itself defines as having no hallucination tolerance. beholder's rewrite is the stronger honest version: "a deterministic studio where the only model in the loop segments props, and it never touches the product."

## the same project through event rubrics

this run uses audience-style lenses. the same project model scored through two real event rubrics, with fit scores, gates, and the overclaims each target tempts, is in [lenses.md](../spec/lenses.md), one project, different fronts.
