"""Consult subgraph 節點實作（technical_design.md §3.2.3）。

M4 起改用 Gemini:
- auto_fill_outline:用 prompt + structured output 一次填所有章節
- section_loop:用 prompt 串流產章節提問
- quality_gate:用 structured output 偵測跨章節矛盾
- build_deliverables:仍 deterministic（合成 markdown）
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.graph.consult.template_loader import load_template
from app.graph.shared.events import bus
from app.graph.shared.knowledge_loader import load_card
from app.graph.shared.llm import get_llm
from app.graph.shared.prompts import render
from app.graph.shared.state import (
    CandidateDirection,
    ConflictListOutput,
    GraphState,
    PainSignal,
    SectionDraftListOutput,
    SectionState,
    TraceEntry,
)

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _section_to_state(s_tpl, status: str, content: str = "") -> SectionState:
    return SectionState(
        section_id=s_tpl.id,
        title=s_tpl.title,
        status=status,
        draft_content=content,
        last_edit_by=None,
    )


# ---------- nodes ----------


async def load_template_node(state: GraphState) -> dict:
    """依 BU + project_type 載 YAML,組初步 brd_outline 骨架(尚無內容)。"""
    project_type = (
        state.structured_json.get("predicted_consult_fields", {}).get("project_type")
        if state.structured_json
        else "分類"
    ) or "分類"
    tpl = load_template(state.bu, project_type)
    outline: list[SectionState] = []
    for s in tpl.sections:
        outline.append(_section_to_state(s, status=s.default_status))
    return {"brd_outline": outline}


def _candidate_dict(state: GraphState) -> dict:
    """取出 selected candidate（dict 形式,跨 dict/Pydantic 雙形態）。"""
    selected = state.selected_candidate or 1
    for c in state.scored_candidates:
        if isinstance(c, CandidateDirection):
            if c.rank == selected:
                return c.model_dump()
        else:
            if c.get("rank") == selected:
                return c
    if state.scored_candidates:
        c = state.scored_candidates[0]
        return c.model_dump() if isinstance(c, CandidateDirection) else c
    return {}


def _pain_strs(state: GraphState) -> list[str]:
    out = []
    for p in state.pain_signals:
        if isinstance(p, PainSignal):
            out.append(p.raw_text)
        else:
            out.append(p.get("raw_text", ""))
    return [s for s in out if s]


async def auto_fill_outline(state: GraphState) -> dict:
    """用 LLM 一次產所有章節 draft;失敗時退 heuristic。"""
    cand = _candidate_dict(state)
    pains = _pain_strs(state)
    paragraph = state.paragraph_description or ""
    direction = cand.get("direction", "（候選方向）")

    outline_in: list = list(state.brd_outline)
    sections_for_prompt = []
    for sec in outline_in:
        sid = getattr(sec, "section_id", None) or sec["section_id"]
        title = getattr(sec, "title", None) or sec["title"]
        status = getattr(sec, "status", None) or sec["status"]
        sections_for_prompt.append(
            {
                "id": sid,
                "title": title,
                "default_status": status,
                "extract_from_explore": _section_extract_hints(state, sid),
            }
        )

    # 用 LLM 產 draft（map: section_id → content_md）
    draft_map: dict[str, str] = {}
    triage = (
        state.structured_json.get("ai_necessity_triage")
        if state.structured_json
        else None
    )
    kc = load_card(state.bu)
    user = render(
        "auto_fill_outline",
        direction=direction,
        process_target=cand.get("process_target", ""),
        project_type=cand.get("project_type", "分類"),
        one_line_goal=(
            state.structured_json.get("predicted_consult_fields", {}).get("one_line_goal", "")
            if state.structured_json
            else ""
        ),
        pain_signals=pains,
        paragraph=paragraph,
        sections=sections_for_prompt,
        ai_necessity_triage=triage,
        kc=kc,
    )
    try:
        llm = get_llm()
        result = await llm.chat_structured(
            [{"role": "user", "content": user}], SectionDraftListOutput
        )
        draft_map = {d.section_id: d.content_md for d in result.sections}
    except Exception as e:
        log.warning("auto_fill_outline.llm_failed", error=str(e))

    new_outline: list[SectionState] = []
    for sec in outline_in:
        sid = getattr(sec, "section_id", None) or sec["section_id"]
        title = getattr(sec, "title", None) or sec["title"]
        status = getattr(sec, "status", None) or sec["status"]

        if status == "placeholder":
            new_outline.append(
                SectionState(
                    section_id=sid,
                    title=title,
                    status=status,
                    draft_content="（由 AI 科 / CD 科後續補充）",
                )
            )
            continue

        # 從 LLM map 取;缺失時退 heuristic
        draft = draft_map.get(sid, "").strip()
        if not draft:
            draft = _heuristic_draft(sid, status, cand, pains, paragraph)

        new_outline.append(
            SectionState(
                section_id=sid, title=title, status=status, draft_content=draft
            )
        )

    next_idx = next(
        (i for i, s in enumerate(new_outline) if s.status == "needs_round2"), None
    )

    await bus.publish(
        state.session_id,
        "outline_ready",
        {"sections": [s.model_dump() for s in new_outline]},
    )
    return {
        "brd_outline": new_outline,
        "current_section_idx": next_idx,
        "mode": "consult_step2",
    }


def _section_extract_hints(state: GraphState, sid: str) -> list[str]:
    """從 template 撈 extract_from_explore hint(供 prompt context)。"""
    cand = _candidate_dict(state)
    project_type = cand.get("project_type", "分類")
    try:
        tpl = load_template(state.bu, project_type)
        sec_tpl = next((s for s in tpl.sections if s.id == sid), None)
        return list(sec_tpl.extract_from_explore) if sec_tpl else []
    except Exception:
        return []


def _heuristic_draft(
    sid: str, status: str, cand: dict, pains: list[str], paragraph: str
) -> str:
    """LLM 失敗時的 fallback。"""
    direction = cand.get("direction", "（候選方向）")
    process = cand.get("process_target", "（流程目標）")
    project_type = cand.get("project_type", "分類")
    pain_str = "、".join(pains[:3]) if pains else "（待 BU 補充）"

    if status == "needs_round2":
        return f"_(此章節待第 2 輪訪談補完;將針對「{direction}」深入詢問)_"

    if sid == "sec_bg":
        return (
            f"目前 {process} 由 BU 人工處理,主要痛點包括:{pain_str}。"
            f"本次提案希望以 AI 協助 {direction},減輕人工負擔。"
        )
    if sid == "sec_req_analysis":
        return (
            f"AI 介入後,{process} 預期由 {project_type} 模型先行處理,"
            f"再由 BU 進行重點覆核。具體業務規則待 BU 於本章補充。"
        )
    return "（內容待補）"


async def section_loop(state: GraphState) -> dict:
    """對當前 needs_round2 章節用 LLM 產一道問題,streaming 推 SSE。"""
    idx = state.current_section_idx
    if idx is None or idx >= len(state.brd_outline):
        return {}

    sec = state.brd_outline[idx]
    sid = getattr(sec, "section_id", None) or sec["section_id"]
    title = getattr(sec, "title", None) or sec["title"]
    section_draft = getattr(sec, "draft_content", None) or sec.get("draft_content", "")

    cand = _candidate_dict(state)
    project_type = cand.get("project_type", "分類")
    tpl = load_template(state.bu, project_type)
    sec_tpl = next((s for s in tpl.sections if s.id == sid), None)
    seed_questions = sec_tpl.questions if sec_tpl else []

    # 本章 BU 已回幾次:用 history 中 role=bu 且 mode=consult_step2 計
    rounds_so_far = sum(
        1
        for h in state.history
        if (
            getattr(h, "role", None) == "bu"
            or (isinstance(h, dict) and h.get("role") == "bu")
        )
        and (
            getattr(h, "mode", None) == "consult_step2"
            or (isinstance(h, dict) and h.get("mode") == "consult_step2")
        )
    )

    user = render(
        "section_question",
        section_title=title,
        direction=cand.get("direction", ""),
        process_target=cand.get("process_target", ""),
        project_type=project_type,
        section_draft=section_draft,
        seed_questions=seed_questions,
        rounds_so_far=rounds_so_far,
    )

    turn_id = len(state.history) + 1
    prefix = f"【{title}】"

    # 先送 prefix(立即顯示章節標籤)
    await bus.publish(
        state.session_id,
        "agent_reply_delta",
        {"turn_id": turn_id, "text_delta": prefix},
    )

    body = ""
    try:
        llm = get_llm()
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": user}]
        ):
            body += chunk
            await bus.publish(
                state.session_id,
                "agent_reply_delta",
                {"turn_id": turn_id, "text_delta": chunk},
            )
        body = body.strip()
    except Exception as e:
        log.warning("section_loop.llm_failed", error=str(e))

    if not body:
        # fallback:用 template seed 第一條
        body = seed_questions[0] if seed_questions else f"關於「{title}」,你還想補充什麼?"
        await bus.publish(
            state.session_id,
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": body},
        )

    full = f"{prefix}{body}"

    await bus.publish(
        state.session_id,
        "agent_reply_done",
        {"turn_id": turn_id, "full_text": full, "section_id": sid},
    )

    trace = TraceEntry(
        turn_id=turn_id,
        mode="consult_step2",
        role="agent",
        raw_text=full,
        timestamp=_now_iso(),
        linked_candidate_id=state.selected_candidate,
    )
    existing_history = [
        h if isinstance(h, TraceEntry) else TraceEntry.model_validate(h)
        for h in state.history
    ]
    return {
        "history": existing_history + [trace],
        "pending_question": full,
    }


async def quality_gate(state: GraphState) -> dict:
    """跨章節一致性檢查:用 LLM 偵測明顯矛盾。LLM 失敗時 pass。"""
    sections_for_prompt = []
    for sec in state.brd_outline:
        sid = getattr(sec, "section_id", None) or sec["section_id"]
        title = getattr(sec, "title", None) or sec["title"]
        status = getattr(sec, "status", None) or sec["status"]
        content = getattr(sec, "draft_content", None) or sec.get("draft_content", "")
        # 跳過 placeholder 與 flagged_for_ba(會干擾 LLM 判斷)
        if status in ("placeholder", "flagged_for_ba"):
            continue
        if not content:
            continue
        sections_for_prompt.append(
            {"section_id": sid, "title": title, "content_md": content}
        )

    if len(sections_for_prompt) < 2:
        return {"conflicts": []}

    user = render("quality_gate", sections=sections_for_prompt)
    conflicts: list[str] = []
    try:
        llm = get_llm()
        result = await llm.chat_structured(
            [{"role": "user", "content": user}], ConflictListOutput
        )
        conflicts = [
            f"{','.join(c.section_ids)}: {c.description}" for c in result.conflicts
        ]
        if conflicts:
            await bus.publish(
                state.session_id,
                "conflict_detected",
                {"conflicts": [c.model_dump() for c in result.conflicts]},
            )
    except Exception as e:
        log.warning("quality_gate.llm_failed", error=str(e))

    return {"conflicts": conflicts}


async def build_deliverables(state: GraphState) -> dict:
    """組 summary.json / conversation_trace / brd_doc_ref。"""
    cand = _candidate_dict(state)
    flag_for_ba: list[str] = []
    sections_md: list[str] = []
    for sec in state.brd_outline:
        sid = getattr(sec, "section_id", None) or sec["section_id"]
        title = getattr(sec, "title", None) or sec["title"]
        status = getattr(sec, "status", None) or sec["status"]
        content = getattr(sec, "draft_content", None) or sec.get("draft_content", "")
        sections_md.append(f"## {title}\n\n{content or '_(未填)_'}\n")
        if status == "flagged_for_ba":
            flag_for_ba.append(sid)

    brd_md = (
        f"# {cand.get('direction', 'BRD 初稿')}\n\n"
        f"> 由 BU Agent 於 {_now_iso()} 產出,v1.0 粗略版\n\n"
        + "\n".join(sections_md)
    )

    summary = {
        "one_line_goal": (
            state.structured_json.get("predicted_consult_fields", {}).get("one_line_goal")
            if state.structured_json
            else None
        ),
        "key_business_rules": [],
        "io_fields": {},
        "exception_cases": [],
        "open_for_ai_team": ["AI 方法建議", "資料規格"],
        "flag_for_ba_review": flag_for_ba,
        "ai_necessity_triage": (
            state.structured_json.get("ai_necessity_triage")
            if state.structured_json
            else None
        ),
    }

    trace = [
        h.model_dump() if isinstance(h, TraceEntry) else h for h in state.history
    ]

    await bus.publish(
        state.session_id,
        "deliverables_ready",
        {
            "summary": summary,
            "brd_md": brd_md,
            "flag_for_ba_review": flag_for_ba,
        },
    )

    return {
        "summary_json": summary,
        "conversation_trace": trace,
        "brd_doc_ref": brd_md,
        "mode": "done",
    }
