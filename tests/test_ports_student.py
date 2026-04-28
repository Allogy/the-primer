from __future__ import annotations

from uuid import uuid4

import pytest

from primer_sdk.ports.student_model import (
    CohortStorePort,
    CohortStrategyPort,
    IngestSignalPort,
    ManageCohortPort,
    QueryCohortPort,
    SignalStorePort,
)

# ---------------------------------------------------------------------------
# ABC instantiation tests
# ---------------------------------------------------------------------------


class TestIngestSignalPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            IngestSignalPort()  # type: ignore[abstract]


class TestQueryCohortPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            QueryCohortPort()  # type: ignore[abstract]


class TestManageCohortPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ManageCohortPort()  # type: ignore[abstract]


class TestCohortStrategyPortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            CohortStrategyPort()  # type: ignore[abstract]


class TestSignalStorePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            SignalStorePort()  # type: ignore[abstract]


class TestCohortStorePortIsAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            CohortStorePort()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Concrete implementation tests
# ---------------------------------------------------------------------------


class ConcreteIngestSignalPort(IngestSignalPort):
    async def ingest(self, signal):
        return None

    async def ingest_batch(self, signals):
        from primer_sdk.models.student_model import IngestResult

        return IngestResult(processed=len(signals), skipped=0, failed=0)


class TestConcreteIngestSignalPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteIngestSignalPort()
        assert isinstance(port, IngestSignalPort)


class ConcreteQueryCohortPort(QueryCohortPort):
    async def get_user_cohorts(self, user_id, org_id):
        return []

    async def get_cohort_preferences(self, cohort_id):
        return {}

    async def get_user_effective_preferences(self, user_id, org_id):
        return {}


class TestConcreteQueryCohortPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteQueryCohortPort()
        assert isinstance(port, QueryCohortPort)


class ConcreteManageCohortPort(ManageCohortPort):
    async def create_cohort(self, org_id, name, strategy_type, config):
        from datetime import datetime, timezone

        from primer_sdk.models.student_model import Cohort

        return Cohort(
            id=uuid4(),
            org_id=org_id,
            name=name,
            description="",
            strategy_type=strategy_type,
            state_version=1,
            last_evolved=datetime.now(timezone.utc),
        )

    async def list_cohorts(self, org_id):
        return []

    async def get_cohort(self, cohort_id):
        from datetime import datetime, timezone

        from primer_sdk.models.student_model import Cohort

        return Cohort(
            id=cohort_id,
            org_id=uuid4(),
            name="test",
            description="",
            strategy_type="similarity",
            state_version=1,
            last_evolved=datetime.now(timezone.utc),
        )

    async def delete_cohort(self, cohort_id):
        return None

    async def force_evolution(self, cohort_id):
        from datetime import datetime, timezone

        from primer_sdk.models.student_model import CohortSnapshot

        return CohortSnapshot(
            timestamp=datetime.now(timezone.utc),
            member_count=0,
            aggregate_state={},
            drift_score=0.0,
        )


class TestConcreteManageCohortPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteManageCohortPort()
        assert isinstance(port, ManageCohortPort)


class ConcreteCohortStrategyPort(CohortStrategyPort):
    @property
    def strategy_type(self) -> str:
        return "similarity"

    async def assign(self, user_id, signals):
        return []

    async def evolve(self, cohort_id, new_signals):
        return {}

    async def should_reorganize(self, cohort_id):
        return False

    async def reorganize(self, org_id):
        return {}


class TestConcreteCohortStrategyPort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteCohortStrategyPort()
        assert isinstance(port, CohortStrategyPort)

    def test_strategy_type_property_returns_value(self):
        port = ConcreteCohortStrategyPort()
        assert port.strategy_type == "similarity"

    def test_strategy_type_is_string(self):
        port = ConcreteCohortStrategyPort()
        assert isinstance(port.strategy_type, str)


class ConcreteSignalStorePort(SignalStorePort):
    async def store(self, signal):
        return None

    async def query(self, user_id=None, org_id=None, signal_type=None, since=None, limit=None):
        return []


class TestConcreteSignalStorePort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteSignalStorePort()
        assert isinstance(port, SignalStorePort)


class ConcreteCohortStorePort(CohortStorePort):
    async def save_cohort(self, cohort):
        return None

    async def get_cohort(self, cohort_id):
        return None

    async def get_user_cohorts(self, user_id, org_id):
        return []

    async def save_snapshot(self, cohort_id, snapshot):
        return None


class TestConcreteCohortStorePort:
    def test_can_instantiate_concrete_subclass(self):
        port = ConcreteCohortStorePort()
        assert isinstance(port, CohortStorePort)
