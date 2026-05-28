from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END

from backend.agents.orchestrator import (
    WhatToDoState,
    intent_classifier, collect_results, output_validator, general_chat,
    route_by_intent,
)


def build_graph():
    from backend.agents.subagents.briefing_agent import briefing_agent_node
    from backend.agents.subagents.report_agent import report_agent_node
    from backend.agents.subagents.action_agent import action_agent_node
    from backend.agents.subagents.search_agent import search_agent_node

    g = StateGraph(WhatToDoState)

    g.add_node("intent_classifier", intent_classifier)
    g.add_node("briefing",         briefing_agent_node)
    g.add_node("report",           report_agent_node)
    g.add_node("action",           action_agent_node)
    g.add_node("search",           search_agent_node)
    g.add_node("chat",             general_chat)
    g.add_node("collect",          collect_results)
    g.add_node("output_validator", output_validator)

    g.add_edge(START, "intent_classifier")
    g.add_conditional_edges("intent_classifier", route_by_intent, {
        "briefing": "briefing",
        "report":   "report",
        "action":   "action",
        "search":   "search",
        "chat":     "chat",
    })
    for node in ["briefing", "report", "action", "search", "chat"]:
        g.add_edge(node, "collect")
    g.add_edge("collect", "output_validator")
    g.add_edge("output_validator", END)

    return g.compile(checkpointer=MemorySaver())


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_graph(
    user_input: str,
    thread_id: str,
    user_preferences: dict | None = None,
) -> WhatToDoState:
    initial: WhatToDoState = {
        "messages":         [HumanMessage(content=user_input)],  # add_messages가 누적
        "user_input":       user_input,
        "intent":           "",
        "work_items":       [],
        "results":          {},
        "error":            None,
        "retry_count":      0,
        "has_write_output": False,
        "user_preferences": user_preferences or {},
    }
    config = {"configurable": {"thread_id": thread_id}}
    return get_graph().invoke(initial, config=config)
