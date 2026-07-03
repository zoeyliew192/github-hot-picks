"""数据采集模块：从推荐源仓库（OpenGithubs/weekly、GitHubDaily、OSSNAV）抓取最新推荐项目"""

import requests
from bs4 import BeautifulSoup
import re
import time


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_github_repo_file(owner, repo, path="README.md", github_token=None):
    """从 GitHub 仓库抓取指定文件内容"""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/{path}"
    headers = HEADERS.copy()
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.text
        # 尝试 master 分支
        url2 = f"https://raw.githubusercontent.com/{owner}/{repo}/master/{path}"
        resp2 = requests.get(url2, headers=headers, timeout=20)
        if resp2.status_code == 200:
            return resp2.text
    except Exception:
        pass

    # fallback: 通过 GitHub API
    api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
    headers["Accept"] = "application/vnd.github.v3.raw"
    try:
        resp = requests.get(api_url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"[GitHub API] 获取 {owner}/{repo} README 失败: {e}")

    return None


def parse_github_links_from_markdown(md_content, source_name):
    """从 Markdown 内容中解析出 GitHub 项目链接"""
    if not md_content:
        return []

    projects = []
    # 匹配 GitHub 仓库链接: https://github.com/owner/repo
    pattern = r'https://github\.com/([a-zA-Z0-9\-_\.]+/[a-zA-Z0-9\-_\.]+)'
    matches = re.findall(pattern, md_content)

    seen = set()
    for full_name in matches:
        # 过滤掉非项目链接（如个人主页、组织主页）
        parts = full_name.split("/")
        if len(parts) != 2:
            continue
        # 过滤常见非项目路径
        ignore_prefixes = ["features", "marketplace", "topics", "explore", "settings", "organizations"]
        if parts[0] in ignore_prefixes or parts[1] in ["README", "LICENSE", ".gitignore"]:
            continue

        if full_name not in seen:
            seen.add(full_name)
            # 尝试提取附近的描述文字
            projects.append({
                "name": full_name,
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "source": source_name,
            })

    return projects


def fetch_openithubs_weekly(github_token=None):
    """抓取 OpenGithubs/weekly 最新推荐"""
    print("  [推荐源] 抓取 OpenGithubs/weekly...")
    content = fetch_github_repo_file("OpenGithubs", "weekly", "README.md", github_token)
    return parse_github_links_from_markdown(content, "OpenGithubs/weekly")


def fetch_github_daily(github_token=None):
    """抓取 GitHubDaily 最新推荐"""
    print("  [推荐源] 抓取 GitHubDaily/GitHubDaily...")
    content = fetch_github_repo_file("GitHubDaily", "GitHubDaily", "README.md", github_token)
    return parse_github_links_from_markdown(content, "GitHubDaily")


def fetch_ossnav(github_token=None):
    """抓取 OSSNAV 最新推荐"""
    print("  [推荐源] 抓取 OSSNAV...")
    content = fetch_github_repo_file("maxiaobang7", "ossnav", "README.md", github_token)
    return parse_github_links_from_markdown(content, "OSSNAV")


def fetch_all_recommend_sources(github_token=None):
    """从所有推荐源抓取"""
    all_projects = []

    all_projects.extend(fetch_openithubs_weekly(github_token))
    time.sleep(0.5)

    all_projects.extend(fetch_github_daily(github_token))
    time.sleep(0.5)

    all_projects.extend(fetch_ossnav(github_token))

    # 去重
    seen = set()
    unique = []
    for p in all_projects:
        if p["full_name"] not in seen:
            seen.add(p["full_name"])
            unique.append(p)

    print(f"  [推荐源] 总计获取 {len(unique)} 个推荐项目（去重后）")
    return unique
