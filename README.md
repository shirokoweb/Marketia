# Marketia

**A Streamlit + CLI front-end for Google's Gemini Deep Research Agent.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

Marketia wraps the April 2026 Gemini Deep Research agents with a clean UI and CLI for running multi-step market research, capturing reports with YAML frontmatter (Obsidian-compatible), and iterating via follow-up questions that append to the parent report.

---

## What is Gemini Deep Research?

Deep Research is an **agentic** Gemini model: one call autonomously plans, runs multi-step web searches, reads pages, and synthesizes a detailed report. See Google's [Deep Research docs](https://ai.google.dev/gemini-api/docs/deep-research). Unlike a single-shot LLM call, a research task runs in the background and must be polled (or streamed) to completion.

> **Cost & latency warning.** A single research call typically processes hundreds of thousands of tokens and takes **5–15+ minutes**. Per Google's published estimates (subject to change), expect **$1–3 per Fast report** and **$3–7 per Max report**. Keep your prompts focused.

---

## Features

- **Streamlit UI** with two tabs: *New Research* and *Follow-up Analysis*.
- **CLI scripts**: `marketia-research`, `marketia-followup`.
- **Model choice** — Fast (`deep-research-preview-04-2026`, ~$1–3) or Max (`deep-research-max-preview-04-2026`, ~$3–7). Toggle in UI sidebar or `--mode fast|max` on CLI.
- **Live streaming** — thought summaries and text stream live in the UI; `--live` flag on CLI streams to stderr.
- **Collaborative planning** — optional plan review round before full research executes.
- **Multimodal input** — attach PDFs, PNGs, JPEGs via UI upload or `--attach PATH` on CLI.
- **Image output** — chart images from responses are saved to `<report>_assets/` and linked inline in markdown.
- **Private corpus** — configure `fileSearchStores/<name>` in sidebar; stored in `~/.marketia/settings.json`.
- **MCP servers** — add custom tool endpoints via sidebar (auth headers are ephemeral, never persisted).
- **YAML frontmatter** on every report: title, tags, date, token counts, estimated cost range, follow-up count, agent, attachments, file-search stores used.
- **Follow-up threading**: sync follow-ups (~$0.01–0.05) reuse the parent interaction ID; deep follow-ups run a new research task with the parent as context.
- **Obsidian-ready**: point `OBSIDIAN_VAULT_PATH` at a vault folder and reports land there with filenames like `competitive-landscape_2026-04-26.md`.

---

## Prerequisites

- **Python 3.11+** (Google GenAI SDK requires 3.11; 3.9 is EOL and unsupported).
- `google-genai >= 1.73.0` — the `client.interactions` API was added in this release.
- A **Google AI Studio API key** — get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

---

## Installation

```bash
git clone https://github.com/shirokoweb/marketia.git
cd marketia
python3.11 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .

cp .env.example .env
# Edit .env and set GOOGLE_API_KEY
```

---

## Usage

### Streamlit UI

```bash
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). Enter a research prompt in the **New Research** tab and submit. The task streams live; when done, the report is saved to your configured output directory and rendered in-page.

To iterate, switch to **Follow-up Analysis**, pick the parent report, and ask a follow-up question — it's appended to the same file.

### CLI

```bash
# New research report (Fast model, default)
marketia-research "European e-bike market 2026: size, growth, competitors, regulations"

# Max model (more comprehensive, ~$3-7)
marketia-research "..." --mode max

# Stream thought summaries live
marketia-research "..." --live

# Attach a PDF and a chart image
marketia-research "Analyze the attached report" --attach ./report.pdf --attach ./chart.png

# From a prompt file with custom output dir
marketia-research --prompt-file ./prompt.txt --output-dir ~/Obsidian/Research

# With an explicit title (skips AI title/tag generation)
marketia-research "Prompt..." --title "E-Bike Market EU 2026" --no-tags

# Follow-up on an existing report (sync, cheap)
marketia-followup ~/Obsidian/Research/e-bike-market-eu-2026_2026-04-26.md \
    "Compare pricing strategies between Cowboy and VanMoof"

# Deep follow-up (full new research task)
marketia-followup ~/Obsidian/Research/report.md "..." --deep
```

---

## Model choice

| Flag | Model ID | Est. cost | Notes |
|------|----------|-----------|-------|
| `--mode fast` (default) | `deep-research-preview-04-2026` | $1–3 | Quick, broad |
| `--mode max` | `deep-research-max-preview-04-2026` | $3–7 | Deeper, more comprehensive |

Cost ranges are Google's published estimates (subject to change). Actual billing depends on token usage.

---

## Configuration

Environment variables (set in `.env` or your shell):

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Required. Your Google AI Studio API key. |
| `OBSIDIAN_VAULT_PATH` | Optional. Default output directory for saved reports. |
| `MARKETIA_FOLLOWUP_MODEL` | Optional. Override follow-up model (default: `gemini-2.5-flash`). |

Persistent settings are stored in `~/.marketia/settings.json` (file-search stores, MCP server URLs).

---

## Private corpus (file_search)

To query your own documents, create a Gemini file-search store out-of-band via the API, then add its name in the Streamlit sidebar under **Private Data**:

```
fileSearchStores/my-corpus
```

The store name is persisted to `~/.marketia/settings.json` and passed to every research call.

---

## MCP servers

Add MCP server endpoints in the Streamlit sidebar under **MCP Servers** as a JSON list:

```json
[{"name": "MyTool", "url": "https://mcp.example.com", "allowed_tools": ["search"]}]
```

Auth headers (e.g. `Bearer <token>`) are entered separately and are **never written to disk**.

---

## Project layout

```
marketia/
├── marketia/
│   ├── core.py          # client, polling/streaming loop, model IDs, ImageOut
│   ├── reports.py       # frontmatter, save, append, list, title/tag generation
│   ├── settings.py      # ~/.marketia/settings.json (file_search, MCP servers)
│   └── ui/
│       ├── app.py       # Streamlit page + sidebar
│       ├── styles.py    # inline CSS
│       └── tabs.py      # new-research and follow-up tab bodies
├── cli/
│   ├── research.py      # marketia-research
│   └── followup.py      # marketia-followup
├── streamlit_app.py     # `streamlit run` entry point
└── pyproject.toml
```

---

## Development

```bash
pip install -e ".[dev]"
ruff check .               # lint
ruff format .              # format
pytest tests/              # unit tests (no API calls)
```

CI runs ruff and the test suite on every push. The CI does not call the deep-research model (it costs real money).

---

## License

MIT. See [LICENSE](LICENSE).
