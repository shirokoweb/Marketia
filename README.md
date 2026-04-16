# Marketia Research Hub 📊

Marketia is an advanced AI-powered market research tool designed to leverage Google's Gemini Deep Research Agent (`deep-research-pro-preview-12-2025`). It automates the process of gathering comprehensive market insights, generating detailed reports, and performing context-aware follow-up analysis.

## 🚀 Features

*   **Deep Research Automation**: Generates extensive market research reports from a single prompt.
*   **Contextual Follow-up**: Ask follow-up questions — they're appended to the original report for a complete research history.
*   **Obsidian Integration**: Reports include YAML frontmatter (title, date, tags, cost) for seamless use with Obsidian.
*   **AI-Generated Titles & Tags**: Automatic descriptive titles and tags using Gemini Flash.
*   **Custom Output Directory**: Save reports directly to your Obsidian vault or any folder.
*   **Cost & Usage Tracking**: Real-time estimation of costs based on token usage (Input, Output, Reasoning).
*   **Dual Interface**: Access via **Streamlit Web App** or **CLI scripts**.

## 🛠️ Prerequisites

*   Python 3.8+
*   A Google Cloud Project with the **Gemini API** enabled.
*   Access to the **Deep Research** model (`deep-research-pro-preview-12-2025`).
*   A valid `GOOGLE_API_KEY`.

## 📦 Installation

1.  **Clone the repository** or navigate to the project directory.

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Setup**:
    Create a `.env` file in the root directory:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    OBSIDIAN_VAULT_PATH=/path/to/your/obsidian/vault
    ```
    *Note: Both values can also be set in the Streamlit sidebar.*

## 🖥️ Usage

### Streamlit Web App (Recommended)

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser.

**Workflow:**
1.  **Sidebar**: Configure API key, model, and output directory.
2.  **New Research Tab**: Enter a prompt (or upload `.txt`), optionally set a title, click **Start Deep Research**.
3.  **Follow-up Tab**: Select a parent report and ask follow-up questions — they're appended to that report.

### Command Line Interface (CLI)

```bash
# Run a research task
python market_research.py "Analyze the competitive landscape of AI coding assistants"

# Run a follow-up question
python follow_up.py "Which competitors offer the best enterprise pricing?"
```

## 📂 Output Format

Reports are saved with Obsidian-compatible YAML frontmatter:

```yaml
---
title: AI Coding Assistants Market Analysis
type: research
date: 2025-12-18
tags:
  - ai
  - coding-assistants
  - market-analysis
tokens_used: 45230
estimated_cost: $0.2892
follow_up_count: 2
last_updated: 2025-12-18 15:30:00
---

# AI Coding Assistants Market Analysis

## Research Report
(content...)

---

## Follow-up 1: Pricing comparison
*Asked: 2025-12-18 15:00 | Tokens: 12,450 | Cost: $0.0823*

(follow-up content...)
```

**Filenames** use slugified titles: `ai-coding-assistants-market-analysis_2025-12-18.md`

## 🧩 Project Structure

| File | Description |
|------|-------------|
| `app.py` | Main Streamlit application |
| `market_research.py` | CLI script for research tasks |
| `follow_up.py` | CLI script for follow-up questions |
| `requirements.txt` | Python dependencies |
| `.env` | Environment variables (API key, vault path) |

## 📋 Dependencies

- `google-genai` — Google Generative AI SDK
- `streamlit` — Web application framework
- `python-dotenv` — Environment variable management
- `pyyaml` — YAML frontmatter generation
