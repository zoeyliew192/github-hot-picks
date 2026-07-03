import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import main
from fetcher_recommend import (
    load_seen_projects,
    parse_github_links_from_markdown,
    save_seen_projects,
    select_latest_markdown_path,
    select_unseen_projects,
)
from fetcher_trending import parse_period_stars
from run_status import RunStatus


class CoreTests(unittest.TestCase):
    def test_relative_paths_are_resolved_from_project_root(self):
        self.assertEqual(main.resolve_project_path("output"), ROOT / "output")

    def test_example_config_preserves_nested_values_and_lists(self):
        config = main.load_config(str(ROOT / "config.example.yaml"))
        self.assertEqual(config["llm"]["provider"], "openai")
        self.assertEqual(config["sources"]["github_trending"]["languages"][1], "python")
        self.assertEqual(config["sources"]["recommend_selection"]["max_per_source"], 10)
        self.assertGreater(len(config["sections"]), 1)

    def test_invalid_top_level_config_is_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
            handle.write("- invalid\n- top-level\n")
            path = handle.name
        try:
            with self.assertRaises(ValueError):
                main.load_config(path)
        finally:
            os.unlink(path)

    def test_recommendation_selection_skips_seen_and_is_bounded(self):
        projects = [
            {"full_name": "org/one"},
            {"full_name": "org/two"},
            {"full_name": "org/three"},
        ]
        selected = select_unseen_projects(projects, {"org/one"}, 1)
        self.assertEqual([item["full_name"] for item in selected], ["org/two"])

    def test_seen_state_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "seen.json")
            save_seen_projects(path, ["org/one", "org/two"])
            save_seen_projects(path, ["org/two", "org/three"])
            self.assertEqual(load_seen_projects(path), {"org/one", "org/two", "org/three"})

    def test_markdown_parser_deduplicates_repositories(self):
        markdown = "https://github.com/org/repo https://github.com/org/repo.git"
        parsed = parse_github_links_from_markdown(markdown, "test")
        self.assertEqual([item["full_name"] for item in parsed], ["org/repo"])

    def test_latest_markdown_path_ignores_readme(self):
        paths = ["README.md", "2024/8月第二周.md", "2024/8月第三周.md", "2025/01.md"]
        self.assertEqual(select_latest_markdown_path(paths), "2025/01.md")

    def test_latest_week_uses_chronological_chinese_week_order(self):
        paths = ["2024/8月第二周.md", "2024/8月第三周.md"]
        self.assertEqual(select_latest_markdown_path(paths), "2024/8月第三周.md")

    def test_trending_period_stars_are_parsed(self):
        self.assertEqual(parse_period_stars("1,234 stars today"), 1234)
        self.assertEqual(parse_period_stars("876 stars this week"), 876)

    def test_status_file_is_machine_readable(self):
        status = RunStatus("test", "2026-07-03")
        status.record_source("trending", 2)
        status.finish(True, "output.md")
        with tempfile.TemporaryDirectory() as directory:
            path = status.write(directory)
            text = Path(path).read_text(encoding="utf-8")
        self.assertIn('"status": "success"', text)
        self.assertIn('"trending": 2', text)

    def test_warning_changes_status_without_failing_run(self):
        status = RunStatus("test", "2026-07-03")
        status.warn("optional", "degraded")
        status.finish(True)
        self.assertEqual(status.status, "success_with_warnings")

    @patch.dict(os.environ, {"RUN_STATUS_WEBHOOK_URL": "https://example.test/hook"})
    @patch("run_status.requests.post")
    def test_webhook_posts_status_payload(self, mocked_post):
        mocked_post.return_value.raise_for_status.return_value = None
        status = RunStatus("test", "2026-07-03")
        status.finish(True)
        status.notify_webhook()
        mocked_post.assert_called_once()
        self.assertEqual(mocked_post.call_args.kwargs["json"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
