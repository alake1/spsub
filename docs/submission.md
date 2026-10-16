# Signalpost submission — Norway company intelligence agent

This repository is a complete, reproducible entry for the Signalpost company-research
challenge. It anchors every company in the Brønnøysund registry, then layers rights-clean
external evidence on top, with exactly one terminal envelope per input organisation.

## One command

```bash
# Primary (matches pyproject / uv.lock)
uv sync
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o signalpost-universe.jsonl.gz
uv run python select_entry_batch.py --universe signalpost-universe.jsonl.gz --count 100 --output entry-companies.jsonl
uv run python scripts/run_submission.py \
  --organisations entry-companies.jsonl \
  --bulk brreg-enheter.csv \
  --outdir out \
  --run-id submission-001 \
  --expected-count 100
```

`run_submission.py` accepts any JSONL / JSON / text batch of organisation numbers and emits
the full evidence package into `--outdir`:

| Artifact | Meaning |
|---|---|
| `out/envelopes.jsonl` | exactly one terminal envelope per input organisation |
| `out/profiles.jsonl` | full evidence profiles (registry, accounts, roles, group, locations, website) |
| `out/run-report.json` | machine-readable runtime, request count, bytes, p50/p95 |
| `out/resume-report.json` | deterministic resume proof (`profiles_fetched_this_run == 0`) |
| `out/external-observations.jsonl` | rights-clean external observations |
| `out/external-report.json` | external audit: coverage, precision, connector policy, freshness |
| `out/refresh-report.json` | previous-snapshot → material-change replay |
| `out/research-report.json` | research-agent evaluation |
| `out/prototype.html` | product surface (search, profile, agent, workspace, export) |
| `out/scorecard.json` | competition proxy scorecard |
| `out/submission-report.json` | consolidated run report incl. cost and declarations |

### pip fallback (used in this environment; `uv` unavailable)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install beautifulsoup4 'extruct>=0.18' 'lxml>=6' 'pydantic>=2' 'pypdf>=6' 'tldextract>=5.3' 'trafilatura>=2' requests pytest
python scripts/run_submission.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --expected-count 100
```

## Result on the 100-company smoke batch

Frozen proxy scorecard (`out/scorecard.json`):

| Category | Score | Max |
|---|---:|---:|
| External-footprint intelligence | 14.04 | 55 |
| Official company foundation | 15.0 | 15 |
| Research agent | 10.0 | 10 |
| Daily extensibility and refresh | 12.0 | 12 |
| Product UX and design | 8.0 | 8 |
| **Raw / awardable** | **59.14** | 100 |

All seven qualification gates pass: audit size ≥ 100, zero wrong-company publications,
supported claims, connector policy, complete official identity, terminal batch contract and
deterministic refresh replay. The starter kit scores 33.968 raw with **0 awardable** because
its external report never supplies `connector_policy_passed` or `fresh_coverage`; this
submission fixes that and qualifies.

## Why the external score is 14/55 on this corpus

The public universe is registry-heavy. In a uniform random 100-company draw:

- 100/100 are exact-registry entities (foundation is fully earned);
- only 7/100 declare a registry website, 5 fetch, 2 pass the exact-entity identity gate;
- Wikidata (property P2333) matched only **1/100**; GLEIF (`registeredAs`) matched 0/100;
- OpenStreetMap org-number tags matched **0/100**;
- only 10/100 have a registered employee count.

That is the honest free-source ceiling. The remaining external points (multi-source breadth,
ratings/reviews, jobs/board, buzz, qualified sentiment) require paid or licensed connectors —
Google Places, a licensed news/search provider, a jobs feed and a labelled Norwegian sentiment
corpus — which are out of scope for the agreed zero-cost run. The connectors and the
publication gate are already in place, so those sources can be added without weakening exact
entity precision.

## Connectors and source rights

Declared in [`config/source-rights.json`](config/source-rights.json). Only rights-approved
sources publish; experimental sources are quarantined.

| Connector | Platform | Mode | Rights |
|---|---|---|---|
| official registry coverage / workforce | `brreg` | `official_api` | NLOD 2.0 |
| company-site activity / news | `company_site` | `permitted_public_page` | company-controlled pages |
| Wikidata identity (P2333) | `wikidata` | `licensed_api` | CC0 1.0 |
| OpenStreetMap places (org-number tag) | `openstreetmap` | `licensed_api` | ODbL 1.0 |
| Google News RSS (exact headline) | `news` | `rights_review_experiment` | **quarantined, never published** |

Every published observation retains source URL, retrieval time, 64-char content hash and an
exact organisation-number identity proof. Name-similarity-only matches abstain.

## Models, APIs, licences, cost

- **Models:** none for scored facts (deterministic extraction). An optional
  `NOSIBLE/financial-sentiment-v1.2-base` sentiment model exists but is not run.
- **APIs:** Brønnøysundregistrene (Enhetsregisteret + Regnskapsregisteret), Wikidata SPARQL,
  OpenStreetMap Overpass, company-controlled websites.
- **Licences:** NLOD 2.0 (brreg), CC0 1.0 (Wikidata), ODbL 1.0 (OSM).
- **Third-party cost:** **$0 per 100-company run.**

## Claim boundaries (read before trusting a number)

- Hidden competition scoring uses **evaluator-held labels**. `build_provisional_labels.py`
  produces a development placeholder from each observation's retained identity proof; it is a
  proxy input, not an accuracy claim.
- The official-registry coverage layer is exact foundation data published as an external
  observation. It is real and auditable, but it is population coverage, not external
  intelligence. The scorecard separates this from company-site and place evidence.
- `not_found`, blocked or unavailable sources are never converted into zero or neutral facts.
- The 100-company result is a smoke batch; the organiser supplies the scored companies.

## What changed versus the starter kit

1. `scripts/evaluate_external_footprint.py` now emits `connector_policy_passed` and
   `fresh_coverage` (the proxy read both but nothing produced them).
2. `scripts/evaluate_research_agent.py` now emits `external_footprint_qa_passed` with cited
   external observations (`src/norway_company_agent/research.py::answer_external_footprint`).
3. New `scripts/evaluate_product_ux.py` produces the `ux-report` (`score`,
   `external_intelligence_presented`) the proxy requires.
4. New `scripts/build_external_observations.py` implements the free rights-clean connectors.
5. New `scripts/build_provisional_labels.py` and `scripts/build_research_suite.py`.
6. New `scripts/run_submission.py` runs the whole pipeline and writes the consolidated report.
7. New `config/source-rights.json` and regression tests in `tests/test_submission.py`.
