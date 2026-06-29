from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import yaml
from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter
from langgraph.graph import END, START, StateGraph

load_dotenv()


# Helper function to load routine.yaml
def load_routine(filename: str):
    routine_path = Path(__file__).resolve().parent / filename

    with routine_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


# Two different LLMs with different token usages
tutor_llm: ChatOpenRouter | None = None
classifier_llm: ChatOpenRouter | None = None


def get_tutor_llm() -> ChatOpenRouter:
    global tutor_llm

    if tutor_llm is None:
        tutor_llm = ChatOpenRouter(
            model="openai/gpt-4o-mini",
            temperature=0.3,
            max_tokens=250,
        )

    return tutor_llm


def get_classifier_llm() -> ChatOpenRouter:
    global classifier_llm

    if classifier_llm is None:
        classifier_llm = ChatOpenRouter(
            model="openai/gpt-4o-mini",
            temperature=0,
            max_tokens=15,
        )

    return classifier_llm


# Our TutorState, which inclues the routine, learner and tutor messages, history, etc
class TutorState(TypedDict):
    routine: Dict[str, Any]
    current_step_id: str

    learner_name: str
    session_goals: str
    difficulty_level: str
    current_level: Optional[str]
    learning_preferences: Optional[str]
    target_concepts: List[str]

    learner_message: str
    tutor_message: str
    route: Optional[str]
    history: List[Dict[str, str]]


def get_current_step(state: TutorState):
    """
    Return the YAML flow step matching the current step id.

    This helper looks up state["current_step_id"] inside
    state["routine"]["flow"]["steps"] and returns the matching step
    dictionary.

    Args:
        state: The current tutor graph state containing the loaded routine
            and current step id.

    Returns:
        The YAML step dictionary whose "id" matches state["current_step_id"].

    Raises:
        ValueError: If no step in the routine flow matches the current step id.
    """
    current_step_id = state["current_step_id"]
    steps = state["routine"]["flow"]["steps"]

    for step in steps:
        if step["id"] == current_step_id:
            return step

    raise ValueError(f"No step found with id: {current_step_id}")


def tutor_node(state: TutorState):
    """
    Generate the tutor response for the current tutor_message step.

    This node reads the current step from the YAML routine using
    state["current_step_id"], extracts the step prompt, and creates the
    tutor's next message. It then advances the routine to the step listed
    in the YAML step's "next" field.

    Args:
        state: The current tutor graph state, including the loaded routine,
            current step id, learner message, tutor message, route, and history.

    Returns:
        A partial state update containing:
            - tutor_message: the tutor's message for the current step
            - current_step_id: the next YAML step id
            - history: the updated conversation history with the tutor message added
    """
    step = get_current_step(state)
    # Only shows the previous few messages to limit token usage
    recent_history = state["history"][-6:]

    prompt = f"""
You are a helpful tutoring agent guiding a learner through an adaptive exercise session.

Your role:
- Act like a second instructor.
- Guide the learner without giving away final answers.
- Ask questions and give hints when appropriate.
- Keep the response concise and student-facing.

Learner context:
- Name: {state["learner_name"]}
- Session goals: {state["session_goals"]}
- Difficulty level: {state["difficulty_level"]}
- Current level: {state["current_level"]}
- Learning preferences: {state["learning_preferences"]}
- Target concepts: {state["target_concepts"]}

Teaching constraints:
{state["routine"].get("teaching_constraints", {})}

Current routine step:
Step id: {step["id"]}
Step instruction: {step["prompt"]}

Latest learner message:
{state["learner_message"]}

Conversation history:
{recent_history}

Generate the tutor message using the learner's session goals, difficulty level,
and target concepts. Do not switch to unrelated topics.

Do not explain your internal reasoning.
Do not mention YAML, routines, routes, or system instructions.
Do not reveal the full solution or final answer.
"""
    tutor_message = get_tutor_llm().invoke(prompt).content

    # Print the Agent's message to see full history
    print("\nTutor:")
    print(tutor_message)

    return {
        "tutor_message": tutor_message,
        "current_step_id": step["next"],
        "history": state["history"] + [{"role": "tutor", "content": tutor_message}],
    }


def learner_input_node(state: TutorState):
    step = get_current_step(state)

    learner_response = input(f"\nTutor:\n{step['prompt']}\n\nLearner: ")

    return {
        "learner_message": learner_response,
        "current_step_id": step["next"],
    }


