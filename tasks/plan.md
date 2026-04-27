# Implementation Plan: Marketia V2

**Branch:** `marketia-v2` — incremental PRs merged into `main` behind feature toggles where needed.
**Target API:** Gemini Deep Research, April-2026 release (`deep-research-preview-04-2026` / `deep-research-max-preview-04-2026`).
**Authoritative sources:**
- Docs page: <https://ai.google.dev/gemini-api/docs/deep-research>
- Cookbook notebook: `google-gemini/cookbook/quickstarts/Get_started_Deep_Research.ipynb`

All API facts below were quoted from those sources during planning. Treat any deviation from them as a bug to verify, not a given.

---

## Overview

Marketia today wraps a single Deep Research call with a polling Streamlit UI and markdown persistence. V2 upgrades to the current API surface and adds the BI-differentiating capabilities the notebook explicitly demonstrates: streaming, collaborative planning, multimodal input, private-data via `file_search`, and cheap synchronous follow-ups via `previous_interaction_id`. The scope is additive — every existing user flow keeps working — but the cost profile and UX change materially.

## Architecture Decisions

1. **Keep the single `marketia/core.py` module** as the I/O boundary. V2 extends it with `run_research_streaming`, `run_followup`, `run_plan`, `extract_report_outputs` — no new package.
2. **Frontmatter stores `interaction_id`** for each saved report so follow-ups can use `previous_interaction_id` instead of re-pasting the report. Old reports without the id fall back to the legacy paste-context path — no migration script.
3. **Streaming is the default UX for the Streamlit tab**; the CLI stays polling (stdout-friendly) and optionally streams thought summaries.
4. **Follow-ups use a standard Gemini model** (`gemini-3.1-pro-preview`, per the notebook) with `previous_interaction_id`. They are synchronous, single-shot, and cheap. Full Deep Research follow-up is available as an explicit "deep follow-up" mode.
5. **Cost model replaced, not extended.** Drop the tiered per-token estimator and replace with per-task ranges keyed off agent choice, labeled as estimates. Token counts are still displayed from `usage`.
6. **No rename of existing public surface.** CLI entry points and Streamlit tab names are preserved; features are added as new tabs / flags.
7. **`agent=` vs `model=` split (source-verified).** Deep Research calls use `agent=<model-id>` (e.g. `agent="deep-research-preview-04-2026"`). Standard-Gemini follow-ups use `model="gemini-3.1-pro-preview"`. These are not interchangeable. All wrapper functions (`run_research`, `run_research_streaming`) use `agent=`; `run_followup` uses `model=`. Never pass both in one call.
8. **`agent_config` always includes `"type": "deep-research"`.** Centralise a base dict in Task 1 and merge caller overrides into it. Every `create()` call to the Deep Research agent must include this key per the official docs and notebook.

## Dependency Graph

```
Model IDs + agent_config (core.py)           ← Phase 1 foundation
    │
    ├── Baseline tests (reports.py, core.py pure)   ← Phase 1 safety net
    │
    ├── Frontmatter stores interaction_id
    │       │
    │       └── Synchronous follow-ups (previous_interaction_id)
    │
    ├── Streaming (thinking_summaries + deltas)
    │       │
    │       └── Collaborative planning (plan/refine/execute states)
    │
    ├── Multimodal input (text+document+image parts)
    │       │
    │       └── Image output rendering (charts visible in reports)
    │
    └── Tools config
            ├── file_search (private corpora)
            └── mcp_server (external systems)
```

Bottom-up implementation order.

## Task List

### Phase 1 — Foundation

- [ ] **Task 1:** Upgrade model IDs and expose agent-speed toggle
- [ ] **Task 2:** Baseline unit tests for pure-Python helpers

### Checkpoint A — Foundation
- [ ] `pytest` runs green (tests from Task 2)
- [ ] `ruff check .` and `ruff format --check .` clean
- [ ] `streamlit run streamlit_app.py` boots, new agent dropdown visible, submitting a short prompt returns a report on the new model
- [ ] Human review: confirm the `deep-research-preview-04-2026` ID is accepted by the user's API key (one live smoke test)

