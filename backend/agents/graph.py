from __future__ import annotations

import asyncio
import queue
import threading

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from backend.agents.orchestrator import build_supervisor

_graph = None

# Supervisor astream_events 전용 루프 — _bg_loop(서브에이전트)와 분리해 데드락 방지
_stream_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
threading.Thread(target=_stream_loop.run_forever, daemon=True).start()


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_supervisor()
    return _graph


def get_graph_state(thread_id: str):
    """현재 그래프 상태를 반환한다 (interrupt·messages 확인용)."""
    config = {"configurable": {"thread_id": thread_id}}
    return get_graph().get_state(config)


def stream_graph_events(
    user_input: str,
    thread_id: str,
    history: list[BaseMessage] | None = None,
):
    """supervisor astream_events를 동기 이터레이터로 노출한다.

    Streamlit 메인 스레드(동기)에서 호출 가능.
    내부적으로 _stream_loop(별도 스레드)에서 async 실행 후 queue로 전달.
    서브에이전트가 사용하는 _bg_loop와 분리되어 데드락이 없다.
    """
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    messages = [HumanMessage(content=user_input)]

    event_queue: queue.Queue = queue.Queue()
    _DONE = object()

    async def _producer():
        try:
            async for event in get_graph().astream_events(
                {"messages": messages}, config=config, version="v2"
            ):
                event_queue.put(event)
        except Exception as exc:
            event_queue.put(exc)
        finally:
            event_queue.put(_DONE)

    asyncio.run_coroutine_threadsafe(_producer(), _stream_loop)

    while True:
        item = event_queue.get()
        if item is _DONE:
            break
        if isinstance(item, Exception):
            raise item
        yield item


def run_graph(user_input: str, thread_id: str) -> dict:
    """HitL resume 이후 등 비스트리밍이 필요한 경우에 사용."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    return get_graph().invoke(
        {"messages": [HumanMessage(content=user_input)]},
        config=config,
    )


def resume_graph(thread_id: str, value: object) -> dict:
    """interrupt()로 중단된 그래프를 재개한다."""
    config = {"configurable": {"thread_id": thread_id}}
    return get_graph().invoke(Command(resume=value), config=config)
