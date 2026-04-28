from __future__ import annotations

from uuid import uuid4

import pytest

from primer_sdk.events import (
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from primer_sdk.models.presentation import ChannelSession
from primer_sdk.ports.presentation import ChannelAdapterPort
from primer_sdk.reference.slack_adapter import SlackChannelAdapter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_session(thread_ts: str = "1234567890.000100") -> ChannelSession:
    return ChannelSession(
        id=uuid4(),
        channel_type="slack",
        channel_user_id="U123456",
        channel_conversation_id="C789012",
        metadata={"thread_ts": thread_ts, "channel": "C789012"},
    )


def make_adapter() -> SlackChannelAdapter:
    return SlackChannelAdapter(bot_token="xoxb-test-token", signing_secret="test-secret")


def make_text_start_event(message_id: str = "msg-1") -> TextMessageStartEvent:
    return TextMessageStartEvent(
        message_id=message_id,
        role="assistant",
        thread_id="thread-1",
        run_id="run-1",
    )


def make_text_content_event(content: str, message_id: str = "msg-1") -> TextMessageContentEvent:
    return TextMessageContentEvent(
        message_id=message_id,
        content=content,
        thread_id="thread-1",
        run_id="run-1",
    )


def make_text_end_event(message_id: str = "msg-1") -> TextMessageEndEvent:
    return TextMessageEndEvent(
        message_id=message_id,
        thread_id="thread-1",
        run_id="run-1",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSlackChannelAdapterInterface:
    def test_implements_channel_adapter_port(self):
        adapter = make_adapter()
        assert isinstance(adapter, ChannelAdapterPort)

    def test_channel_type(self):
        adapter = make_adapter()
        assert adapter.channel_type == "slack"


class TestTextMessageBuffering:
    @pytest.mark.asyncio
    async def test_buffers_text_message_tokens(self):
        adapter = make_adapter()
        session = make_session()

        await adapter.send_event(make_text_start_event(), session)
        await adapter.send_event(make_text_content_event("Hello"), session)
        await adapter.send_event(make_text_content_event(", world"), session)

        session_id = str(session.id)
        assert session_id in adapter._message_buffer
        assert adapter._message_buffer[session_id] == ["Hello", ", world"]

    @pytest.mark.asyncio
    async def test_flushes_buffer_on_message_end(self):
        adapter = make_adapter()
        session = make_session()

        await adapter.send_event(make_text_start_event(), session)
        await adapter.send_event(make_text_content_event("Hello"), session)
        await adapter.send_event(make_text_content_event(", world"), session)
        await adapter.send_event(make_text_end_event(), session)

        session_id = str(session.id)
        # Buffer should be cleared after END
        assert session_id not in adapter._message_buffer
        # Outbox should contain the flushed message
        assert len(adapter._outbox) == 1
        msg = adapter._outbox[0]
        assert msg["text"] == "Hello, world"


class TestInboundParsing:
    @pytest.mark.asyncio
    async def test_parse_button_click_as_hitl_decision(self):
        adapter = make_adapter()
        payload = {
            "type": "block_actions",
            "user": {"id": "U123"},
            "channel": {"id": "C456"},
            "actions": [{"action_id": "approve", "value": "approve"}],
        }
        msg = await adapter.receive_message({"payload": payload})
        assert msg.message_type == "hitl_decision"

    @pytest.mark.asyncio
    async def test_parse_regular_message_as_text_input(self):
        adapter = make_adapter()
        payload = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "user": "U123",
                "channel": "C456",
                "text": "Hello there",
            },
        }
        msg = await adapter.receive_message(payload)
        assert msg.message_type == "text_input"

    @pytest.mark.asyncio
    async def test_parse_slash_command_as_command(self):
        adapter = make_adapter()
        payload = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "user": "U123",
                "channel": "C456",
                "text": "/run some-workflow",
            },
        }
        msg = await adapter.receive_message(payload)
        assert msg.message_type == "command"
