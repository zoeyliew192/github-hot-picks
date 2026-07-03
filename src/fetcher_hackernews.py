"""数据采集模块：从 HackerNews 抓取 GitHub 相关帖子"""

import requests
import time
from datetime import datetime


HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


def fetch_github_related_stories(top_n=30):
    """抓取 HackerNews 中与 GitHub 项目相关的帖子"""
    try:
        resp = requests.get(f"{HN_API_BASE}/topstories.json", timeout=10)
        story_ids = resp.json()[:top_n]
    except Exception as e:
        print(f"[HN] 获取 topstories 失败: {e}")
        return []

    stories = []
    github_keywords = [
        "github", "open source", "opensource", "repo", "repository",
        "project", "tool", "framework", "library", "cli", "terminal",
        "developer", "coding", "software",
    ]

    for sid in story_ids:
        try:
            item = requests.get(f"{HN_API_BASE}/item/{sid}.json", timeout=10).json()
            if not item or item.get("type") != "story":
                continue

            title = item.get("title", "")
            url = item.get("url", "")
            score = item.get("score", 0)

            # 判断是否包含 GitHub 链接
            is_github = "github.com" in url if url else False
            # 或标题中包含相关关键词
            title_lower = title.lower()
            is_related = any(kw in title_lower for kw in github_keywords)

            if is_github or (is_related and score >= 50):
                # 从 GitHub 链接提取项目名
                project_name = ""
                if is_github:
                    import re
                    match = re.search(r'github\.com/([a-zA-Z0-9\-_\.]+/[a-zA-Z0-9\-_\.]+)', url)
                    if match:
                        project_name = match.group(1)

                stories.append({
                    "id": item.get("id"),
                    "title": title,
                    "url": url,
                    "score": score,
                    "descendants": item.get("descendants", 0),
                    "hn_url": f"https://news.ycombinator.com/item?id={item.get('id')}",
                    "project_name": project_name,
                    "source": "HackerNews",
                })
        except Exception:
            continue
        time.sleep(0.05)

    return stories
