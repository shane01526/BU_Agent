"""Consult subgraph 節點實作（technical_design.md §3.2.3）。

M4 起改用 Gemini:
- auto_fill_outline:用 prompt + structured output 一次填所有章節
- section_loop:用 prompt 串流產章節提問
- quality_gate:用 structured output 偵測跨章節矛盾
- build_deliverables:仍 deterministic（合成 markdown）
"""

from __future__ import annotations

import re
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


def _previous_qa_for_section(history, sid: str) -> list[dict]:
    """從 history 抽出該章節的 Q&A 序列(role / text);舊 trace 缺 section_id 自動略過。"""
    out: list[dict] = []
    for h in history:
        h_sid = (
            getattr(h, "section_id", None)
            if not isinstance(h, dict)
            else h.get("section_id")
        )
        if h_sid != sid:
            continue
        role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else None)
        text = (
            getattr(h, "raw_text", None)
            or (h.get("raw_text", "") if isinstance(h, dict) else "")
        )
        if role and text:
            out.append({"role": role, "text": text})
    return out


# 短回覆 / 客套字判定;用於規則 5b 決定 BU 是否真的還有東西可講
_SHORT_BU_HINT_RE = re.compile(
    r"^(嗯+|哦|喔|好|ok|okay|yes|對|是|不知道|沒有|沒|還好|看你|你決定|都可以)\b",
    re.IGNORECASE,
)


def _last_bu_text_in_section(previous_qa: list[dict]) -> str:
    for qa in reversed(previous_qa):
        if qa.get("role") == "bu":
            return qa.get("text", "")
    return ""


def _is_short_or_idle(text: str) -> bool:
    t = text.strip()
    if len(t) <= 20:
        return True
    return bool(_SHORT_BU_HINT_RE.match(t))


def _count_accept_hints(previous_qa: list[dict]) -> int:
    """數 agent 在本章已提示過幾次「資訊夠了 / 要不要 Accept」。"""
    n = 0
    for qa in previous_qa:
        if qa.get("role") != "agent":
            continue
        text = qa.get("text", "")
        if any(kw in text for kw in ("Accept", "資訊夠了", "資訊足夠", "夠了嗎", "想 Accept")):
            n += 1
    return n


