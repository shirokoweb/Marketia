"""Core primitives: client bootstrap, cost accounting, and the research polling loop.

All shared logic used by both the Streamlit UI and the CLI entry points lives here.
The module is intentionally free of Streamlit and argparse imports so it can be
reused in any context.
"""

from __future__ import annotations

import logging
import os
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from google import genai

logger = logging.getLogger("marketia")

# Model IDs — verified against https://ai.google.dev/gemini-api/docs/deep-research on 2026-04-24.
RESEARCH_MODEL_FAST = "deep-research-preview-04-2026"
RESEARCH_MODEL_MAX = "deep-research-max-preview-04-2026"
# gemini-3.1-pro-preview rejects previous_interaction_id; 2.5-flash accepts it and is cheap.
FOLLOWUP_MODEL = os.getenv("MARKETIA_FOLLOWUP_MODEL", "gemini-2.5-flash")
FLASH_MODEL = "gemini-2.5-flash-lite"

# base agent_config required by every Deep Research call (type key is mandatory per docs).
_AGENT_CONFIG_BASE: dict[str, Any] = {"type": "deep-research"}

# Pricing tiers for RESEARCH_MODEL (USD per 1M tokens).
_INPUT_RATE_LOW, _INPUT_RATE_HIGH = 1.00, 2.00
_OUTPUT_RATE_LOW, _OUTPUT_RATE_HIGH = 6.00, 9.00
_TIER_BOUNDARY_TOKENS = 200_000

# Known API statuses reported by `interaction.status`.
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"
_STATUS_IN_PROGRESS = "in_progress"


def __getattr__(name: str) -> Any:
    if name == "RESEARCH_MODEL":
        warnings.warn(
            "RESEARCH_MODEL is deprecated and will be removed in a future release. "
            "Use RESEARCH_MODEL_FAST or RESEARCH_MODEL_MAX instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return RESEARCH_MODEL_FAST
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class MissingAPIKeyError(RuntimeError):
    """Raised when no Google API key is available to bootstrap the client."""


class ResearchTimeoutError(TimeoutError):
    """Raised when a research interaction exceeds the configured timeout."""


class ResearchFailedError(RuntimeError):
    """Raised when the remote research interaction reports a failed status."""


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the ``marketia`` logger with a simple console handler.

    Safe to call multiple times; idempotent for the root ``marketia`` logger.
    """
    if logger.handlers:
        logger.setLevel(level)
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Return the estimated USD cost for a single research interaction.

    Uses the tiered pricing published for ``deep-research-pro-preview-12-2025``:
    input tier boundary at 200k tokens. Output cost includes reasoning tokens —
    callers must fold reasoning into ``output_tokens`` before calling.
    """
    if input_tokens <= _TIER_BOUNDARY_TOKENS:
        input_rate, output_rate = _INPUT_RATE_LOW, _OUTPUT_RATE_LOW
    else:
        input_rate, output_rate = _INPUT_RATE_HIGH, _OUTPUT_RATE_HIGH
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate


@dataclass(frozen=True)
class Usage:
    """Normalized usage snapshot for an interaction."""

    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    cost_usd: float

    @classmethod
    def from_interaction(cls, interaction: Any) -> Usage | None:
        """Build a ``Usage`` from a Google GenAI Interaction, or return None if absent."""
        usage = getattr(interaction, "usage", None)
        if not usage:
            return None
        input_tokens = int(getattr(usage, "total_input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "total_output_tokens", 0) or 0)
        reasoning_tokens = int(getattr(usage, "total_reasoning_tokens", 0) or 0)
        total_tokens = input_tokens + output_tokens + reasoning_tokens
        cost_usd = calculate_cost(input_tokens, output_tokens + reasoning_tokens)
        return cls(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )


def load_client(api_key: str | None = None) -> genai.Client:
    """Construct a ``genai.Client`` from ``api_key`` or the ``GOOGLE_API_KEY`` env var.

    Raises ``MissingAPIKeyError`` with a human-readable message if neither is set.
    """
    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "No Google API key provided. Set GOOGLE_API_KEY in your environment "
            "(.env) or pass one explicitly. Get a key at https://aistudio.google.com/apikey."
        )
    return genai.Client(api_key=key)


StatusCallback = Callable[[str, float], None]


def run_research(
    client: genai.Client,
    prompt: str,
    *,
    agent: str = RESEARCH_MODEL_FAST,
    on_status: StatusCallback | None = None,
    poll_interval: float = 5.0,
    timeout: float = 30 * 60,
) -> Any:
    """Submit a research interaction in background mode and poll to completion.

    Args:
        client: An authenticated ``genai.Client``.
        prompt: The research prompt to submit.
        agent: Agent model ID; defaults to the fast deep-research model.
        on_status: Optional callback invoked on each poll with
            ``(status_string, elapsed_seconds)``. Use for honest progress UX.
        poll_interval: Seconds between status polls.
        timeout: Seconds to wait before raising ``ResearchTimeoutError``.

    Returns:
        The completed interaction object from the Google GenAI SDK.

    Raises:
        ResearchFailedError: If the API reports a failed status.
        ResearchTimeoutError: If the interaction exceeds ``timeout`` seconds.
    """
    interaction = client.interactions.create(agent=agent, input=prompt, background=True)
    logger.info("Research interaction started: id=%s agent=%s", interaction.id, agent)
    start = time.time()

    while True:
        interaction = client.interactions.get(interaction.id)
        status = interaction.status
        elapsed = time.time() - start

        if on_status is not None:
            on_status(status, elapsed)

        if status == _STATUS_COMPLETED:
            logger.info("Research completed in %.1fs: id=%s", elapsed, interaction.id)
            return interaction
        if status == _STATUS_FAILED:
            error = getattr(interaction, "error", "unknown error")
            raise ResearchFailedError(f"Research failed: {error}")
        if status not in (_STATUS_IN_PROGRESS, _STATUS_COMPLETED, _STATUS_FAILED):
            logger.warning("Unexpected interaction status %r; continuing to poll", status)
        if elapsed > timeout:
            raise ResearchTimeoutError(
                f"Research did not complete within {timeout:.0f}s (id={interaction.id})"
            )

        time.sleep(poll_interval)


def run_followup(
    client: genai.Client,
    question: str,
    previous_interaction_id: str,
    *,
    model: str = FOLLOWUP_MODEL,
) -> Any:
    """Submit a synchronous follow-up using ``previous_interaction_id``.

    Uses the direct-model path (``model=``, no ``agent=``, no ``background=True``),
    which is cheap and fast (<30 s) compared to a full deep-research task.

    Returns the interaction object directly — no polling required.
    """
    interaction = client.interactions.create(
        input=question,
        model=model,
        previous_interaction_id=previous_interaction_id,
    )
    logger.info("Sync follow-up completed: id=%s model=%s", interaction.id, model)
    return interaction


def extract_report_text(interaction: Any) -> str:
    """Concatenate all text outputs from a completed interaction.

    Returns an empty string if the interaction has no outputs.
    """
    outputs = getattr(interaction, "outputs", None) or []
    return "".join(getattr(o, "text", "") for o in outputs)
