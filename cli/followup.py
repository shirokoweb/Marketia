"""CLI entry point: append a follow-up question to an existing research report.

Usage:
    marketia-followup ./report.md "Compare the pricing models"
    marketia-followup ./report.md --question-file ./question.txt
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from marketia.core import (
    RESEARCH_MODEL_FAST,
    MissingAPIKeyError,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    configure_logging,
    extract_report_text,
    load_client,
    run_followup,
    run_research,
)
from marketia.reports import append_followup_to_report, parse_frontmatter


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marketia-followup",
        description="Append a follow-up to an existing Marketia research report.",
    )
    parser.add_argument(
        "report_path",
        type=Path,
        help="Path to the parent report markdown file.",
    )
    question_group = parser.add_mutually_exclusive_group()
    question_group.add_argument(
        "question",
        nargs="?",
        help="Follow-up question. If omitted, you will be prompted on stdin.",
    )
    question_group.add_argument(
        "--question-file",
        type=Path,
        help="Read the question from a file.",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help=(
            "Force a full Deep Research follow-up (~$1–3) even if the report has an "
            "interaction_id. Default: sync follow-up when possible."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def _read_question(args: argparse.Namespace) -> str:
    if args.question_file:
        return args.question_file.read_text(encoding="utf-8").strip()
    if args.question:
        return args.question
    print("Enter your follow-up question:", file=sys.stderr)
    return input("> ").strip()


def _on_status(phase: str, elapsed: float) -> None:
    print(f"\r[{int(elapsed):4d}s] status={phase}", end="", flush=True)


def main() -> int:
    """Entry point. Returns a POSIX exit code."""
    load_dotenv()
    args = _build_parser().parse_args()
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.report_path.is_file():
        print(f"Error: report not found: {args.report_path}", file=sys.stderr)
        return 2

    question = _read_question(args)
    if not question:
        print("Error: empty question.", file=sys.stderr)
        return 2

    try:
        client = load_client()
    except MissingAPIKeyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    try:
        context = args.report_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error reading report: {exc}", file=sys.stderr)
        return 1

    frontmatter, _ = parse_frontmatter(context)
    parent_id = frontmatter.get("interaction_id", "") if frontmatter else ""
    use_sync = bool(parent_id) and not args.deep

    print(f"Running follow-up for: {question[:120]}{'...' if len(question) > 120 else ''}")
    if use_sync:
        print(f"Mode: sync (previous_interaction_id={parent_id[:12]}...)")
        try:
            interaction = run_followup(client, question, parent_id)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        followup_mode = "sync"
    else:
        reason = "--deep flag" if args.deep else "no interaction_id in report"
        print(f"Mode: deep ({reason})")
        deep_prompt = (
            "CONTEXT:\n"
            "The following is a market research report generated previously:\n"
            f"===\n{context}\n===\n\n"
            "TASK:\n"
            "Based on the report above (and performing additional research if necessary), "
            "please answer this follow-up request:\n"
            f"{question}"
        )
        try:
            interaction = run_research(
                client, deep_prompt, agent=RESEARCH_MODEL_FAST, on_status=_on_status
            )
        except ResearchFailedError as exc:
            print(f"\n{exc}", file=sys.stderr)
            return 1
        except ResearchTimeoutError as exc:
            print(f"\n{exc}", file=sys.stderr)
            return 1
        print()
        followup_mode = "deep"

    followup_text = extract_report_text(interaction)
    if not followup_text:
        print("Follow-up completed but returned no text output.", file=sys.stderr)
        return 1

    usage = Usage.from_interaction(interaction)
    if usage:
        print(
            f"Metrics: input={usage.input_tokens:,} output={usage.output_tokens:,} "
            f"reasoning={usage.reasoning_tokens:,} cost=${usage.cost_usd:.4f}"
        )

    total_tokens = usage.total_tokens if usage else 0
    total_cost = usage.cost_usd if usage else 0.0

    try:
        count = append_followup_to_report(
            report_path=args.report_path,
            followup_content=followup_text,
            question=question,
            tokens_used=total_tokens,
            estimated_cost=total_cost,
            mode=followup_mode,
        )
    except OSError as exc:
        print(f"Error appending follow-up: {exc}", file=sys.stderr)
        return 1

    print(f"Appended as Follow-up #{count} to {args.report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
