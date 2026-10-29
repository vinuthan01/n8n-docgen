import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import n8n_docgen as g  # noqa: E402

SAMPLE = ROOT / "examples" / "daily-news-digest.json"


class DocgenTests(unittest.TestCase):
    def setUp(self):
        self.wf = g.load_workflow(SAMPLE)
        self.md = g.render(self.wf)

    def test_title_and_counts(self):
        self.assertIn("# Daily News Digest", self.md)
        self.assertIn("**Nodes:** 7 (1 disabled)", self.md)

    def test_trigger_detected(self):
        self.assertIn("Every Morning (`scheduleTrigger`)", self.md)

    def test_steps_follow_flow_order(self):
        self.assertLess(self.md.index("1. **Every Morning**"), self.md.index("2. **Fetch Headlines**"))

    def test_credentials_listed_by_name_only(self):
        self.assertIn("slackApi (My Slack)", self.md)

    def test_secret_value_never_printed(self):
        self.assertNotIn("demo-not-a-real-key", self.md)
        self.assertIn("hardcoded value in `apiKey`", self.md)

    def test_warnings(self):
        self.assertIn("**Forgotten Note** is not connected", self.md)
        self.assertIn("**Old Email Step** is disabled", self.md)

    def test_mermaid_block(self):
        self.assertIn("```mermaid\nflowchart LR", self.md)
        self.assertIn("|output 2|", self.md)

    def test_rejects_non_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text(json.dumps({"hello": "world"}))
            with self.assertRaises(ValueError):
                g.load_workflow(bad)

    def test_cli_writes_file_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.md"
            self.assertEqual(g.main([str(SAMPLE), "-o", str(out)]), 0)
            self.assertIn("# Daily News Digest", out.read_text(encoding="utf-8"))
            self.assertEqual(g.main([str(Path(d) / "missing.json")]), 1)


if __name__ == "__main__":
    unittest.main()
