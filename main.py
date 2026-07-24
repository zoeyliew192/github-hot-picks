#!/usr/bin/env python3
"""GitHub 热点精选：采集、Agent/API 生成与确定性校验。"""

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from agent_runtime import (
    load_input_packet,
    run_codex_skill,
    save_input_packet,
    validate_markdown_report,
)
from fetcher_hackernews import fetch_github_related_stories
from fetcher_recommend import fetch_all_recommend_sources, load_seen_projects, save_seen_projects
from fetcher_trending import scrape_trending_all_languages
from generator import generate_report
from run_status import RunStatus


PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_NAME = "github-hot-picks"
SKILL_NAME = "generate-github-hot-picks"
REQUIRED_HEADINGS = [
    "AI 编码智能体",
    "AI 应用与工具",
    "开发效率工具",
    "实用开源软件",
    "今日趋势总结",
]


def resolve_project_path(path):
    resolved = Path(path).expanduser()
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config():
    return {
        "runtime": {
            "engine": "codex",
            "codex_command": "codex",
            "input_dir": "input",
        },
        "llm": {"provider": "openai", "model": "gpt-4o", "api_key": ""},
        "github": {"token": ""},
        "output": {"dir": "output", "filename_template": "GitHub热点-{date}.md"},
        "sources": {
            "github_trending": {"enabled": True, "since": "daily", "languages": [""]},
            "hackernews": {"enabled": True, "top_n": 30},
            "recommend_selection": {
                "max_per_source": 10,
                "state_file": ".state/seen-projects.json",
                "enrich_metadata": True,
            },
        },
    }


def load_config(config_path):
    config_path = resolve_project_path(config_path)
    if not config_path.exists():
        print(f"[配置] 未找到 {config_path}，使用默认配置")
        return default_config()
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError("配置文件顶层必须是 YAML mapping")
    return deep_merge(default_config(), loaded)


def collect_data(config, status):
    raw_data = {}
    github_token = os.environ.get("GITHUB_TOKEN") or config.get("github", {}).get("token", "")
    sources = config.get("sources", {})

    print("[采集] 正在抓取 GitHub Trending...")
    trending_config = sources.get("github_trending", {})
    trending_enabled = trending_config.get("enabled", True)
    trending = (
        scrape_trending_all_languages(
            since=trending_config.get("since", "daily"),
            languages=trending_config.get("languages", [""]),
            github_token=github_token,
        )
        if trending_enabled
        else []
    )
    raw_data["trending"] = trending
    if trending_enabled:
        status.record_source("github_trending", len(trending))
    print(f"[采集] GitHub Trending: {len(trending)} 个项目")

    print("[采集] 正在抓取推荐源...")
    selection = sources.get("recommend_selection", {})
    state_file = str(resolve_project_path(selection.get("state_file", ".state/seen-projects.json")))
    recommend = fetch_all_recommend_sources(
        github_token,
        source_config=sources,
        seen_projects=load_seen_projects(state_file),
        max_per_source=int(selection.get("max_per_source", 10)),
        enrich_metadata=selection.get("enrich_metadata", True),
    )
    raw_data["recommend"] = recommend
    raw_data["recommend_state_file"] = state_file
    status.record_source("recommend", len(recommend))
    missing_metadata = sum(1 for project in recommend if "total_stars" not in project)
    if missing_metadata:
        status.warn("github_metadata", f"{missing_metadata} recommendation projects lack API metadata")
    print(f"[采集] 推荐源: {len(recommend)} 个项目")

    print("[采集] 正在抓取 HackerNews GitHub 相关帖子...")
    hn_config = sources.get("hackernews", {})
    hn_enabled = hn_config.get("enabled", True)
    hn_stories = fetch_github_related_stories(top_n=hn_config.get("top_n", 30)) if hn_enabled else []
    raw_data["hackernews"] = hn_stories
    if hn_enabled:
        status.record_source("hackernews", len(hn_stories))
    print(f"[采集] HackerNews: {len(hn_stories)} 条 GitHub 相关帖子")
    return raw_data


def input_path(date_str, config):
    input_dir = resolve_project_path(config.get("runtime", {}).get("input_dir", "input"))
    return input_dir / f"{PROJECT_NAME}-{date_str}.json"


def report_path(date_str, config):
    output_dir = resolve_project_path(config.get("output", {}).get("dir", "output"))
    template = config.get("output", {}).get("filename_template", "GitHub热点-{date}.md")
    return output_dir / template.replace("{date}", date_str)


