from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from primer_sdk.events import AGUIEvent
from primer_sdk.models.presentation import (
    ChannelFile,
    ChannelMessage,
    ChannelSession,
    HitlGateConfig,
)


class ChannelAdapterPort(ABC):
    """Outbound port representing a pluggable channel integration (e.g. Slack, Teams).

    Participants implement this ABC to connect a new messaging channel to the
    platform.  The platform invokes these methods when it needs to communicate
    with the channel, or delegates inbound webhook payloads to it for parsing.
    """

    @property
    @abstractmethod
    def channel_type(self) -> str:
        """Short identifier for this channel (e.g. ``'slack'``, ``'teams'``)."""
        ...

    @abstractmethod
    async def send_event(self, event: AGUIEvent, session: ChannelSession) -> None:
        """Forward an AG-UI event to the channel for a given session.

        Args:
            event: The AG-UI event to deliver.
            session: The channel session identifying the recipient.
        """
        ...

    @abstractmethod
    async def send_error(self, error: str, session: ChannelSession) -> None:
        """Deliver an error message to a channel session.

        Args:
            error: Human-readable error description.
            session: The channel session identifying the recipient.
        """
        ...

    @abstractmethod
    async def render_hitl_gate(
        self,
        gate_type: str,
        gate_config: HitlGateConfig,
        session: ChannelSession,
    ) -> None:
        """Render a human-in-the-loop gate prompt to the channel.

        Args:
            gate_type: The type of gate (e.g. ``'approval'``, ``'input'``).
            gate_config: Configuration describing the gate UI and options.
            session: The channel session to render the gate in.
        """
        ...

    @abstractmethod
    async def receive_message(self, raw_payload: dict) -> ChannelMessage:
        """Parse an inbound message payload from the channel.

        Args:
            raw_payload: Raw webhook payload from the channel platform.

        Returns:
            Normalised :class:`~primer_sdk.models.presentation.ChannelMessage`.
        """
        ...

    @abstractmethod
    async def receive_file(self, raw_payload: dict) -> ChannelFile | None:
        """Parse an inbound file upload payload, if present.

        Args:
            raw_payload: Raw webhook payload from the channel platform.

        Returns:
            :class:`~primer_sdk.models.presentation.ChannelFile` if a file
            was uploaded, otherwise ``None``.
        """
        ...

    @abstractmethod
    async def resolve_session(self, raw_payload: dict) -> ChannelSession:
        """Identify or create the channel session from an inbound payload.

        Args:
            raw_payload: Raw webhook payload from the channel platform.

        Returns:
            The :class:`~primer_sdk.models.presentation.ChannelSession`
            associated with this inbound event.
        """
        ...

    @abstractmethod
    async def register_webhook(self, callback_url: str) -> None:
        """Register this adapter's webhook endpoint with the channel platform.

        Args:
            callback_url: The public URL the channel should POST events to.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify that the channel integration is reachable and functional.

        Returns:
            ``True`` if the channel is healthy, ``False`` otherwise.
        """
        ...


class ChannelSessionStorePort(ABC):
    """Outbound port for persisting and querying channel sessions."""

    @abstractmethod
    async def bind(self, session: ChannelSession, workflow_run_id: UUID) -> None:
        """Associate a channel session with an active workflow run.

        Args:
            session: The channel session to bind.
            workflow_run_id: The workflow run to associate with.
        """
        ...

    @abstractmethod
    async def unbind(self, workflow_run_id: UUID) -> None:
        """Remove the association between a channel session and a workflow run.

        Args:
            workflow_run_id: The workflow run whose session binding should be removed.
        """
        ...

    @abstractmethod
    async def lookup(
        self,
        channel_type: str,
        channel_user_id: str,
        channel_conversation_id: str,
    ) -> ChannelSession | None:
        """Look up a channel session by its channel-native identifiers.

        Args:
            channel_type: The channel type (e.g. ``'slack'``).
            channel_user_id: The user's identifier within the channel.
            channel_conversation_id: The conversation identifier within the channel.

        Returns:
            The matching :class:`~primer_sdk.models.presentation.ChannelSession`,
            or ``None`` if no session exists.
        """
        ...

    @abstractmethod
    async def get_by_workflow_run(self, workflow_run_id: UUID) -> list[ChannelSession]:
        """Retrieve all channel sessions bound to a workflow run.

        Args:
            workflow_run_id: The workflow run to look up.

        Returns:
            List of :class:`~primer_sdk.models.presentation.ChannelSession`
            instances bound to this run.
        """
        ...

    @abstractmethod
    async def create(
        self,
        channel_type: str,
        channel_user_id: str,
        channel_conversation_id: str,
        platform_user_id: UUID | None = None,
        org_id: UUID | None = None,
    ) -> ChannelSession:
        """Create and persist a new channel session.

        Args:
            channel_type: The channel type (e.g. ``'slack'``).
            channel_user_id: The user's identifier within the channel.
            channel_conversation_id: The conversation identifier within the channel.
            platform_user_id: Optional platform user UUID to associate.
            org_id: Optional organisation UUID to associate.

        Returns:
            The newly created :class:`~primer_sdk.models.presentation.ChannelSession`.
        """
        ...
