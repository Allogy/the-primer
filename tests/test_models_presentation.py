from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from primer_sdk.models.presentation import (
    ChannelFile,
    ChannelMessage,
    ChannelSession,
    HitlGateConfig,
)


class TestChannelSession:
    def test_unbound_session(self):
        session = ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U12345",
            channel_conversation_id="C67890",
        )
        assert isinstance(session.id, UUID)
        assert session.channel_type == "slack"
        assert session.channel_user_id == "U12345"
        assert session.channel_conversation_id == "C67890"
        assert session.platform_user_id is None
        assert session.org_id is None
        assert session.workflow_run_id is None
        assert session.thread_id is None
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_active, datetime)
        assert session.metadata == {}

    def test_bound_session_with_all_fields(self):
        session_id = uuid4()
        platform_user_id = uuid4()
        org_id = uuid4()
        workflow_run_id = uuid4()

        session = ChannelSession(
            id=session_id,
            channel_type="teams",
            channel_user_id="user@example.com",
            channel_conversation_id="conv-abc-123",
            platform_user_id=platform_user_id,
            org_id=org_id,
            workflow_run_id=workflow_run_id,
            thread_id="thread-xyz",
            metadata={"source": "teams", "region": "us-east-1"},
        )
        assert session.id == session_id
        assert session.platform_user_id == platform_user_id
        assert session.org_id == org_id
        assert session.workflow_run_id == workflow_run_id
        assert session.thread_id == "thread-xyz"
        assert session.metadata == {"source": "teams", "region": "us-east-1"}

    def test_created_at_defaults_to_utcnow(self):
        before = datetime.now(timezone.utc)
        session = ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U99",
            channel_conversation_id="C99",
        )
        after = datetime.now(timezone.utc)
        assert before <= session.created_at <= after
        assert before <= session.last_active <= after

    def test_mutable_metadata_defaults_are_independent(self):
        s1 = ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U1",
            channel_conversation_id="C1",
        )
        s2 = ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U2",
            channel_conversation_id="C2",
        )
        s1.metadata["key"] = "value"
        assert "key" not in s2.metadata


class TestChannelMessage:
    def _make_session(self) -> ChannelSession:
        return ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U12345",
            channel_conversation_id="C67890",
        )

    def test_text_input_message(self):
        session = self._make_session()
        msg = ChannelMessage(
            id="msg-001",
            message_type="text_input",
            content="Hello, world!",
            session=session,
            raw_payload={"text": "Hello, world!", "channel": "C67890"},
        )
        assert msg.id == "msg-001"
        assert msg.message_type == "text_input"
        assert msg.content == "Hello, world!"
        assert msg.session is session
        assert isinstance(msg.timestamp, datetime)

    def test_hitl_decision_message(self):
        session = self._make_session()
        decision_content = {"decision": "approve", "comment": "Looks good"}
        msg = ChannelMessage(
            id="msg-002",
            message_type="hitl_decision",
            content=decision_content,
            session=session,
            raw_payload={"payload": decision_content},
        )
        assert msg.message_type == "hitl_decision"
        assert msg.content == decision_content
        assert isinstance(msg.content, dict)

    def test_command_message(self):
        session = self._make_session()
        msg = ChannelMessage(
            id="msg-003",
            message_type="command",
            content="/start-workflow",
            session=session,
            raw_payload={"command": "/start-workflow", "user": "U12345"},
        )
        assert msg.message_type == "command"
        assert msg.content == "/start-workflow"

    def test_timestamp_defaults_to_utcnow(self):
        session = self._make_session()
        before = datetime.now(timezone.utc)
        msg = ChannelMessage(
            id="msg-004",
            message_type="text_input",
            content="ping",
            session=session,
            raw_payload={},
        )
        after = datetime.now(timezone.utc)
        assert before <= msg.timestamp <= after

    def test_explicit_timestamp(self):
        session = self._make_session()
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        msg = ChannelMessage(
            id="msg-005",
            message_type="text_input",
            content="test",
            session=session,
            raw_payload={},
            timestamp=ts,
        )
        assert msg.timestamp == ts


class TestChannelFile:
    def test_file_without_source_url(self):
        f = ChannelFile(
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            content=b"%PDF-1.4 binary content",
        )
        assert f.filename == "report.pdf"
        assert f.content_type == "application/pdf"
        assert f.size_bytes == 1024
        assert f.content == b"%PDF-1.4 binary content"
        assert f.source_url is None

    def test_file_with_source_url(self):
        f = ChannelFile(
            filename="image.png",
            content_type="image/png",
            size_bytes=4096,
            content=b"\x89PNG\r\n\x1a\n",
            source_url="https://files.slack.com/files/U123/F456/image.png",
        )
        assert f.filename == "image.png"
        assert f.source_url == "https://files.slack.com/files/U123/F456/image.png"

    def test_empty_content(self):
        f = ChannelFile(
            filename="empty.txt",
            content_type="text/plain",
            size_bytes=0,
            content=b"",
        )
        assert f.content == b""
        assert f.size_bytes == 0


class TestHitlGateConfig:
    def test_human_review_gate_config(self):
        config = HitlGateConfig(
            node_id="review-step-1",
            instructions="Please review the generated content.",
            context={"document": "draft-v2.docx", "summary": "AI-generated draft"},
        )
        assert config.node_id == "review-step-1"
        assert config.instructions == "Please review the generated content."
        assert config.context == {"document": "draft-v2.docx", "summary": "AI-generated draft"}
        assert config.options == ["approve", "reject", "revise"]
        assert config.allow_comment is True
        assert config.prompt is None
        assert config.input_type == "text"
        assert config.input_schema is None
        assert config.placeholder is None

    def test_input_gate_config(self):
        config = HitlGateConfig(
            node_id="gather-info",
            instructions="Please provide the required information.",
            prompt="What is the customer name?",
            input_type="text",
            placeholder="Enter customer name...",
        )
        assert config.node_id == "gather-info"
        assert config.prompt == "What is the customer name?"
        assert config.input_type == "text"
        assert config.placeholder == "Enter customer name..."

    def test_structured_input_gate_config(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
            },
            "required": ["name"],
        }
        config = HitlGateConfig(
            node_id="structured-input",
            instructions="Fill out the form.",
            input_type="form",
            input_schema=schema,
        )
        assert config.node_id == "structured-input"
        assert config.input_type == "form"
        assert config.input_schema == schema

    def test_default_options(self):
        config = HitlGateConfig(node_id="approval-gate")
        assert config.options == ["approve", "reject", "revise"]

    def test_custom_options(self):
        config = HitlGateConfig(
            node_id="custom-gate",
            options=["yes", "no", "maybe"],
        )
        assert config.options == ["yes", "no", "maybe"]

    def test_mutable_options_defaults_are_independent(self):
        c1 = HitlGateConfig(node_id="gate-1")
        c2 = HitlGateConfig(node_id="gate-2")
        c1.options.append("skip")
        assert "skip" not in c2.options

    def test_allow_comment_false(self):
        config = HitlGateConfig(
            node_id="no-comment-gate",
            allow_comment=False,
        )
        assert config.allow_comment is False
