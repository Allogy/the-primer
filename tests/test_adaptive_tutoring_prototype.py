from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

# The prototype depends on optional extras (langgraph, langchain-openrouter).
# Skip the whole module when they are not installed: `uv sync --extra adaptive-tutoring`.
routine_graph = pytest.importorskip("examples.adaptive_tutoring_prototype.routine_graph")


class FakeLLM:
    """Return a fixed response without making an API request."""

    def __init__(self, content: str) -> None:
        self.content = content
        self.last_prompt: str | None = None

    def invoke(self, prompt: str) -> SimpleNamespace:
        self.last_prompt = prompt
        return SimpleNamespace(content=self.content)


@pytest.fixture
def routine() -> dict[str, Any]:
    """Load a fresh copy of the runnable v1 routine for each test."""

    return routine_graph.load_routine("routine.yaml")


def make_state(
    routine: dict[str, Any],
    step_id: str,
    learner_message: str = "",
) -> dict[str, Any]:
    """Create a minimal valid TutorState for unit tests."""

    return {
        "routine": routine,
        "current_step_id": step_id,
        "learner_name": "Test Learner",
        "session_goals": "Physics",
        "difficulty_level": "Easy",
        "current_level": "Beginner",
        "learning_preferences": "Quick",
        "target_concepts": ["Energy"],
        "learner_message": learner_message,
        "tutor_message": "Previous tutor message",
        "route": None,
        "history": [],
    }


def test_routine_references_are_valid(routine: dict[str, Any]) -> None:
    """Every next step, route target, and fallback must be valid."""

    steps = routine["flow"]["steps"]
    step_ids = [step["id"] for step in steps]
    known_ids = set(step_ids)

    assert len(step_ids) == len(known_ids)
    assert routine["flow"]["start_step"] in known_ids

    for step in steps:
        if "next" in step:
            assert step["next"] in known_ids

        for destination in step.get("routes", {}).values():
            assert destination in known_ids

        if step["type"] == "learner_check":
            assert "routes" in step
            assert "fallback_route" in step
            assert step["fallback_route"] in step["routes"]