def save_report(content, date_str, config):
    path = report_path(date_str, config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"[保存] 报告已保存到: {path}")
    return str(path)


def configure_api(config):
    provider = config.get("llm", {}).get("provider", "openai")
    env_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key = os.environ.get(env_name) or config.get("llm", {}).get("api_key", "")
    if not api_key:
        raise ValueError(f"API engine requires {env_name}")
    config["llm"]["api_key"] = api_key


def validate_output(date_str, config):
    return validate_markdown_report(report_path(date_str, config), date_str, REQUIRED_HEADINGS, 10)


def commit_seen_state(raw_data, status):
    try:
        save_seen_projects(
            raw_data.get("recommend_state_file", ".state/seen-projects.json"),
            [project.get("full_name", "") for project in raw_data.get("recommend", [])],
        )
    except Exception as exc:
        status.warn("recommend_state", exc)


def write_status(status, config):
    output_dir = resolve_project_path(config.get("output", {}).get("dir", "output"))
    path = status.write(str(output_dir))
    status.notify_webhook()
    print(f"[监控] 运行状态: {path}")


def parse_args():
    parser = argparse.ArgumentParser(description="GitHub 热点精选生成工具")
    parser.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--engine", choices=("codex", "api"), default=None)
    parser.add_argument("--collect-only", action="store_true", help="只采集并保存 Agent 输入包")
    parser.add_argument("--render-only", action="store_true", help="使用已有输入包生成报告")
    parser.add_argument("--validate-output", action="store_true", help="只校验指定日期报告")
    parser.add_argument("--dry-run", action="store_true", help="兼容别名：等同 --collect-only")
    return parser.parse_args()


def main():
    args = parse_args()
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        config = load_config(args.config)
    except Exception as exc:
        status = RunStatus(PROJECT_NAME, date_str)
        status.error("config", exc)
        status.finish(False)
        status.write(str(PROJECT_ROOT / "output"))
        return 2

    engine = args.engine or config.get("runtime", {}).get("engine", "codex")
    status = RunStatus(PROJECT_NAME, date_str, engine=engine)

    if args.validate_output:
        errors = validate_output(date_str, config)
        for error in errors:
            status.error("validation", error)
        if not errors:
            try:
                raw_data = load_input_packet(input_path(date_str, config), PROJECT_NAME)["data"]
                status.input_file = str(input_path(date_str, config))
                commit_seen_state(raw_data, status)
            except Exception as exc:
                status.warn("recommend_state", f"report valid but input packet unavailable: {exc}")
        status.finish(not errors, str(report_path(date_str, config)) if not errors else "")
        write_status(status, config)
        return 0 if not errors else 5

    packet_file = input_path(date_str, config)
    try:
        if args.render_only:
            packet = load_input_packet(packet_file, PROJECT_NAME)
            raw_data = packet["data"]
        else:
            raw_data = collect_data(config, status)
            packet_file = Path(
                save_input_packet(
                    raw_data,
                    date_str,
                    PROJECT_NAME,
                    resolve_project_path(config.get("runtime", {}).get("input_dir", "input")),
                )
            )
        status.input_file = str(packet_file)
    except Exception as exc:
        status.error("collection", exc)
        status.finish(False)
        write_status(status, config)
        return 3

    if args.collect_only or args.dry_run:
        success = bool(raw_data) and (bool(raw_data) if args.render_only else any(status.source_counts.values()))
        status.finish(success)
        write_status(status, config)
        print(f"[采集] Agent 输入包: {packet_file}")
        return 0 if success else 3

    output_file = report_path(date_str, config)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if engine == "api":
            configure_api(config)
            save_report(generate_report(raw_data, date_str, config), date_str, config)
        else:
            run_codex_skill(
                PROJECT_ROOT,
                SKILL_NAME,
                str(packet_file),
                str(output_file),
                date_str,
                config.get("runtime", {}).get("codex_command", "codex"),
            )
    except Exception as exc:
        status.error(engine, exc)
        status.finish(False)
        write_status(status, config)
        return 4

    errors = validate_output(date_str, config)
    for error in errors:
        status.error("validation", error)
    if not errors:
        commit_seen_state(raw_data, status)
    status.finish(not errors, str(output_file) if not errors else "")
    write_status(status, config)
    if errors:
        return 5
    print(f"\n✅ GitHub 热点精选生成完成：{output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
