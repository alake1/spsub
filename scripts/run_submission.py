#!/usr/bin/env python3
"""Signalpost submission runner.

One documented command that accepts a JSONL batch of organisation numbers and
produces the full evidence package: terminal envelopes, foundation profiles,
external-footprint observations + audit, provisional labels, the research-agent
evaluation, the deterministic refresh replay, the product UX report, the
machine-readable run report, and the competition proxy scorecard.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    printable = " ".join(str(part) for part in args)
    print(f"\n$ {printable}", flush=True)
    completed = subprocess.run([str(part) for part in args], cwd=ROOT, text=True, capture_output=False)
    if check and completed.returncode not in (0, 1):
        raise SystemExit(f"command failed ({completed.returncode}): {printable}")
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full Signalpost submission pipeline on a JSONL batch.")
    parser.add_argument("--organisations", required=True, help="JSONL / JSON / text batch of organisation numbers")
    parser.add_argument("--bulk", required=True, help="Frozen Brreg entity snapshot (gzipped CSV)")
    parser.add_argument("--outdir", default="out")
    parser.add_argument("--run-id", default="submission-001")
    parser.add_argument("--expected-count", type=int, default=100)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--refresh-manifest", default="tests/fixtures/refresh-snapshots.json")
    parser.add_argument("--source-rights", default="config/source-rights.json")
    args = parser.parse_args()

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    profiles = out / "profiles.jsonl"
    envelopes = out / "envelopes.jsonl"
    batch_report = out / "run-report.json"
    resume_report = out / "resume-report.json"
    observations = out / "external-observations.jsonl"
    labels = out / "external-labels.jsonl"
    external_report = out / "external-report.json"
    suite = out / "research-suite.json"
    research_report = out / "research-report.json"
    workspace = out / "workspace.json"
    refresh_report = out / "refresh-report.json"
    prototype = out / "prototype.html"
    ux_report = out / "ux-report.json"
    scorecard = out / "scorecard.json"

    batch = ["--organisations", args.organisations, "--bulk", args.bulk,
             "--profiles-output", str(profiles), "--output", str(envelopes),
             "--run-id", args.run_id, "--expected-count", str(args.expected_count), "--workers", str(args.workers)]

    run(PY, "scripts/run_competition_batch.py", *batch, "--report", str(batch_report))
    run(PY, "scripts/run_competition_batch.py", *batch, "--report", str(resume_report), "--resume")
    run(PY, "scripts/build_external_observations.py", "--profiles", str(profiles),
        "--organisations", args.organisations, "--output", str(observations),
        "--report", str(out / "external-connectors.json"))
    run(PY, "scripts/build_provisional_labels.py", "--observations", str(observations), "--output", str(labels))
    run(PY, "scripts/evaluate_external_footprint.py", "--profiles", str(profiles),
        "--observations", str(observations), "--labels", str(labels), "--output", str(external_report),
        "--source-rights", args.source_rights)
    run(PY, "scripts/build_research_suite.py", "--profiles", str(profiles), "--output", str(suite))
    run(PY, "scripts/evaluate_research_agent.py", "--input", str(profiles), "--suite", str(suite),
        "--output", str(research_report), "--workspace", str(workspace), "--observations", str(observations))
    run(PY, "scripts/run_refresh_replay.py", "--manifest", args.refresh_manifest, "--output", str(refresh_report))
    run(PY, "scripts/build_prototype.py", "--input", str(profiles), "--external-observations", str(observations),
        "--output", str(prototype))
    run(PY, "scripts/evaluate_product_ux.py", "--prototype", str(prototype),
        "--observations", str(observations), "--output", str(ux_report))
    run(PY, "scripts/score_competition_v3.py", "--profiles", str(profiles),
        "--external-report", str(external_report), "--batch-report", str(batch_report),
        "--resume-report", str(resume_report), "--refresh-report", str(refresh_report),
        "--research-report", str(research_report), "--ux-report", str(ux_report), "--output", str(scorecard))
    run(PY, "scripts/build_prototype.py", "--input", str(profiles), "--score", str(scorecard),
        "--external-observations", str(observations), "--output", str(prototype))

    from datetime import datetime

    batch_data = json.loads(batch_report.read_text(encoding="utf-8"))
    external_data = json.loads(external_report.read_text(encoding="utf-8"))
    connectors_data = json.loads((out / "external-connectors.json").read_text(encoding="utf-8"))
    score = json.loads(scorecard.read_text(encoding="utf-8"))
    started = datetime.fromisoformat(str(batch_data["started_at"]).replace("Z", "+00:00"))
    finished = datetime.fromisoformat(str(batch_data["completed_at"]).replace("Z", "+00:00"))
    submission_report = {
        "submission": "signalpost-norway-company-agent",
        "run_id": args.run_id,
        "command": (
            f"python scripts/run_submission.py --organisations {args.organisations} "
            f"--bulk {args.bulk} --expected-count {args.expected_count} --run-id {args.run_id}"
        ),
        "batch": {
            "expected": batch_data["expected_count"],
            "emitted_envelopes": batch_data["emitted_envelopes"],
            "zero_silent_drops": batch_data["validation"]["checks"]["zero_silent_drops"],
            "wall_clock_seconds": round((finished - started).total_seconds(), 3),
            "requests": batch_data["operations"]["requests"],
            "bytes": batch_data["operations"]["bytes"],
            "p50_ms": batch_data["operations"]["p50_ms"],
            "p95_ms": batch_data["operations"]["p95_ms"],
        },
        "external_footprint": {
            "observations": external_data["observations"],
            "companies_with_observations": connectors_data.get("companies_with_observations"),
            "connector_counts": connectors_data.get("connector_counts"),
            "published_audited": external_data["published_audited"],
            "wrong_entity_publications": external_data["wrong_entity_publications"],
            "unsupported_publications": external_data["unsupported_publications"],
            "coverage": external_data["coverage"],
            "connector_policy_passed": external_data["connector_policy_passed"],
        },
        "third_party_cost_usd": 0,
        "declarations": {
            "models": ["No model is used for scored facts. Deterministic extraction only; the optional sentiment model is not run."],
            "apis": [
                "Brønnøysundregistrene Enhetsregisteret + Regnskapsregisteret (NLOD 2.0)",
                "Wikidata SPARQL (CC0)",
                "OpenStreetMap Overpass (ODbL 1.0)",
                "Company-controlled public websites (bounded, robots-respecting crawl)",
            ],
            "licences": {
                "brreg": "NLOD 2.0",
                "wikidata": "CC0 1.0",
                "openstreetmap": "ODbL 1.0",
                "company_site": "Company-controlled public pages",
                "google_news_rss": "Discovery only; quarantined, never published",
            },
            "source_rights_manifest": args.source_rights,
        },
        "score": {
            "raw_score": score["raw_score"],
            "awardable_score": score["awardable_score"],
            "qualification_passed": score["qualification_passed"],
            "failed_gates": score["unproven_or_failed"],
        },
    }
    (out / "submission-report.json").write_text(
        json.dumps(submission_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = score
    print("\n" + "=" * 60)
    print(f"RAW SCORE {report['raw_score']}/100 | TARGET {report['target']} | QUALIFIED {report['qualification_passed']}")
    print(f"AWARDABLE {report['awardable_score']} | FAILED GATES {report['unproven_or_failed']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
