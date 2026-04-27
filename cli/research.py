"""CLI entry point: run a new deep-research interaction and save the report.

Usage:
    marketia-research "Your market research prompt"
    marketia-research --prompt-file ./prompt.txt --output-dir ~/Research
    marketia-research "..." --title "My Title" --no-tags
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from marketia.core import (
    RESEARCH_MODEL_FAST,
    RESEARCH_MODEL_MAX,
    MissingAPIKeyError,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    configure_logging,
    estimate_cost_range,
    extract_report_text,
    file_to_attachment,
    load_client,
    run_research,
    run_research_streaming,
)
from marketia.reports import generate_title_and_tags, save_research_report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marketia-research",
        description=(
            "Run a new Gemini Deep Research task and save a markdown report with YAML frontmatter."
        ),
    )
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "prompt",
        nargs="?",
        help="Research prompt. If omitted, you will be prompted on stdin.",
    )
    prompt_group.add_argument(
        "--prompt-file",
        type=Path,
        help="Read the prompt from a file instead of the positional argument.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Directory to save the report (default: current directory).",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="",
        help="Report title. If omitted, an AI-generated title is produced.",
    )
    parser.add_argument(
        "--no-tags",
        action="store_true",
        help="Skip AI-generated tags (useful with --title).",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "max"],
        default="fast",
        help=(
            "Agent speed: 'fast' (~$1-3, default) or 'max' (~$3-7, more comprehensive). "
            "Maps to the April-2026 deep-research model variants."
        ),
    )
    parser.add_argument(
        "--attach",
        type=Path,
        action="append",
        dest="attachments",
        metavar="PATH",
        help="Attach a file (.pdf, .png, .jpg). Repeatable.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Stream thought summaries to stderr as they arrive (uses streaming API).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def _read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return args.prompt_file.read_text(encoding="utf-8").strip()
    if args.prompt:
        return args.prompt
    print("Enter your market research prompt:", file=sys.stderr)
    return input("> ").strip()


def _on_status(phase: str, elapsed: float) -> None:
    print(f"\r[{int(elapsed):4d}s] status={phase}", end="", flush=True)


def _run_streaming(
    client: object, prompt: str, agent: str, attachments: list[dict] | None = None
) -> tuple[str, object | None]:
    """Run research via streaming, printing thought summaries to stderr.

    Returns ``(report_text, interaction)`` or ``("", None)`` on error.
    """
    text_parts: list[str] = []
    interaction = None
    try:
        for event_type, delta_type, payload in run_research_streaming(
            client, prompt, agent=agent, attachments=attachments
        ):
            if event_type == "content.delta":
                if delta_type == "text":
                    text_parts.append(payload)
                elif delta_type == "thought_summary" and payload:
                    print(f"[thought] {payload[:120]}", file=sys.stderr)
            elif event_type == "interaction.status_update":
                print(f"\r[status] {payload}", end="", file=sys.stderr, flush=True)
            elif event_type == "interaction.complete":
                interaction = payload
                print(file=sys.stderr)
            elif event_type == "error":
                print(f"\nStream error: {payload}", file=sys.stderr)
                return "", None
    except Exception as exc:
        print(f"\nStreaming failed: {exc}", file=sys.stderr)
        return "", None
    return "".join(text_parts), interaction


def main() -> int:
    """Entry point. Returns a POSIX exit code."""
    load_dotenv()
    args = _build_parser().parse_args()
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    prompt = _read_prompt(args)
    if not prompt:
        print("Error: empty prompt.", file=sys.stderr)
        return 2

    try:
        client = load_client()
    except MissingAPIKeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    agent_model = RESEARCH_MODEL_MAX if args.mode == "max" else RESEARCH_MODEL_FAST
    print(f"Starting research for: {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
    print(f"Mode: {args.mode} ({agent_model})")

    attachments: list[dict] = []
    for path in args.attachments or []:
        try:
            attachments.append(file_to_attachment(path))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 2

    if args.live:
        report_text, interaction = _run_streaming(
            client, prompt, agent_model, attachments=attachments or None
        )
        if interaction is None:
            return 1
    else:
        try:
            interaction = run_research(
                client,
                prompt,
                agent=agent_model,
                on_status=_on_status,
                attachments=attachments or None,
            )
        except ResearchFailedError as exc:
            print(f"\n{exc}", file=sys.stderr)
            return 1
        except ResearchTimeoutError as exc:
            print(f"\n{exc}", file=sys.stderr)
            return 1
        print()  # close the status line
        report_text = extract_report_text(interaction)
    if not report_text:
        print("Research completed but returned no text output.", file=sys.stderr)
        return 1

    usage = Usage.from_interaction(interaction)
    lo, hi = estimate_cost_range(agent_model)
    if usage:
        print(
            f"Metrics: input={usage.input_tokens:,} output={usage.output_tokens:,} "
            f"reasoning={usage.reasoning_tokens:,} est. cost=${lo:.2f}–${hi:.2f}"
        )

    if args.title:
        title, tags = args.title, []
    elif args.no_tags:
        title, tags = (args.title or prompt[:60].strip()), []
    else:
        title, tags = generate_title_and_tags(prompt, report_text, client)

    total_tokens = usage.total_tokens if usage else 0
    cost_range_str = f"{lo:.2f}-{hi:.2f}"

    attachment_names = [p.name for p in (args.attachments or [])]
    try:
        saved_path = save_research_report(
            content=report_text,
            title=title,
            tags=tags,
            prompt_summary=prompt[:200],
            tokens_used=total_tokens,
            estimated_cost_range=cost_range_str,
            interaction_id=getattr(interaction, "id", ""),
            agent=agent_model,
            attachments=attachment_names or [],
            output_dir=args.output_dir,
        )
    except (OSError, NotADirectoryError) as exc:
        print(f"Error saving report: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {saved_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
