from __future__ import annotations

from uuid import uuid4

import pytest

from primer_sdk.ports.presentation import (
    ChannelAdapterPort,
    ChannelSessionStorePort,
)

# ---------------------------------------------------------------------------
# ABC instantiation tests
# ---------------------------------------------------------------------------


class TestChannelAdapterPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ChannelAdapterPort()  # type: ignore[abstract]


class TestChannelSessionStorePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ChannelSessionStorePort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete implementation tests
# ---------------------------------------------------------------------------


class ConcreteChannelAdapterPort(ChannelAdapterPort):
    @property
    def channel_type(self) -> str:
        return "slack"

    async def send_event(self, event, session):
        return None

    async def send_error(self, error, session):
        return None

    async def render_hitl_gate(self, gate_type, gate_config, session):
        return None

    async def receive_message(self, raw_payload):
        from primer_sdk.models.presentation import ChannelMessage, ChannelSession

        session = ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U123",
            channel_conversation_id="C456",
        )
        return ChannelMessage(
            id="msg-1",
            message_type="text_input",
            content="hello",
            session=session,
            raw_payload=raw_payload,
        )

    async def receive_file(self, raw_payload):
        return None

    async def resolve_session(self, raw_payload):
        from primer_sdk.models.presentation import ChannelSession

        return ChannelSession(
            id=uuid4(),
            channel_type="slack",
            channel_user_id="U123",
            channel_conversation_id="C456",
        )

    async def register_webhook(self, callback_url):
        return None

    async def health_check(self):
        return True


class TestConcreteChannelAdapterPort:
    def test_can_instantiate_concrete_subclass(self):
        adapter = ConcreteChannelAdapterPort()
        assert isinstance(adapter, ChannelAdapterPort)

    def test_channel_type_property_returns_value(self):
        adapter = ConcreteChannelAdapterPort()
        assert adapter.channel_type == "slack"

    def test_channel_type_is_string(self):
        adapter = ConcreteChannelAdapterPort()
        assert isinstance(adapter.channel_type, str)


class ConcreteChannelSessionStorePort(ChannelSessionStorePort):
    async def bind(self, session, workflow_run_id):
        return None

    async def unbind(self, workflow_run_id):
        return None

    async def lookup(self, channel_type, channel_user_id, channel_conversation_id):
        return None

    async def get_by_workflow_run(self, workflow_run_id):
        return []

    async def create(
        self,
        channel_type,
        channel_user_id,
        channel_conversation_id,
        platform_user_id=None,
        org_id=None,
    ):
        from primer_sdk.models.presentation import ChannelSession

        return ChannelSession(
            id=uuid4(),
            channel_type=channel_type,
            channel_user_id=channel_user_id,
            channel_conversation_id=channel_conversation_id,
            platform_user_id=platform_user_id,
            org_id=org_id,
        )


class TestConcreteChannelSessionStorePort:
    def test_can_instantiate_concrete_subclass(self):
        store = ConcreteChannelSessionStorePort()
        assert isinstance(store, ChannelSessionStorePort)
