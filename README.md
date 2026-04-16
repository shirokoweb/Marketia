# Marketia

**A Streamlit + CLI front-end for Google's Gemini Deep Research Agent.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Marketia wraps the `deep-research-pro-preview-12-2025` agent with a clean UI and CLI for running multi-step market research, capturing reports with YAML frontmatter (Obsidian-compatible), and iterating via follow-up questions that append to the parent report.

---

## What is Gemini Deep Research?

Deep Research is an **agentic** Gemini model: one call autonomously plans, runs multi-step web searches, reads pages, and synthesizes a detailed report. See Google's [Deep Research model page](https://ai.google.dev/gemini-api/docs/models). Unlike a single-shot LLM call, a research task runs in the background and must be polled to completion.

> **Cost & latency warning.** A single research call typically processes hundreds of thousands of tokens and takes **5–10+ minutes**. Pricing at the time of writing is $1–2 per 1M input tokens and $6–9 per 1M output tokens — expect **several USD per report**. Keep your prompts focused.

---

## Features

- **Streamlit UI** with two tabs: *New Research* and *Follow-up Analysis*.
- **CLI scripts** for scripted / batch usage: `marketia-research`, `marketia-followup`.
- **YAML frontmatter** on every report: title, tags, date, token usage, estimated cost, follow-up count.
- **Follow-up threading**: follow-ups append to the parent report as numbered sections; the UI lists reports sorted by recency.
- **Obsidian-ready**: point `OBSIDIAN_VAULT_PATH` at a vault folder and reports land there with filenames like `competitive-landscape_2026-04-16.md`.
- **Honest progress UX** — no fake progress bar; the UI reports the API's actual status (`pending`, `running`, `completed`) with live elapsed time.

---

## Prerequisites

- **Python 3.10+**
- A **Google AI Studio API key** — get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

## Installation

```bash
git clone https://github.com/shirokoweb/marketia.git
cd marketia
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
```

Alternative (editable install, pulls `[project.scripts]` entry points):

```bash
pip install -e .
```

---

## Usage

### Streamlit UI

```bash
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). Enter a research prompt in the **New Research** tab and submit. The task runs for several minutes; status updates live. When done, the report is saved to your configured output directory and rendered in-page.

To iterate, switch to **Follow-up Analysis**, pick the parent report, and ask a follow-up question — it's appended to the same file and the `follow_up_count` is bumped.

### CLI

After `pip install -e .`:

```bash
# New research report
marketia-research "European e-bike market 2025: size, growth, competitors, regulations"

# From a prompt file
marketia-research --prompt-file ./prompt.txt --output-dir ~/Obsidian/Research

# With an explicit title (skips AI title/tag generation)
marketia-research "Prompt..." --title "E-Bike Market EU 2025" --no-tags

# Follow-up on an existing report
marketia-followup ~/Obsidian/Research/e-bike-market-eu-2025_2026-04-16.md \
    "Compare pricing strategies between Cowboy and VanMoof"
```

Or without installing:

```bash
python -m cli.research "..."
python -m cli.followup path/to/report.md "..."
```

---

## Configuration

Environment variables (set in `.env` or your shell):

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Required. Your Google AI Studio API key. |
| `OBSIDIAN_VAULT_PATH` | Optional. Default output directory for saved reports. |

Model IDs are defined as constants in `marketia/core.py`:

- `RESEARCH_MODEL` — `deep-research-pro-preview-12-2025` (agentic research).
- `FLASH_MODEL` — `gemini-2.5-flash-lite` (cheap, fast; used for AI-generated titles/tags).

---

## Project layout

```
marketia/
├── marketia/
│   ├── core.py          # client, polling loop, cost, model IDs, logging
│   ├── reports.py       # frontmatter, save, append, list, title/tag generation
│   └── ui/
│       ├── app.py       # Streamlit page + sidebar
│       ├── styles.py    # inline CSS
│       └── tabs.py      # new-research and follow-up tab bodies
├── cli/
│   ├── research.py      # `marketia-research`
│   └── followup.py      # `marketia-followup`
├── streamlit_app.py     # `streamlit run` entry point
├── pyproject.toml       # packaging + ruff config
├── requirements.txt     # pinned direct deps
└── .env.example
```

---

## Development

```bash
pip install -e ".[dev]"
pre-commit install         # ruff + hygiene hooks on every commit
ruff check .               # lint
ruff format .              # format
python -c "import marketia.core, marketia.reports, marketia.ui.app"  # smoke test
```

GitHub Actions runs ruff and an import smoke test on every push / PR across Python 3.9–3.12. The CI **does not** call the deep-research model (it costs real money).

---

## Contributing

Issues and PRs welcome. Please run `ruff check` and `ruff format` before submitting.

---

## License

[MIT](LICENSE) © 2026 shirokoweb