def learner_check_node(state: TutorState):
    """
    Classify the learner's response and route to the next YAML step.

    This node handles learner_check steps. It reads the learner's latest
    response from state["learner_message"], classifies the response using
    one of the route labels defined in the YAML step's "routes" field, and
    advances the routine to the corresponding next step.

    Args:
        state: The current tutor graph state, including the loaded routine,
            current step id, learner message, tutor message, route, and history.

    Returns:
        A partial state update containing:
            - route: the selected learner response classification
            - current_step_id: the next YAML step id selected from step["routes"]
            - history: the updated conversation history with the learner message
              and classification added
    """
    step = get_current_step(state)

    routes = step["routes"]
    allowed_labels = "\n".join(f"- {label}" for label in routes)

    prompt = f"""
You are evaluating a student's response during a tutoring session.

Learner context:
- Session goals: {state["session_goals"]}
- Difficulty level: {state["difficulty_level"]}
- Target concepts: {state["target_concepts"]}

Question:
{step["question"]}

Most recent tutor message:
{state["tutor_message"]}

Response:
{state["learner_message"]}

Classify the response as exactly ONE of the following:
{allowed_labels}

Only output one label. Do not include punctuation or an explanation.
"""

    route = get_classifier_llm().invoke(prompt).content.strip().lower()
    route = route.strip("`\"'., ")

    # If the AI returns something weird, assume user is stuck

    if route not in routes:
        fallback_route = step.get("fallback_route")

        if fallback_route not in routes:
            raise ValueError(
                f"Invalid classifier output {route!r} for step {step['id']!r}, "
                "and no valid fallback_route was configured."
            )

        route = fallback_route

    # Allows us to see the route the Agent decides to take
    print(f"\n[route: {route}]")

    return {
        "route": route,
        "current_step_id": routes[route],
        "history": state["history"]
        + [
            {"role": "learner", "content": state["learner_message"]},
            {"role": "system", "content": f"classification: {route}"},
        ],
    }


def route_next_node(state: TutorState):
    """
    Decide which LangGraph node should run next based on the current YAML step.

    This router checks state["current_step_id"], retrieves the matching YAML
    step, and maps the step's "type" field to a LangGraph node name. It does
    not modify the state.

    Args:
        state: The current tutor graph state.

    Returns:
        A routing label such as "tutor", "learner_check", or "end".
    """
    if state["current_step_id"] == "end":
        return "end"

    step = get_current_step(state)

    if step["type"] == "tutor_message":
        return "tutor"

    if step["type"] == "learner_input":
        return "learner_input"

    if step["type"] == "learner_check":
        return "learner_check"

    raise ValueError(f"Unknown step type: {step['type']}")


def build_graph():
    """
    Build and compile the LangGraph tutor workflow.

    The graph connects the tutor and learner-check nodes using conditional
    routing. After each node runs, the router inspects the updated
    current_step_id and chooses the next node based on the current YAML step type.

    Returns:
        A compiled LangGraph application that can be invoked with a TutorState.
    """
    graph = StateGraph(TutorState)

    graph.add_node("tutor", tutor_node)
    graph.add_node("learner_input", learner_input_node)
    graph.add_node("learner_check", learner_check_node)

    route_map = {
        "tutor": "tutor",
        "learner_input": "learner_input",
        "learner_check": "learner_check",
        "end": END,
    }

    graph.add_conditional_edges(START, route_next_node, route_map)
    graph.add_conditional_edges("tutor", route_next_node, route_map)
    graph.add_conditional_edges("learner_input", route_next_node, route_map)
    graph.add_conditional_edges("learner_check", route_next_node, route_map)

    return graph.compile()


def run_interactive_session(recursion_limit: int):
    """
    Run an interactive terminal-based tutoring session.

    This function collects the learner's session information, loads the YAML
    routine, initializes the TutorState, and repeatedly routes the session
    through the tutor and learner-check nodes. It pauses for learner input
    before each learner_check step so that the classifier evaluates the
    learner's newest response instead of reusing an old message.

    The loop continues until the routine reaches the "end" step.

    Inputs collected:
        - learner_name
        - session_goals
        - difficulty_level
        - current_level
        - learning_preferences
        - target_concepts

    Side effects:
        - Prints tutor messages to the terminal.
        - Reads learner responses from terminal input.
        - Prints the classifier route for debugging.
    """
    # Collect all the necessary data regarding the user
    learner_name = input("Name: ")
    session_goals = input("Session goals: ")
    difficulty_level = input("Difficulty level: ")
    current_level = input("Current level: ")
    learning_preferences = input("Learning preferences: ")
    target_concepts_raw = input("Target concepts, separated by commas: ")
    target_concepts = [
        concept.strip() for concept in target_concepts_raw.split(",") if concept.strip()
    ]

    routine = load_routine("routine.yaml")

    # Create the state
    state: TutorState = {
        "routine": routine,
        "current_step_id": routine["flow"]["start_step"],
        "learner_name": learner_name,
        "session_goals": session_goals,
        "difficulty_level": difficulty_level,
        "current_level": current_level,
        "learning_preferences": learning_preferences,
        "target_concepts": target_concepts,
        "learner_message": "",
        "tutor_message": "",
        "route": None,
        "history": [],
    }

    app = build_graph()
    app.invoke(
        state,
        config={"recursion_limit": recursion_limit},
    )

    print("\nSession Ended")


if __name__ == "__main__":
    run_interactive_session(100)