def test_load_routine_does_not_depend_on_working_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Routine loading must resolve relative to routine_graph.py."""

    monkeypatch.chdir(tmp_path)

    loaded = routine_graph.load_routine("routine.yaml")

    assert loaded["routine_id"] == "adaptive_exercise_session_v1"


def test_routine_v2_parses_as_design_artifact() -> None:
    """The non-runnable v2 design artifact should still contain valid YAML."""

    loaded = routine_graph.load_routine("routine_v2.yaml")

    assert isinstance(loaded, dict)
    assert "flow" in loaded


def test_get_current_step_returns_matching_step(
    routine: dict[str, Any],
) -> None:
    state = make_state(routine, "present_exercise")

    step = routine_graph.get_current_step(state)

    assert step["id"] == "present_exercise"
    assert step["type"] == "tutor_message"


def test_get_current_step_rejects_unknown_step(
    routine: dict[str, Any],
) -> None:
    state = make_state(routine, "missing_step")

    with pytest.raises(ValueError, match="No step found with id"):
        routine_graph.get_current_step(state)


@pytest.mark.parametrize(
    ("step_id", "expected_route"),
    [
        ("present_exercise", "tutor"),
        ("wait_for_learner_response", "learner_input"),
        ("evaluate_response", "learner_check"),
        ("check_another_exercise", "learner_check"),
        ("end", "end"),
    ],
)
def test_route_next_node(
    routine: dict[str, Any],
    step_id: str,
    expected_route: str,
) -> None:
    state = make_state(routine, step_id)

    assert routine_graph.route_next_node(state) == expected_route


def test_route_next_node_rejects_unknown_type(
    routine: dict[str, Any],
) -> None:
    invalid_routine = deepcopy(routine)

    present_step = next(
        step for step in invalid_routine["flow"]["steps"] if step["id"] == "present_exercise"
    )
    present_step["type"] = "unknown_step_type"

    state = make_state(invalid_routine, "present_exercise")

    with pytest.raises(ValueError, match="Unknown step type"):
        routine_graph.route_next_node(state)


@pytest.mark.parametrize(
    ("step_id", "classifier_output", "expected_step"),
    [
        ("evaluate_response", "correct", "correct_feedback"),
        ("evaluate_response", "incorrect", "targeted_hint"),
        ("evaluate_response", "stuck", "scaffold"),
        ("evaluate_response", "off_topic", "redirect"),
        ("check_another_exercise", "yes", "present_exercise"),
        ("check_another_exercise", "no", "end"),
        ("check_another_exercise", "unclear", "another_exercise"),
    ],
)
def test_learner_check_uses_yaml_routes(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
    step_id: str,
    classifier_output: str,
    expected_step: str,
) -> None:
    fake_llm = FakeLLM(classifier_output)
    monkeypatch.setattr(
        routine_graph,
        "get_classifier_llm",
        lambda: fake_llm,
    )

    state = make_state(
        routine,
        step_id,
        learner_message="Test response",
    )

    result = routine_graph.learner_check_node(state)

    assert result["route"] == classifier_output
    assert result["current_step_id"] == expected_step
    assert result["history"][-2] == {
        "role": "learner",
        "content": "Test response",
    }
    assert result["history"][-1] == {
        "role": "system",
        "content": f"classification: {classifier_output}",
    }


@pytest.mark.parametrize(
    ("step_id", "expected_fallback", "expected_step"),
    [
        ("evaluate_response", "stuck", "scaffold"),
        ("check_another_exercise", "unclear", "another_exercise"),
    ],
)
def test_invalid_classifier_output_uses_yaml_fallback(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
    step_id: str,
    expected_fallback: str,
    expected_step: str,
) -> None:
    fake_llm = FakeLLM("not_a_valid_route")
    monkeypatch.setattr(
        routine_graph,
        "get_classifier_llm",
        lambda: fake_llm,
    )

    state = make_state(
        routine,
        step_id,
        learner_message="Ambiguous response",
    )

    result = routine_graph.learner_check_node(state)

    assert result["route"] == expected_fallback
    assert result["current_step_id"] == expected_step


def test_invalid_fallback_route_raises(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
) -> None:
    invalid_routine = deepcopy(routine)

    evaluate_step = next(
        step for step in invalid_routine["flow"]["steps"] if step["id"] == "evaluate_response"
    )
    evaluate_step["fallback_route"] = "missing_route"

    fake_llm = FakeLLM("not_a_valid_route")
    monkeypatch.setattr(
        routine_graph,
        "get_classifier_llm",
        lambda: fake_llm,
    )

    state = make_state(
        invalid_routine,
        "evaluate_response",
        learner_message="Test response",
    )

    with pytest.raises(ValueError, match="no valid fallback_route"):
        routine_graph.learner_check_node(state)


def test_classifier_prompt_uses_current_step_routes(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
) -> None:
    """Continuation labels must come from YAML rather than Python constants."""

    fake_llm = FakeLLM("no")
    monkeypatch.setattr(
        routine_graph,
        "get_classifier_llm",
        lambda: fake_llm,
    )

    state = make_state(
        routine,
        "check_another_exercise",
        learner_message="no",
    )

    routine_graph.learner_check_node(state)

    assert fake_llm.last_prompt is not None
    assert "- yes" in fake_llm.last_prompt
    assert "- no" in fake_llm.last_prompt
    assert "- unclear" in fake_llm.last_prompt
    assert "- correct" not in fake_llm.last_prompt
    assert "- incorrect" not in fake_llm.last_prompt


def test_learner_input_displays_yaml_prompt(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
) -> None:
    captured_prompt: dict[str, str] = {}

    def fake_input(prompt: str) -> str:
        captured_prompt["value"] = prompt
        return "My answer"

    monkeypatch.setattr("builtins.input", fake_input)

    state = make_state(routine, "wait_for_learner_response")
    result = routine_graph.learner_input_node(state)

    assert "Please respond to the current exercise" in captured_prompt["value"]
    assert result["learner_message"] == "My answer"
    assert result["current_step_id"] == "evaluate_response"


def test_continuation_input_displays_yaml_prompt(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
) -> None:
    captured_prompt: dict[str, str] = {}

    def fake_input(prompt: str) -> str:
        captured_prompt["value"] = prompt
        return "no"

    monkeypatch.setattr("builtins.input", fake_input)

    state = make_state(routine, "another_exercise")
    result = routine_graph.learner_input_node(state)

    assert "Would you like another exercise" in captured_prompt["value"]
    assert result["learner_message"] == "no"
    assert result["current_step_id"] == "check_another_exercise"


def test_tutor_node_uses_fake_model_and_advances_step(
    monkeypatch: pytest.MonkeyPatch,
    routine: dict[str, Any],
) -> None:
    fake_llm = FakeLLM("Here is a test exercise.")
    monkeypatch.setattr(
        routine_graph,
        "get_tutor_llm",
        lambda: fake_llm,
    )

    state = make_state(routine, "present_exercise")

    result = routine_graph.tutor_node(state)

    assert result["tutor_message"] == "Here is a test exercise."
    assert result["current_step_id"] == "wait_for_learner_response"
    assert result["history"][-1] == {
        "role": "tutor",
        "content": "Here is a test exercise.",
    }

    assert fake_llm.last_prompt is not None
    assert "Physics" in fake_llm.last_prompt
    assert "Energy" in fake_llm.last_prompt


def test_graph_compiles() -> None:
    """Compilation catches missing or stale LangGraph node references."""

    graph = routine_graph.build_graph()

    assert graph is not None
