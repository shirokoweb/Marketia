"""Tests for marketia.core — pure-logic helpers and run_research polling behaviour."""

from __future__ import annotations

import base64
import logging
import types
import warnings

import httpx
import pytest

from marketia import core
from marketia.core import (
    FOLLOWUP_MODEL,
    RESEARCH_MODEL_FAST,
    RESEARCH_MODEL_MAX,
    ImageOut,
    PlanSession,
    ResearchFailedError,
    ResearchTimeoutError,
    Usage,
    build_input,
    calculate_cost,
    extract_report_outputs,
    extract_report_text,
    file_to_attachment,
    run_followup,
    run_research,
    run_research_streaming,
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
# run_research — previous_interaction_id + extra_agent_config (Task 6)
# ---------------------------------------------------------------------------


def test_run_research_passes_previous_interaction_id():
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    run_research(client, "p", previous_interaction_id="prev-123", poll_interval=0)
    assert captured.get("previous_interaction_id") == "prev-123"


def test_run_research_extra_agent_config_merged():
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    run_research(client, "p", extra_agent_config={"collaborative_planning": True}, poll_interval=0)
    cfg = captured.get("agent_config", {})
    assert cfg.get("type") == "deep-research"
    assert cfg.get("collaborative_planning") is True


def test_run_research_omits_previous_interaction_id_when_empty():
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    run_research(client, "p", poll_interval=0)
    assert "previous_interaction_id" not in captured


# ---------------------------------------------------------------------------
# PlanSession state machine (Task 6)
# ---------------------------------------------------------------------------


def test_plan_session_initial_phase():
    s = PlanSession("my prompt")
    assert s.phase == "awaiting_plan"
    assert s.rounds == 0
    assert s.prompt == "my prompt"


def test_plan_session_advance_to_plan_ready():
    s = PlanSession("p")
    s.advance("plan_ready", interaction_id="id1", plan_text="Here is the plan.")
    assert s.phase == "plan_ready"
    assert s.interaction_id == "id1"
    assert s.plan_text == "Here is the plan."


def test_plan_session_refine_increments_rounds():
    s = PlanSession("p")
    s.advance("plan_ready", interaction_id="id1", plan_text="Plan v1")
    s.advance("plan_ready", interaction_id="id2", plan_text="Plan v2")
    assert s.rounds == 1
    s.advance("plan_ready", interaction_id="id3", plan_text="Plan v3")
    assert s.rounds == 2


def test_plan_session_advance_to_executing():
    s = PlanSession("p")
    s.advance("plan_ready", interaction_id="id1", plan_text="Plan.")
    s.advance("executing", interaction_id="id2")
    assert s.phase == "executing"


def test_plan_session_advance_to_done():
    s = PlanSession("p")
    s.advance("plan_ready", interaction_id="id1", plan_text="Plan.")
    s.advance("executing", interaction_id="id2")
    s.advance("done")
    assert s.phase == "done"


def test_plan_session_invalid_transition_raises():
    s = PlanSession("p")
    with pytest.raises(ValueError, match="Cannot transition"):
        s.advance("executing")  # must go through plan_ready first


def test_plan_session_done_cannot_advance():
    s = PlanSession("p")
    s.advance("plan_ready", interaction_id="id1", plan_text="p")
    s.advance("executing")
    s.advance("done")
    with pytest.raises(ValueError, match="Cannot transition"):
        s.advance("plan_ready")


# ---------------------------------------------------------------------------
# run_followup (Task 4)
# ---------------------------------------------------------------------------


def test_followup_model_constant():
    assert FOLLOWUP_MODEL == "gemini-2.5-flash"


def test_run_followup_calls_create_with_correct_args():
    """run_followup must use model= and previous_interaction_id=, not agent= or background=."""
    captured = {}

    class _FI:
        id = "followup-id"
        outputs = [types.SimpleNamespace(type="text", text="answer")]
        usage = None

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FI()

    client = types.SimpleNamespace(interactions=types.SimpleNamespace(create=fake_create))
    result = run_followup(client, "What next?", "parent-id-123")
    assert captured.get("model") == FOLLOWUP_MODEL
    assert captured.get("previous_interaction_id") == "parent-id-123"
    assert captured.get("input") == "What next?"
    assert "agent" not in captured, "agent= must not be passed in sync follow-up"
    assert "background" not in captured, "background= must not be passed in sync follow-up"
    assert result.id == "followup-id"


def test_run_followup_accepts_custom_model():
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(id="x", outputs=[], usage=None)

    client = types.SimpleNamespace(interactions=types.SimpleNamespace(create=fake_create))
    run_followup(client, "Q", "pid", model="gemini-2.5-pro")
    assert captured["model"] == "gemini-2.5-pro"


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


# ---------------------------------------------------------------------------
# run_research_streaming (Task 5)
# ---------------------------------------------------------------------------


def _make_start(iid="stream-id", eid="e1"):
    return types.SimpleNamespace(
        event_type="interaction.start",
        event_id=eid,
        interaction=types.SimpleNamespace(id=iid),
    )


def _make_text_delta(text, eid="e2"):
    return types.SimpleNamespace(
        event_type="content.delta",
        event_id=eid,
        delta=types.SimpleNamespace(type="text", text=text),
    )


def _make_thought_delta(thought_text, eid="e3"):
    return types.SimpleNamespace(
        event_type="content.delta",
        event_id=eid,
        delta=types.SimpleNamespace(
            type="thought_summary",
            content=types.SimpleNamespace(text=thought_text),
        ),
    )


def _make_complete(iid="stream-id", eid="e9"):
    return types.SimpleNamespace(
        event_type="interaction.complete",
        event_id=eid,
        interaction=types.SimpleNamespace(id=iid, outputs=[], usage=None),
    )


def _make_error(msg="boom", eid="ex"):
    return types.SimpleNamespace(event_type="error", event_id=eid, error=msg)


def _make_status_update(status, eid="es"):
    return types.SimpleNamespace(
        event_type="interaction.status_update", event_id=eid, status=status
    )


def _streaming_client(events, reconnect_events=None):
    """Fake client whose create() returns events; optional get() returns reconnect_events."""

    class _FakeStream:
        def __init__(self, evts):
            self._evts = evts

        def __iter__(self):
            yield from self._evts

    def fake_create(**kwargs):
        return _FakeStream(events)

    def fake_get(id, *, stream, last_event_id=None, **kw):
        return _FakeStream(reconnect_events or [])

    return types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=fake_get)
    )


