"""Session 層的 orchestration：建 session、接 BU reply、跑 graph。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.graph.main_graph import get_graph
from app.graph.shared.events import bus
from app.graph.shared.state import GraphState, TraceEntry
from app.models.db import ExplorationOutput, SessionRow, User
from app.models.schemas import SessionCreateRequest

log = get_logger(__name__)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def create_session(
    db: Session, user: User, payload: SessionCreateRequest
) -> SessionRow:
    session = SessionRow(
        session_id=uuid.uuid4(),
        user_id=user.user_id,
        bu=payload.bu,
        sme_role=payload.sme_role,
        raw_hint=payload.raw_hint,
        mode="explore",
        stage=1,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


async def run_turn(
    db: Session, session: SessionRow, bu_text: str | None
) -> GraphState:
    """核心 loop：若有 BU text 先寫入 state，再 invoke graph。

    - 第一次呼叫（bu_text=None）→ graph 自己跑 discovery_loop 產第一題
    - 之後呼叫（bu_text 非空）→ 先塞 BU trace，graph 進 extract_signals 路徑
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}

    # 讀現況：首次呼叫 checkpoint 會是空
    current = await graph.aget_state(config)
    is_first = not current.values

    if is_first:
        initial = GraphState(
            session_id=str(session.session_id),
            user_id=session.user_id,
            bu=session.bu,
            sme_role=session.sme_role,
            raw_hint=session.raw_hint,
            mode="explore",
        )
        # 首次 invoke：graph 從 START 跑到 END，出第一題
        await graph.ainvoke(initial.model_dump(), config=config)
    else:
        # 從 checkpoint 讀既有 state
        state = GraphState.model_validate(current.values)

        # 若是 BU reply，append 到 checkpoint 裡的 history。
        # history 已改 replace semantics → 必須傳完整新 list 進 update_state。
        if bu_text:
            turn_id = len(state.history) + 1
            bu_trace = TraceEntry(
                turn_id=turn_id,
                mode=state.mode,
                role="bu",
                raw_text=bu_text,
                timestamp=_now_iso(),
            )
            new_history = list(state.history) + [bu_trace]
            await graph.aupdate_state(config, {"history": new_history})
            await bus.publish(
                str(session.session_id),
                "bu_turn_recorded",
                {"turn_id": turn_id, "text": bu_text},
            )

            # Consult Step 2：把 BU 回答整合進當前 pending 章節的 draft
            if state.mode == "consult_step2" and state.current_section_idx is not None:
                await _integrate_bu_answer_to_section(
                    graph, config, state, bu_text
                )

        # 讓 graph 從 START 再跑一輪。傳 {} 讓 pregel 啟動;
        # reducer 已改 replace semantics,空 dict 不會 merge 衝突。
        await graph.ainvoke({}, config=config)

    # 拿最新 state 做為回傳（含 reducer 後累積結果）
    final = await graph.aget_state(config)
    final_state = GraphState.model_validate(final.values)

    # 同步 DB：mode / stage / status / exploration_outputs
    session.mode = final_state.mode
    session.stage = final_state.stage
    if final_state.mode == "cold":
        session.status = "cold"
    if final_state.structured_json and final_state.paragraph_description:
        existing = db.get(ExplorationOutput, session.session_id)
        if existing is None:
            db.add(
                ExplorationOutput(
                    session_id=session.session_id,
                    structured_json=final_state.structured_json,
                    paragraph_description=final_state.paragraph_description,
                )
            )
    db.commit()

    return final_state


