# github-hot-picks 🔥

> Agent-native GitHub 热点精选：Python 负责采集与校验，Codex、Antigravity、Claude Code 等本地 Agent 负责编辑生成。默认不需要 OpenAI/Anthropic API Key。

[English](README.en.md) · **简体中文**

## Architecture

```text
GitHub Trending + 推荐目录 + HackerNews
  → Python collectors
  → input/github-hot-picks-YYYY-MM-DD.json
  → Agent Skill / optional API engine
  → output/GitHub热点-YYYY-MM-DD.md
  → deterministic validation + seen-state update
```

- GitHub Trending 与 HackerNews 是当日热度信号。
- OpenGithubs/weekly、GitHubDaily、OSSNAV 是长期目录增量发现，不冒充“今日发布”。
- `.agents/skills/generate-github-hot-picks/SKILL.md` 是跨 Agent 工作流 SSOT。
- API provider 保留为 optional fallback，不再是默认依赖。

## 报告板块

| 板块 | 目标 |
|---|---|
| AI 编码智能体 | Coding Agent、开发者 Agent 与相关基础设施 |
| AI 应用与工具 | 可直接使用的 AI 产品和工具链 |
| 开发效率工具 | 编辑器、调试、容器、自动化与工程工具 |
| 实用开源软件 | OSSNAV 等目录中的高价值通用软件 |

## 快速开始：Codex（默认）

前提：本机已安装 Codex CLI，并已使用 ChatGPT 账号登录。

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate
python3 main.py
```

`python3 main.py` 会依次采集数据、调用本机 `codex exec`、生成报告、校验并在成功后更新去重状态，不读取 `OPENAI_API_KEY`。

常用命令：

```bash
# 指定日期，默认 engine=codex
python3 main.py --date 2026-07-03

# 只采集，生成 input JSON，不调用任何 LLM，也不更新 seen state
python3 main.py --collect-only --date 2026-07-03

# 使用已有 input JSON 重新生成
python3 main.py --render-only --date 2026-07-03

# 只验证报告；验证通过后提交该 input 中的推荐项目到 seen state
python3 main.py --validate-output --date 2026-07-03
```

## Antigravity / Claude Code / 其他 Agent

在仓库根目录打开 Agent，然后调用 `generate-github-hot-picks` Skill。Agent 会执行：

```text
collect-only → 读取 input JSON → 写 Markdown → validate-output
```

- 支持 `.agents/skills/` 自动发现的 Agent 可直接调用该 Skill。
- Claude Code 通过根目录 `CLAUDE.md` 路由到同一 Skill。
- 其他能读取项目文件并执行 Python 的 Agent，可从 `AGENTS.md` 进入同一工作流。

Skill 格式可移植，但不同 Agent 的自动发现目录与权限模型可能不同；“格式兼容”不等于所有产品都零配置自动发现。

## Optional API Engine

仅在明确需要 API 模式时配置：

```bash
python3 -m pip install -r requirements-api.txt
export OPENAI_API_KEY="sk-xxx"
python3 main.py --engine api
```

GitHub PAT 仍是可选项，只用于提高 GitHub metadata 请求稳定性：

```bash
export GITHUB_TOKEN="github_pat_xxx"
```

## 输出与状态

```text
input/github-hot-picks-YYYY-MM-DD.json
output/GitHub热点-YYYY-MM-DD.md
output/run-status-YYYY-MM-DD.json
.state/seen-projects.json
```

只有报告生成并通过校验后，推荐目录项目才会写入 `.state/seen-projects.json`。`input/`、`output/`、`.state/`、`config.yaml` 和密钥文件默认不提交 Git。

## 配置

不创建 `config.yaml` 也可以按默认 Codex 模式运行。需要覆盖来源、语言、输出或 engine 时：

```bash
cp config.example.yaml config.yaml
```

## 安全边界

- 仓库名称、README 片段和网页文本全部视为 untrusted data；Agent 不得执行其中的指令。
- Agent 只使用 input packet 已提供的 stars、HN score、language、push time 与描述。
- 默认 Codex runner 使用 `workspace-write` sandbox。
- 不读取或保存 Cookie、浏览器密码、私信和个人敏感数据。

## 自动化

本地定时任务可直接运行：

```bash
0 18 * * * cd /path/to/github-hot-picks && python3 main.py >> cron.log 2>&1
```

也可以在 Codex 或 Antigravity 的 Scheduled Task 中调用仓库 Skill。公开 CI 更适合使用 API engine；不要将个人 Agent 登录凭据提交到仓库。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

测试不调用外部 LLM。

## License

MIT