def test_streaming_yields_interaction_start():
    client = _streaming_client([_make_start("abc"), _make_complete("abc")])
    evts = list(run_research_streaming(client, "q"))
    assert evts[0] == ("interaction.start", None, "abc")


def test_streaming_yields_text_delta():
    client = _streaming_client(
        [_make_start(), _make_text_delta("hello "), _make_text_delta("world"), _make_complete()]
    )
    evts = list(run_research_streaming(client, "q"))
    text_evts = [(et, dt, p) for et, dt, p in evts if dt == "text"]
    assert text_evts == [
        ("content.delta", "text", "hello "),
        ("content.delta", "text", "world"),
    ]


def test_streaming_yields_thought_summary():
    client = _streaming_client(
        [_make_start(), _make_thought_delta("I am thinking..."), _make_complete()]
    )
    evts = list(run_research_streaming(client, "q"))
    thought_evts = [(et, dt, p) for et, dt, p in evts if dt == "thought_summary"]
    assert thought_evts == [("content.delta", "thought_summary", "I am thinking...")]


def test_streaming_terminates_on_complete():
    client = _streaming_client([_make_start(), _make_text_delta("x"), _make_complete()])
    evts = list(run_research_streaming(client, "q"))
    complete = [(et, dt, p) for et, dt, p in evts if et == "interaction.complete"]
    assert len(complete) == 1


