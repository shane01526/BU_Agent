"""Explore subgraph（technical_design.md §3.2.2）。

Invoke 語意：
- 第一次 invoke（history 空）→ 直接產第一題 → END
- 後續 invoke（剛被塞入 BU reply）→ extract_signals → cluster → score → converge_check
  - converge 判 cold ⇒ END（mode=cold）
  - converge 判 ready_to_handoff ⇒ emit_dual_output → END
  - 否則 ⇒ discovery_loop 產下一題 → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.explore import nodes
from app.graph.shared.state import GraphState


def build_explore_subgraph() -> StateGraph:
    g = StateGraph(GraphState)

    g.add_node("discovery_loop", nodes.discovery_loop)
    g.add_node("extract_signals", nodes.extract_signals)
    g.add_node("cluster_pain_points", nodes.cluster_pain_points)
    g.add_node("score_candidates", nodes.score_candidates)
    g.add_node("converge_check", nodes.converge_check)
    g.add_node("emit_dual_output", nodes.emit_dual_output)

    def entry(state: GraphState) -> str:
        """進入分支：
        1. 已 ready_to_handoff（BU 在 stage 5 點卡片觸發）→ 直接 emit_dual_output
        2. 有 BU reply → 走完整 pipeline
        3. 都沒有 → 出第一題
        """

        def role_of(h) -> str:
            return getattr(h, "role", None) or h.get("role", "")

        if state.ready_to_handoff:
            return "emit_dual_output"
        has_bu_reply = any(role_of(h) == "bu" for h in state.history)
        return "extract_signals" if has_bu_reply else "discovery_loop"

    g.add_conditional_edges(
        START, entry, ["extract_signals", "discovery_loop", "emit_dual_output"]
    )
    g.add_edge("discovery_loop", END)
    g.add_edge("extract_signals", "cluster_pain_points")
    g.add_edge("cluster_pain_points", "score_candidates")
    g.add_edge("score_candidates", "converge_check")

    def after_converge(state: GraphState) -> str:
        if state.mode == "cold":
            return END
        if state.ready_to_handoff:
            return "emit_dual_output"
        return "discovery_loop"

    g.add_conditional_edges(
        "converge_check", after_converge, [END, "emit_dual_output", "discovery_loop"]
    )
    g.add_edge("emit_dual_output", END)

    return g