### Phase 2 — Cost-Cutting Wins

- [ ] **Task 3:** Persist `interaction_id` and `agent` in frontmatter
- [ ] **Task 4:** Cheap synchronous follow-ups via `previous_interaction_id`

### Checkpoint B — Follow-ups
- [ ] Follow-up on a freshly-created V2 report completes in <30s and costs <$0.10 (verify from `usage`)
- [ ] Follow-up on a legacy V1 report (no `interaction_id` in frontmatter) still works via the paste-context fallback
- [ ] Follow-up tab shows which mode ran (sync / deep) and the actual cost
- [ ] Human review of one sample output quality

### Phase 3 — Live UX

- [ ] **Task 5:** Streaming with thought summaries in the Streamlit tab
- [ ] **Task 6:** Collaborative planning flow (plan → refine → execute)

### Checkpoint C — Live UX
- [ ] Running a new research task shows incremental thoughts and streamed text (no blank wait)
- [ ] Collaborative-plan checkbox produces a plan, accepts refinement, and executes only after explicit approval
- [ ] Cancellation path: closing the browser tab during stream does not orphan the interaction (reconnect via `last_event_id`)
- [ ] Human review

### Phase 4 — BI Differentiation

- [ ] **Task 7:** Multimodal input (PDF and image attachments)
- [ ] **Task 8:** Render image outputs (charts) in reports
- [ ] **Task 9:** `file_search` private-corpus support
- [ ] **Task 10:** MCP server tool support

### Checkpoint D — BI Differentiation
- [ ] Attaching a PDF to a prompt yields a report that references it by content
- [ ] Asking for "charts comparing X" saves a markdown file that renders inline images when opened in Obsidian
- [ ] A `file_search` store configured in settings is used by a research task and cited in output
- [ ] A dummy MCP server is queried during a task (integration test with a public MCP echo server, or a manual walkthrough)

### Phase 5 — Polish & Ship

- [ ] **Task 11:** Replace per-token cost tiers with per-task cost-range estimator
- [ ] **Task 12:** Update README, add MIGRATION.md, tag `v2.0.0`

### Checkpoint E — Ship
- [ ] All acceptance criteria above met
- [ ] CI (GitHub Actions) green
- [ ] `pip install -e .` works from a clean venv
- [ ] README reflects V2 capabilities; MIGRATION.md explains follow-up mode change and model-ID update

---

## Tasks — Detail

### Task 1: Upgrade model IDs and expose agent-speed toggle

**Description:** Replace the deprecated `deep-research-pro-preview-12-2025` constant with the two current agents and surface the choice in both the Streamlit sidebar and the CLI. This is the smallest change that makes Marketia run on the current API.

**Acceptance criteria:**
- [ ] `marketia/core.py` defines `RESEARCH_MODEL_FAST = "deep-research-preview-04-2026"` and `RESEARCH_MODEL_MAX = "deep-research-max-preview-04-2026"`; old `RESEARCH_MODEL` kept as an alias to `RESEARCH_MODEL_FAST` for one release with a `DeprecationWarning`.
- [ ] Deep Research calls use `agent=<model-id>` (not `model=`); any existing `model=` kwarg on `run_research` is renamed to `agent` in this task.
- [ ] A base `_AGENT_CONFIG_BASE = {"type": "deep-research"}` dict is defined and merged into every `agent_config` passed to `client.interactions.create(...)`.
- [ ] Polling loop handles `status in ("completed", "failed", "in_progress")` explicitly; any other status value logs a warning and terminates (guards against silent hangs on new states).
- [ ] Streamlit sidebar: a radio "Speed vs. Depth" selector that maps to the two model IDs; default is Fast. Selection is persisted in `st.session_state`.
- [ ] CLI: `--mode {fast,max}` flag (default `fast`) on `marketia-research`.
- [ ] README section "Model choice" updated.

**Verification:**
- [ ] `ruff check . && ruff format --check .` clean
- [ ] Live smoke test: one short prompt on each model returns `status == "completed"`
- [ ] Smoke test: confirm background calls succeed without explicit `store=True`; if they fail, add `store=True` to the wrapper and update this doc.
- [ ] Manual UI check: toggle visible, default Fast

