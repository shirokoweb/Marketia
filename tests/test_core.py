"""Tests for marketia.core — pure-logic helpers and run_research polling behaviour."""

from __future__ import annotations

import logging
import types
import warnings

import pytest

from marketia import core
from marketia.core import (
    RESEARCH_MODEL_FAST,
    RESEARCH_MODEL_MAX,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    calculate_cost,
    run_research,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_client(create_status: str, poll_statuses: list[str]):
    """Return a minimal fake genai.Client that mimics interactions.create/get."""

    class _FakeInteraction:
        def __init__(self, status: str):
            self.id = "fake-id"
            self.status = status
            self.outputs = []
            self.usage = None
            self.error = None

    poll_iter = iter(_FakeInteraction(s) for s in poll_statuses)

    interactions = types.SimpleNamespace(
        create=lambda **kw: _FakeInteraction(create_status),
        get=lambda id: next(poll_iter),
    )
    return types.SimpleNamespace(interactions=interactions)


# ---------------------------------------------------------------------------
# Model ID constants (Task 1)
# ---------------------------------------------------------------------------


def test_research_model_fast_id():
    assert RESEARCH_MODEL_FAST == "deep-research-preview-04-2026"


def test_research_model_max_id():
    assert RESEARCH_MODEL_MAX == "deep-research-max-preview-04-2026"


def test_research_model_alias_equals_fast():
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        assert core.RESEARCH_MODEL == RESEARCH_MODEL_FAST


def test_research_model_alias_triggers_deprecation():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        _ = core.RESEARCH_MODEL
        assert any(issubclass(x.category, DeprecationWarning) for x in w), (
            "Expected DeprecationWarning when accessing RESEARCH_MODEL"
        )


# ---------------------------------------------------------------------------
# run_research polling behaviour (Task 1)
# ---------------------------------------------------------------------------


def test_run_research_returns_on_completed():
    client = _make_fake_client("in_progress", ["in_progress", "completed"])
    result = run_research(client, "test", poll_interval=0)
    assert result.status == "completed"


def test_run_research_raises_on_failed():
    client = _make_fake_client("in_progress", ["in_progress", "failed"])
    with pytest.raises(ResearchFailedError):
        run_research(client, "test", poll_interval=0)


def test_run_research_raises_timeout():
    poll_responses = ["in_progress"] * 100
    client = _make_fake_client("in_progress", poll_responses)
    with pytest.raises(ResearchTimeoutError):
        run_research(client, "test", poll_interval=0, timeout=0)


def test_run_research_warns_on_unknown_status(caplog):
    client = _make_fake_client("in_progress", ["weird_status", "completed"])
    with caplog.at_level(logging.WARNING, logger="marketia"):
        run_research(client, "test", poll_interval=0)
    assert any("weird_status" in r.message for r in caplog.records)


def test_run_research_uses_agent_kwarg():
    """run_research passes the agent value via agent= to client.interactions.create."""
    captured = {}

    class _FI:
        id = "fake"
        status = "completed"
        outputs = []
        usage = None
        error = None

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FI()

    interactions = types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    client = types.SimpleNamespace(interactions=interactions)
    run_research(client, "prompt", agent=RESEARCH_MODEL_FAST, poll_interval=0)
    assert captured.get("agent") == RESEARCH_MODEL_FAST
    assert "model" not in captured, "model= must not be passed to client.interactions.create"


# ---------------------------------------------------------------------------
# Usage.from_interaction (Task 2)
# ---------------------------------------------------------------------------


def test_usage_from_interaction_none_when_no_usage():
    interaction = types.SimpleNamespace(usage=None)
    assert Usage.from_interaction(interaction) is None


def test_usage_from_interaction_none_when_attr_missing():
    assert Usage.from_interaction(types.SimpleNamespace()) is None


def test_usage_from_interaction_builds_correctly():
    fake_usage = types.SimpleNamespace(
        total_input_tokens=100_000,
        total_output_tokens=50_000,
        total_reasoning_tokens=10_000,
    )
    interaction = types.SimpleNamespace(usage=fake_usage)
    u = Usage.from_interaction(interaction)
    assert u is not None
    assert u.input_tokens == 100_000
    assert u.output_tokens == 50_000
    assert u.reasoning_tokens == 10_000
    assert u.total_tokens == 160_000


# ---------------------------------------------------------------------------
# calculate_cost (Task 2)
# ---------------------------------------------------------------------------


def test_calculate_cost_below_threshold():
    cost = calculate_cost(input_tokens=100_000, output_tokens=50_000)
    assert cost > 0


def test_calculate_cost_above_threshold_higher():
    cost_low = calculate_cost(input_tokens=100_000, output_tokens=50_000)
    cost_high = calculate_cost(input_tokens=300_000, output_tokens=50_000)
    assert cost_high > cost_low


def test_calculate_cost_zero_tokens():
    assert calculate_cost(0, 0) == 0.0