async def confirm_handoff(db: Session, session: SessionRow) -> GraphState:
    """BU 在 modal 點「進入 Consult mode」：切 mode 並驅動 consult subgraph
    跑 load_template → auto_fill_outline,讓前端立刻看到 BRD 大綱。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(config, {"mode": "consult_step1"})
    session.mode = "consult_step1"
    db.commit()
    await bus.publish(
        str(session.session_id),
        "mode_changed",
        {"from": "explore", "to": "consult_step1"},
    )

    # 第 1 輪：route_mode → consult subgraph → load_template → auto_fill_outline
    #         → publish outline_ready, mode 切 consult_step2
    await graph.ainvoke({}, config=config)
    # 第 2 輪：consult_step2 + 有 needs_round2 → section_loop publish 第一個提問
    await graph.ainvoke({}, config=config)

    snap = await graph.aget_state(config)
    final_state = GraphState.model_validate(snap.values)
    session.mode = final_state.mode
    db.commit()
    return final_state


async def dismiss_handoff(db: Session, session: SessionRow) -> GraphState:
    """BU 在 modal 點「再討論一下」：清 ready_to_handoff，回到 stage 5 對話。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(config, {"ready_to_handoff": False})
    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def _integrate_bu_answer_to_section(
    graph, config: dict, state: GraphState, bu_text: str
) -> None:
    """把 BU 在 Consult Step 2 的回答 LLM-merge 進當前 pending 章節的 draft。

    失敗時退而把 BU 原話 append 在章節末端,確保資訊不丟失。
    """
    from app.graph.shared.llm import get_llm
    from app.graph.shared.prompts import render
    from app.graph.shared.state import SectionState

    idx = state.current_section_idx
    if idx is None or idx >= len(state.brd_outline):
        return

    sec_raw = state.brd_outline[idx]
    sec = (
        sec_raw
        if isinstance(sec_raw, SectionState)
        else SectionState.model_validate(sec_raw)
    )
    if sec.status not in ("needs_round2",):
        return  # auto_filled / placeholder 等不在這裡處理

    # 找出 selected candidate(雙形態兼容)
    cand: dict = {}
    selected = state.selected_candidate or 1
    for c in state.scored_candidates:
        d = c.model_dump() if hasattr(c, "model_dump") else c
        if d.get("rank") == selected:
            cand = d
            break

    user = render(
        "apply_section_answer",
        section_title=sec.title,
        current_draft=sec.draft_content or "（尚未填）",
        bu_answer=bu_text,
        direction=cand.get("direction", ""),
        process_target=cand.get("process_target", ""),
        project_type=cand.get("project_type", ""),
    )

    new_content = ""
    try:
        llm = get_llm()
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": user}]
        ):
            new_content += chunk
        new_content = new_content.strip()
    except Exception as e:
        log.warning("integrate_bu_answer.llm_failed", error=str(e))

    if not new_content or len(new_content) < 30:
        # fallback:原 draft + BU 原話
        new_content = (
            f"{sec.draft_content}\n\n[BU 補充] {bu_text}"
            if sec.draft_content
            else bu_text
        )

    updated_sec = sec.model_copy(
        update={"draft_content": new_content, "last_edit_by": "agent"}
    )

    # 寫回 outline
    new_outline = list(state.brd_outline)
    new_outline[idx] = updated_sec
    await graph.aupdate_state(config, {"brd_outline": new_outline})

    await bus.publish(
        str(state.session_id),
        "section_updated",
        {"section_id": sec.section_id, "section": updated_sec.model_dump()},
    )