**Dependencies:** None

**Files likely touched:** `marketia/core.py`, `marketia/ui/tabs.py`, `marketia/ui/app.py` (sidebar), `cli/research.py`, `README.md`

**Estimated scope:** S (3–4 files)

---

### Task 2: Baseline unit tests for pure-Python helpers

**Description:** Add `pytest` and a `tests/` tree covering the pure functions that have no API dependency: `slugify`, `generate_frontmatter`, `parse_frontmatter` round-trip, `update_frontmatter`, `save_research_report` name-collision handling, `append_followup_to_report`, `calculate_cost` boundary behaviour, and `Usage.from_interaction` against a hand-rolled fake. No Google API calls.

**Acceptance criteria:**
- [ ] `tests/` directory created with `test_reports.py` and `test_core.py`
- [ ] ≥15 assertions across both files; 100% coverage of `slugify`, `calculate_cost`, `Usage.from_interaction`, `parse_frontmatter`, `generate_frontmatter`
- [ ] `pytest` dep added to `[project.optional-dependencies].dev`
- [ ] GitHub Actions workflow runs `pytest` alongside ruff

**Verification:**
- [ ] `pip install -e ".[dev]" && pytest` exits 0
- [ ] `pytest -q` prints ≥15 passing
- [ ] CI workflow green on a pushed branch

**Dependencies:** None (can run in parallel with Task 1)

**Files likely touched:** `tests/__init__.py`, `tests/test_reports.py`, `tests/test_core.py`, `pyproject.toml`, `.github/workflows/ci.yml`

**Estimated scope:** M (4–5 files)

---

### Task 3: Persist `interaction_id` and `agent` in frontmatter

**Description:** Data-only change that makes follow-ups upgradeable. Extend `generate_frontmatter` and `save_research_report` with two new fields: `interaction_id` (string) and `agent` (string). Plumb them from the interaction object at save time. No behaviour change yet.

**Acceptance criteria:**
- [ ] New frontmatter fields present on every freshly saved report
- [ ] `save_research_report(...)` signature extended with `interaction_id: str = ""` and `agent: str = ""`
- [ ] Streamlit `new_research_tab` and `cli/research.py` pass the values
- [ ] `parse_frontmatter` round-trip test for the new fields
- [ ] Legacy reports (no new fields) read back cleanly with `frontmatter.get("interaction_id", "")`

**Verification:**
- [ ] Unit test: new fields appear with correct values after save
- [ ] Manual: run a research task, open the saved .md, confirm frontmatter block
- [ ] Load a pre-V2 sample report — frontmatter parses without error

**Dependencies:** Task 1 (agent string comes from the toggle)

**Files likely touched:** `marketia/reports.py`, `marketia/ui/tabs.py`, `cli/research.py`, `tests/test_reports.py`

**Estimated scope:** S (3–4 files)

---

### Task 4: Cheap synchronous follow-ups via `previous_interaction_id`

**Description:** Add `run_followup(client, question, previous_interaction_id, model)` in `core.py` that calls `client.interactions.create(input=question, model=<standard-gemini>, previous_interaction_id=<id>)` — synchronous, no `background=True`, no `agent=`, no poll. This is the direct-model path (not the agent path); `model=` is correct here. Wire the Streamlit follow-up tab and `cli/followup.py` to prefer this path when the parent report has an `interaction_id` in frontmatter. Fall back to the legacy paste-context deep-research path otherwise, and expose a "Deep follow-up" checkbox that forces the expensive path regardless.

**Acceptance criteria:**
- [ ] `run_followup` helper exists and returns an `Interaction` or equivalent object without polling
- [ ] `FOLLOWUP_MODEL = "gemini-3.1-pro-preview"` constant in `core.py` (source: notebook)
- [ ] `run_followup` passes `model=FOLLOWUP_MODEL` and `previous_interaction_id=<id>`; it does **not** pass `agent=` or `background=True`
- [ ] Follow-up tab auto-detects mode from frontmatter and shows a badge ("Sync · $0.02" vs. "Deep · $1–3")
- [ ] "Deep follow-up" checkbox forces the legacy path
- [ ] CLI `marketia-followup` grows `--deep` flag; default is sync when id is present
- [ ] `append_followup_to_report` records which mode was used (new frontmatter field `last_followup_mode` or per-section annotation)

