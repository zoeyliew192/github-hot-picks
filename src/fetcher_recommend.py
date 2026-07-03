"""数据采集模块：从推荐源仓库（OpenGithubs/weekly、GitHubDaily、OSSNAV）抓取最新推荐项目"""

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
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


def select_latest_markdown_path(paths):
    candidates = [
        path for path in paths
        if path.lower().endswith(".md")
        and Path(path).name.lower() not in {"readme.md", "readme_zh.md"}
    ]
    week_order = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5}

    def period_key(path):
        monthly = re.search(r"(^|/)(\d{4})/(\d{1,2})\.md$", path)
        if monthly:
            return int(monthly.group(2)), int(monthly.group(3)), 9
        weekly = re.search(r"(^|/)(\d{4})/(\d{1,2})月第([一二三四五])周\.md$", path)
        if weekly:
            return int(weekly.group(2)), int(weekly.group(3)), week_order[weekly.group(4)]
        return 0, 0, 0

    return max(candidates, key=lambda path: (period_key(path), path)) if candidates else ""


def fetch_latest_markdown_file(owner, repo, github_token=None):
    headers = HEADERS.copy()
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        paths = [
            item.get("path", "")
            for item in response.json().get("tree", [])
            if item.get("size", 0) > 50
        ]
        latest_path = select_latest_markdown_path(paths)
        if not latest_path:
            return None, ""
        return fetch_github_repo_file(owner, repo, latest_path, github_token), latest_path
    except Exception as exc:
        print(f"[GitHub API] 获取 {owner}/{repo} 文件树失败: {exc}")
        return None, ""


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
        full_name = full_name.removesuffix(".git")
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


def load_seen_projects(path):
    state_path = Path(path)
    if not state_path.exists():
        return set()
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return set(data.get("seen_projects", []))
    except (OSError, ValueError, TypeError):
        return set()


def save_seen_projects(path, project_names):
    state_path = Path(path)
    seen = load_seen_projects(path)
    seen.update(name for name in project_names if name)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"seen_projects": sorted(seen)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def select_unseen_projects(projects, seen_projects, limit):
    selected = []
    for project in projects:
        if project.get("full_name") in seen_projects:
            continue
        selected.append(project)
        if len(selected) >= limit:
            break
    return selected


def fetch_repo_metadata(project, github_token=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": HEADERS["User-Agent"]}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    response = requests.get(
        f"https://api.github.com/repos/{project['full_name']}",
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    enriched = dict(project)
    enriched.update({
        "description": data.get("description") or "",
        "language": data.get("language") or "",
        "total_stars": data.get("stargazers_count", 0),
        "pushed_at": data.get("pushed_at") or "",
        "archived": bool(data.get("archived", False)),
    })
    return enriched


def enrich_projects_with_metadata(projects, github_token=None, max_workers=8):
    if not projects:
        return []
    enriched_by_name = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(projects))) as executor:
        futures = {
            executor.submit(fetch_repo_metadata, project, github_token): project
            for project in projects
        }
        for future in as_completed(futures):
            project = futures[future]
            try:
                enriched_by_name[project["full_name"]] = future.result()
            except Exception as exc:
                print(f"  [GitHub metadata] {project['full_name']} 获取失败: {exc}")
                enriched_by_name[project["full_name"]] = project
    return [enriched_by_name[project["full_name"]] for project in projects]


def fetch_openithubs_weekly(github_token=None):
    """抓取 OpenGithubs/weekly 最新推荐"""
    print("  [推荐源] 抓取 OpenGithubs/weekly...")
    content, path = fetch_latest_markdown_file("OpenGithubs", "weekly", github_token)
    if path:
        print(f"  [推荐源] OpenGithubs 最新一期: {path}")
    return [
        project for project in parse_github_links_from_markdown(content, "OpenGithubs/weekly")
        if not project["full_name"].startswith("OpenGithubs/")
    ]


def fetch_github_daily(github_token=None):
    """抓取 GitHubDaily 最新推荐"""
    print("  [推荐源] 抓取 GitHubDaily/GitHubDaily...")
    content = fetch_github_repo_file("GitHubDaily", "GitHubDaily", "README.md", github_token)
    return [
        project for project in parse_github_links_from_markdown(content, "GitHubDaily")
        if project["full_name"] != "GitHubDaily/GitHubDaily"
    ]


def fetch_ossnav(github_token=None):
    """抓取 OSSNAV 最新推荐"""
    print("  [推荐源] 抓取 OSSNAV...")
    content = fetch_github_repo_file("maxiaobang7", "ossnav", "README.md", github_token)
    return [
        project for project in parse_github_links_from_markdown(content, "OSSNAV")
        if project["full_name"] != "maxiaobang7/ossnav"
    ]


def fetch_all_recommend_sources(
    github_token=None,
    source_config=None,
    seen_projects=None,
    max_per_source=10,
    enrich_metadata=True,
):
    """Fetch a bounded, unseen slice from each evergreen recommendation catalog."""
    all_projects = []
    source_config = source_config or {}
    seen_projects = seen_projects or set()
    sources = [
        ("openithubs_weekly", fetch_openithubs_weekly),
        ("github_daily", fetch_github_daily),
        ("ossnav", fetch_ossnav),
    ]

    for config_key, fetcher in sources:
        if not source_config.get(config_key, {}).get("enabled", True):
            continue
        projects = fetcher(github_token)
        selected = select_unseen_projects(projects, seen_projects, max_per_source)
        print(f"  [推荐源] {config_key}: 目录 {len(projects)} 个，本次新增 {len(selected)} 个")
        all_projects.extend(selected)
        time.sleep(0.2)

    # 去重
    seen = set()
    unique = []
    for p in all_projects:
        if p["full_name"] not in seen:
            seen.add(p["full_name"])
            unique.append(p)

    print(f"  [推荐源] 本次选择 {len(unique)} 个未见项目（去重后）")
    return enrich_projects_with_metadata(unique, github_token) if enrich_metadata else unique
