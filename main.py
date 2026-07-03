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
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fetcher_trending import scrape_trending_all_languages
from fetcher_recommend import fetch_all_recommend_sources
from fetcher_hackernews import fetch_github_related_stories
from generator import generate_report


def load_config(config_path):
    """加载 YAML 配置文件"""
    config = {}
    if not os.path.exists(config_path):
        print(f"[配置] 未找到 {config_path}，使用默认配置")
        return default_config()

    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 简易 YAML 解析
    current_section = None
    current_subsection = None
    list_key = None
    list_items = []

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # 处理列表项
        if stripped.startswith("- ") and list_key:
            item = stripped[2:].strip()
            if item.startswith('"') and item.endswith('"'):
                item = item[1:-1]
            list_items.append(item)
            continue

        # 重置列表收集
        if list_key and list_items:
            if current_subsection:
                config[current_section][current_subsection][list_key] = list_items
            elif current_section:
                config[current_section][list_key] = list_items
            list_key = None
            list_items = []

        # 键值行
        if ":" in stripped and not stripped.startswith("-"):
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()

            if not value:
                # 可能是列表开始
                list_key = key
                list_items = []
                continue

            # 解析值类型
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "", 1).isdigit():
                value = float(value)

            # 嵌套键 (如 github.token)
            if "." in key:
                parts = key.split(".", 1)
                if parts[0] not in config:
                    config[parts[0]] = {}
                if not isinstance(config[parts[0]], dict):
                    config[parts[0]] = {}
                config[parts[0]][parts[1]] = value
            elif current_section:
                if current_subsection:
                    if current_section not in config:
                        config[current_section] = {}
                    if current_subsection not in config[current_section]:
                        config[current_section][current_subsection] = {}
                    config[current_section][current_subsection][key] = value
                else:
                    if current_section not in config:
                        config[current_section] = {}
                    config[current_section][key] = value
            else:
                config[key] = value

    # 处理末尾列表
    if list_key and list_items:
        if current_section:
            if current_section not in config:
                config[current_section] = {}
            config[current_section][list_key] = list_items

    return config


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
    }


def collect_data(config):
    """采集所有数据源"""
    raw_data = {}
    github_token = config.get("github", {}).get("token", "")

    # 1. GitHub Trending
    print("[采集] 正在抓取 GitHub Trending...")
    languages = config.get("sources", {}).get("github_trending", {}).get("languages", [""])
    since = config.get("sources", {}).get("github_trending", {}).get("since", "daily")
    trending = scrape_trending_all_languages(since=since, languages=languages, github_token=github_token)
    raw_data["trending"] = trending
    print(f"[采集] GitHub Trending: {len(trending)} 个项目")

    # 2. 推荐源
    print("[采集] 正在抓取推荐源...")
    recommend = fetch_all_recommend_sources(github_token)
    raw_data["recommend"] = recommend
    print(f"[采集] 推荐源: {len(recommend)} 个项目")

    # 3. HackerNews
    print("[采集] 正在抓取 HackerNews GitHub 相关帖子...")
    top_n = config.get("sources", {}).get("hackernews", {}).get("top_n", 30)
    hn_stories = fetch_github_related_stories(top_n=top_n)
    raw_data["hackernews"] = hn_stories
    print(f"[采集] HackerNews: {len(hn_stories)} 条 GitHub 相关帖子")

    return raw_data


def save_report(content, date_str, config):
    """保存生成的报告到文件"""
    output_dir = config.get("output", {}).get("dir", "output")
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
    config = load_config(args.config)

    # Step 1: 采集数据
    raw_data = collect_data(config)

    if args.dry_run:
        print("\n[Dry Run] 仅采集数据，跳过生成")
        print(f"  GitHub Trending: {len(raw_data.get('trending', []))} 个")
        print(f"  推荐源项目: {len(raw_data.get('recommend', []))} 个")
        print(f"  HackerNews: {len(raw_data.get('hackernews', []))} 条")
        return

    # Step 2: 检查 API Key
    api_key = config.get("llm", {}).get("api_key", "")
    if not api_key:
        print("[错误] 未配置 LLM API Key！请编辑 config.yaml 填入 api_key")
        print("  支持的提供商: openai / anthropic")
        print("  配置文件位置: config.yaml（参考 config.example.yaml）")
        sys.exit(1)

    # Step 3: LLM 生成报告
    print("[生成] 正在调用 LLM 生成报告...")
    try:
        report_content = generate_report(raw_data, date_str, config)
    except Exception as e:
        print(f"[错误] LLM 生成失败: {e}")
        sys.exit(1)

    # Step 4: 保存文件
    filepath = save_report(report_content, date_str, config)

    print(f"\n✅ GitHub 热点精选生成完成！")
    print(f"   文件: {filepath}")
    print(f"   日期: {date_str}")


if __name__ == "__main__":
    main()