**Verification:**
- [ ] Sync follow-up on a V2 report returns in <30 s and reports <$0.10 cost
- [ ] Legacy V1 report triggers paste-context path and still works
- [ ] Deep follow-up checkbox forces the deep path even on V2 reports
- [ ] Unit test: `run_followup` is not called if id is missing; deep path is not called if id is present and flag is off

**Dependencies:** Task 3

**Files likely touched:** `marketia/core.py`, `marketia/reports.py`, `marketia/ui/tabs.py`, `cli/followup.py`, `tests/test_core.py`

**Estimated scope:** M (4–5 files)

---

### Task 5: Streaming with thought summaries

**Description:** Add `run_research_streaming(client, prompt, *, agent, agent_config, on_event)` that iterates `client.interactions.create(..., agent=agent, stream=True, background=True)` and yields tuples of `(event_type, delta_type, payload)`. The Streamlit tab replaces the poll-loop status label with a live-updating "thoughts" panel (collapsed by default, showing the most recent 3 summaries) and a streaming-text placeholder that fills as `content.delta` of type `text` arrives. Handle the documented ~600 s disconnect by reconnecting with `last_event_id`. CLI streams thought summaries to stderr behind `--live`.

**Streaming event attribute reference (source: notebook — do not guess):**
- `chunk.event_type` → `"interaction.start" | "content.delta" | "interaction.complete" | "error"`
- `chunk.event_id` → use as `last_event_id` on reconnect
- `chunk.delta.type` → `"text" | "thought_summary" | "image"`
- `chunk.delta.text` → text body (when `delta.type == "text"`)
- `chunk.delta.content.text` → thought-summary text (nested under `content`, **not** `chunk.delta.text`)
- `chunk.delta.data` → base64-encoded image bytes
- `chunk.interaction.id` → interaction ID, emitted on `interaction.start`

**Acceptance criteria:**
- [ ] `run_research_streaming` yields events in order and terminates on `interaction.complete`
- [ ] `agent_config` merges `{"type": "deep-research", "thinking_summaries": "auto"}` when streaming
- [ ] Streamlit tab shows a live thoughts panel and streaming text; no poll-status label
- [ ] Thought-summary text read from `chunk.delta.content.text` (not `chunk.delta.text`)
- [ ] Reconnect-on-disconnect implemented with `last_event_id` (`chunk.event_id` persisted across reconnects)
- [ ] `extract_report_outputs` also reconstructs text from accumulated deltas when `interaction.outputs` is empty mid-stream
- [ ] Fallback to `run_research` (poll) on SDK errors — logged, not crashed

**Verification:**
- [ ] Streamlit manual: start a task, watch thoughts stream, verify no blank spinner period >5s
- [ ] Kill network for 30 s mid-stream — stream resumes after reconnect
- [ ] Unit test with a fake stream iterator covering normal flow and mid-stream disconnect

**Dependencies:** Task 1

**Files likely touched:** `marketia/core.py`, `marketia/ui/tabs.py`, `cli/research.py`, `tests/test_core.py`

**Estimated scope:** M (3–4 files)

---

### Task 6: Collaborative planning flow

**Description:** Add a "Review plan first" checkbox to the new-research tab. When checked: submit with `agent_config={"type": "deep-research", "collaborative_planning": True}`, render the returned plan, offer a "Refine plan" text box (posts a follow-up with `previous_interaction_id` and `collaborative_planning: True`), and an "Approve & run" button that posts an approval message with `collaborative_planning: False`. All state lives in `st.session_state` keyed by the initial interaction id so browser refreshes don't lose it.

**Acceptance criteria:**
- [ ] Checkbox present, default off
- [ ] Three session-state phases: `awaiting_plan`, `plan_ready`, `executing`, `done`
- [ ] Each refinement round uses `previous_interaction_id` correctly
- [ ] Approval round sets `collaborative_planning: False` and executes full research
- [ ] The final saved report's frontmatter includes `plan_rounds: <n>` for auditability
- [ ] CLI gets a `--plan` flag that opens a `$EDITOR` for plan review (stretch; may skip)

