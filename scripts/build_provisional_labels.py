#!/usr/bin/env python3
"""Derive provisional audit labels for the local development proxy.

The hidden competition evaluation uses evaluator-held labels. This script only
produces a development placeholder so the local proxy can be exercised: an
observation is labelled exact/correct when its retained identity proof names the
same legal entity (organisation number or exact-entity gate) that the observation
claims. It never invents a positive label for an observation lacking a proof.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def proof_names_entity(observation: dict[str, Any]) -> bool:
    org = str(observation.get("organisation_number") or "")
    if not org.isdigit():
        return False
    for proof in observation.get("identity_proof") or []:
        value = str(proof.get("value") or "")
        proof_type = str(proof.get("type") or "")
        if org and org in value:
            return True
        if proof_type == "website_identity_gate" and proof.get("status") == "exact":
            return True
        if proof_type == "wikidata_property_P233" and value == org:
            return True
        if proof_type == "osm_org_number_tag" and value == org:
            return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Provisional development labels derived from retained identity proofs.")
    parser.add_argument("--observations", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    observations = read_jsonl(Path(args.observations))
    rows = []
    for observation in observations:
        exact = proof_names_entity(observation)
        rows.append({
            "id": observation["id"],
            "exact_entity": exact,
            "metric_correct": exact and bool(observation.get("metrics")),
            "sentiment_correct": observation.get("sentiment_label") is None,
        })
    Path(args.output).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8"
    )
    print(json.dumps({
        "labels": len(rows),
        "exact_entity_true": sum(row["exact_entity"] for row in rows),
        "metric_correct_true": sum(row["metric_correct"] for row in rows),
        "claim_boundary": "Development placeholder labels; hidden scoring uses evaluator-held labels.",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
