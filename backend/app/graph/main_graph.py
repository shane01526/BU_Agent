"""父 graph + PostgresSaver singleton（technical_design.md §3.2.1 / §3.9）。

M2 範圍：Explore subgraph 直接嵌入父 graph；Consult 尚為空殼，
route_mode 僅判斷 explore / consult 兩路。
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from app.graph.consult.subgraph import build_consult_subgraph
from app.graph.explore.subgraph import build_explore_subgraph
from app.graph.shared.state import GraphState


def _build_main_graph() -> StateGraph:
    g = StateGraph(GraphState)

    explore = build_explore_subgraph().compile()
    consult = build_consult_subgraph().compile()

    g.add_node("explore", explore)
    g.add_node("consult", consult)

    def route(state: GraphState) -> str:
        # done / cold 不再進任何 subgraph;但 graph 入口被呼叫前外層
        # service 通常已直接寫 state,這裡兜底走 consult 讓它自己判斷後 END
        if state.mode in ("consult_step1", "consult_step2", "submit", "done"):
            return "consult"
        return "explore"

    g.add_conditional_edges(START, route, ["explore", "consult"])
    g.add_edge("explore", END)
    g.add_edge("consult", END)

    return g


_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """PostgresSaver singleton；首次呼叫時 setup()。"""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer
    _pool = AsyncConnectionPool(
        conninfo=settings.langgraph_checkpoint_url,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    await _checkpointer.setup()
    return _checkpointer


@lru_cache(maxsize=1)
def _compiled_main():
    return _build_main_graph()


async def get_graph():
    """回 compiled main graph（含 checkpointer）。"""
    checkpointer = await get_checkpointer()
    return _compiled_main().compile(checkpointer=checkpointer)


async def close_graph() -> None:
    global _pool, _checkpointer
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None
