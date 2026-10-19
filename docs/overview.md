# overview

## the problem

you built something. you now have to pitch it to hackathon judges, grant committees, investors, partners, and customers. each one is judging by a different standard, usually written down somewhere (a rubric, a call for proposals, a thesis). most people write one pitch and reuse it, or guess what each audience wants.

the result: the strongest part of the project gets buried, the thing the judges weight most is missing, and claims that sound great to one audience read as overreach to another.

## the idea

beholder makes the target the unit. you give it:

1. **the project:** repo, url, docs, or just pasted text
2. **the target:** an uploaded rubric, a preset (yc, emergent ventures), or a custom brief

it returns:

- how the project **scores** against the target's criteria
- what is **missing**, ranked by how much the target weights it
- which of your own claims **overreach** the evidence, and a rewrite that holds up
- the **pitch**, reframed for that reader, in their format

## one model, many views

beholder builds one **project model**: a list of facts, each with evidence. every target gets a **pitch view** generated from that same model. a view can only say what the model supports. so every pitch stays consistent, and nothing is invented to fit a lens.

## the example

for a product-photo studio, the same facts become:

- to made-to-order jewelers: "the listing photo can precede the cast, rendered from your exact mesh"
- to sellers burned by ai-image flags: "no diffusion model touches the product; captures re-render byte-identical"
- to preorder brands: "the same piece in every crop, on a schedule"

and beholder flags the overclaims: "won't get flagged" is marked needs-full-read in the repo's own research; "an ai studio" contradicts the deterministic architecture. see [example-studiogram.md](example-studiogram.md).

## the name

from "beauty is in the eye of the beholder." same project, different eye.
