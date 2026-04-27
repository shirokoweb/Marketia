"""Core primitives: client bootstrap, cost accounting, and the research polling loop.

All shared logic used by both the Streamlit UI and the CLI entry points lives here.
The module is intentionally free of Streamlit and argparse imports so it can be
reused in any context.
"""

from __future__ import annotations

import base64
import logging
import os
import time
import warnings
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
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

_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024  # 20 MB
_MIME_BY_EXT: dict[str, tuple[str, str]] = {
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".pdf": ("document", "application/pdf"),
}

# Pricing tiers for RESEARCH_MODEL (USD per 1M tokens).
_INPUT_RATE_LOW, _INPUT_RATE_HIGH = 1.00, 2.00
_OUTPUT_RATE_LOW, _OUTPUT_RATE_HIGH = 6.00, 9.00
_TIER_BOUNDARY_TOKENS = 200_000

# Known API statuses reported by `interaction.status`.
_STATUS_COMPLETED = "completed"
_STATUS_FAILED = "failed"
_STATUS_IN_PROGRESS = "in_progress"


def file_to_attachment(path: Path) -> dict[str, str]:
    """Read a local file and return an API-ready content-part dict.

    Raises ``ValueError`` for unsupported extensions or files exceeding 20 MB.
    ``data`` is base64-encoded (str) as the SDK expects.
    """
    ext = path.suffix.lower()
    if ext not in _MIME_BY_EXT:
        raise ValueError(f"Unsupported attachment type: {ext!r}. Supported: {sorted(_MIME_BY_EXT)}")
    raw = path.read_bytes()
    if len(raw) > _MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"Attachment too large: {path.name} "
            f"({len(raw) / 1_048_576:.1f} MB > {_MAX_ATTACHMENT_BYTES // 1_048_576} MB)"
        )
    content_type, mime_type = _MIME_BY_EXT[ext]
    return {"type": content_type, "data": base64.b64encode(raw).decode(), "mime_type": mime_type}


def build_input(prompt: str, attachments: list[dict] | None = None) -> str | list:
    """Combine a text prompt with optional attachment parts into API input format.

    Returns the plain ``prompt`` string when there are no attachments, or a list
    of content-part dicts (``[{"type": "text", "text": prompt}, *attachments]``)
    when attachments are present.
    """
    if not attachments:
        return prompt
    return [{"type": "text", "text": prompt}, *attachments]


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


_PLAN_TRANSITIONS: dict[str, frozenset[str]] = {
    "awaiting_plan": frozenset({"plan_ready"}),
    "plan_ready": frozenset({"plan_ready", "executing"}),
    "executing": frozenset({"done"}),
    "done": frozenset(),
}


