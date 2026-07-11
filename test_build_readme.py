#!/usr/bin/env python3
"""Offline tests for the README builder — no network, no tokens.

The page carries my name: these guard the abort-on-failure rules (stale
beats wrong), the audit-score ordering, fallback descriptions, and that
a fully rendered page never leaks a placeholder."""

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import build_readme as br


PROFILE = {
    "projects": [
        {"repo": "alpha", "fallback": "fallback alpha"},
        {"repo": "beta", "fallback": "fallback beta"},
    ],
    "unscheduled_agents": ["housekeeper", "repo-audit"],
}


def fake_gh(responses):
    """gh() stub keyed by substring of the first arg."""
    def _gh(args, raw=False):
        for key, value in responses.items():
            if key in args[0]:
                return value
        return None
    return _gh


class ProjectsTableTest(unittest.TestCase):
    def test_audit_scores_order_the_table(self):
        report = json.dumps({"repos": [
            {"name": "alpha", "score": 3}, {"name": "beta", "score": 8},
        ]})
        responses = {
            "repo-audit/contents": report,
            "repos/astroboy1183/alpha": {"name": "alpha",
                                         "description": "A thing",
                                         "language": "Python"},
            "repos/astroboy1183/beta": {"name": "beta",
                                        "description": "B thing",
                                        "language": "TypeScript"},
        }
        with mock.patch.object(br, "gh", fake_gh(responses)):
            table = br.projects_table(PROFILE)
        self.assertLess(table.index("beta"), table.index("alpha"))  # 8 before 3
        self.assertIn("A thing (Python)", table)

    def test_missing_description_uses_fallback(self):
        responses = {
            "repos/astroboy1183/alpha": {"name": "alpha", "description": None,
                                         "language": "Python"},
            "repos/astroboy1183/beta": {"name": "beta", "description": "",
                                        "language": None},
        }
        with mock.patch.object(br, "gh", fake_gh(responses)):
            table = br.projects_table(PROFILE)
        self.assertIn("fallback alpha (Python)", table)
        self.assertIn("fallback beta", table)

    def test_github_fully_down_aborts(self):
        with mock.patch.object(br, "gh", fake_gh({})):
            self.assertIsNone(br.projects_table(PROFILE))


class FleetCountTest(unittest.TestCase):
    def test_counted_from_scheduler_source(self):
        src = 'repo: "a" repo: "b" repo: "a" repo: "c"'
        with mock.patch.object(br, "gh", fake_gh({"fleet-scheduler": src})):
            self.assertEqual(br.fleet_count(PROFILE), 3 + 2)  # unique + extras

    def test_unreachable_scheduler_falls_back_never_zero(self):
        with mock.patch.object(br, "gh", fake_gh({})):
            self.assertGreater(br.fleet_count(PROFILE), 0)


class RenderGuardTest(unittest.TestCase):
    def test_leftover_placeholder_aborts(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tpl = Path(tmp) / "template.md"
            tpl.write_text("hello {{MYSTERY}}")
            prof = Path(tmp) / "profile.yaml"
            prof.write_text(
                "projects: [{repo: alpha}]\ncredibility: c\nabout: a\n"
                "certifications: c\nexperience: e\ncurrently_building: b\n"
                "fleet: f\nlearning: l\n")
            with mock.patch.object(br, "TEMPLATE", tpl), \
                 mock.patch.object(br, "PROFILE", prof), \
                 mock.patch.object(br, "projects_table", return_value="T"), \
                 mock.patch.object(br, "fleet_count", return_value=11), \
                 mock.patch.object(br, "now_block", return_value="N"):
                with self.assertRaises(SystemExit):
                    br.build()

    def test_real_template_and_profile_render_clean(self):
        """The actual template + yaml in this repo must render with no
        leftovers when the network pieces are stubbed."""
        responses = {
            "fleet-scheduler": 'repo: "a" repo: "b"',
            "repo-audit/contents": json.dumps({"repos": []}),
        }
        for entry in (
            "news-intelligence-platform", "election-dashboard", "DocMind",
            "ipl-intelligence-platform", "SmartDay-App", "Quiz-App",
            "sentiment-analysis",
        ):
            responses[f"repos/astroboy1183/{entry}"] = {
                "name": entry, "description": "d", "language": "Python"}
        with mock.patch.object(br, "gh", fake_gh(responses)), \
             mock.patch.object(br, "credly_badges", return_value=[]), \
             mock.patch.object(br, "now_block",
                               return_value="<!--NOW-START-->x<!--NOW-END-->"):
            page = br.build()
        self.assertNotIn("{{", page)
        self.assertIn("Jayanth Appalla", page)
        self.assertIn("GENERATED FILE", page)


class CareerDerivationTest(unittest.TestCase):
    RESUME = {
        "years_experience": "~3 years",
        "current": {"company": "trigyan.io", "company_url": "https://trigyan.io",
                    "role": "data engineer", "focus": "healthcare data"},
        "work": [
            {"org": "Trigyan", "role": "Data Engineer", "current": True,
             "note": "healthcare platform"},
            {"org": "AWS", "role": "SDE", "note": "DynamoDB"},
            {"org": "Earlier", "note": "various"},
        ],
        "certifications": [
            {"name": "Databricks Certified Associate Data Engineer", "year": 2025},
            {"name": "Tableau Certified Desktop Specialist", "year": 2024},
        ],
        "credly_user": "someone",
        "publication": "**Publication:** paper.",
        "experience_footer": "Full resume on my site.",
    }

    def test_certs_merge_dedupe_and_sort(self):
        live = [
            {"name": "AWS Certified Cloud Practitioner", "year": 2023},
            {"name": "databricks certified associate data engineer", "year": 2025},  # dup
        ]
        with mock.patch.object(br, "credly_badges", return_value=live):
            certs = br.merged_certifications(self.RESUME)
        names = [c["name"] for c in certs]
        self.assertEqual(len(certs), 3)  # dup collapsed
        self.assertEqual(names[0], "Databricks Certified Associate Data Engineer")
        self.assertEqual(names[-1], "AWS Certified Cloud Practitioner")  # oldest last

    def test_credly_down_keeps_baseline(self):
        with mock.patch.object(br, "credly_badges", return_value=[]):
            certs = br.merged_certifications(self.RESUME)
        self.assertEqual(len(certs), 2)

    def test_experience_block_shape(self):
        block = br.experience_block(self.RESUME)
        self.assertIn("- **Trigyan** — Data Engineer *(current)*: healthcare platform", block)
        self.assertIn("- **Earlier**: various", block)  # role-less entry
        self.assertIn("**Publication:** paper.", block)
        self.assertIn("Full resume on my site.", block)

    def test_about_slots(self):
        slots = br.about_slots(self.RESUME)
        self.assertEqual(slots["CURRENT_ROLE"], "data engineer")
        self.assertIn("trigyan.io", slots["CURRENT_COMPANY_LINK"])
        self.assertEqual(slots["YEARS"], "~3 years")

    def test_certifications_line_format(self):
        line = br.certifications_line(
            [{"name": "A", "year": 2025}, {"name": "B", "year": 2024}])
        self.assertTrue(line.startswith("**Certifications:** A (2025)"))
        self.assertIn("B (2024)", line)


class NowBlockTest(unittest.TestCase):
    def test_lines_degrade_never_raise(self):
        with mock.patch.object(br, "gh", fake_gh({})):
            block = br.now_block()
        self.assertIn("NOW-START", block)
        self.assertIn("last updated", block)  # stamp always present


if __name__ == "__main__":
    unittest.main(verbosity=2)