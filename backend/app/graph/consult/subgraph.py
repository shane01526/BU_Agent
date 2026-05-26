"""Consult subgraph（technical_design.md §3.2.3）。

Invoke 語意：
- 進入時 mode=consult_step1 + outline 空 → load_template → auto_fill_outline → END
  (mode 在 auto_fill_outline 內被切到 consult_step2;下次 invoke 直接走 step2)
- mode=consult_step2 + 有 needs_round2 章節 → section_loop 問下一題 → END
- mode=consult_step2 + 沒有 needs_round2 待處理 → quality_gate → END
- mode 由外部設成 'submit' 觸發 → build_deliverables → END

實作上用 entry router 判斷;每個節點末端直接 END,等下次 invoke 推進。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.graph.consult import nodes
from app.graph.shared.state import GraphState

PENDING_STATUSES = {"needs_round2"}


def _has_pending_section(outline) -> bool:
    for sec in outline:
        status = getattr(sec, "status", None) or (
            sec.get("status") if isinstance(sec, dict) else None
        )
        if status in PENDING_STATUSES:
            return True
    return False


def build_consult_subgraph() -> StateGraph:
    g = StateGraph(GraphState)

    g.add_node("load_template", nodes.load_template_node)
    g.add_node("auto_fill_outline", nodes.auto_fill_outline)
    g.add_node("section_loop", nodes.section_loop)
    g.add_node("quality_gate", nodes.quality_gate)
    g.add_node("build_deliverables", nodes.build_deliverables)

    def entry(state: GraphState) -> str:
        # mode='submit' 是 service 層用來觸發送 BA 的特殊值
        if state.mode == "submit":
            return "build_deliverables"
        # outline 還沒建 → step 1
        if not state.brd_outline:
            return "load_template"
        # 還有待訪談章節
        if _has_pending_section(state.brd_outline):
            return "section_loop"
        # 都填完 → quality gate
        return "quality_gate"

    g.add_conditional_edges(
        START,
        entry,
        ["load_template", "section_loop", "quality_gate", "build_deliverables"],
    )
    g.add_edge("load_template", "auto_fill_outline")
    # v9: auto_fill_outline 末端 set current_section_idx + mode=consult_step2,
    # 接下來在同一個 super-step 直接進 section_loop publish 第一章提問。
    # 避免 confirm_handoff 兩輪 ainvoke 第 2 輪變 noop 的問題。
    g.add_edge("auto_fill_outline", "section_loop")
    g.add_edge("section_loop", END)
    g.add_edge("quality_gate", END)
    g.add_edge("build_deliverables", END)

    return g