class PlanSession:
    """Manages collaborative-planning session state across plan/refine/execute rounds."""

    def __init__(self, prompt: str) -> None:
        self.prompt = prompt
        self.phase = "awaiting_plan"
        self.interaction_id = ""
        self.plan_text = ""
        self.rounds = 0

    def advance(
        self,
        new_phase: str,
        *,
        interaction_id: str = "",
        plan_text: str = "",
    ) -> None:
        """Transition to ``new_phase``, updating tracked state.

        Raises ``ValueError`` for invalid transitions.
        Refinements (plan_ready → plan_ready) increment ``rounds``.
        """
        allowed = _PLAN_TRANSITIONS.get(self.phase, frozenset())
        if new_phase not in allowed:
            raise ValueError(
                f"Cannot transition from {self.phase!r} to {new_phase!r}. "
                f"Allowed: {sorted(allowed)}"
            )
        if new_phase == "plan_ready" and self.phase == "plan_ready":
            self.rounds += 1
        self.phase = new_phase
        if interaction_id:
            self.interaction_id = interaction_id
        if plan_text:
            self.plan_text = plan_text


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
    previous_interaction_id: str = "",
    extra_agent_config: dict | None = None,
    attachments: list[dict] | None = None,
    tools: list[dict] | None = None,
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
        previous_interaction_id: For plan refinement/approval rounds.
        extra_agent_config: Keys merged into ``_AGENT_CONFIG_BASE``
            (e.g. ``{"collaborative_planning": True}``).

    Returns:
        The completed interaction object from the Google GenAI SDK.

    Raises:
        ResearchFailedError: If the API reports a failed status.
        ResearchTimeoutError: If the interaction exceeds ``timeout`` seconds.
    """
    agent_config: dict[str, Any] = {**_AGENT_CONFIG_BASE}
    if extra_agent_config:
        agent_config.update(extra_agent_config)

    create_kwargs: dict[str, Any] = {
        "agent": agent,
        "input": build_input(prompt, attachments),
        "background": True,
        "agent_config": agent_config,
    }
    if previous_interaction_id:
        create_kwargs["previous_interaction_id"] = previous_interaction_id
    if tools:
        create_kwargs["tools"] = tools

    interaction = client.interactions.create(**create_kwargs)
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


def run_research_streaming(
    client: genai.Client,
    prompt: str,
    *,
    agent: str = RESEARCH_MODEL_FAST,
    agent_config: dict | None = None,
    previous_interaction_id: str = "",
    attachments: list[dict] | None = None,
    tools: list[dict] | None = None,
    max_reconnects: int = 3,
) -> Iterator[tuple[str, str | None, Any]]:
    """Stream a Deep Research task, yielding ``(event_type, delta_type, payload)`` tuples.

    Handles ~600 s SSE disconnects by reconnecting with ``last_event_id`` (up to
    ``max_reconnects`` times). Yields:

    - ``("interaction.start", None, interaction_id)``
    - ``("content.delta", "text", text_str)``
    - ``("content.delta", "thought_summary", text_str)``
    - ``("content.delta", "image", raw_bytes)``
    - ``("interaction.status_update", None, status_str)``
    - ``("interaction.complete", None, interaction_obj)``
    - ``("error", None, error_message_str)``
    """
    config: dict[str, Any] = {**_AGENT_CONFIG_BASE, "thinking_summaries": "auto"}
    if agent_config:
        config.update(agent_config)

    create_kwargs: dict[str, Any] = {
        "agent": agent,
        "input": build_input(prompt, attachments),
        "stream": True,
        "background": True,
        "agent_config": config,
    }
    if previous_interaction_id:
        create_kwargs["previous_interaction_id"] = previous_interaction_id
    if tools:
        create_kwargs["tools"] = tools

    stream = client.interactions.create(**create_kwargs)

    interaction_id: str | None = None
    last_event_id: str | None = None
    reconnects = 0

    while True:
        try:
            for chunk in stream:
                eid = getattr(chunk, "event_id", None)
                if eid:
                    last_event_id = eid

                event_type: str = chunk.event_type

                if event_type == "interaction.start":
                    interaction_id = chunk.interaction.id
                    yield ("interaction.start", None, interaction_id)

                elif event_type == "content.delta":
                    delta = chunk.delta
                    delta_type = getattr(delta, "type", None)
                    if delta_type == "text":
                        yield ("content.delta", "text", delta.text)
                    elif delta_type == "thought_summary":
                        content = getattr(delta, "content", None)
                        text = getattr(content, "text", "") if content else ""
                        yield ("content.delta", "thought_summary", text or "")
                    elif delta_type == "image":
                        raw = getattr(delta, "data", None)
                        if raw:
                            yield ("content.delta", "image", base64.b64decode(raw))

                elif event_type == "interaction.status_update":
                    yield ("interaction.status_update", None, chunk.status)

                elif event_type == "interaction.complete":
                    yield ("interaction.complete", None, chunk.interaction)
                    return

                elif event_type == "error":
                    yield ("error", None, str(getattr(chunk, "error", chunk)))
                    return

            return  # stream ended without interaction.complete

        except (httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError) as exc:
            if interaction_id and last_event_id and reconnects < max_reconnects:
                reconnects += 1
                logger.warning(
                    "Stream disconnected (%s); reconnecting (attempt %d)", exc, reconnects
                )
                stream = client.interactions.get(
                    id=interaction_id, stream=True, last_event_id=last_event_id
                )
            else:
                raise


@dataclass(frozen=True)
class ImageOut:
    """A decoded image output from a research interaction."""

    data: bytes
    mime_type: str


def extract_report_outputs(interaction: Any) -> tuple[str, list[ImageOut]]:
    """Return (full_text, images) from a completed interaction.

    Text outputs are concatenated; image outputs are base64-decoded into ImageOut.
    """
    outputs = getattr(interaction, "outputs", None) or []
    text_parts: list[str] = []
    images: list[ImageOut] = []
    for o in outputs:
        otype = getattr(o, "type", "text")
        if otype == "image":
            raw = getattr(o, "data", None)
            mime = getattr(o, "mime_type", "image/png")
            if raw:
                images.append(ImageOut(data=base64.b64decode(raw), mime_type=mime))
            text_parts.append("")
        else:
            text_parts.append(getattr(o, "text", ""))
    return "".join(text_parts), images


def extract_report_text(interaction: Any) -> str:
    """Concatenate all text outputs from a completed interaction.

    Returns an empty string if the interaction has no outputs.
    """
    text, _ = extract_report_outputs(interaction)
    return text
