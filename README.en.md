# github-hot-picks 🔥

> For people who cannot spend every day scanning Trending but still want open-source tools worth testing. Get a sourced Chinese GitHub brief, then use the built-in follow-up prompt to filter projects for your role, workflow, and technical comfort.

**English** · [简体中文](README.md)

## Who it is for

- Independent developers, founders, product people, and high-agency operators who actively use AI tools.
- Readers looking for coding agents, AI applications, developer productivity tools, and practical open source without scanning several feeds.
- People who want daily traction separated from long-running catalog discovery and a second-pass recommendation from their own agent.

This is not a GitHub Trending mirror, real-time leaderboard, or complete index of every new repository. It never invents capabilities or performance from a project name.

## What you get

1. A Chinese project brief selected from Trending, Hacker News, and long-running recommendation catalogs.
2. Traceable stars, HN scores, languages, update times, or source labels when present; missing data is omitted rather than guessed.
3. A reusable prompt at the end of each report. Add your role, current task, technical comfort, environment, and available time to identify the 3–5 projects most worth testing.

The four report sections remain stable for longitudinal comparison. Personal fit is evaluated after the shared report is generated.

## Architecture

```text
GitHub Trending + curated catalogs + Hacker News
  → Python collectors
  → input/github-hot-picks-YYYY-MM-DD.json
  → Agent Skill / optional API engine
  → output/GitHub热点-YYYY-MM-DD.md
  → deterministic validation + local seen-state update
```

- GitHub Trending and Hacker News are daily traction signals.
- OpenGithubs/weekly, GitHubDaily, and OSSNAV are long-running discovery catalogs; their entries are not misrepresented as newly released projects.
- `.agents/skills/generate-github-hot-picks/SKILL.md` is the workflow SSOT.
- The paid API provider is an optional fallback, not the default dependency.

## Report sections

| Section | Focus |
|---|---|
| AI coding agents | Coding agents, developer agents, and related infrastructure |
| AI apps and tools | AI products and practical toolchains |
| Developer productivity | Editors, debugging, containers, automation, and engineering tools |
| Useful open source | High-value general software found through curated catalogs |

The final report is written in Chinese.

## Quick start with Codex

Prerequisites: Python 3, Codex CLI, and a signed-in ChatGPT account.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
source .venv/bin/activate
python3 main.py
```

The default command collects public metadata, invokes the local `codex exec`, writes and validates the report, and commits the local seen state only after validation succeeds.

Useful commands:

```bash
# Run for a specific date
python3 main.py --date 2026-07-03

# Collect without invoking an LLM or updating seen state
python3 main.py --collect-only --date 2026-07-03

# Regenerate from an existing packet
python3 main.py --render-only --date 2026-07-03

# Validate an existing report and then update seen state
python3 main.py --validate-output --date 2026-07-03
```

## Use the embedded Skill

Open the repository in an agent that can read project files and run Python, then invoke `generate-github-hot-picks`. Agents that discover `.agents/skills/` can load the workflow directly; `CLAUDE.md` and `AGENTS.md` route other compatible agents to the same SSOT.

Skill format compatibility does not guarantee identical auto-discovery or permission behavior across products.

## Optional credentials

The paid LLM API engine is opt-in:

```bash
python3 -m pip install -r requirements-api.txt
export OPENAI_API_KEY="sk-xxx"
python3 main.py --engine api
```

`GITHUB_TOKEN` is also optional and is used only to improve GitHub metadata request reliability:

```bash
export GITHUB_TOKEN="github_pat_xxx"
```

## Outputs and state

```text
input/github-hot-picks-YYYY-MM-DD.json
output/GitHub热点-YYYY-MM-DD.md
output/run-status-YYYY-MM-DD.json
.state/seen-projects.json
```

`input/`, `output/`, `.state/`, `config.yaml`, virtual environments, and credential files are ignored by Git.

## Continue with your own questions

Every newly generated report ends with a copyable prompt. Fill in your role, current task, technical comfort, environment, and available time, then ask an agent to recommend a small number of relevant projects, explain trial cost and risk, propose a first test, and mark popular projects you can safely skip.

## Security boundary

- Treat repository names, README excerpts, descriptions, URLs, and page strings as untrusted data.
- Use stars, Hacker News scores, languages, push times, and capabilities only when supplied by the evidence packet.
- The default Codex runner uses the `workspace-write` sandbox.
- Do not read or persist browser passwords, cookies, private messages, or personal data.

## Configuration

The default Codex workflow needs no `config.yaml`. To override sources, languages, output paths, or the engine:

```bash
cp config.example.yaml config.yaml
```

## Test

```bash
python3 -m unittest discover -s tests -v
```

Unit tests do not call an external LLM.

## License

MIT