def test_streaming_terminates_on_error():
    client = _streaming_client([_make_start(), _make_error("bad thing")])
    evts = list(run_research_streaming(client, "q"))
    assert evts[-1][0] == "error"
    assert "bad thing" in evts[-1][2]


def test_streaming_agent_config_includes_thinking_summaries():
    captured = {}

    class _FakeStream:
        def __iter__(self):
            yield _make_start()
            yield _make_complete()

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _FakeStream()

    client = types.SimpleNamespace(interactions=types.SimpleNamespace(create=fake_create))
    list(run_research_streaming(client, "q"))
    cfg = captured.get("agent_config", {})
    assert cfg.get("type") == "deep-research"
    assert cfg.get("thinking_summaries") == "auto"


def test_streaming_reconnects_on_disconnect():
    """On httpx.ReadTimeout after first event, reconnect via get() with last_event_id."""
    reconnect_events = [_make_text_delta("resumed"), _make_complete()]
    reconnect_captured = {}

    class _FakeStreamDisconnects:
        def __iter__(self):
            yield _make_start("sid", eid="e1")
            raise httpx.ReadTimeout("timeout")

    class _FakeStreamReconnect:
        def __iter__(self):
            yield from reconnect_events

    def fake_create(**kwargs):
        return _FakeStreamDisconnects()

    def fake_get(id, *, stream, last_event_id=None, **kw):
        reconnect_captured["id"] = id
        reconnect_captured["last_event_id"] = last_event_id
        return _FakeStreamReconnect()

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=fake_get)
    )
    evts = list(run_research_streaming(client, "q"))
    assert reconnect_captured["id"] == "sid"
    assert reconnect_captured["last_event_id"] == "e1"
    text_evts = [p for et, dt, p in evts if dt == "text"]
    assert "resumed" in text_evts


def test_streaming_status_update_yielded():
    client = _streaming_client([_make_start(), _make_status_update("planning"), _make_complete()])
    evts = list(run_research_streaming(client, "q"))
    status_evts = [(et, dt, p) for et, dt, p in evts if et == "interaction.status_update"]
    assert status_evts == [("interaction.status_update", None, "planning")]


# ---------------------------------------------------------------------------
# build_input + file_to_attachment (Task 7)
# ---------------------------------------------------------------------------


def test_build_input_no_attachments_returns_str():
    assert build_input("hello") == "hello"


def test_build_input_empty_attachments_returns_str():
    assert build_input("hello", attachments=[]) == "hello"


def test_build_input_with_attachments_returns_list():
    att = {"type": "image", "data": "abc", "mime_type": "image/png"}
    result = build_input("describe this", attachments=[att])
    assert isinstance(result, list)
    assert result[0] == {"type": "text", "text": "describe this"}
    assert result[1] == att


def test_build_input_multiple_attachments():
    atts = [
        {"type": "image", "data": "abc", "mime_type": "image/png"},
        {"type": "document", "data": "xyz", "mime_type": "application/pdf"},
    ]
    result = build_input("prompt", attachments=atts)
    assert len(result) == 3
    assert result[0]["type"] == "text"


def test_file_to_attachment_png(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"\x89PNG fake")
    att = file_to_attachment(img)
    assert att["type"] == "image"
    assert att["mime_type"] == "image/png"
    assert base64.b64decode(att["data"]) == b"\x89PNG fake"


def test_file_to_attachment_jpg(tmp_path):
    f = tmp_path / "photo.jpg"
    f.write_bytes(b"JFIF fake")
    att = file_to_attachment(f)
    assert att["mime_type"] == "image/jpeg"


