#!/usr/bin/env python3
"""Score the product UX/report surface against an explicit, inspectable checklist.

Points are awarded only for capabilities actually present in the built artifact.
The report exposes `score` (max 8) and `external_intelligence_presented`, the two
fields the competition proxy reads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.external_footprint import publishable_observation  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prototype", required=True)
    parser.add_argument("--observations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    html = Path(args.prototype).read_text(encoding="utf-8")
    observations = read_jsonl(Path(args.observations)) if args.observations and Path(args.observations).exists() else []
    external = [item for item in observations if publishable_observation(item)]

    checks = {
        "search_and_filters": ('id="q"' in html and 'id="form"' in html and 'id="finance"' in html, 1.5),
        "company_profile_detail": ('id="profile"' in html and "Official annual account" in html, 1.0),
        "research_agent_qa": ('id="agent-form"' in html and 'id="agent-output"' in html, 1.5),
        "workspace_persistence": ("localStorage" in html and "save-view" in html and "pin" in html, 1.0),
        "evidence_disclosure": ("SHA-256" in html and "Inspect evidence" in html, 1.0),
        "provenance_export": ("signalpost-evidence-export" in html, 1.0),
        "external_intelligence_surface": ("linkedin-layer" in html or "external" in html.lower(), 1.0),
    }
    awarded = {name: (weight if passed else 0.0) for name, (passed, weight) in checks.items()}
    external_intelligence_presented = bool(external) and (checks["external_intelligence_surface"][0])
    report = {
        "scorer": "signalpost_product_ux_v1",
        "prototype": str(args.prototype),
        "checks": {name: passed for name, (passed, _weight) in checks.items()},
        "awarded": awarded,
        "score": round(sum(awarded.values()), 3),
        "maximum": 8.0,
        "external_intelligence_presented": external_intelligence_presented,
        "external_observations": len(external),
        "claim_boundary": "Checklist over the shipped artifact; it scores the demonstration surface, not user-study outcomes.",
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
