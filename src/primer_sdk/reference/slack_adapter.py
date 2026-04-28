from __future__ import annotations

from typing import Any
from uuid import uuid4

from primer_sdk.events import (
    AGUIEvent,
    AGUIEventType,
    RunErrorEvent,
    StateSnapshotEvent,
    TextMessageContentEvent,
)
from primer_sdk.models.presentation import (
    ChannelFile,
    ChannelMessage,
    ChannelSession,
    HitlGateConfig,
)
from primer_sdk.ports.presentation import ChannelAdapterPort


class SlackChannelAdapter(ChannelAdapterPort):
    """Reference implementation of :class:`ChannelAdapterPort` for Slack.

    Uses an in-memory outbox (list of dicts) instead of real Slack API calls,
    making it suitable for testing and development and testing.
    """

    def __init__(self, bot_token: str, signing_secret: str) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._message_buffer: dict[str, list[str]] = {}  # session_id -> tokens
        self._outbox: list[dict[str, Any]] = []  # captures sent messages for testing

    @property
    def channel_type(self) -> str:
        return "slack"

    async def send_event(self, event: AGUIEvent, session: ChannelSession) -> None:
        """Forward an AG-UI event to the Slack channel (buffered in-memory)."""
        session_id = str(session.id)

        if event.event_type == AGUIEventType.TEXT_MESSAGE_START:
            self._message_buffer[session_id] = []

        elif event.event_type == AGUIEventType.TEXT_MESSAGE_CONTENT:
            assert isinstance(event, TextMessageContentEvent)
            if session_id not in self._message_buffer:
                self._message_buffer[session_id] = []
            self._message_buffer[session_id].append(event.content)

        elif event.event_type == AGUIEventType.TEXT_MESSAGE_END:
            tokens = self._message_buffer.pop(session_id, [])
            text = "".join(tokens)
            self._outbox.append(
                {
                    "type": "message",
                    "channel": session.metadata.get("channel", session.channel_conversation_id),
                    "text": text,
                    "thread_ts": session.metadata.get("thread_ts"),
                }
            )

        elif event.event_type == AGUIEventType.STATE_SNAPSHOT:
            assert isinstance(event, StateSnapshotEvent)
            fields = [{"type": "mrkdwn", "text": f"*{k}*\n{v}"} for k, v in event.state.items()]
            self._outbox.append(
                {
                    "type": "blocks",
                    "channel": session.metadata.get("channel", session.channel_conversation_id),
                    "thread_ts": session.metadata.get("thread_ts"),
                    "blocks": [
                        {
                            "type": "section",
                            "fields": fields,
                        }
                    ],
                }
            )

        elif event.event_type == AGUIEventType.RUN_FINISHED:
            self._outbox.append(
                {
                    "type": "message",
                    "channel": session.metadata.get("channel", session.channel_conversation_id),
                    "thread_ts": session.metadata.get("thread_ts"),
                    "text": "Run completed.",
                }
            )

        elif event.event_type == AGUIEventType.RUN_ERROR:
            assert isinstance(event, RunErrorEvent)
            await self.send_error(event.error, session)

    async def send_error(self, error: str, session: ChannelSession) -> None:
        """Append an error message with :x: prefix to the outbox."""
        self._outbox.append(
            {
                "type": "message",
                "channel": session.metadata.get("channel", session.channel_conversation_id),
                "thread_ts": session.metadata.get("thread_ts"),
                "text": f":x: {error}",
            }
        )

    async def render_hitl_gate(
        self,
        gate_type: str,
        gate_config: HitlGateConfig,
        session: ChannelSession,
    ) -> None:
        """Render a human-in-the-loop gate as Slack Block Kit."""
        channel = session.metadata.get("channel", session.channel_conversation_id)
        thread_ts = session.metadata.get("thread_ts")

        if gate_type == "human_review":
            buttons = [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": option},
                    "action_id": option,
                    "value": option,
                }
                for option in gate_config.options
            ]
            self._outbox.append(
                {
                    "type": "blocks",
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": gate_config.instructions or "Please review:",
                            },
                        },
                        {
                            "type": "actions",
                            "elements": buttons,
                        },
                    ],
                }
            )
        else:
            # input gate — send prompt text
            self._outbox.append(
                {
                    "type": "message",
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "text": (
                        gate_config.prompt or gate_config.instructions or "Please provide input:"
                    ),
                }
            )

    async def receive_message(self, raw_payload: dict) -> ChannelMessage:
        """Parse an inbound Slack payload into a :class:`ChannelMessage`."""
        session = await self.resolve_session(raw_payload)

        # Detect block_actions (button click) -> hitl_decision
        payload = raw_payload.get("payload", raw_payload)
        if payload.get("type") == "block_actions":
            actions = payload.get("actions", [])
            action_value = actions[0].get("value", "") if actions else ""
            return ChannelMessage(
                id=str(uuid4()),
                message_type="hitl_decision",
                content=action_value,
                session=session,
                raw_payload=raw_payload,
            )

        # Regular event_callback message
        event = raw_payload.get("event", {})
        text = event.get("text", "")
        if text.startswith("/"):
            message_type = "command"
        else:
            message_type = "text_input"

        return ChannelMessage(
            id=str(uuid4()),
            message_type=message_type,
            content=text,
            session=session,
            raw_payload=raw_payload,
        )

    async def receive_file(self, raw_payload: dict) -> ChannelFile | None:
        """Parse an inbound file upload payload from Slack."""
        event = raw_payload.get("event", {})
        files = event.get("files", [])
        if not files:
            return None

        first = files[0]
        return ChannelFile(
            filename=first.get("name", "unknown"),
            content_type=first.get("mimetype", "application/octet-stream"),
            size_bytes=first.get("size", 0),
            content=b"",
            source_url=first.get("url_private"),
        )

    async def resolve_session(self, raw_payload: dict) -> ChannelSession:
        """Identify or create the channel session from an inbound Slack payload."""
        payload = raw_payload.get("payload", raw_payload)

        if payload.get("type") == "block_actions":
            user_id = payload.get("user", {}).get("id", "unknown")
            channel_id = payload.get("channel", {}).get("id", "unknown")
        else:
            event = raw_payload.get("event", {})
            user_id = event.get("user", "unknown")
            channel_id = event.get("channel", "unknown")

        return ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id=user_id,
            channel_conversation_id=channel_id,
            metadata={"channel": channel_id},
        )

    async def register_webhook(self, callback_url: str) -> None:
        """No-op: webhook registration is handled externally for Slack."""
        pass

    async def health_check(self) -> bool:
        """Return True if a bot token is configured."""
        return bool(self._bot_token)
