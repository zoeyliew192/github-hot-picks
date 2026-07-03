"""数据采集模块：从 GitHub Trending 页面抓取当日热门项目"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def parse_period_stars(text):
    match = re.search(r"([\d,]+)\s+stars?\s+(?:today|this week|this month)", text or "", re.I)
    return int(match.group(1).replace(",", "")) if match else 0


def scrape_trending(since="daily", language="", github_token=None):
    """抓取 GitHub Trending 页面

    Args:
        since: "daily" / "weekly" / "monthly"
        language: 编程语言筛选，空字符串=全部
        github_token: GitHub PAT（可选，增加请求成功率）

    Returns:
        list of dict: [{name, description, language, stars, today_stars, url}]
    """
    url = f"https://github.com/trending/{language}?since={since}"
    headers = HEADERS.copy()
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    projects = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        articles = soup.select("article.Box-row")
        if not articles:
            # 尝试新版 GitHub 页面结构
            articles = soup.select("[class*='repo-item']") or soup.select(".repo")

        for article in articles:
            try:
                # 项目名
                name_el = article.select_one("h2 a") or article.select_one("a[href]")
                if not name_el:
                    continue
                href = name_el.get("href", "").strip("/")
                name = href if href else ""

                # 描述
                desc_el = article.select_one("p") or article.select_one("[class*='description']")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # 编程语言
                lang_el = article.select_one("[itemprop='programmingLanguage']")
                lang = lang_el.get_text(strip=True) if lang_el else ""

                # 总 star 数
                stars_el = article.select_one("a[href$='/stargazers']")
                total_stars = 0
                if stars_el:
                    stars_text = stars_el.get_text(strip=True).replace(",", "")
                    total_stars = int(stars_text) if stars_text.isdigit() else 0

                # 今日新增 star
                today_text = ""
                today_el = article.select_one(".d-inline-block.float-sm-right")
                if today_el:
                    today_text = today_el.get_text(strip=True)

                # 备选：找所有包含 "stars today" 的文本
                if not today_text:
                    all_text = article.get_text()
                    match = re.search(r"([\d,]+)\s*stars\s*today", all_text)
                    if match:
                        today_text = match.group(1)

                today_stars = parse_period_stars(today_text or article.get_text(" ", strip=True))

                projects.append({
                    "name": name,
                    "full_name": name,
                    "description": description,
                    "language": lang,
                    "total_stars": total_stars,
                    "today_stars": today_stars,
                    "url": f"https://github.com/{name}",
                    "source": "GitHub Trending",
                })
            except Exception:
                continue

    except Exception as e:
        print(f"[GitHub Trending] 抓取失败: {e}")

    return projects


def scrape_trending_all_languages(since="daily", languages=None, github_token=None):
    """抓取多个语言的 GitHub Trending 页面"""
    if languages is None:
        languages = ["", "python", "javascript", "typescript", "rust", "go"]

    all_projects = []
    seen_names = set()

    for lang in languages:
        print(f"  [Trending] 抓取语言: {lang or 'all'}")
        projects = scrape_trending(since=since, language=lang, github_token=github_token)
        for p in projects:
            if p["name"] not in seen_names:
                seen_names.add(p["name"])
                all_projects.append(p)

    return all_projects
