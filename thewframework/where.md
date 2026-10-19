# where

dimension: channels and deployment. product management function: distribution
and ux environment.

## what beholder extracts

- **platform facts**: where the project runs and ships, from dockerfiles,
  deploy configs, package targets, store metadata, and stated platforms.
- **constraint facts**: stated technical and platform constraints, from
  manifests, requirement lists, and docs.
- **distribution statements**: channels described in growth or positioning
  docs, stored with the same citation bar as code-level facts.

## how beholder addresses it

- the category frame section places the project in the world the reader
  already knows: where it lives is part of what it is to them.
- lens criteria about environment and delivery score against platform and
  constraint facts; a partner who needs on-prem reads the same repo
  differently than one who wants a hosted api.
- multi-repo projects keep each repo's where distinct: main, site, and api
  split are separate sources with separate refs.

## what beholder never does

- it never claims a deployment a config does not show. "runs anywhere a
  container runs" is only stated when a containerfile is cited.
- it never treats a platform mention as a platform commitment. the static pass
  records what is declared, not what is promised.
