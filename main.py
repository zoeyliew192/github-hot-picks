#!/usr/bin/env python3
"""GitHub 热点精选 - 主入口

使用方式:
  python main.py                    # 使用默认配置生成今日报告
  python main.py --date 2026-07-03  # 指定日期
  python main.py --dry-run          # 仅采集数据不生成报告
  python main.py --config my.yaml   # 使用自定义配置文件

工作流程:
  1. 从 GitHub Trending 页面抓取当日/本周热门项目
  2. 从 OpenGithubs/weekly、GitHubDaily、OSSNAV 推荐源获取精选项目
  3. 从 HackerNews 抓取 GitHub 相关热门帖子
  4. 将所有原始数据交给 LLM 分类、精炼、生成4板块报告
  5. 保存为 Markdown 文件到 output 目录
"""

import argparse
import os
from pathlib import Path
import sys
from datetime import datetime

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fetcher_trending import scrape_trending_all_languages
from fetcher_recommend import fetch_all_recommend_sources, load_seen_projects, save_seen_projects
from fetcher_hackernews import fetch_github_related_stories
from generator import generate_report
from run_status import RunStatus


PROJECT_ROOT = Path(__file__).resolve().parent


def resolve_project_path(path):
    resolved = Path(path).expanduser()
    return resolved if resolved.is_absolute() else PROJECT_ROOT / resolved


def load_config(config_path):
    """Load YAML config and merge it onto safe defaults."""
    config_path = resolve_project_path(config_path)
    if not os.path.exists(config_path):
        print(f"[配置] 未找到 {config_path}，使用默认配置")
        return default_config()

    with open(config_path, "r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    if not isinstance(loaded, dict):
        raise ValueError("配置文件顶层必须是 YAML mapping")
    return deep_merge(default_config(), loaded)


def deep_merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config():
    """返回默认配置"""
    return {
        "llm": {
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "",
        },
        "github": {
            "token": "",
        },
        "output": {
            "dir": "output",
            "filename_template": "GitHub热点-{date}.md",
        },
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


def collect_data(config, status):
    """采集所有数据源"""
    raw_data = {}
    github_token = os.environ.get("GITHUB_TOKEN") or config.get("github", {}).get("token", "")
    sources = config.get("sources", {})

    # 1. GitHub Trending
    print("[采集] 正在抓取 GitHub Trending...")
    trending_config = sources.get("github_trending", {})
    languages = trending_config.get("languages", [""])
    since = trending_config.get("since", "daily")
    trending_enabled = trending_config.get("enabled", True)
    trending = scrape_trending_all_languages(since=since, languages=languages, github_token=github_token) if trending_enabled else []
    raw_data["trending"] = trending
    if trending_enabled:
        status.record_source("github_trending", len(trending))
    print(f"[采集] GitHub Trending: {len(trending)} 个项目")

    # 2. 推荐源
    print("[采集] 正在抓取推荐源...")
    selection = sources.get("recommend_selection", {})
    state_file = str(resolve_project_path(selection.get("state_file", ".state/seen-projects.json")))
    seen_projects = load_seen_projects(state_file)
    recommend = fetch_all_recommend_sources(
        github_token,
        source_config=sources,
        seen_projects=seen_projects,
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

    # 3. HackerNews
    print("[采集] 正在抓取 HackerNews GitHub 相关帖子...")
    hn_config = sources.get("hackernews", {})
    top_n = hn_config.get("top_n", 30)
    hn_enabled = hn_config.get("enabled", True)
    hn_stories = fetch_github_related_stories(top_n=top_n) if hn_enabled else []
    raw_data["hackernews"] = hn_stories
    if hn_enabled:
        status.record_source("hackernews", len(hn_stories))
    print(f"[采集] HackerNews: {len(hn_stories)} 条 GitHub 相关帖子")

    return raw_data


def save_report(content, date_str, config):
    """保存生成的报告到文件"""
    output_dir = resolve_project_path(config.get("output", {}).get("dir", "output"))
    filename_template = config.get("output", {}).get("filename_template", "GitHub热点-{date}.md")
    filename = filename_template.replace("{date}", date_str)

    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[保存] 报告已保存到: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="GitHub 热点精选生成工具")
    parser.add_argument("--date", default=None, help="指定日期 (YYYY-MM-DD)，默认今天")
    parser.add_argument("--config", default="config.yaml", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="仅采集数据不生成报告")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    try:
        config = load_config(args.config)
    except Exception as exc:
        status = RunStatus("github-hot-picks", date_str)
        status.error("config", exc)
        status.finish(False)
        status.write(str(PROJECT_ROOT / "output"))
        status.notify_webhook()
        print(f"[错误] 配置加载失败: {exc}")
        return 2

    status = RunStatus("github-hot-picks", date_str)
    output_dir = str(resolve_project_path(config.get("output", {}).get("dir", "output")))

    provider = config.get("llm", {}).get("provider", "openai")
    env_name = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    api_key = os.environ.get(env_name) or config.get("llm", {}).get("api_key", "")
    config["llm"]["api_key"] = api_key
    if not args.dry_run and not api_key:
        print("[错误] 未配置 LLM API Key！请编辑 config.yaml 或设置 environment variable")
        print("  支持的提供商: openai / anthropic")
        print(f"  当前需要: {env_name}")
        status.error("llm", f"missing {env_name}")
        status.finish(False)
        print(f"[监控] 运行状态: {status.write(output_dir)}")
        status.notify_webhook()
        return 2

    # Step 1: 采集数据
    try:
        raw_data = collect_data(config, status)
    except Exception as exc:
        status.error("collection", exc)
        status.finish(False)
        status.write(output_dir)
        status.notify_webhook()
        print(f"[错误] 采集阶段失败: {exc}")
        return 3

    if args.dry_run:
        print("\n[Dry Run] 仅采集数据，跳过生成")
        print(f"  GitHub Trending: {len(raw_data.get('trending', []))} 个")
        print(f"  推荐源项目: {len(raw_data.get('recommend', []))} 个")
        print(f"  HackerNews: {len(raw_data.get('hackernews', []))} 条")
        success = any(status.source_counts.values())
        status.finish(success)
        print(f"[监控] 运行状态: {status.write(output_dir)}")
        status.notify_webhook()
        return 0 if success else 3

    # Step 2: 检查 API Key
    # Step 3: LLM 生成报告
    print("[生成] 正在调用 LLM 生成报告...")
    try:
        report_content = generate_report(raw_data, date_str, config)
    except Exception as e:
        print(f"[错误] LLM 生成失败: {e}")
        status.error("llm", e)
        status.finish(False)
        print(f"[监控] 运行状态: {status.write(output_dir)}")
        status.notify_webhook()
        return 4

    # Step 4: 保存文件
    try:
        filepath = save_report(report_content, date_str, config)
    except Exception as exc:
        status.error("output", exc)
        status.finish(False)
        print(f"[监控] 运行状态: {status.write(output_dir)}")
        status.notify_webhook()
        print(f"[错误] 输出写入失败: {exc}")
        return 5
    try:
        save_seen_projects(
            raw_data.get("recommend_state_file", ".state/seen-projects.json"),
            [project.get("full_name", "") for project in raw_data.get("recommend", [])],
        )
    except Exception as exc:
        status.warn("recommend_state", exc)
    status.finish(True, filepath)
    print(f"[监控] 运行状态: {status.write(output_dir)}")
    status.notify_webhook()

    print(f"\n✅ GitHub 热点精选生成完成！")
    print(f"   文件: {filepath}")
    print(f"   日期: {date_str}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