**Verification:**
- [ ] Manual: check the box, submit, receive a plan, refine twice, approve, confirm final report cites the refined scope
- [ ] Unit test on the state machine: wrong transitions are rejected
- [ ] Cost check: plan rounds should be cheap (<$0.50 each) per docs

**Dependencies:** Tasks 1, 5 (streaming is how the plan is shown)

**Files likely touched:** `marketia/core.py`, `marketia/ui/tabs.py`, `tests/test_core.py`

**Estimated scope:** M (2–3 files, mostly UI state)

---

### Task 7: Multimodal input — PDFs and images

**Description:** Switch `run_research` / `run_research_streaming` to accept `input: str | list[dict]`. The Streamlit tab gets a multi-file uploader accepting `.pdf` / `.png` / `.jpg`; each file becomes a part dict. MVP input shapes (both demonstrated in the notebook; `client.files.upload()` is **not** shown in source and deferred to V2.1):
- Public URL: `{"type": "document", "uri": "https://...", "mime_type": "application/pdf"}` or `{"type": "image", "uri": "https://..."}`
- Inline base64: `{"type": "image", "data": <bytes>}` (verify in smoke test — PDF base64 inline not demonstrated in notebook; may need public-URI-only for PDFs)

CLI `marketia-research` grows `--attach PATH` (repeatable).

**Acceptance criteria:**
- [ ] `run_research*` accept list-of-parts input and pass it through unchanged
- [ ] Streamlit uploader accepts `.pdf`, `.png`, `.jpg`; visible file chips with remove buttons
- [ ] Images are inlined as base64 (`{"type": "image", "data": <bytes>}`); PDFs use public URI path first (smoke test inline base64 PDF and document here — if it works, use it; otherwise require a hosted URL)
- [ ] `client.files.upload(...)` is **not** used in V2.0; Files API integration is V2.1
- [ ] CLI `--attach ./file.pdf` repeatable; `mime_type` inferred from extension
- [ ] Frontmatter records attachment basenames (not full paths) for privacy

**Verification:**
- [ ] Manual: attach a publicly-hosted PDF, run a prompt that asks for a summary, confirm report cites document content
- [ ] Unit test: input normalizer converts `str`, `list[str]`, and `list[dict]` shapes correctly
- [ ] Oversize attachment rejected with a clear error message

**Dependencies:** Task 1

**Files likely touched:** `marketia/core.py`, `marketia/ui/tabs.py`, `cli/research.py`, `tests/test_core.py`

**Estimated scope:** M (3–4 files)

---

### Task 8: Render image outputs (charts) in reports

**Description:** Replace `extract_report_text` with `extract_report_outputs(interaction) -> tuple[str, list[ImageOut]]` that returns the text body and a list of `ImageOut(data: bytes, mime_type: str)` decoded from `output.type == "image"`. On save, write images to a sibling directory (`<report-slug>_assets/`) and inject `![](...)` markdown links at the position they were emitted. The Streamlit tab renders images inline with `st.image`.

**Acceptance criteria:**
- [ ] New extractor function; old `extract_report_text` kept as a thin wrapper returning only text (deprecation warning)
- [ ] Images are saved as PNG next to the markdown file and linked relatively
- [ ] Obsidian renders the saved markdown with inline images
- [ ] `visualization: "auto"` is set by default in `agent_config`; can be disabled via a sidebar toggle

**Verification:**
- [ ] Manual: request "charts showing market share changes", confirm images appear in the rendered Streamlit view and in the saved markdown when opened
- [ ] Unit test: extractor handles text-only, image-only, and interleaved outputs

**Dependencies:** Task 5 (streaming emits images too)

**Files likely touched:** `marketia/core.py`, `marketia/reports.py`, `marketia/ui/tabs.py`, `tests/test_core.py`

**Estimated scope:** S–M (3 files)

---

### Task 9: `file_search` private-corpus support