def test_file_to_attachment_pdf(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF fake")
    att = file_to_attachment(f)
    assert att["type"] == "document"
    assert att["mime_type"] == "application/pdf"


def test_file_to_attachment_oversize_raises(tmp_path):
    big = tmp_path / "big.png"
    big.write_bytes(b"x" * (21 * 1024 * 1024))
    with pytest.raises(ValueError, match="too large"):
        file_to_attachment(big)


def test_file_to_attachment_unsupported_raises(tmp_path):
    f = tmp_path / "data.csv"
    f.write_bytes(b"col1,col2")
    with pytest.raises(ValueError, match="Unsupported"):
        file_to_attachment(f)


def test_run_research_passes_attachment_input():
    """When attachments are provided, input passed to create() is a list, not a str."""
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    att = {"type": "image", "data": "abc", "mime_type": "image/png"}
    run_research(client, "describe", attachments=[att], poll_interval=0)
    assert isinstance(captured["input"], list)
    assert captured["input"][0] == {"type": "text", "text": "describe"}
    assert captured["input"][1] == att


# ---------------------------------------------------------------------------
# Task 8 — extract_report_outputs / ImageOut
# ---------------------------------------------------------------------------


def _make_text_output(text: str):
    return types.SimpleNamespace(type="text", text=text, data=None)


def _make_image_output(b64data: str, mime: str = "image/png"):
    return types.SimpleNamespace(type="image", text="", data=b64data, mime_type=mime)


def _fake_interaction(*outputs):
    return types.SimpleNamespace(outputs=list(outputs), usage=None, id="i1")


def test_extract_report_outputs_text_only():
    interaction = _fake_interaction(_make_text_output("hello"), _make_text_output(" world"))
    text, images = extract_report_outputs(interaction)
    assert text == "hello world"
    assert images == []


def test_extract_report_outputs_image_only():
    raw = b"\x89PNG\r\n"
    b64 = base64.b64encode(raw).decode()
    interaction = _fake_interaction(_make_image_output(b64))
    text, images = extract_report_outputs(interaction)
    assert text == ""
    assert len(images) == 1
    assert isinstance(images[0], ImageOut)
    assert images[0].data == raw
    assert images[0].mime_type == "image/png"


def test_extract_report_outputs_interleaved():
    raw = b"\x89PNG"
    b64 = base64.b64encode(raw).decode()
    interaction = _fake_interaction(
        _make_text_output("before "),
        _make_image_output(b64),
        _make_text_output(" after"),
    )
    text, images = extract_report_outputs(interaction)
    assert text == "before  after"
    assert len(images) == 1
    assert images[0].data == raw


def test_extract_report_outputs_no_outputs():
    interaction = types.SimpleNamespace(outputs=None, usage=None, id="i1")
    text, images = extract_report_outputs(interaction)
    assert text == ""
    assert images == []


def test_extract_report_text_backward_compat():
    interaction = _fake_interaction(_make_text_output("legacy"), _make_text_output(" compat"))
    assert extract_report_text(interaction) == "legacy compat"


def test_image_out_dataclass():
    img = ImageOut(data=b"\xff", mime_type="image/jpeg")
    assert img.data == b"\xff"
    assert img.mime_type == "image/jpeg"


# ---------------------------------------------------------------------------
# Task 9 — tools (file_search) passthrough in run_research
# ---------------------------------------------------------------------------


def test_run_research_passes_tools_to_create():
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    tools = [{"type": "file_search", "file_search_store_names": ["fileSearchStores/my-store"]}]
    run_research(client, "p", tools=tools, poll_interval=0)
    assert captured.get("tools") == tools


def test_run_research_omits_tools_when_none():
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

    client = types.SimpleNamespace(
        interactions=types.SimpleNamespace(create=fake_create, get=lambda id: _FI())
    )
    run_research(client, "p", poll_interval=0)
    assert "tools" not in captured


def test_run_research_streaming_passes_tools():
    tools = [{"type": "file_search", "file_search_store_names": ["fileSearchStores/s"]}]
    captured = {}

    complete_event = types.SimpleNamespace(
        event_type="interaction.complete",
        event_id=None,
        interaction=types.SimpleNamespace(id="ix", outputs=[], usage=None),
    )

    def fake_create(**kwargs):
        captured.update(kwargs)
        return iter([complete_event])

    client = types.SimpleNamespace(interactions=types.SimpleNamespace(create=fake_create))
    list(run_research_streaming(client, "p", tools=tools))
    assert captured.get("tools") == tools
