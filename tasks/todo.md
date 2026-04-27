# Marketia V2 — Todo

Short checklist version of `tasks/plan.md`. Tick as PRs land.

## Phase 1 — Foundation
- [x] **1.** Upgrade model IDs + agent-speed toggle (S) — `core.py`, `ui/*`, `cli/research.py`, `README.md`
- [x] **2.** Baseline unit tests for pure helpers (M) — `tests/`, `pyproject.toml`, `.github/workflows/ci.yml`

**Checkpoint A:** pytest + ruff green · Streamlit boots on new model · smoke tests on both model IDs (`deep-research-preview-04-2026` and `-max-`) · verify `store=True` not needed (or add it if needed) · confirm `agent=` parameter accepted (not `model=`)

## Phase 2 — Cost-Cutting Wins
- [x] **3.** Persist `interaction_id` + `agent` in frontmatter (S) — `reports.py`, `ui/tabs.py`, `cli/research.py`, tests
- [x] **4.** Synchronous follow-ups via `previous_interaction_id` (M) — `core.py`, `reports.py`, `ui/tabs.py`, `cli/followup.py`, tests

**Checkpoint B:** sync follow-up <30 s and <$0.10 · V1 reports still work · mode + cost visible

## Phase 3 — Live UX
- [ ] **5.** Streaming + thought summaries (M) — `core.py`, `ui/tabs.py`, `cli/research.py`, tests
- [ ] **6.** Collaborative planning flow (M) — `core.py`, `ui/tabs.py`, tests

**Checkpoint C:** thoughts stream live · plan → refine → approve flow works · reconnect on disconnect

## Phase 4 — BI Differentiation
- [ ] **7.** Multimodal input (PDF + image attachments) (M) — `core.py`, `ui/tabs.py`, `cli/research.py`, tests
- [ ] **8.** Render image outputs (charts) in reports (S–M) — `core.py`, `reports.py`, `ui/tabs.py`, tests
- [ ] **9.** `file_search` private-corpus support (M) — `core.py`, `ui/*`, tests
- [ ] **10.** MCP server tool support (S) — `core.py`, `ui/*`, `README.md`

**Checkpoint D:** PDF attachment cited · charts rendered inline · `file_search` store used · MCP walkthrough passes

## Phase 5 — Ship
- [ ] **11.** Per-task cost-range estimator (S) — `core.py`, `reports.py`, `ui/tabs.py`, `cli/research.py`, tests
- [ ] **12.** Docs + MIGRATION.md + `v2.0.0` tag (S) — `README.md`, `MIGRATION.md`, `CHANGELOG.md`, `pyproject.toml`

**Checkpoint E:** CI green · clean-venv install walks README end-to-end · tag pushed

---

## Parallel-safe pairs
- 1 ∥ 2
- 7 ∥ 9 ∥ 10 (after 1)
- 11 ∥ 12 (drafting)

## Sequential chains
- 3 → 4
- 5 → 6
- 7 → 8

## Open questions (need human input before starting affected tasks)
- Q1 · who runs Task 1 smoke test?
- Q2 · follow-up model default (`gemini-3.1-pro-preview` vs. configurable)?
- Q3 · image-assets directory layout for Obsidian?
- Q4 · MCP auth storage (plain vs. keyring)?
- Q5 · deprecation window for legacy paste-context follow-up?
- Q6 · does existing `core.py` use `model=` or `agent=` for Deep Research? (read before writing Task 1)
- Q7 · does background call succeed without `store=True`? (verify in Task 1 smoke test)
- Q8 · does Deep Research accept inline base64 PDFs? (verify in Task 7 smoke test; restrict to public URIs if not)
