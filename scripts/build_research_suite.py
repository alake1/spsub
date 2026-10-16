#!/usr/bin/env python3
"""Build a frozen research-agent suite for an arbitrary profile batch.

The organiser scores the research agent against their own hidden suite. This
generator produces an equivalent local suite from a frozen batch so the same
deterministic answer/screen layer can be exercised end-to-end. Screen
expectations are derived with an independent filter here, not by calling the
agent under test, so the evaluation still checks the agent's parser and filters.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest_revenue(row: dict[str, Any]) -> float | None:
    records = ((row.get("evidence", {}).get("financials", {}).get("value") or {}).get("records") or [])
    value = records[0].get("revenue") if records else None
    return float(value) if isinstance(value, (int, float)) else None


def top_by_revenue(rows: list[dict[str, Any]], limit: int) -> list[str]:
    ranked = sorted(
        rows,
        key=lambda row: (latest_revenue(row) is None, -(latest_revenue(row) or 0), str(row["organisation_number"])),
    )
    return [str(row["organisation_number"]) for row in ranked[:limit]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--corpus-label", default="frozen local research-agent suite")
    args = parser.parse_args()
    rows = read_jsonl(Path(args.profiles))

    single = next(
        row for row in rows
        if (row.get("evidence", {}).get("financials", {}).get("status") == "available")
        and (row.get("evidence", {}).get("roles", {}).get("status") == "available")
    )
    municipalities = Counter(str(row.get("municipality") or "").strip() for row in rows if str(row.get("municipality") or "").strip())
    municipality = municipalities.most_common(1)[0][0]

    with_accounts = [
        row for row in rows
        if str(row.get("municipality") or "").strip().casefold() == municipality.casefold()
        and row.get("evidence", {}).get("financials", {}).get("status") == "available"
    ]
    suite = {
        "corpus": args.corpus_label,
        "single_company": {
            "organisation_number": str(single["organisation_number"]),
            "question": "Who leads this company and what financial facts and locations are available?",
            "minimum_facts": 6,
        },
        "screens": [
            {
                "query": "top 10 by revenue",
                "expected_organisation_numbers": top_by_revenue(rows, 10),
                "expected_filter_fields": [],
            },
            {
                "query": f"companies in {municipality} with annual accounts top 5 by revenue",
                "expected_organisation_numbers": top_by_revenue(with_accounts, 5),
                "expected_filter_fields": ["municipality", "financials"],
            },
        ],
        "unsupported": {
            "query": "companies in Oslo with positive Glassdoor sentiment",
            "must_abstain": True,
        },
    }
    Path(args.output).write_text(json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"suite": args.output, "profiles": len(rows), "municipality": municipality,
                      "top_revenue": suite["screens"][0]["expected_organisation_numbers"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
