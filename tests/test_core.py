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
from agent_runtime import load_input_packet, run_codex_skill, save_input_packet, validate_markdown_report
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
        self.assertEqual(config["runtime"]["engine"], "codex")
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

    def test_agent_packet_round_trip_has_no_credentials(self):
        data = {"trending": [{"full_name": "org/repo"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = save_input_packet(data, "2026-07-03", "github-hot-picks", directory)
            packet = load_input_packet(path, "github-hot-picks")
        self.assertEqual(packet["data"]["trending"][0]["full_name"], "org/repo")
        self.assertNotIn("api_key", packet)

    def test_report_validator_rejects_template_placeholders(self):
        report = "# 2026年7月3日 GitHub 热点\n\n## 今日趋势总结\n" + "内容 " * 500 + "\n[GitHub](url)\n"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
            handle.write(report)
            path = handle.name
        try:
            errors = validate_markdown_report(path, "2026-07-03", ["今日趋势总结"], 0)
            self.assertIn("report still contains template placeholders", errors)
        finally:
            os.unlink(path)

    def test_codex_engine_does_not_require_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.yaml"
            config_path.write_text(
                "runtime:\n"
                "  engine: codex\n"
                f"  input_dir: {root / 'input'}\n"
                "output:\n"
                f"  dir: {root / 'output'}\n",
                encoding="utf-8",
            )

            def fake_collect(config, status):
                status.record_source("fixture", 1)
                return {
                    "trending": [{"full_name": "org/repo", "url": "https://github.com/org/repo"}],
                    "recommend": [],
                    "hackernews": [],
                    "recommend_state_file": str(root / ".state" / "seen.json"),
                }

            def fake_codex(project_root, skill, input_file, output_file, date_str, configured):
                sections = "\n".join(f"## {heading}" for heading in main.REQUIRED_HEADINGS)
                links = "\n".join(f"https://github.com/org/repo{index}" for index in range(10))
                Path(output_file).write_text(
                    f"# 2026年7月3日 GitHub 热点\n{sections}\n" + "内容 " * 500 + links,
                    encoding="utf-8",
                )

            with patch.object(main, "collect_data", side_effect=fake_collect), patch.object(
                main, "run_codex_skill", side_effect=fake_codex
            ) as mocked_codex, patch.object(
                sys, "argv", ["main.py", "--date", "2026-07-03", "--config", str(config_path)]
            ), patch.dict(os.environ, {}, clear=True):
                result = main.main()
            self.assertEqual(result, 0)
            mocked_codex.assert_called_once()

    @patch("agent_runtime.resolve_codex_command", return_value="codex")
    @patch("agent_runtime.subprocess.run")
    def test_codex_usage_limit_error_is_concise(self, mocked_run, _mocked_resolve):
        mocked_run.return_value.returncode = 1
        mocked_run.return_value.stderr = "WARN noisy\nERROR: You've hit your usage limit. Try later.\n"
        mocked_run.return_value.stdout = ""
        with self.assertRaisesRegex(RuntimeError, "usage limit.*Antigravity"):
            run_codex_skill(ROOT, "generate-github-hot-picks", "input.json", "output.md", "2026-07-03")

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
