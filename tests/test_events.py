from __future__ import annotations

from primer_sdk.events import (
    AGUIEvent,
    AGUIEventType,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)


class TestAGUIEventType:
    def test_all_12_event_types_defined(self):
        expected = {
            "RUN_STARTED",
            "RUN_FINISHED",
            "RUN_ERROR",
            "TEXT_MESSAGE_START",
            "TEXT_MESSAGE_CONTENT",
            "TEXT_MESSAGE_END",
            "STATE_SNAPSHOT",
            "STATE_DELTA",
            "TOOL_CALL_START",
            "TOOL_CALL_ARGS",
            "TOOL_CALL_END",
            "TOOL_CALL_RESULT",
        }
        actual = {member.name for member in AGUIEventType}
        assert actual == expected

    def test_event_type_is_str_enum(self):
        assert isinstance(AGUIEventType.RUN_STARTED, str)
        assert AGUIEventType.RUN_STARTED.value == "RUN_STARTED"


class TestAGUIEventBase:
    def test_base_event_creation(self):
        event = AGUIEvent(
            event_type=AGUIEventType.RUN_STARTED,
            thread_id="thread-123",
            run_id="run-456",
        )
        assert event.event_type == AGUIEventType.RUN_STARTED
        assert event.thread_id == "thread-123"
        assert event.run_id == "run-456"
        assert event.event_id is not None
        assert event.timestamp is not None

    def test_base_event_default_timestamp_is_utc(self):
        event = AGUIEvent(
            event_type=AGUIEventType.RUN_STARTED,
            thread_id="t",
            run_id="r",
        )
        assert event.timestamp.tzinfo is not None

    def test_base_event_default_event_id_is_uuid(self):
        event1 = AGUIEvent(
            event_type=AGUIEventType.RUN_STARTED,
            thread_id="t",
            run_id="r",
        )
        event2 = AGUIEvent(
            event_type=AGUIEventType.RUN_STARTED,
            thread_id="t",
            run_id="r",
        )
        assert event1.event_id != event2.event_id

    def test_base_to_dict(self):
        event = AGUIEvent(
            event_type=AGUIEventType.RUN_STARTED,
            thread_id="thread-123",
            run_id="run-456",
        )
        d = event.to_dict()
        assert d["type"] == "RUN_STARTED"
        assert d["thread_id"] == "thread-123"
        assert d["run_id"] == "run-456"
        assert "event_id" in d
        assert "timestamp" in d

    def test_base_to_dict_uses_event_type_value(self):
        event = AGUIEvent(
            event_type=AGUIEventType.TOOL_CALL_RESULT,
            thread_id="t",
            run_id="r",
        )
        assert event.to_dict()["type"] == "TOOL_CALL_RESULT"


class TestRunStartedEvent:
    def test_event_type(self):
        event = RunStartedEvent(thread_id="t", run_id="r")
        assert event.event_type == AGUIEventType.RUN_STARTED

    def test_to_dict(self):
        event = RunStartedEvent(thread_id="t", run_id="r")
        d = event.to_dict()
        assert d["type"] == "RUN_STARTED"


class TestRunFinishedEvent:
    def test_event_type(self):
        event = RunFinishedEvent(thread_id="t", run_id="r")
        assert event.event_type == AGUIEventType.RUN_FINISHED

    def test_to_dict(self):
        event = RunFinishedEvent(thread_id="t", run_id="r")
        assert event.to_dict()["type"] == "RUN_FINISHED"


class TestRunErrorEvent:
    def test_event_type(self):
        event = RunErrorEvent(thread_id="t", run_id="r", error="something went wrong")
        assert event.event_type == AGUIEventType.RUN_ERROR

    def test_to_dict_with_error(self):
        event = RunErrorEvent(thread_id="t", run_id="r", error="oops")
        d = event.to_dict()
        assert d["type"] == "RUN_ERROR"
        assert d["error"] == "oops"
        assert d["code"] is None

    def test_to_dict_with_code(self):
        event = RunErrorEvent(thread_id="t", run_id="r", error="oops", code="E001")
        d = event.to_dict()
        assert d["code"] == "E001"

    def test_code_optional(self):
        event = RunErrorEvent(thread_id="t", run_id="r", error="oops")
        assert event.code is None


class TestTextMessageStartEvent:
    def test_event_type(self):
        event = TextMessageStartEvent(thread_id="t", run_id="r", message_id="m1", role="assistant")
        assert event.event_type == AGUIEventType.TEXT_MESSAGE_START

    def test_to_dict(self):
        event = TextMessageStartEvent(thread_id="t", run_id="r", message_id="m1", role="assistant")
        d = event.to_dict()
        assert d["type"] == "TEXT_MESSAGE_START"
        assert d["message_id"] == "m1"
        assert d["role"] == "assistant"


