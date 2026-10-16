# Signalpost submission — Norway company intelligence agent

An evidence-bounded agent that anchors every company in the Brønnøysund registry, layers
rights-clean external evidence on top, and emits exactly one terminal envelope per input
organisation number.

Frozen 100-company smoke result: **59.14 / 100 awardable, all 7 qualification gates pass.**
(External 14.14/55 · Foundation 15/15 · Research agent 10/10 · Extensibility 12/12 · UX 8/8.)
Full write-up, declarations and claim boundaries: [`docs/submission.md`](docs/submission.md).

## Quick start

Requires Python 3.12+ with [`uv`](https://docs.astral.sh/uv/) (a pip fallback is in
`docs/submission.md`). This downloads the registry snapshot and the public universe, freezes
a 100-company batch, and runs the whole pipeline with one command:

```bash
uv sync
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://builderr.ai/signalpost-company-universe-2025.jsonl.gz' -o signalpost-universe.jsonl.gz

uv run python select_entry_batch.py \
  --universe signalpost-universe.jsonl.gz --count 100 --output entry-companies.jsonl

uv run python scripts/run_submission.py \
  --organisations entry-companies.jsonl \
  --bulk brreg-enheter.csv \
  --outdir out --run-id submission-001 --expected-count 100
```

`run_submission.py` accepts any JSONL, JSON or text batch of organisation numbers. Increase
`--count` and `--expected-count` together for a larger local run; the organiser supplies the
companies for official scoring.

## What it produces (`out/`)

| Artifact | Meaning |
|---|---|
| `envelopes.jsonl` | exactly one terminal envelope per input organisation |
| `profiles.jsonl` | full evidence profiles (registry, accounts, roles, group, locations, website) |
| `run-report.json` | runtime, request count, bytes, p50/p95 latency |
| `resume-report.json` | deterministic resume proof (`profiles_fetched_this_run == 0`) |
| `external-observations.jsonl` | rights-clean external observations (exact organisation-number proof) |
| `external-report.json` | external audit: coverage, entity/metric precision, connector policy, freshness |
| `refresh-report.json` | previous-snapshot → material-change replay |
| `research-report.json` | research-agent evaluation |
| `prototype.html` | product surface (search, profile, agent, workspace, export) |
| `scorecard.json` | competition proxy scorecard |
| `submission-report.json` | consolidated run report incl. cost and declarations |

## Data sources, rights and cost

Only rights-approved sources publish; experimental sources are quarantined. Declared in
[`config/source-rights.json`](config/source-rights.json):

| Source | Platform | Basis |
|---|---|---|
| Brønnøysund Enhetsregisteret + Regnskapsregisteret | `brreg` | official API, NLOD 2.0 |
| Company-controlled public websites (bounded, robots-respecting) | `company_site` | permitted public pages |
| Wikidata (property P2333) | `wikidata` | CC0 1.0 |
| OpenStreetMap Overpass (org-number tag) | `openstreetmap` | ODbL 1.0 |
| Google News RSS | `news` | discovery only — **quarantined, never published** |

Models: none for scored facts (deterministic extraction). Third-party cost: **$0 per run.**

## Tests

```bash
uv run --with pytest pytest -q      # 112 tests
```

## Source rule

Open-source code does not grant permission to scrape a platform. Follow each source's terms,
robots policy, rate limits and licence. LinkedIn, Meta and Indeed are useful identity targets
but direct automated collection may be restricted; use permitted APIs, licensed providers or
company-owned links, or return `blocked` / `not_available`.

## Claim boundaries

- Hidden competition scoring uses **evaluator-held labels**;
  `scripts/build_provisional_labels.py` is a development placeholder, not an accuracy claim.
- `not_found`, blocked or unavailable sources are never converted into zero or neutral facts.
- The public universe is registry-heavy, so free/rights-clean sources reach ~59 on a random
  batch. The remaining external points need paid/licensed connectors (places, news, jobs,
  labelled sentiment); the publication gate is already in place to add them without weakening
  exact-entity precision.

## Submission contract mapping

| Requirement | Where |
|---|---|
| 100-company smoke result/report | `out/scorecard.json`, `out/run-report.json` |
| one command accepting a JSONL batch | `scripts/run_submission.py` |
| exactly one terminal envelope per input | `out/envelopes.jsonl`, `run-report.json:zero_silent_drops` |
| pinned deps + reproducible setup | `pyproject.toml`, `uv.lock` |
| previous-snapshot → material-change output | `out/refresh-report.json` |
| machine-readable run report (runtime/requests/cost) | `out/submission-report.json` |
| declared models/APIs/licences/source-rights | `docs/submission.md`, `config/source-rights.json` |