def _bu_replies_since_last_accept_hint(previous_qa: list[dict]) -> int:
    """從 previous_qa 倒序,找最後一個 agent 含「Accept / 夠了」字眼的 turn,
    回傳那之後 BU 已回過幾次。

    用途:revisit 場景下章節 history 累積了過去 Accept 提示;這個值能讓
    section_loop 判斷「自從上次提示 Accept 後 BU 是否新講了內容」,
    決定是否進「續訪開場」prompt。
    """
    last_hint_idx = -1
    for i, qa in enumerate(previous_qa):
        if qa.get("role") != "agent":
            continue
        text = qa.get("text", "")
        if any(kw in text for kw in ("Accept", "資訊夠了", "資訊足夠", "夠了嗎", "想 Accept")):
            last_hint_idx = i
    if last_hint_idx < 0:
        # 沒任何 hint 過 → 整段 BU 回應都是 fresh
        return sum(1 for x in previous_qa if x.get("role") == "bu")
    after = previous_qa[last_hint_idx + 1 :]
    return sum(1 for x in after if x.get("role") == "bu")


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
        llm = get_llm(state.llm_model)
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
    # v6 防禦:即便沒有 needs_round2 章節(意外狀況),只要 outline 非空就指第 0 個,
    # 避免 section_loop 因 idx=None silent skip,讓 chat 變空白
    if next_idx is None and new_outline:
        next_idx = 0

    log.info(
        "auto_fill_outline.done",
        outline_n=len(new_outline),
        next_idx=next_idx,
        needs_round2_n=sum(1 for s in new_outline if s.status == "needs_round2"),
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
    log.info(
        "section_loop.enter",
        session_id=state.session_id,
        current_section_idx=idx,
        outline_n=len(state.brd_outline),
        mode=state.mode,
    )
    if idx is None or idx >= len(state.brd_outline):
        log.warning(
            "section_loop.skip",
            reason="no_idx_or_oob",
            idx=idx,
            outline_n=len(state.brd_outline),
        )
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

    # 本章節 Q&A 序列(取 last 10 筆),取代舊的全 history 計數
    previous_qa = _previous_qa_for_section(state.history, sid)[-10:]
    rounds_in_this_section = sum(1 for x in previous_qa if x["role"] == "bu")
    was_visited = (
        rounds_in_this_section >= 1 or len(section_draft or "") > 100
    )
    accept_hint_count = _count_accept_hints(previous_qa)
    last_bu_text = _last_bu_text_in_section(previous_qa)
    last_bu_is_short = _is_short_or_idle(last_bu_text) if last_bu_text else False
    # is_fresh_revisit:was_visited + 從上次 Accept 提示後 BU 還沒新講太多話
    # → 用於 prompt 規則「續訪開場」與「不要立刻收斂」
    bu_replies_since_revisit = _bu_replies_since_last_accept_hint(previous_qa)
    is_fresh_revisit = was_visited and bu_replies_since_revisit < 2

    # Auto-advance:agent 已提示 ≥ 2 次「Accept / 資訊夠了」+ BU 仍短答/客套
    # → 強制把本章標 accepted、跳下一章,避免卡住。
    # 改完後仍會繼續往下跑(但 idx 已切到下一章),不直接 return
    # 以便對「新的下一章」publish 第一道訪談題,讓 chat 不空白。
    auto_advanced = False
    if (
        accept_hint_count >= 2
        and last_bu_is_short
        and not is_fresh_revisit
    ):
        new_outline_pre = list(state.brd_outline)
        sec_obj = sec if isinstance(sec, SectionState) else SectionState.model_validate(sec)
        updated_sec = sec_obj.model_copy(update={"status": "accepted"})
        new_outline_pre[idx] = updated_sec
        next_idx = next(
            (i for i, s in enumerate(new_outline_pre) if (
                getattr(s, "status", None) or s.get("status")) == "needs_round2"
            ),
            None,
        )
        await bus.publish(
            state.session_id,
            "section_updated",
            {"section_id": sid, "section": updated_sec.model_dump()},
        )
        if next_idx is not None and 0 <= next_idx < len(new_outline_pre):
            next_sid = (
                getattr(new_outline_pre[next_idx], "section_id", None)
                or new_outline_pre[next_idx]["section_id"]
            )
            await bus.publish(
                state.session_id,
                "current_section_changed",
                {"section_id": next_sid},
            )
        log.info(
            "section_loop.auto_advance",
            session_id=state.session_id,
            from_section=sid,
            to_section_idx=next_idx,
            accept_hint_count=accept_hint_count,
        )
        # 沒下一個 needs_round2 → 整段訪談完成,本輪不再 stream 提問,
        # 等下次 ainvoke entry 走 quality_gate。
        if next_idx is None:
            return {
                "brd_outline": new_outline_pre,
                "current_section_idx": None,
            }
        # 切到下一章後 reload 該章 context,改用新 sid 跑下面 prompt 流程
        idx = next_idx
        sec = new_outline_pre[idx]
        sid = getattr(sec, "section_id", None) or sec["section_id"]
        title = getattr(sec, "title", None) or sec["title"]
        section_draft = (
            getattr(sec, "draft_content", None) or sec.get("draft_content", "")
        )
        sec_tpl = next((s for s in tpl.sections if s.id == sid), None)
        seed_questions = sec_tpl.questions if sec_tpl else []
        previous_qa = _previous_qa_for_section(state.history, sid)[-10:]
        rounds_in_this_section = sum(1 for x in previous_qa if x["role"] == "bu")
        was_visited = rounds_in_this_section >= 1 or len(section_draft or "") > 100
        accept_hint_count = _count_accept_hints(previous_qa)
        last_bu_text = _last_bu_text_in_section(previous_qa)
        last_bu_is_short = _is_short_or_idle(last_bu_text) if last_bu_text else False
        bu_replies_since_revisit = _bu_replies_since_last_accept_hint(previous_qa)
        is_fresh_revisit = was_visited and bu_replies_since_revisit < 2
        auto_advanced = True

    user = render(
        "section_question",
        section_title=title,
        direction=cand.get("direction", ""),
        process_target=cand.get("process_target", ""),
        project_type=project_type,
        section_draft=section_draft,
        seed_questions=seed_questions,
        previous_qa=previous_qa,
        rounds_in_this_section=rounds_in_this_section,
        was_visited=was_visited,
        accept_hint_count=accept_hint_count,
        last_bu_is_short=last_bu_is_short,
        is_fresh_revisit=is_fresh_revisit,
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
        llm = get_llm(state.llm_model)
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
        section_id=sid,
    )
    existing_history = [
        h if isinstance(h, TraceEntry) else TraceEntry.model_validate(h)
        for h in state.history
    ]
    patch: dict = {
        "history": existing_history + [trace],
        "pending_question": full,
    }
    if auto_advanced:
        # 把本輪自動 accept + 跳章的結果一併寫回 state
        patch["brd_outline"] = new_outline_pre
        patch["current_section_idx"] = idx
    return patch


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
        llm = get_llm(state.llm_model)
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
