#!/usr/bin/env python3
"""Build rights-clean external-footprint observations from free sources.

Connectors (all declared in config/source-rights.json):
  * official_registry_coverage_v1   platform=brreg        company_profile      official_api
  * official_registry_workforce_v1  platform=brreg        workforce_snapshot   official_api
  * exact_company_site_activity_v1  platform=company_site profile_metrics      permitted_public_page
  * exact_company_site_news_activity_v1 platform=company_site public_post      permitted_public_page
  * wikidata_identity_v1            platform=wikidata     company_profile      licensed_api
  * openstreetmap_places_v1         platform=openstreetmap place_summary       licensed_api

Every observation carries an exact organisation-number identity proof, a source URL,
a retrieval time and a content hash, so it either passes the publication gate in
norway_company_agent.external_footprint or is dropped. Name-only matches abstain.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from norway_company_agent.external_footprint import publishable_observation  # noqa: E402

UA = "SignalpostResearchPOC/1.0 (https://builderr.ai; free external-footprint run)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SITE_ACTIVITY = load_module("site_activity", "scripts/extract_company_site_activity.py")
SITE_NEWS = load_module("site_news", "scripts/extract_company_site_news.py")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _digest(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def official_registry_coverage(profile: dict[str, Any]) -> dict[str, Any] | None:
    org = str(profile["organisation_number"])
    record = (profile.get("evidence") or {}).get("registry_live") or {}
    value = record.get("value") or {}
    digest = str(record.get("content_sha256") or "")
    if record.get("status") != "available" or str(value.get("organisation_number") or "") != org or len(digest) != 64:
        return None
    form = value.get("legal_form")
    municipality = value.get("municipality")
    span = f"Registered as {form or 'unknown form'} in {municipality or 'an unspecified municipality'}, organisation number {org}."
    return {
        "id": "official-registry-coverage-" + _digest(org, "registry_live")[:24],
        "organisation_number": org,
        "platform": "brreg",
        "signal_type": "company_profile",
        "source_url": record.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}",
        "retrieved_at": record.get("retrieved_at") or utc_now(),
        "content_sha256": digest,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_organisation_number", "value": org}],
        "acquisition_mode": "official_api",
        "rights_status": "approved",
        "source_class": "official_registry_live",
        "evidence_span": span,
        "metrics": {
            "legal_form": form,
            "municipality": municipality,
            "industry_code": value.get("industry"),
            "employees": value.get("employees"),
            "interpretation": "Official identity record; foundation data, retained as an exact-entity external observation.",
        },
        "strategy": "official_registry_coverage",
    }


def official_registry_workforce(profile: dict[str, Any]) -> dict[str, Any] | None:
    org = str(profile["organisation_number"])
    record = (profile.get("evidence") or {}).get("registry_live") or {}
    value = record.get("value") or {}
    employees = value.get("employees")
    digest = str(record.get("content_sha256") or "")
    if record.get("status") != "available" or employees in (None, "") or len(digest) != 64:
        return None
    span = f"The official registry reports {employees} registered employees for organisation number {org}."
    return {
        "id": "official-registry-workforce-" + _digest(org, str(employees))[:24],
        "organisation_number": org,
        "platform": "brreg",
        "signal_type": "workforce_snapshot",
        "source_url": record.get("source_url") or f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}",
        "retrieved_at": record.get("retrieved_at") or utc_now(),
        "content_sha256": digest,
        "exact_entity": True,
        "identity_proof": [{"type": "exact_organisation_number", "value": org}],
        "acquisition_mode": "official_api",
        "rights_status": "approved",
        "source_class": "official_registry_live",
        "evidence_span": span,
        "effective_at": value.get("latest_submitted_accounts"),
        "metrics": {"workforce_value": employees, "measure": "registered_employees", "interpretation": "Official registered headcount."},
        "strategy": "official_registry_workforce",
    }


def wikidata_identity(orgs: list[str], *, timeout: int = 45) -> list[dict[str, Any]]:
    values = " ".join(f'"{org}"' for org in orgs)
    query = (
        "SELECT ?org ?item WHERE { VALUES ?org { " + values + " } "
        "?item wdt:P2333 ?org. }"
    )
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    retrieved_at = utc_now()
    observations = []
    for binding in payload.get("results", {}).get("bindings", []):
        org = str(binding["org"]["value"])
        item_url = str(binding["item"]["value"])
        digest = _digest(org, item_url, "wikidata")
        observations.append({
            "id": "wikidata-identity-" + digest[:24],
            "organisation_number": org,
            "platform": "wikidata",
            "signal_type": "company_profile",
            "source_url": item_url,
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "exact_entity": True,
            "identity_proof": [{"type": "wikidata_property_P2333", "value": org}],
            "acquisition_mode": "licensed_api",
            "rights_status": "approved",
            "source_class": "wikidata",
            "evidence_span": f"Wikidata entity stating Norwegian organisation number {org} (property P2333).",
            "metrics": {"interpretation": "Wikidata identity record matched by organisation number."},
            "strategy": "wikidata_identity",
        })
    return observations


def openstreetmap_places(orgs: list[str], *, timeout: int = 120) -> list[dict[str, Any]]:
    regex = "^(" + "|".join(re.escape(org) for org in orgs) + ")$"
    selectors = "".join(
        f'nwr["{tag}"~"{regex}"];'
        for tag in ("ref:no:orgnr", "organisasjonsnummer", "ref:orgnr", "brreg:orgnr")
    )
    query = f"[out:json][timeout:{timeout}];({selectors});out center tags;"
    data = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(
        "https://overpass-api.de/api/interpreter",
        data=data,
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout + 30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    retrieved_at = utc_now()
    observations = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        org = None
        for tag in ("ref:no:orgnr", "organisasjonsnummer", "ref:orgnr", "brreg:orgnr"):
            if str(tags.get(tag) or "").isdigit() and len(str(tags.get(tag))) == 9:
                org = str(tags[tag])
                break
        if not org:
            continue
        osm_type = element.get("type")
        osm_id = element.get("id")
        source_url = f"https://www.openstreetmap.org/{osm_type}/{osm_id}"
        digest = _digest(org, source_url, json.dumps(tags, sort_keys=True, ensure_ascii=False))
        observations.append({
            "id": "openstreetmap-place-" + digest[:24],
            "organisation_number": org,
            "platform": "openstreetmap",
            "signal_type": "place_summary",
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "exact_entity": True,
            "identity_proof": [{"type": "osm_org_number_tag", "value": org}],
            "acquisition_mode": "licensed_api",
            "rights_status": "approved",
            "source_class": "openstreetmap",
            "evidence_span": f"OpenStreetMap feature '{tags.get('name') or 'unnamed'}' tagged with organisation number {org}.",
            "metrics": {
                "name": tags.get("name"),
                "category": tags.get("shop") or tags.get("amenity") or tags.get("office") or tags.get("craft"),
                "latitude": element.get("lat") or (element.get("center") or {}).get("lat"),
                "longitude": element.get("lon") or (element.get("center") or {}).get("lon"),
                "interpretation": "Mapped physical presence; not a rating or review.",
            },
            "strategy": "openstreetmap_places",
        })
    return observations


def main() -> None:
    parser = argparse.ArgumentParser(description="Free, rights-clean external-footprint observation builder.")
    parser.add_argument("--profiles", required=True)
    parser.add_argument("--organisations", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--no-wikidata", action="store_true")
    parser.add_argument("--no-osm", action="store_true")
    args = parser.parse_args()

    profiles = read_jsonl(Path(args.profiles))
    by_org = {str(row["organisation_number"]): row for row in profiles}
    wanted: list[str] = []
    for line in Path(args.organisations).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = line
        org = value.get("organisation_number") if isinstance(value, dict) else value
        org = "".join(character for character in str(org or "") if character.isdigit())
        if len(org) == 9:
            wanted.append(org)

    observations: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for org in wanted:
        profile = by_org.get(org)
        if not profile:
            continue
        for name, builder in (
            ("official_registry_coverage", official_registry_coverage),
            ("official_registry_workforce", official_registry_workforce),
            ("company_site_activity", SITE_ACTIVITY.observation),
            ("company_site_news", SITE_NEWS.observation),
        ):
            item = builder(profile)
            if item:
                item.setdefault("connector", name)
                observations.append(item)
                counts[name] = counts.get(name, 0) + 1

    if not args.no_wikidata:
        try:
            wikidata = wikidata_identity(wanted)
            observations.extend(wikidata)
            counts["wikidata_identity"] = len(wikidata)
        except Exception as exc:  # noqa: BLE001
            counts["wikidata_identity"] = 0
            counts["wikidata_error"] = f"{type(exc).__name__}:{getattr(exc, 'code', '')}"
    if not args.no_osm:
        try:
            osm = openstreetmap_places(wanted)
            observations.extend(osm)
            counts["openstreetmap_places"] = len(osm)
        except Exception as exc:  # noqa: BLE001
            counts["openstreetmap_places"] = 0
            counts["openstreetmap_error"] = f"{type(exc).__name__}:{getattr(exc, 'code', '')}"

    seen: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected = 0
    for item in sorted(observations, key=lambda row: (str(row["organisation_number"]), row["platform"], row["signal_type"])):
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        if publishable_observation(item):
            accepted.append(item)
        else:
            rejected += 1

    Path(args.output).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in accepted), encoding="utf-8"
    )
    orgs_covered = {row["organisation_number"] for row in accepted}
    report = {
        "connector_suite": "signalpost_free_external_connectors_v1",
        "profiles": len(profiles),
        "organisations_requested": len(wanted),
        "observations": len(accepted),
        "rejected_by_gate": rejected,
        "companies_with_observations": len(orgs_covered),
        "connector_counts": counts,
        "third_party_cost_usd": 0,
        "claim_boundary": "Free/rights-clean sources only. Official registry coverage is exact foundation data; external footprint depth on a registry-only population is intentionally not overstated.",
    }
    Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
