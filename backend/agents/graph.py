from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from backend.agents.orchestrator import build_supervisor

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_supervisor()
    return _graph


def run_graph(user_input: str, thread_id: str, user_preferences: dict | None = None) -> dict:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    return get_graph().invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )


def resume_graph(thread_id: str, value: object) -> dict:
    """interrupt()로 중단된 그래프를 재개한다."""
    config = {"configurable": {"thread_id": thread_id}}
    return get_graph().invoke(Command(resume=value), config=config)
