"""LLM 生成模块：调用 OpenAI / Anthropic API 生成 GitHub 热点精选报告"""

import json
from datetime import datetime


SYSTEM_PROMPT = """你是 GitHub 热点精选编辑助手，擅长从海量开源项目中筛选、分类、提炼最有价值的项目。

你的写作风格：
- 项目标题格式：`### N. 项目名 — 一句话hook`，hook要抓人、有观点、不干巴巴。例如："agency-agents — 让AI专家代理分工协作，日增3000星登顶Trending"、"caveman — 像原始人一样说话，砍掉65%的token消耗"
- 绝对不要用"一句话描述："这种机械标签，直接把hook融进标题行
- 正文自然衔接，数据前置加粗（star增长、HN热度等），技术特色和适用场景紧随其后
- 项目描述要突出"为什么值得关注"，而非干巴巴的功能罗列
- 趋势总结要提炼当日项目分布的整体趋势方向（如AI Agent爆发、本地隐私优先等）
- 只能使用输入中明确提供的事实和数字；没有 star、日期或性能数据时必须省略，禁止补写或猜测
"""


def build_user_prompt(raw_data, date_str):
    """根据采集的原始数据构建发给 LLM 的 Prompt"""

    date_cn = f"{date_str[:4]}年{int(date_str[5:7])}月{int(date_str[8:10])}日"

    prompt = f"""请根据以下采集到的原始项目数据，生成「每日 GitHub 热点精选 | {date_cn}」。

## 要求
1. 总共精选 13-15 个最有价值的项目
2. 按 4 个板块分类：
   - 一、AI 编码智能体（近期最火方向）2-4个
   - 二、AI 应用与工具 5-7个
   - 三、开发效率工具 3-4个
   - 四、实用开源软件（OSSNAV 精选）3-4个
3. 每个项目格式：
   ```
   ### N. 项目名 — 一句话hook（要有观点、有冲击力，不是功能罗列）
   [2-3句正文：数据前置加粗，技术特色+适用场景自然衔接]
   [GitHub](url)
   ```
   ❌ 禁止格式：`**一句话描述**：xxx` 这种机械标签
   ✅ 正确格式：`### 1. caveman — 像原始人一样说话，砍掉65%的token消耗`
4. 板块间用 `* * *` 分隔
5. 开头写一段介绍，区分当日热度源（GitHub Trending、HackerNews）与长期目录增量发现（OpenGithubs/weekly、GitHubDaily、OSSNAV）
6. 最后写「今日趋势总结」，提炼3个趋势方向
7. 结尾附信息源链接和分享引导
8. 分享引导之后附上 `templates/github_hot_picks.md` 中的「把热点变成你的试用清单（可选）」追问 Prompt；它不属于四个项目板块，也不替读者预设技术能力或当前任务

## 原始数据

### GitHub Trending 热门项目
{format_trending_data(raw_data.get("trending", []))}

### 推荐源项目（OpenGithubs/weekly + GitHubDaily + OSSNAV）
{format_recommend_data(raw_data.get("recommend", []))}

### HackerNews GitHub 相关帖子
{format_hn_data(raw_data.get("hackernews", []))}

请生成完整的 Markdown 格式报告。"""

    return prompt


def format_trending_data(projects):
    """格式化 GitHub Trending 数据"""
    if not projects:
        return "（未获取到 Trending 数据）"
    lines = []
    for p in sorted(projects, key=lambda x: x.get("today_stars", 0), reverse=True)[:25]:
        stars_info = f"总星标 {p.get('total_stars', 'N/A')}"
        if p.get("today_stars", 0) > 0:
            stars_info += f"，今日增长 {p['today_stars']}"
        lang = p.get("language", "")
        lang_str = f" [{lang}]" if lang else ""
        lines.append(f"- [{p.get('name', '')}]({p.get('url', '')}){lang_str} — {stars_info} | {p.get('description', '无描述')[:80]}")
    return "\n".join(lines)


def format_recommend_data(projects):
    """格式化推荐源数据"""
    if not projects:
        return "（未获取到推荐源数据）"
    lines = []
    for p in projects[:30]:
        metadata = []
        if p.get("total_stars") is not None:
            metadata.append(f"总星标 {p.get('total_stars', 0)}")
        if p.get("language"):
            metadata.append(f"语言 {p['language']}")
        if p.get("pushed_at"):
            metadata.append(f"最近 push {p['pushed_at']}")
        if p.get("description"):
            metadata.append(p["description"][:120])
        detail = " | ".join(metadata) or "无可验证 metadata"
        lines.append(
            f"- [{p.get('full_name', '')}]({p.get('url', '')}) — "
            f"来源: {p.get('source', '')} | {detail}"
        )
    return "\n".join(lines)


def format_hn_data(stories):
    """格式化 HackerNews 数据"""
    if not stories:
        return "（未获取到 HN 数据）"
    lines = []
    for s in stories[:15]:
        lines.append(f"- [{s.get('title', '')}]({s.get('url', '')}) — HN {s.get('score', 0)}分, {s.get('descendants', 0)}评论")
    return "\n".join(lines)


def generate_with_openai(raw_data, date_str, api_key, model="gpt-4o"):
    """使用 OpenAI API 生成报告"""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    user_prompt = build_user_prompt(raw_data, date_str)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=4000,
    )

    return response.choices[0].message.content


def generate_with_anthropic(raw_data, date_str, api_key, model="claude-sonnet-4-20250514"):
    """使用 Anthropic API 生成报告"""
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    user_prompt = build_user_prompt(raw_data, date_str)

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.content[0].text


def generate_report(raw_data, date_str, config):
    """根据配置选择 LLM 提供商生成报告"""
    provider = config.get("llm", {}).get("provider", "openai")
    api_key = config.get("llm", {}).get("api_key", "")
    model = config.get("llm", {}).get("model", "")

    if not api_key:
        raise ValueError("请在 config.yaml 中填入 LLM API Key")

    if provider == "anthropic":
        return generate_with_anthropic(raw_data, date_str, api_key, model)
    else:
        return generate_with_openai(raw_data, date_str, api_key, model)