async def get_outline(db: Session, session: SessionRow) -> list[dict]:
    """讀目前 brd_outline 全部章節（dict 形式）。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    if not snap.values:
        return []
    state = GraphState.model_validate(snap.values)
    return [s.model_dump() for s in state.brd_outline]


def _normalize_section_list(outline) -> list:
    """把可能是 list[dict] 或 list[SectionState] 的東西統一成 SectionState list。"""
    from app.graph.shared.state import SectionState

    out = []
    for s in outline:
        if isinstance(s, SectionState):
            out.append(s)
        else:
            out.append(SectionState.model_validate(s))
    return out


async def edit_section(
    db: Session, session: SessionRow, section_id: str, content: str
) -> dict:
    """E3 inline edit：把章節內容覆寫,標 last_edit_by=bu。"""
    from app.graph.shared.state import SectionState

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    if not snap.values:
        raise ValueError("session has no graph state")

    state = GraphState.model_validate(snap.values)
    outline = _normalize_section_list(state.brd_outline)
    target: SectionState | None = None
    new_outline = []
    for sec in outline:
        if sec.section_id == section_id:
            updated = sec.model_copy(
                update={"draft_content": content, "last_edit_by": "bu"}
            )
            new_outline.append(updated)
            target = updated
        else:
            new_outline.append(sec)
    if target is None:
        raise KeyError(f"section {section_id} not found")

    await graph.aupdate_state(config, {"brd_outline": new_outline})
    await bus.publish(
        str(session.session_id),
        "section_updated",
        {"section_id": section_id, "section": target.model_dump()},
    )
    return target.model_dump()


_VALID_ACTIONS = {"accept", "refine", "skip", "flag"}


async def section_action(
    db: Session, session: SessionRow, section_id: str, action: str
) -> dict:
    """E2 Accept / Refine / Skip / Flag。

    accept → status=accepted；skip → status=skipped；flag → status=flagged_for_ba；
    refine → 回到 needs_round2 由 section_loop 重新提問（M3 mock：保持 needs_round2）。
    動作後若沒有 needs_round2 章節,推進到 quality gate（由下一次 ainvoke 觸發）。
    """
    if action not in _VALID_ACTIONS:
        raise ValueError(f"invalid action: {action}")

    from app.graph.shared.state import SectionState

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    outline = _normalize_section_list(state.brd_outline)
    status_map = {
        "accept": "accepted",
        "skip": "skipped",
        "flag": "flagged_for_ba",
        "refine": "needs_round2",
    }
    new_status = status_map[action]

    target: SectionState | None = None
    new_outline = []
    for sec in outline:
        if sec.section_id == section_id:
            updated = sec.model_copy(update={"status": new_status})
            new_outline.append(updated)
            target = updated
        else:
            new_outline.append(sec)
    if target is None:
        raise KeyError(f"section {section_id} not found")

    # 找下一個 needs_round2;沒有則 current_section_idx=None,觸發 quality gate
    next_idx = next(
        (i for i, s in enumerate(new_outline) if s.status == "needs_round2"),
        None,
    )

    await graph.aupdate_state(
        config,
        {"brd_outline": new_outline, "current_section_idx": next_idx},
    )
    await bus.publish(
        str(session.session_id),
        "section_updated",
        {"section_id": section_id, "section": target.model_dump()},
    )

    # 推進 graph 一輪：若還有 needs_round2,section_loop 會問下一題;
    # 否則 quality_gate 走完 → 等 BU 點「送 BA」
    # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
    await graph.ainvoke({}, config=config)

    return target.model_dump()


async def submit_session(
    db: Session, session: SessionRow
) -> dict:
    """F1 送 BA：跑 build_deliverables,寫 deliverables 表,標 session 完成。"""
    from app.models.db import Deliverable

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}

    # 推進 mode 進 build_deliverables
    await graph.aupdate_state(config, {"mode": "submit"})
    # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
    await graph.ainvoke({}, config=config)

    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # 寫 deliverables 表（冪等：upsert）
    existing = db.get(Deliverable, session.session_id)
    payload = {
        "brd_doc_ref": state.brd_doc_ref or "",
        "summary_json": state.summary_json or {},
        "flag_for_ba_review": {"sections": (state.summary_json or {}).get("flag_for_ba_review", [])},
        "handed_off_at": datetime.now(UTC),
        "handed_off_to": None,  # M3 mock：未指定 BA
    }
    if existing is None:
        db.add(Deliverable(session_id=session.session_id, **payload))
    else:
        for k, v in payload.items():
            setattr(existing, k, v)

    session.mode = "done"
    session.status = "done"
    db.commit()

    return {
        "brd_doc_ref": state.brd_doc_ref,
        "summary_json": state.summary_json,
        "flag_for_ba_review": (state.summary_json or {}).get("flag_for_ba_review", []),
    }


async def acknowledge_ai_necessity_warning(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「我了解了/讓我繼續想想」:本 session 不再彈警示。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(config, {"ai_necessity_warned": True})
    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def override_ai_necessity_warning(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「還是想試試 AI」:標 bu_overrode、本 session 不再彈、繼續對話。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(
        config,
        {
            "ai_necessity_warned": True,
            "bu_overrode_ai_necessity": True,
        },
    )
    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def explain_solution_class(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「想了解 [solution_class] 跟 AI 的差別」:
    在對話區用 LLM 產一段白話說明,作為 agent 的下一個 turn。"""
    from app.graph.shared.llm import get_llm
    from app.graph.shared.prompts import render

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # 找 top 1 candidate
    top = None
    for c in state.scored_candidates:
        d = c.model_dump() if hasattr(c, "model_dump") else c
        if d.get("rank") == 1:
            top = d
            break
    if top is None:
        return state

    user = render(
        "explain_solution_class",
        bu=state.bu,
        sme_role=state.sme_role,
        solution_class=top.get("solution_class") or "rpa",
        rationale=top.get("solution_rationale") or "",
        direction=top.get("direction") or "",
        process_target=top.get("process_target") or "",
    )

    turn_id = len(state.history) + 1

    # Stream 給對話區
    full = ""
    try:
        llm = get_llm()
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": user}]
        ):
            full += chunk
            await bus.publish(
                str(session.session_id),
                "agent_reply_delta",
                {"turn_id": turn_id, "text_delta": chunk},
            )
        full = full.strip()
    except Exception as e:
        log.warning("explain_solution_class.llm_failed", error=str(e))
        full = f"關於 {top.get('solution_class')} 跟 AI 的差別,LLM 暫時無法產生說明,請稍後重試或直接諮詢 BA。"
        await bus.publish(
            str(session.session_id),
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": full},
        )

    await bus.publish(
        str(session.session_id),
        "agent_reply_done",
        {"turn_id": turn_id, "full_text": full},
    )

    # 寫進 history(replace semantics)
    new_trace = TraceEntry(
        turn_id=turn_id,
        mode=state.mode,
        role="agent",
        raw_text=full,
        timestamp=_now_iso(),
    )
    new_history = list(state.history) + [new_trace]
    await graph.aupdate_state(
        config,
        {
            "history": new_history,
            "ai_necessity_warned": True,
        },
    )

    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def dismiss_stage5_stuck(db: Session, session: SessionRow) -> GraphState:
    """BU 在 stage 5 卡關 modal 點「再聊一下」:
    本 session 不再彈,讓 agent 換個切角繼續對話。"""
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(config, {"stage_5_stuck_acked": True})
    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def quick_handoff(
    db: Session, session: SessionRow, rank: int
) -> GraphState:
    """BU 在 stage 5 卡關 modal 點「先用 #N 試試 BRD」:
    一鍵 select candidate + 觸發 emit_dual_output。

    與 select_candidate 差別:這裡保證 stage=5、不管目前 ready 狀態都強制走完 handoff。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(
        config,
        {
            "selected_candidate": rank,
            "ready_to_handoff": True,
            "stage_5_stuck_acked": True,
        },
    )
    # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
    await graph.ainvoke({}, config=config)
    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def reset_explore(db: Session, session: SessionRow) -> GraphState:
    """C3 重新探索：把當前候選標 cold,mode 切回 explore,清:
    - selected / ready_to_handoff / candidates / dual output / brd_outline
    - history / pain_signals(避免舊脈絡帶偏新 agent context)

    清完後重啟 explore graph,讓 agent 重新出第一題。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(
        config,
        {
            "mode": "explore",
            "stage": 1,
            "selected_candidate": None,
            "ready_to_handoff": False,
            "candidate_directions": [],
            "scored_candidates": [],
            "structured_json": None,
            "paragraph_description": None,
            "brd_outline": [],
            "history": [],
            "pain_signals": [],
            "pending_question": None,
            "current_section_idx": None,
        },
    )
    session.mode = "explore"
    session.stage = 1
    db.commit()
    await bus.publish(
        str(session.session_id),
        "mode_changed",
        {"from": "consult_step1", "to": "explore", "reason": "user_reset"},
    )

    # 重啟 explore graph：history 空 → discovery_loop 會出新的第一題
    # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
    await graph.ainvoke({}, config=config)

    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def select_candidate(
    db: Session, session: SessionRow, rank: int
) -> GraphState:
    """BU 在工作區選定候選方向 → 立刻驅動 emit_dual_output 觸發 handoff_ready。

    只要候選清單已存在(stage 3 收斂之後),BU 點選就視為「我想好了」。
    不要逼 BU 走完 stage 5 才能進 Consult。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(config, {"selected_candidate": rank})

    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # 候選清單已存在 + 還沒進 handoff → 驅動 emit_dual_output
    if state.scored_candidates and not state.ready_to_handoff:
        await graph.aupdate_state(config, {"ready_to_handoff": True})
        # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
        await graph.ainvoke({}, config=config)
        snap = await graph.aget_state(config)
        state = GraphState.model_validate(snap.values)

    return state
