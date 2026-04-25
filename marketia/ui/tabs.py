"""Streamlit tab bodies: new research and follow-up analysis."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import streamlit as st

from marketia.core import (
    RESEARCH_MODEL_FAST,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    extract_report_text,
    run_research,
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


def new_research_tab(client: Any, output_dir: str, agent: str = RESEARCH_MODEL_FAST) -> None:
    """Render the 'New Research' tab."""
    st.subheader("Launch New Deep Research Task")

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

    if not st.button("Start Deep Research", type="primary"):
        return

    if not research_prompt:
        st.error("Please enter a prompt.")
        return

    with st.status("Submitting research task...", expanded=True) as status:
        try:
            interaction = run_research(
                client,
                research_prompt,
                agent=agent,
                on_status=_make_status_writer(status),
            )
        except ResearchFailedError as exc:
            status.update(label="Research failed", state="error")
            st.error(str(exc))
            return
        except ResearchTimeoutError as exc:
            status.update(label="Research timed out", state="error")
            st.error(str(exc))
            return

        status.update(label="Research completed", state="complete", expanded=False)

    full_report = extract_report_text(interaction)
    if not full_report:
        st.warning("Task completed but returned no text output.")
        return

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

    with st.expander("📄 View Parent Report"):
        context_content = Path(selected["filename"]).read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(context_content)
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

    if not st.button("Run Follow-up", type="primary"):
        return

    if not followup_query:
        st.error("Please enter a question.")
        return

    with st.status("Running follow-up research...", expanded=True) as status:
        try:
            context_content = Path(selected["filename"]).read_text(encoding="utf-8")
        except OSError as exc:
            status.update(label="Could not read parent report", state="error")
            st.error(str(exc))
            return

        final_prompt = (
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
                final_prompt,
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