**Description:** Add a "Private data" section to the sidebar that accepts one or more file-search store names (`fileSearchStores/<name>`), persists them to a `.marketia/settings.json` under the user's home, and adds them to the `tools` list of the research call. A minimal "Upload to store" helper command (`marketia-store add ./file.pdf --store my-store`) is out of scope for V2.0 — document that stores are created out-of-band.

**Acceptance criteria:**
- [ ] `run_research*` accept `tools: list[dict] | None`
- [ ] Sidebar lets user configure store names; stored in `~/.marketia/settings.json`
- [ ] When configured, `tools=[{"type":"file_search", "file_search_store_names":[...]}]` is passed through
- [ ] Report frontmatter records `file_search_stores: [...]` used

**Verification:**
- [ ] Manual: with a pre-existing store, run a prompt that references internal content; report cites the store
- [ ] Settings roundtrip: add a store in UI, restart Streamlit, setting persists

**Dependencies:** Task 1

**Files likely touched:** `marketia/core.py`, `marketia/ui/app.py`, `marketia/ui/tabs.py`, `tests/test_core.py`

**Estimated scope:** M (3–4 files)

---

### Task 10: MCP server tool support

**Description:** Extend the tool-config path so an `mcp_server` entry can be added. Sidebar grows an "MCP Servers" collapsible with name / url / auth header / allowed-tools inputs. Multiple servers supported. Stored alongside file_search settings.

**Acceptance criteria:**
- [ ] `tools` list can contain mixed `file_search` and `mcp_server` entries
- [ ] Auth headers stored locally, never written to saved reports
- [ ] `allowed_tools` whitelist respected
- [ ] At least one documented example server in `examples/` or README

**Verification:**
- [ ] Integration walkthrough against a public echo/demo MCP server
- [ ] Auth header does not leak into saved frontmatter (grep verification in tests)

**Dependencies:** Task 9

**Files likely touched:** `marketia/core.py`, `marketia/ui/app.py`, `marketia/ui/tabs.py`, `README.md`

**Estimated scope:** S (3 files)

---

### Task 11: Per-task cost-range estimator

**Description:** Delete the tiered per-token `calculate_cost` and replace with `estimate_cost_range(agent, usage) -> tuple[float, float]` returning a low/high USD range keyed off `agent`: Fast → $1–3, Max → $3–7 (per current docs, labeled as estimates). UI displays the range alongside actual token counts. Follow-up (sync) uses a standard pay-as-you-go formula off its `usage` object.

**Acceptance criteria:**
- [ ] New estimator function, old one deleted (not kept)
- [ ] Streamlit metrics row shows range: `$1.00 – $3.00 (est.)` plus token counts
- [ ] Frontmatter records `estimated_cost_range: "1.00-3.00"` instead of a single number
- [ ] Docstring cites the docs URL and the "subject to change" caveat

**Verification:**
- [ ] Unit test: Fast → (1.0, 3.0); Max → (3.0, 7.0)
- [ ] Manual UI check

**Dependencies:** Task 1

**Files likely touched:** `marketia/core.py`, `marketia/reports.py`, `marketia/ui/tabs.py`, `cli/research.py`, `tests/test_core.py`

**Estimated scope:** S (4 files, mostly small edits)

---

### Task 12: Docs and release

**Description:** Update `README.md` for V2, add `MIGRATION.md` explaining the model-ID change, new follow-up mode, and new frontmatter fields. Bump version to `0.2.0` → `2.0.0` in `pyproject.toml`. Tag release.

**Acceptance criteria:**
- [ ] `README.md` reflects current model IDs, new features (streaming, planning, multimodal, file_search, MCP), and links to the docs
- [ ] `MIGRATION.md` covers: model ID change, new frontmatter fields, sync vs. deep follow-ups, cost-range change
- [ ] `pyproject.toml` version bumped
- [ ] `CHANGELOG.md` added with V2 highlights

**Verification:**
- [ ] Fresh clone + `pip install -e ".[dev]"` + `pytest` + `streamlit run streamlit_app.py` walks through the README without dead ends
- [ ] `git tag v2.0.0 && git push --tags` (only after human approval)

**Dependencies:** All prior

