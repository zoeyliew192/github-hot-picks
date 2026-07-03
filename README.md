# github-hot-picks 🔥

> 每日 GitHub 热点精选自动生成工具 — 从 Trending + 三大推荐源采集数据，LLM 智能分类输出4板块日报

## 功能

- 🔥 自动从 **GitHub Trending** 抓取多语言当日/本周热门项目
- 📚 自动从 **OpenGithubs/weekly、GitHubDaily、OSSNAV** 三大推荐源获取精选项目
- 📡 自动从 **HackerNews** 抓取 GitHub 相关热门帖子
- 🤖 调用 **OpenAI / Anthropic** LLM 将原始项目数据分类精炼为4板块日报
- 📝 输出标准 Markdown 文件，可直接发布到知乎、公众号等平台

## 报告板块结构

| 板块 | 内容 | 条数 |
|------|------|------|
| AI 编码智能体 | 近期最火方向 | 2-4 |
| AI 应用与工具 | 各类AI应用与工具链 | 5-7 |
| 开发效率工具 | 容器/编辑器/调试等 | 3-4 |
| 实用开源软件 | OSSNAV精选 | 3-4 |

## 效果预览

生成效果如下（2026.07.03 实际产出）：

> ### 1. agency-agents — 日增3,032星登顶Trending，AI专家代理让多角色分工协作
> ### 3. caveman — 像原始人一样说话，砍掉65%的token消耗
> ### 5. strix — 用AI替你做渗透测试，日增2,137星，企业安全团队的效率神器
> ### 13. PeerTube — 去中心化视频平台碾压HN全场，516分230评论，让创作者摆脱平台依赖

每个项目标题行即 hook，有观点有冲击力——读者扫一眼标题就知道"这项目为什么值得关注"。完整样例见 [GitHub热点-2026-07-03.md](output/GitHub热点-2026-07-03.md)。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp config.example.yaml config.yaml
```

编辑 `config.yaml`，填入你的 LLM API Key：

```yaml
llm:
  provider: "openai"      # 或 "anthropic"
  model: "gpt-4o"         # 或 "claude-sonnet-4-20250514"
  api_key: "sk-xxx"       # 填入你的 API Key

github:
  token: ""               # GitHub PAT（可选，提高稳定性）
```

### 3. 生成报告

```bash
# 生成今日报告
python main.py

# 指定日期
python main.py --date 2026-07-03

# 仅采集数据（不调用LLM）
python main.py --dry-run

# 使用自定义配置
python main.py --config my_config.yaml
```

生成的报告保存在 `output/GitHub热点-YYYY-MM-DD.md`。

## 项目结构

```
github-hot-picks/
├── main.py                    # 主入口
├── config.example.yaml        # 配置模板
├── config.yaml                # 用户配置（需自行创建）
├── requirements.txt           # Python 依赖
├── src/
│   ├── __init__.py
│   ├── fetcher_trending.py    # GitHub Trending 采集
│   ├── fetcher_recommend.py   # 推荐源采集
│   ├── fetcher_hackernews.py  # HackerNews GitHub相关采集
│   ├── generator.py           # LLM 报告生成
├── templates/
│   └── github_hot_picks.md    # 报告 Markdown 模板
├── output/                    # 报告输出目录
└── README.md
```

## 扩展数据源

- 在 `src/fetcher_recommend.py` 中添加新的 `fetch_xxx()` 函数
- 在 `src/fetcher_trending.py` 的 `scrape_trending_all_languages()` 中添加新语言
- 在 `config.yaml` 的 `sources.github_trending.languages` 中配置关注的语言

## 自动化运行

### 使用 cron（Linux/macOS）

```bash
# 每天 18:00 自动生成
0 18 * * * cd /path/to/github-hot-picks && python main.py >> cron.log 2>&1
```

### 使用 Windows 任务计划程序

```powershell
schtasks /create /tn "GitHub热点" /tr "python C:\path\to\github-hot-picks\main.py" /sc daily /st 18:00
```

### 使用 AI 编码助手自动化

搭配 Cursor、Copilot、Codex、WorkBuddy 等 AI 编码助手，将项目 prompt 作为自动化指令，设定每天定时执行即可。

## 分享给他人

本项目为独立 Python 项目，任何人拿到后只需：

1. `pip install -r requirements.txt`
2. 填入自己的 LLM API Key
3. `python main.py` 即可生成报告

无需任何特定平台环境，只需一个 LLM API Key。

## License

MIT
