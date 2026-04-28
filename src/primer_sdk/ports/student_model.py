from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from primer_sdk.models.student_model import (
    Cohort,
    CohortSnapshot,
    IngestResult,
    PreferenceSignal,
)

# ---------------------------------------------------------------------------
# Inbound ports
# ---------------------------------------------------------------------------


class IngestSignalPort(ABC):
    """Inbound port for ingesting preference signals into the student model."""

    @abstractmethod
    async def ingest(self, signal: PreferenceSignal) -> None:
        """Ingest a single preference signal.

        Args:
            signal: The preference signal to ingest.
        """
        ...

    @abstractmethod
    async def ingest_batch(self, signals: list[PreferenceSignal]) -> IngestResult:
        """Ingest a batch of preference signals.

        Args:
            signals: List of preference signals to ingest.

        Returns:
            :class:`~primer_sdk.models.student_model.IngestResult` summarising
            how many records were processed, skipped, or failed.
        """
        ...


class QueryCohortPort(ABC):
    """Inbound port for querying cohort and preference data."""

    @abstractmethod
    async def get_user_cohorts(self, user_id: UUID, org_id: UUID) -> list[Cohort]:
        """Return all cohorts a user belongs to within an organisation.

        Args:
            user_id: The user to query.
            org_id: The organisation scope.

        Returns:
            List of :class:`~primer_sdk.models.student_model.Cohort` instances.
        """
        ...

    @abstractmethod
    async def get_cohort_preferences(self, cohort_id: UUID) -> dict[str, Any]:
        """Return aggregated preference data for a cohort.

        Args:
            cohort_id: The cohort to query.

        Returns:
            Dictionary of preference key-value pairs.
        """
        ...

    @abstractmethod
    async def get_user_effective_preferences(self, user_id: UUID, org_id: UUID) -> dict[str, Any]:
        """Return the effective (merged) preferences for a user across all cohorts.

        Args:
            user_id: The user to query.
            org_id: The organisation scope.

        Returns:
            Dictionary of merged preference key-value pairs.
        """
        ...


class ManageCohortPort(ABC):
    """Inbound port for managing cohort lifecycle."""

    @abstractmethod
    async def create_cohort(
        self,
        org_id: UUID,
        name: str,
        strategy_type: str,
        config: dict[str, Any],
    ) -> Cohort:
        """Create a new cohort within an organisation.

        Args:
            org_id: The organisation that owns the cohort.
            name: Human-readable cohort name.
            strategy_type: The clustering/assignment strategy to use.
            config: Strategy-specific configuration.

        Returns:
            The newly created :class:`~primer_sdk.models.student_model.Cohort`.
        """
        ...

    @abstractmethod
    async def list_cohorts(self, org_id: UUID) -> list[Cohort]:
        """List all cohorts belonging to an organisation.

        Args:
            org_id: The organisation to query.

        Returns:
            List of :class:`~primer_sdk.models.student_model.Cohort` instances.
        """
        ...

    @abstractmethod
    async def get_cohort(self, cohort_id: UUID) -> Cohort:
        """Retrieve a single cohort by ID.

        Args:
            cohort_id: The cohort to retrieve.

        Returns:
            The :class:`~primer_sdk.models.student_model.Cohort`.
        """
        ...

    @abstractmethod
    async def delete_cohort(self, cohort_id: UUID) -> None:
        """Delete a cohort.

        Args:
            cohort_id: The cohort to delete.
        """
        ...

    @abstractmethod
    async def force_evolution(self, cohort_id: UUID) -> CohortSnapshot:
        """Trigger an immediate evolution cycle for a cohort.

        Args:
            cohort_id: The cohort to evolve.

        Returns:
            A :class:`~primer_sdk.models.student_model.CohortSnapshot` taken
            after the evolution completes.
        """
        ...


# ---------------------------------------------------------------------------
# Outbound ports
# ---------------------------------------------------------------------------


class CohortStrategyPort(ABC):
    """Outbound port representing a pluggable cohort assignment/evolution strategy."""

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Identifier for this strategy (e.g. ``'similarity'``, ``'kmeans'``)."""
        ...

    @abstractmethod
    async def assign(self, user_id: UUID, signals: list[PreferenceSignal]) -> list[UUID]:
        """Assign a user to cohorts based on their signals.

        Args:
            user_id: The user to assign.
            signals: Recent preference signals for this user.

        Returns:
            List of cohort UUIDs the user should belong to.
        """
        ...

    @abstractmethod
    async def evolve(self, cohort_id: UUID, new_signals: list[PreferenceSignal]) -> dict[str, Any]:
        """Update cohort aggregate state with new signals.

        Args:
            cohort_id: The cohort to evolve.
            new_signals: New preference signals to incorporate.

        Returns:
            Updated aggregate state dictionary.
        """
        ...

    @abstractmethod
    async def should_reorganize(self, cohort_id: UUID) -> bool:
        """Determine whether the cohort needs a full reorganisation.

        Args:
            cohort_id: The cohort to evaluate.

        Returns:
            ``True`` if reorganisation is recommended.
        """
        ...

    @abstractmethod
    async def reorganize(self, org_id: UUID) -> dict[str, Any]:
        """Perform a full reorganisation of all cohorts in an organisation.

        Args:
            org_id: The organisation whose cohorts should be reorganised.

        Returns:
            Summary of changes made during reorganisation.
        """
        ...


class SignalStorePort(ABC):
    """Outbound port for persisting and querying preference signals."""

    @abstractmethod
    async def store(self, signal: PreferenceSignal) -> None:
        """Persist a preference signal.

        Args:
            signal: The signal to store.
        """
        ...

    @abstractmethod
    async def query(
        self,
        user_id: UUID | None = None,
        org_id: UUID | None = None,
        signal_type: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[PreferenceSignal]:
        """Query stored preference signals with optional filters.

        Args:
            user_id: Filter by user.
            org_id: Filter by organisation.
            signal_type: Filter by signal type string.
            since: Return only signals at or after this timestamp.
            limit: Maximum number of results to return.

        Returns:
            List of matching :class:`~primer_sdk.models.student_model.PreferenceSignal`
            instances.
        """
        ...


class CohortStorePort(ABC):
    """Outbound port for persisting cohort data and snapshots."""

    @abstractmethod
    async def save_cohort(self, cohort: Cohort) -> None:
        """Persist (insert or update) a cohort.

        Args:
            cohort: The cohort to save.
        """
        ...

    @abstractmethod
    async def get_cohort(self, cohort_id: UUID) -> Cohort | None:
        """Retrieve a cohort by ID, or ``None`` if not found.

        Args:
            cohort_id: The cohort to retrieve.

        Returns:
            The :class:`~primer_sdk.models.student_model.Cohort` or ``None``.
        """
        ...

    @abstractmethod
    async def get_user_cohorts(self, user_id: UUID, org_id: UUID) -> list[Cohort]:
        """Retrieve all cohorts that include a given user within an organisation.

        Args:
            user_id: The user to look up.
            org_id: The organisation scope.

        Returns:
            List of :class:`~primer_sdk.models.student_model.Cohort` instances.
        """
        ...

    @abstractmethod
    async def save_snapshot(self, cohort_id: UUID, snapshot: CohortSnapshot) -> None:
        """Append a snapshot to a cohort's history.

        Args:
            cohort_id: The cohort that owns the snapshot.
            snapshot: The snapshot to persist.
        """
        ...
