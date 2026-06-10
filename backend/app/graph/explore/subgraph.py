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
    g.add_node("acknowledge_and_guide", nodes.acknowledge_and_guide)
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
        # AI 必要性彈窗已發、等 BU 做選擇:本輪不再產 agent 回覆,
        # 由三個 modal endpoint 之一接手後續 LLM stream。
        if state.pending_ai_necessity_decision:
            return END
        # Stage 5 收斂彈窗已發、等 BU 做選擇:dismiss / quick_handoff 接手。
        if state.pending_stage5_decision:
            return END
        if state.mode == "cold":
            return END
        if state.ready_to_handoff:
            return "emit_dual_output"
        # v12: 只要已有候選卡片 → 停話、END,等 BU 在右側對卡片按「採用 / 不採用」決策。
        # agent 不再主動問下一題或回引導語(那會在卡片剛冒出時搶話、打斷 BU 看卡)。
        #  - 採用 → select_candidate 觸發 emit_dual_output
        #  - 不採用 → reject_candidate 移除卡片;全拒時才由 service stream 重新發想回覆
        # 前端輸入框靠 turn_done 事件解鎖;BU 仍可打字補脈絡,下輪重評分更新卡片。
        if state.scored_candidates:
            return END
        return "discovery_loop"

    g.add_conditional_edges(
        "converge_check",
        after_converge,
        [END, "emit_dual_output", "discovery_loop"],
    )
    g.add_edge("acknowledge_and_guide", END)
    g.add_edge("emit_dual_output", END)

    return g
