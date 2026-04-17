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
    MissingAPIKeyError,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    configure_logging,
    extract_report_text,
    load_client,
    run_research,
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

    print(f"Starting research for: {prompt[:120]}{'...' if len(prompt) > 120 else ''}")
    try:
        interaction = run_research(client, prompt, on_status=_on_status)
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
    if usage:
        print(
            f"Metrics: input={usage.input_tokens:,} output={usage.output_tokens:,} "
            f"reasoning={usage.reasoning_tokens:,} cost=${usage.cost_usd:.4f}"
        )

    if args.title:
        title, tags = args.title, []
    elif args.no_tags:
        title, tags = (args.title or prompt[:60].strip()), []
    else:
        title, tags = generate_title_and_tags(prompt, report_text, client)

    total_tokens = usage.total_tokens if usage else 0
    total_cost = usage.cost_usd if usage else 0.0

    try:
        saved_path = save_research_report(
            content=report_text,
            title=title,
            tags=tags,
            prompt_summary=prompt[:200],
            tokens_used=total_tokens,
            estimated_cost=total_cost,
            output_dir=args.output_dir,
        )
    except (OSError, NotADirectoryError) as exc:
        print(f"Error saving report: {exc}", file=sys.stderr)
        return 1

    print(f"Saved: {saved_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
