"""Streamlit tab bodies: new research and follow-up analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import streamlit as st

from marketia.core import (
    FOLLOWUP_MODEL,
    RESEARCH_MODEL_FAST,
    PlanSession,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    extract_report_text,
    run_followup,
    run_research,
    run_research_streaming,
)
from marketia.reports import (
    append_followup_to_report,
    generate_title_and_tags,
    list_reports,
    parse_frontmatter,
    save_research_report,
)

logger = logging.getLogger("marketia")

_PARENT_PREVIEW_MAX = 800


def _render_usage_metrics(usage: Usage | None) -> None:
    """Render a 4-column metrics row for a completed interaction."""
    if usage is None:
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Input Tokens", f"{usage.input_tokens:,}")
    c2.metric("Output Tokens", f"{usage.output_tokens:,}")
    c3.metric("Reasoning Tokens", f"{usage.reasoning_tokens:,}")
    c4.metric("Estimated Cost", f"${usage.cost_usd:.4f}")


def _make_status_writer(status: Any) -> Any:
    """Return an ``on_status`` callback that writes to ``st.status``."""
    last = {"phase": ""}

    def on_status(phase: str, elapsed: float) -> None:
        # Only re-render the phase line when the API-reported status changes,
        # but always update elapsed time as a label.
        status.update(label=f"Research in progress — {phase} ({int(elapsed)}s elapsed)")
        if phase != last["phase"]:
            status.write(f"Status: `{phase}`")
            last["phase"] = phase

    return on_status


def _stream_research(
    client: Any,
    prompt: str,
    agent: str,
    *,
    extra_agent_config: dict | None = None,
    previous_interaction_id: str = "",
) -> tuple[str, Any]:
    """Run streaming research, returning ``(full_text, interaction)``.

    Falls back to poll mode on streaming errors. Returns ``("", None)`` on failure
    (caller must check and surface the error).
    """
    thoughts_expander = st.expander("Thoughts (live)", expanded=False)
    thoughts_placeholder = thoughts_expander.empty()
    text_placeholder = st.empty()
    thoughts: list[str] = []
    full_text = ""
    interaction = None

    try:
        stream_cfg = extra_agent_config or {}
        for event_type, delta_type, payload in run_research_streaming(
            client,
            prompt,
            agent=agent,
            agent_config={**stream_cfg, "thinking_summaries": "auto"} if stream_cfg else None,
            previous_interaction_id=previous_interaction_id,
        ):
            if event_type == "content.delta":
                if delta_type == "text":
                    full_text += payload
                    text_placeholder.markdown(full_text)
                elif delta_type == "thought_summary" and payload:
                    thoughts.append(payload)
                    thoughts_placeholder.markdown(
                        "\n\n".join(f"_{t}_" for t in thoughts[-3:])
                    )
            elif event_type == "interaction.status_update":
                logger.debug("status_update: %s", payload)
            elif event_type == "interaction.complete":
                interaction = payload
            elif event_type == "error":
                st.error(f"Stream error: {payload}")
                return "", None
    except Exception as exc:
        logger.warning("Streaming failed (%s); falling back to poll mode", exc)
        status_box = st.status("Research in progress (poll mode)...", expanded=True)
        try:
            interaction = run_research(
                client,
                prompt,
                agent=agent,
                extra_agent_config=extra_agent_config,
                previous_interaction_id=previous_interaction_id,
                on_status=_make_status_writer(status_box),
            )
        except (ResearchFailedError, ResearchTimeoutError) as exc2:
            st.error(str(exc2))
            return "", None
        full_text = extract_report_text(interaction)

    text_placeholder.empty()
    return full_text, interaction


def _save_and_display(
    client: Any,
    full_report: str,
    interaction: Any,
    research_prompt: str,
    report_title: str,
    agent: str,
    output_dir: str,
    plan_rounds: int = 0,
) -> None:
    """Render metrics, the report body, and save the file."""
    usage = Usage.from_interaction(interaction)
    logger.debug("usage=%s", usage)
    st.divider()
    _render_usage_metrics(usage)
    st.success("Research Report Generated")
    st.markdown(full_report)

    if report_title.strip():
        final_title, final_tags = report_title.strip(), []
    else:
        with st.spinner("Generating title and tags..."):
            final_title, final_tags = generate_title_and_tags(
                prompt=research_prompt,
                report_content=full_report,
                api_client=client,
            )

    total_tokens = usage.total_tokens if usage else 0
    total_cost = usage.cost_usd if usage else 0.0

    try:
        saved_path = save_research_report(
            content=full_report,
            title=final_title,
            tags=final_tags,
            prompt_summary=research_prompt[:200],
            tokens_used=total_tokens,
            estimated_cost=total_cost,
            interaction_id=getattr(interaction, "id", ""),
            agent=agent,
            plan_rounds=plan_rounds,
            output_dir=output_dir,
        )
    except (OSError, NotADirectoryError) as exc:
        st.error(f"Could not save report: {exc}")
        return

    st.success(f"📁 Saved to `{saved_path}`")
    st.download_button(
        label="Download Report as MD",
        data=saved_path.read_text(encoding="utf-8"),
        file_name=saved_path.name,
        mime="text/markdown",
    )


def new_research_tab(client: Any, output_dir: str, agent: str = RESEARCH_MODEL_FAST) -> None:
    """Render the 'New Research' tab."""
    st.subheader("Launch New Deep Research Task")

    # ── Planning session in progress ────────────────────────────────────────
    plan_session: PlanSession | None = st.session_state.get("plan_session")
    if plan_session is not None and plan_session.phase == "plan_ready":
        st.info(
            f"**Plan ready** · {plan_session.rounds} refinement(s) so far · "
            f"Prompt: _{plan_session.prompt[:80]}_"
        )
        st.markdown("### Proposed Research Plan")
        st.markdown(plan_session.plan_text)
        st.divider()

        refinement = st.text_area(
            "Refine the plan (optional)",
            placeholder="e.g. 'Focus more on cost comparison, drop the history section.'",
        )
        col_refine, col_approve = st.columns(2)

        if col_refine.button("Refine Plan", disabled=not refinement):
            with st.spinner("Refining plan..."):
                plan_text, interaction = _stream_research(
                    client,
                    refinement,
                    agent,
                    extra_agent_config={"collaborative_planning": True},
                    previous_interaction_id=plan_session.interaction_id,
                )
            if interaction is None:
                return
            plan_session.advance(
                "plan_ready",
                interaction_id=getattr(interaction, "id", plan_session.interaction_id),
                plan_text=plan_text or plan_session.plan_text,
            )
            st.rerun()

        if col_approve.button("Approve & Run", type="primary"):
            with st.spinner("Approving plan and starting full research…"):
                full_report, interaction = _stream_research(
                    client,
                    "Approved. Please proceed with the full research.",
                    agent,
                    extra_agent_config={"collaborative_planning": False},
                    previous_interaction_id=plan_session.interaction_id,
                )
            if interaction is None:
                return
            plan_rounds = plan_session.rounds
            prompt = plan_session.prompt
            del st.session_state["plan_session"]
            if not full_report:
                st.warning("Task completed but returned no text output.")
                return
            _save_and_display(
                client, full_report, interaction, prompt, "", agent, output_dir,
                plan_rounds=plan_rounds,
            )
        return

    # ── Normal research form ─────────────────────────────────────────────────
    report_title = st.text_input(
        "Report Title (optional)",
        placeholder="Leave empty for AI-generated title, or enter your own...",
        help="A descriptive title for your research. If empty, one is generated from the prompt.",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        research_prompt = st.text_area(
            "Research Objectives & Prompt",
            height=250,
            placeholder=(
                "Describe your market research goal, key questions, and desired output format..."
            ),
        )
    with col2:
        uploaded = st.file_uploader("Or upload prompt file (.txt)", type=["txt"])
        if uploaded is not None:
            research_prompt = uploaded.read().decode("utf-8")
            st.success(f"Loaded: {uploaded.name}")

    review_plan = st.checkbox(
        "Review plan first (collaborative planning)",
        value=False,
        help=(
            "Ask the agent to produce a research plan before executing. "
            "You can refine the plan before approving full execution (~$0.10–0.50 per round)."
        ),
    )

    if not st.button("Start Deep Research", type="primary"):
        return

    if not research_prompt:
        st.error("Please enter a prompt.")
        return

    if review_plan:
        with st.spinner("Generating research plan…"):
            plan_text, interaction = _stream_research(
                client,
                research_prompt,
                agent,
                extra_agent_config={"collaborative_planning": True},
            )
        if interaction is None:
            return
        session = PlanSession(research_prompt)
        session.advance(
            "plan_ready",
            interaction_id=getattr(interaction, "id", ""),
            plan_text=plan_text,
        )
        st.session_state["plan_session"] = session
        st.rerun()
        return

    full_report, interaction = _stream_research(client, research_prompt, agent)
    if interaction is None:
        return
    if not full_report:
        st.warning("Task completed but returned no text output.")
        return
    _save_and_display(
        client, full_report, interaction, research_prompt, report_title, agent, output_dir
    )


def followup_tab(client: Any, output_dir: str, agent: str = RESEARCH_MODEL_FAST) -> None:
    """Render the 'Follow-up Analysis' tab."""
    st.subheader("Continue Research (Follow-up)")

    reports = list_reports(search_dir=output_dir)
    if not reports:
        st.info("No existing reports found. Run a new research task first.")
        return

    options = {r["display"]: r for r in reports}
    selected_display = st.selectbox(
        "Select Parent Report",
        options=list(options.keys()),
        help="Follow-up will be appended to this report",
    )
    selected = options[selected_display]

    # Read frontmatter to detect whether this is a V2 report with an interaction_id.
    context_content = Path(selected["filename"]).read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(context_content)
    parent_interaction_id = frontmatter.get("interaction_id", "") if frontmatter else ""

    with st.expander("📄 View Parent Report"):
        if frontmatter:
            st.caption(
                f"**Title:** {frontmatter.get('title', 'N/A')} | "
                f"**Follow-ups:** {frontmatter.get('follow_up_count', 0)} | "
                f"**Last updated:** {frontmatter.get('last_updated', 'N/A')}"
            )
        preview = body[:_PARENT_PREVIEW_MAX]
        if len(body) > _PARENT_PREVIEW_MAX:
            preview += "..."
        st.text(preview)

    followup_query = st.text_input(
        "Follow-up Question",
        placeholder="e.g., 'Compare the pricing models' or 'Deep dive on competitor X'",
    )

    force_deep = st.checkbox(
        "Deep follow-up (full Deep Research task, ~$1–3)",
        value=False,
        help="Forces a full Deep Research task even when a sync shortcut is available.",
    )

    use_sync = bool(parent_interaction_id) and not force_deep
    if use_sync:
        st.info(
            f"**Sync** · Uses `previous_interaction_id` via `{FOLLOWUP_MODEL}` · ~$0.01–0.05"
        )
    else:
        reason = (
            "no interaction ID in this report" if not parent_interaction_id else "deep mode forced"
        )
        st.info(f"**Deep** · Full Deep Research task (~$1–3) · {reason}")

    if not st.button("Run Follow-up", type="primary"):
        return

    if not followup_query:
        st.error("Please enter a question.")
        return

    if use_sync:
        with st.status("Running sync follow-up...", expanded=True) as status:
            try:
                interaction = run_followup(client, followup_query, parent_interaction_id)
                status.update(label="Follow-up complete", state="complete", expanded=False)
            except Exception as exc:
                status.update(label="Follow-up failed", state="error")
                st.error(str(exc))
                return
        followup_mode = "sync"
    else:
        with st.status("Running deep follow-up research...", expanded=True) as status:
            try:
                context_content = Path(selected["filename"]).read_text(encoding="utf-8")
            except OSError as exc:
                status.update(label="Could not read parent report", state="error")
                st.error(str(exc))
                return

            deep_prompt = (
                "CONTEXT:\n"
                "The following is a market research report generated previously:\n"
                f"===\n{context_content}\n===\n\n"
                "TASK:\n"
                "Based on the report above (and performing additional research if necessary), "
                "please answer this follow-up request:\n"
                f"{followup_query}"
            )
            try:
                interaction = run_research(
                    client,
                    deep_prompt,
                    agent=agent,
                    on_status=_make_status_writer(status),
                    poll_interval=3.0,
                )
            except ResearchFailedError as exc:
                status.update(label="Follow-up failed", state="error")
                st.error(str(exc))
                return
            except ResearchTimeoutError as exc:
                status.update(label="Follow-up timed out", state="error")
                st.error(str(exc))
                return
            status.update(label="Follow-up complete", state="complete", expanded=False)
        followup_mode = "deep"

    followup_out = extract_report_text(interaction)
    if not followup_out:
        st.warning("No output.")
        return

    usage = Usage.from_interaction(interaction)
    logger.debug("usage=%s", usage)
    st.divider()
    _render_usage_metrics(usage)
    st.markdown(followup_out)

    total_tokens = usage.total_tokens if usage else 0
    total_cost = usage.cost_usd if usage else 0.0

    try:
        follow_up_num = append_followup_to_report(
            report_path=selected["filename"],
            followup_content=followup_out,
            question=followup_query,
            tokens_used=total_tokens,
            estimated_cost=total_cost,
            mode=followup_mode,
        )
    except OSError as exc:
        st.error(f"Could not append follow-up: {exc}")
        return

    st.success(f"✅ Appended as Follow-up #{follow_up_num} to `{selected['filename']}`")
    st.download_button(
        "Download Updated Report",
        Path(selected["filename"]).read_text(encoding="utf-8"),
        file_name=selected["basename"],
    )