class TestTextMessageContentEvent:
    def test_event_type(self):
        event = TextMessageContentEvent(thread_id="t", run_id="r", message_id="m1", content="hello")
        assert event.event_type == AGUIEventType.TEXT_MESSAGE_CONTENT

    def test_to_dict(self):
        event = TextMessageContentEvent(thread_id="t", run_id="r", message_id="m1", content="hello")
        d = event.to_dict()
        assert d["type"] == "TEXT_MESSAGE_CONTENT"
        assert d["message_id"] == "m1"
        assert d["content"] == "hello"


class TestTextMessageEndEvent:
    def test_event_type(self):
        event = TextMessageEndEvent(thread_id="t", run_id="r", message_id="m1")
        assert event.event_type == AGUIEventType.TEXT_MESSAGE_END

    def test_to_dict(self):
        event = TextMessageEndEvent(thread_id="t", run_id="r", message_id="m1")
        d = event.to_dict()
        assert d["type"] == "TEXT_MESSAGE_END"
        assert d["message_id"] == "m1"


class TestStateSnapshotEvent:
    def test_event_type(self):
        event = StateSnapshotEvent(thread_id="t", run_id="r", state={"key": "value"})
        assert event.event_type == AGUIEventType.STATE_SNAPSHOT

    def test_to_dict(self):
        event = StateSnapshotEvent(thread_id="t", run_id="r", state={"key": "value", "count": 42})
        d = event.to_dict()
        assert d["type"] == "STATE_SNAPSHOT"
        assert d["state"] == {"key": "value", "count": 42}


class TestStateDeltaEvent:
    def test_event_type(self):
        delta = [{"op": "add", "path": "/x", "value": 1}]
        event = StateDeltaEvent(thread_id="t", run_id="r", delta=delta)
        assert event.event_type == AGUIEventType.STATE_DELTA

    def test_to_dict(self):
        delta = [{"op": "replace", "path": "/y", "value": "new"}]
        event = StateDeltaEvent(thread_id="t", run_id="r", delta=delta)
        d = event.to_dict()
        assert d["type"] == "STATE_DELTA"
        assert d["delta"] == delta


class TestToolCallStartEvent:
    def test_event_type(self):
        event = ToolCallStartEvent(
            thread_id="t",
            run_id="r",
            tool_call_id="tc1",
            tool_name="search",
        )
        assert event.event_type == AGUIEventType.TOOL_CALL_START

    def test_to_dict(self):
        event = ToolCallStartEvent(
            thread_id="t",
            run_id="r",
            tool_call_id="tc1",
            tool_name="search",
        )
        d = event.to_dict()
        assert d["type"] == "TOOL_CALL_START"
        assert d["tool_call_id"] == "tc1"
        assert d["tool_name"] == "search"


class TestToolCallArgsEvent:
    def test_event_type(self):
        event = ToolCallArgsEvent(thread_id="t", run_id="r", tool_call_id="tc1", args_chunk='{"q":')
        assert event.event_type == AGUIEventType.TOOL_CALL_ARGS

    def test_to_dict(self):
        event = ToolCallArgsEvent(thread_id="t", run_id="r", tool_call_id="tc1", args_chunk='{"q":')
        d = event.to_dict()
        assert d["type"] == "TOOL_CALL_ARGS"
        assert d["tool_call_id"] == "tc1"
        assert d["args_chunk"] == '{"q":'


class TestToolCallEndEvent:
    def test_event_type(self):
        event = ToolCallEndEvent(thread_id="t", run_id="r", tool_call_id="tc1")
        assert event.event_type == AGUIEventType.TOOL_CALL_END

    def test_to_dict(self):
        event = ToolCallEndEvent(thread_id="t", run_id="r", tool_call_id="tc1")
        d = event.to_dict()
        assert d["type"] == "TOOL_CALL_END"
        assert d["tool_call_id"] == "tc1"


class TestToolCallResultEvent:
    def test_event_type(self):
        event = ToolCallResultEvent(
            thread_id="t",
            run_id="r",
            tool_call_id="tc1",
            result="found it",
        )
        assert event.event_type == AGUIEventType.TOOL_CALL_RESULT

    def test_to_dict(self):
        event = ToolCallResultEvent(
            thread_id="t",
            run_id="r",
            tool_call_id="tc1",
            result="found it",
        )
        d = event.to_dict()
        assert d["type"] == "TOOL_CALL_RESULT"
        assert d["tool_call_id"] == "tc1"
        assert d["result"] == "found it"