**Files likely touched:** `README.md`, `MIGRATION.md`, `CHANGELOG.md`, `pyproject.toml`

**Estimated scope:** S

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `deep-research-pro-preview-12-2025` still works and current docs page listed new IDs prematurely | Med | Task 1 live smoke test before merge; keep old constant as a fallback alias for one release. |
| `gemini-3.1-pro-preview` not yet GA for the user's API key | Med | Make `FOLLOWUP_MODEL` configurable via env var; document fallback to `gemini-2.5-pro`. |
| Streaming reconnect via `last_event_id` has SDK-level quirks | Med | Wrap in a retry loop; fall back to polling on three consecutive reconnect failures. Log loudly. |
| Files API upload for multimodal adds significant scope (auth, lifecycle) | Med | V2.0 accepts public URIs and base64-inline only; Files-API upload lands in V2.1. |
| Cost-range estimates diverge materially from actual billing once Max mode runs | Low | Label as estimate everywhere; always show real token counts too. |
| Collaborative-planning state in `st.session_state` gets wedged across reruns | Med | Key state by initial `interaction.id`; add a "Reset plan state" debug button. |
| Streamlit Community Cloud's default timeout may truncate long Deep-Research streams | Low | Document self-host for >30 min jobs; default to Fast mode in the deployed demo. Also: server-side max runtime is 60 min (documented); tasks that exceed it get `status == "failed"` — surface this in the UI. |
| Docs say `background=True` requires `store=True`; notebook never sets it | Med | Task 1 smoke test verifies whether it's required (may be auto-set by SDK). If background calls fail without it, add `store=True` to the wrapper and update this doc. |
| `agent=` / `model=` confusion in existing `core.py` | High | Task 1 reads the current code, migrates Deep Research calls to `agent=`, and keeps `model=` only on the follow-up path. Never pass both in one call. |
| PDF base64 inline on Deep Research — not demonstrated in source, only URIs shown for documents | Low | Task 7 smoke test; fall back to public-URI-only for PDFs if inline is rejected. |

## Open Questions

1. **Live-smoke ownership.** Who runs the one-off API call in Task 1's Checkpoint A to confirm the April-2026 model IDs are accepted by the user's key? Assume the maintainer; flag as blocker if not.
2. **Follow-up model default.** Stick with `gemini-3.1-pro-preview` (notebook example) or make it configurable from the start? Recommendation: configurable with `gemini-3.1-pro-preview` as default.
3. **Obsidian image rendering path.** The sibling `_assets/` directory is standard, but Obsidian users often prefer a vault-wide `attachments/` folder. Accept a config override in Task 8?
4. **MCP auth storage.** Store Bearer tokens in `~/.marketia/settings.json` plain-text, or require `keyring`? Recommendation: plain-text with a `0600` permission check in V2.0; keyring in V2.1.
5. **Deprecation window for the old follow-up behaviour.** Keep the paste-context path indefinitely for pre-V2 reports, or remove after two releases? Recommendation: indefinitely — it's a fallback, not a feature.
6. **`agent=` in existing `core.py`.** Does the current code use `model=` (broken) or `agent=` (correct) for the Deep Research `create()` call? Answer this on first read of `core.py` before writing any Task 1 code — it determines whether Task 1 is a rename or a bug-fix.
7. **`store=True` requirement.** Does a `background=True` call succeed without `store=True` on your API key? Verify in the Task 1 smoke test; update the wrapper and this doc if needed.
8. **PDF inline base64 on Deep Research.** The notebook only demonstrates PDF via public URI. Are inline-base64 PDFs accepted by the API? Verify in Task 7 smoke test; restrict MVP to public URIs for PDFs if rejected.

## Parallelization

Safe to parallelize:
- Task 1 and Task 2 (no shared files)
- Task 7, Task 9, Task 10 (different subsystems, once Task 1 is merged)
- Task 12 can be drafted in parallel with Task 11

Must be sequential:
- Task 3 → Task 4 (frontmatter change before consumers)
- Task 5 → Task 6 (planning UX consumes the streaming plumbing)
- Task 7 → Task 8 (multimodal input shape before output-image handling is meaningful)
