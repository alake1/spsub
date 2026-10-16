from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build_observations = load("build_observations", "scripts/build_external_observations.py")
build_labels = load("build_labels", "scripts/build_provisional_labels.py")
evaluate_ux = load("evaluate_ux", "scripts/evaluate_product_ux.py")


def profile(org: str, **overrides):
    base = {
        "organisation_number": org,
        "name": "Eksempel AS",
        "legal_form": "AS",
        "employees": None,
        "municipality": "OSLO",
        "website": "",
        "latest_submitted_accounts": "2025",
        "evidence": {
            "registry_live": {
                "status": "available",
                "source_url": f"https://data.brreg.no/enhetsregisteret/api/enheter/{org}",
                "retrieved_at": "2026-10-16T00:00:00Z",
                "content_sha256": "a" * 64,
                "value": {"organisation_number": org, "legal_form": "AS", "municipality": "OSLO", "employees": 3},
            },
            "registry": {
                "status": "available",
                "source_url": "https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv",
                "retrieved_at": "2026-10-16T00:00:00Z",
                "content_sha256": "b" * 64,
                "value": {},
            },
        },
    }
    base.update(overrides)
    return base


class ExternalObservationTests(unittest.TestCase):
    def test_official_coverage_requires_exact_org(self):
        good = build_observations.official_registry_coverage(profile("985589003"))
        self.assertIsNotNone(good)
        self.assertTrue(good["exact_entity"])
        self.assertEqual(good["platform"], "brreg")
        self.assertEqual(good["acquisition_mode"], "official_api")
        self.assertEqual(len(good["content_sha256"]), 64)

    def test_official_coverage_rejects_mismatched_org(self):
        mismatch = profile("985589003")
        mismatch["evidence"]["registry_live"]["value"]["organisation_number"] = "999999999"
        self.assertIsNone(build_observations.official_registry_coverage(mismatch))

    def test_official_coverage_rejects_missing_hash(self):
        broken = profile("985589003")
        broken["evidence"]["registry_live"]["content_sha256"] = ""
        self.assertIsNone(build_observations.official_registry_coverage(broken))

    def test_workforce_only_when_employee_count_present(self):
        self.assertIsNotNone(build_observations.official_registry_workforce(profile("985589003")))
        self.assertIsNone(build_observations.official_registry_workforce(profile("985589003", evidence={
            "registry_live": {"status": "available", "source_url": "u", "retrieved_at": "t", "content_sha256": "a" * 64,
                              "value": {"organisation_number": "985589003", "employees": None}},
            "registry": {},
        })))


class ProvisionalLabelTests(unittest.TestCase):
    def test_exact_proof_labels_positive(self):
        self.assertTrue(build_labels.proof_names_entity(
            {"organisation_number": "985589003", "identity_proof": [{"type": "exact_organisation_number", "value": "985589003"}]}
        ))

    def test_website_gate_exact_labels_positive(self):
        self.assertTrue(build_labels.proof_names_entity(
            {"organisation_number": "985589003", "identity_proof": [{"type": "website_identity_gate", "status": "exact", "score": 1.0}]}
        ))

    def test_missing_proof_is_not_positive(self):
        self.assertFalse(build_labels.proof_names_entity({"organisation_number": "985589003", "identity_proof": []}))


class ProductUxTests(unittest.TestCase):
    def test_ux_score_reads_markers(self):
        html = ('<input id="q"><select id="form"></select><select id="finance"></select>'
                '<article id="profile">Official annual account</article>'
                '<form id="agent-form"></form><div id="agent-output"></div>'
                'localStorage save-view pin SHA-256 Inspect evidence signalpost-evidence-export linkedin-layer')
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmp:
            proto = Path(tmp) / "p.html"
            proto.write_text(html, encoding="utf-8")
            out = Path(tmp) / "ux.json"
            import sys
            sys.argv = ["x", "--prototype", str(proto), "--output", str(out)]
            evaluate_ux.main()
            report = json.loads(out.read_text())
            self.assertEqual(report["score"], 8.0)
            self.assertFalse(report["external_intelligence_presented"])


if __name__ == "__main__":
    unittest.main()
