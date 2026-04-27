# Migration Guide: V1 → V2.0.0

## Breaking changes

### Python version

V2.0.0 requires **Python 3.11+**. The Google GenAI SDK (≥1.73.0) dropped support for Python 3.9 and 3.10. Rebuild your virtualenv:

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
```

### SDK version

V2.0.0 requires `google-genai >= 1.73.0`. The `client.interactions` API used for Deep Research was added in this release. Earlier versions will raise `AttributeError: 'Client' object has no attribute 'interactions'`.

### Model IDs

The V1 model `deep-research-pro-preview-12-2025` has been replaced with two April 2026 variants:

| V1 | V2 |
|----|-----|
| `deep-research-pro-preview-12-2025` | `deep-research-preview-04-2026` (Fast) |
| — | `deep-research-max-preview-04-2026` (Max) |

The old `RESEARCH_MODEL` constant is still exported in V2.0.0 as an alias to `RESEARCH_MODEL_FAST` with a `DeprecationWarning`. It will be removed in V2.1.0.

**In code:** replace `RESEARCH_MODEL` with `RESEARCH_MODEL_FAST` or `RESEARCH_MODEL_MAX`.

### Follow-up model

V1 used `gemini-3.1-pro-preview` for sync follow-ups. This model rejects `previous_interaction_id` with a 400 error. V2 defaults to `gemini-2.5-flash` which accepts it cleanly.

Override with the `MARKETIA_FOLLOWUP_MODEL` environment variable if needed.

### Frontmatter field rename

| V1 field | V2 field | Notes |
|----------|----------|-------|
| `estimated_cost: $X.XXXX` | `estimated_cost_range: "X.XX-Y.YY"` | Now a string range (e.g. `"1.00-3.00"`) |

Existing V1 reports continue to parse correctly — the old field is ignored by `parse_frontmatter`.

### `calculate_cost` removed

The function `marketia.core.calculate_cost` has been deleted. Replace calls with `estimate_cost_range(agent)` which returns `(low_usd, high_usd)`.

## New features (additive, no action required)

- `--mode fast|max` CLI flag and sidebar radio for model selection
- `--live` CLI flag for streaming thought summaries
- `--attach PATH` CLI flag for multimodal input (PDF, PNG, JPEG)
- Collaborative planning (`--review-plan` checkbox in UI)
- Image output: charts saved to `<report>_assets/` and linked in markdown
- `file_search` private-corpus stores via sidebar / `~/.marketia/settings.json`
- MCP server tool support via sidebar
- Streaming reconnect on SSE disconnect (up to 3 attempts)
