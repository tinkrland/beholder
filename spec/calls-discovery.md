# open calls: what can actually be discovered

stage 4 wants to tell a user which calls are newly open and worth their time. that requires two things a project model cannot supply: which calls exist, and when they close. this note records what was probed on november 1 2026, what each source actually returns, and which one beholder can depend on without a key, an account, or a vendor.

every claim below was checked against the live endpoint on that date, not against a vendor description.

## what was verified

### grants.gov (us federal), open and keyless

```
POST https://api.grants.gov/v1/api/search2
{"keyword": "", "oppStatuses": "posted", "rows": 2, "sortBy": "openDate|desc"}
```

- returns `857` posted opportunities on the probe, `hitCount` included, in about `80ms`, with no key, no account, no rate limit hit
- each hit carries: `id`, `number`, `title`, `agency`, `agencyCode`, `openDate`, `closeDate`, `oppStatus`, `docType`, `cfdaList`
- `sortBy: openDate|desc` gives newly opened first, which is exactly the stage 4 question
- `POST https://api.grants.gov/v1/api/fetchOpportunity` with `{"opportunityId": <id>}` returns the full synopsis: `applicantEligibilityDesc`, `applicantTypes`, `awardCeiling`, `awardFloor`, `archiveDate`, description, agency contact

one detail that matters for honesty: eligibility is a list of applicant types, and it is exclusionary. a call a user cannot apply to is not a fit, however well they score. eligibility is a gate before scoring, not a criterion within it.

### EU funding and tenders (SEDIA), works but unadvertised

```
POST https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=*&pageSize=1
```

- responds with `4,290,458` indexed items across every content type, so the index is live and public
- results carry `esDA_endDate` (the deadline), `status`, `title`, `url`, and programme fields in metadata
- the `apiKey=SEDIA` value is the portal's own public key, undocumented and unversioned. it works today and could stop working without notice
- narrowing to calls for proposals rather than events and documents needs careful query construction; a naive `type: 1` filter returned support events

usable as an optional adapter. not something to make the default depend on.

### opengrants.io, commercial

- advertises a matching api that ranks open grants against an organization profile, and a search api over roughly 50,000 us grants
- gated behind a trial and a subscription
- a fine optional integration for someone who already pays for it. not a default for a self-hosted tool, because the moment the dependency is required the tool stops being self-hostable

### 360giving, awarded grants not open calls

- a real open standard with published data, but it records money already granted
- wrong shape for discovery, right shape for outcomes: it is evidence of what funders actually funded, which is exactly the calibration input lens quality wants
- worth remembering for stage 5, not for stage 4

### major league hacking, endpoint gone

- `https://mlh.io/seasons/2026/events.json` returned `200` with an html page, `217,866` bytes of markup, no json
- so the old machine-readable season feed is not usable today

### hackathons and partner tracks, no index exists

- devpost publishes no public api for open hackathons
- yc batches, casting partners, residency programs, and most corporate challenge calls publish dates as prose on a page, not as a feed
- there is nothing honest to scrape here that would stay working

## the shape this implies

three sources, one interface, no pretending they are the same:

1. **open index adapters** behind one `CallIndex` interface: `grants.gov` is the default because it is keyless and official. the EU SEDIA adapter is optional and off unless enabled, because it leans on an undocumented key. every adapter yields the same record: title, agency, url, open date, close date, eligibility list, and the published criteria documents if any
2. **a curated seed file in the repo** for what no feed carries: yc, hackathons, casting partners, residencies. a plain file of calls with dates and links, edited by hand, honest about being hand-made
3. **first_seen, not just dates.** store when beholder first saw a call. "newly opened" is a fact about beholder's own observation, and it is the only version of that claim the tool can make truthfully

and the rule that keeps stage 4 from becoming the thing beholder exists to fight: discovery never claims fit. a discovered call becomes a lens by parsing the criteria it publishes, and a project's fit comes only from the score on that lens, with evidence, like every other target. a ranked list of calls with no rubric behind it would be a recommendation dressed up as analysis.

## open questions

- does stage 4 v1 ship with only the grants.gov adapter and the curated seed file, holding the EU adapter until someone asks for it
- is a hand-maintained seed file acceptable as the honest answer for hackathons, or is it better to leave hackathon discovery out of v1 entirely rather than ship a list that goes stale
- should a discovered call auto-parse its published criteria into a draft lens, or wait for the user to pick a call and ask for the lens
