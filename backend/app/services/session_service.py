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
    from app.core.config import settings as _settings

    chosen_model = (payload.llm_model or _settings.default_model or "").strip() or None
    # 模型清單已改為動態從供應商抓,這裡不再硬擋白名單;
    # llm.py 的 _resolve_backend 會在 prefix 不認識時 fallback 到 mock 並 warning。

    session = SessionRow(
        session_id=uuid.uuid4(),
        user_id=user.user_id,
        bu=payload.bu,
        sme_role=payload.sme_role,
        raw_hint=payload.raw_hint,
        llm_model=chosen_model,
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
            llm_model=session.llm_model,
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
            # Consult Step 2 時推 section_id;BU reply 對應「當下 pending 章節」
            sec_id_for_trace: str | None = None
            if state.mode == "consult_step2" and state.current_section_idx is not None:
                idx_for_trace = state.current_section_idx
                if 0 <= idx_for_trace < len(state.brd_outline):
                    raw_sec = state.brd_outline[idx_for_trace]
                    sec_id_for_trace = (
                        getattr(raw_sec, "section_id", None)
                        or (raw_sec.get("section_id") if isinstance(raw_sec, dict) else None)
                    )
            bu_trace = TraceEntry(
                turn_id=turn_id,
                mode=state.mode,
                role="bu",
                raw_text=bu_text,
                timestamp=_now_iso(),
                section_id=sec_id_for_trace,
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

    # 兜底:無論本輪 graph 有沒有發 agent_reply_done(stage>=4 silent END、cold_exit、
    # ai_necessity 警示等都不會發),都告訴前端「這輪結束了、可以再輸入」。
    await bus.publish(
        str(session.session_id),
        "turn_done",
        {
            "mode": final_state.mode,
            "stage": final_state.stage,
            "history_len": len(final_state.history),
        },
    )

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
    """BU 在 modal 點「進入 Consult mode」:切 mode、單輪 ainvoke 跑完整段。

    v9:consult subgraph 已把 auto_fill_outline 直接連到 section_loop,
    一個 super-step 內依序跑完 load_template → auto_fill_outline → section_loop,
    第一章提問會在同一輪 publish。不再需要 v6/v7 的兩輪 ainvoke + 防禦寫入。
    """
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

    await graph.ainvoke({}, config=config)

    snap = await graph.aget_state(config)
    final_state = GraphState.model_validate(snap.values)
    log.info(
        "confirm_handoff.done",
        mode=final_state.mode,
        outline_n=len(final_state.brd_outline),
        current_section_idx=final_state.current_section_idx,
        history_n=len(final_state.history),
        pending_question_head=(final_state.pending_question or "")[:40],
    )

    session.mode = final_state.mode
    db.commit()
    return final_state


async def dismiss_handoff(db: Session, session: SessionRow) -> GraphState:
    """BU 在 modal 點「再討論一下」：清 ready_to_handoff + selected_candidate，回到對話。

    必須一併清 selected_candidate:否則殘留值會讓 converge_check 在 stage 5 每輪都
    自動 ready_to_handoff(誤觸綜整文字),且讓卡關偵測(需 selected_candidate is None)永遠跳過。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    await graph.aupdate_state(
        config, {"ready_to_handoff": False, "selected_candidate": None}
    )
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
        llm = get_llm(state.llm_model)
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

    # Bug 2 修:讓前端 Strip / SectionInlineHeader 立刻跳到下一章
    # (不必等 5-10s 後 LLM stream 完才跳)
    if next_idx is not None and 0 <= next_idx < len(new_outline):
        next_sec = new_outline[next_idx]
        await bus.publish(
            str(session.session_id),
            "current_section_changed",
            {"section_id": next_sec.section_id},
        )

    # 推進 graph 一輪：若還有 needs_round2,section_loop 會問下一題;
    # 否則 quality_gate 走完 → 等 BU 點「送 BA」
    # ainvoke({}): 從 START 跑新 super-step（None 對 ended graph 是 noop）
    await graph.ainvoke({}, config=config)

    return target.model_dump()


async def select_section(
    db: Session, session: SessionRow, section_id: str
) -> dict:
    """BU 在 strip 上點選某章節 → 切 current_section_idx + 把該章 reset 成
    needs_round2(若先前已 accepted/skipped/flagged) → 推進 graph 讓 section_loop
    對該章重新提問。

    無條件接受任何 section_id(不論 status):BU 想回頭重訪 accepted 章也允許。
    placeholder 章節由 frontend 守門不送過來。
    """
    from app.graph.shared.state import SectionState

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    outline = _normalize_section_list(state.brd_outline)
    idx = next(
        (i for i, s in enumerate(outline) if s.section_id == section_id),
        None,
    )
    if idx is None:
        raise KeyError(f"section {section_id} not found")

    target = outline[idx]
    if target.status == "placeholder":
        raise ValueError("placeholder section cannot be selected")

    # 如果章節已不是 needs_round2,把它 reset 為 needs_round2;
    # 這是讓 consult subgraph entry 路由到 section_loop 的必要條件。
    new_outline: list[SectionState] = list(outline)
    if target.status != "needs_round2":
        updated = target.model_copy(update={"status": "needs_round2"})
        new_outline[idx] = updated
        await bus.publish(
            str(session.session_id),
            "section_updated",
            {"section_id": section_id, "section": updated.model_dump()},
        )

    await graph.aupdate_state(
        config,
        {"current_section_idx": idx, "brd_outline": new_outline},
    )
    # 對稱性:BU 主動切章時也廣播 current_section_changed,
    # 讓 SectionInlineHeader 在 agent stream 開始前就同步顯示該章
    await bus.publish(
        str(session.session_id),
        "current_section_changed",
        {"section_id": section_id},
    )
    # ainvoke({}): 從 START 跑新 super-step → consult subgraph → section_loop
    await graph.ainvoke({}, config=config)

    return {"section_id": section_id, "current_section_idx": idx}


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


# ---- AI necessity modal helpers ----


def _find_top1_candidate(state: GraphState) -> dict | None:
    """從 scored_candidates 拿 rank=1 的 dict;沒有則回 None。"""
    for c in state.scored_candidates:
        d = c.model_dump() if hasattr(c, "model_dump") else c
        if d.get("rank") == 1:
            return d
    return None


def _recent_pain_signals(state: GraphState, limit: int = 5) -> list[dict]:
    out = []
    for p in state.pain_signals[-limit:]:
        d = p.model_dump() if hasattr(p, "model_dump") else p
        out.append({"raw_text": d.get("raw_text", "")})
    return out


def _last_bu_text(state: GraphState) -> str:
    for h in reversed(list(state.history)):
        role = getattr(h, "role", None) or (h.get("role") if isinstance(h, dict) else None)
        if role == "bu":
            return getattr(h, "raw_text", None) or h.get("raw_text", "")
    return ""


async def _record_bu_option_choice(
    graph, config: dict, state: GraphState, label: str
) -> tuple[int, GraphState]:
    """寫一則 role='bu' 的 TraceEntry(內容是 modal 選項標籤),
    publish bu_turn_recorded,回傳 (新 turn_id, 已 reload 的 state)。

    Replace semantics:必須讀完整 history、append、整個寫回。
    """
    bu_turn_id = len(state.history) + 1
    bu_trace = TraceEntry(
        turn_id=bu_turn_id,
        mode=state.mode,
        role="bu",
        raw_text=label,
        timestamp=_now_iso(),
    )
    new_history = list(state.history) + [bu_trace]
    await graph.aupdate_state(config, {"history": new_history})
    await bus.publish(
        str(state.session_id),
        "bu_turn_recorded",
        {"turn_id": bu_turn_id, "text": label},
    )
    snap = await graph.aget_state(config)
    return bu_turn_id, GraphState.model_validate(snap.values)


async def _stream_agent_reply(
    session_id: str,
    turn_id: int,
    llm_model: str | None,
    prompt_text: str,
    fallback_text: str,
) -> str:
    """Stream LLM 回覆,publish agent_reply_delta(N×) + agent_reply_done。
    LLM 失敗時用 fallback_text 維持 UI 不卡死。回傳 full text。"""
    from app.graph.shared.llm import get_llm

    full = ""
    try:
        llm = get_llm(llm_model)
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": prompt_text}]
        ):
            full += chunk
            await bus.publish(
                session_id,
                "agent_reply_delta",
                {"turn_id": turn_id, "text_delta": chunk},
            )
        full = full.strip()
    except Exception as e:
        log.warning("stream_agent_reply.llm_failed", error=str(e))
        full = fallback_text
        await bus.publish(
            session_id,
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": full},
        )

    await bus.publish(
        session_id,
        "agent_reply_done",
        {"turn_id": turn_id, "full_text": full},
    )
    return full


async def _run_ai_necessity_decision(
    session: SessionRow,
    bu_label: str,
    prompt_name: str,
    fallback_text: str,
    extra_state_patch: dict | None = None,
) -> GraphState:
    """三個 modal endpoint(acknowledge / override / explain)的共用主流程:
    1. 寫 BU 選項標籤 trace + 發 bu_turn_recorded
    2. render prompt + stream agent reply
    3. 寫 agent trace + clear pending flag + 套用 extra_state_patch
    """
    from app.graph.shared.prompts import render

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    top = _find_top1_candidate(state)
    if top is None:
        # 沒候選時直接 clear flag,避免 BU 卡在 modal 後狀態無法解
        await graph.aupdate_state(
            config,
            {
                "ai_necessity_warned": True,
                "pending_ai_necessity_decision": False,
                **(extra_state_patch or {}),
            },
        )
        snap = await graph.aget_state(config)
        return GraphState.model_validate(snap.values)

    # 1. BU 選項標籤
    bu_turn_id, state = await _record_bu_option_choice(graph, config, state, bu_label)

    # 2. render prompt with current dialog context
    prompt_text = render(
        prompt_name,
        bu=state.bu,
        sme_role=state.sme_role,
        solution_class=top.get("solution_class") or "rpa",
        rationale=top.get("solution_rationale") or "",
        direction=top.get("direction") or "",
        process_target=top.get("process_target") or "",
        last_bu_text=_last_bu_text(state),
        recent_pain_signals=_recent_pain_signals(state),
    )

    # 3. stream agent reply
    agent_turn_id = bu_turn_id + 1
    agent_text = await _stream_agent_reply(
        str(session.session_id),
        agent_turn_id,
        state.llm_model,
        prompt_text,
        fallback_text=fallback_text,
    )

    # 4. write agent trace + clear flag
    agent_trace = TraceEntry(
        turn_id=agent_turn_id,
        mode=state.mode,
        role="agent",
        raw_text=agent_text,
        timestamp=_now_iso(),
    )
    new_history = list(state.history) + [agent_trace]
    patch: dict = {
        "history": new_history,
        "ai_necessity_warned": True,
        "pending_ai_necessity_decision": False,
        # 彈窗決策結束 → 清空本輪候選卡片,讓使用者跟 agent 繼續對話、下輪再重評分。
        # 避免「彈窗處理完但舊卡片殘留」鎖住輸入框。
        "scored_candidates": [],
        "candidate_directions": [],
    }
    if extra_state_patch:
        patch.update(extra_state_patch)
    await graph.aupdate_state(config, patch)
    await bus.publish(
        str(session.session_id), "candidate_updated", {"candidates": []}
    )

    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def acknowledge_ai_necessity_warning(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「我了解了,讓我繼續想想」:寫 BU 標籤 + agent 帶脈絡承接 + clear pending。"""
    return await _run_ai_necessity_decision(
        session,
        bu_label="我了解了，讓我繼續想想",
        prompt_name="acknowledge_ai_necessity",
        fallback_text=(
            "好,那就先停下來想想。可以再描述多一點目前流程的細節,"
            "或是有沒有什麼判斷上的灰色地帶讓你覺得這件事不那麼單純?"
        ),
    )


async def override_ai_necessity_warning(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「我有理由,還是想用 AI 試試看」:寫 BU 標籤 + agent 承接 + 標 bu_overrode + clear pending。"""
    return await _run_ai_necessity_decision(
        session,
        bu_label="我有理由，還是想用 AI 試試看",
        prompt_name="override_ai_necessity",
        fallback_text=(
            "好,那我們就先朝這個方向繼續推進。"
            "可以再補一句嗎——是因為現有規則處理不了某些案例,還是有別的原因讓你覺得 AI 比較適合?"
            "這段我會帶進 BRD 給 BA 參考。"
        ),
        extra_state_patch={"bu_overrode_ai_necessity": True},
    )


async def explain_solution_class(
    db: Session, session: SessionRow
) -> GraphState:
    """BU 點「想了解 [solution_class] 跟 AI 的差別」:
    寫 BU 標籤 + agent 用 LLM 產白話比較 + clear pending。"""
    # 取 top1 拼 BU label,需先 peek 一次 state
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)
    top = _find_top1_candidate(state)
    sc = (top.get("solution_class") if top else None) or "rpa"

    return await _run_ai_necessity_decision(
        session,
        bu_label=f"想了解 {sc} 跟 AI 的差別",
        prompt_name="explain_solution_class",
        fallback_text=(
            f"關於 {sc} 跟 AI 的差別,LLM 暫時無法產生說明,請稍後重試或直接諮詢 BA。"
        ),
    )


async def dismiss_stage5_stuck(db: Session, session: SessionRow) -> GraphState:
    """BU 在 stage 5 卡關 modal 點「再聊一下」:
    寫 BU 標籤 + agent 用 LLM stream 一段帶脈絡的承接 + clear pending flag。

    走跟 ai_necessity 三個 modal handler 同樣的三段式(record BU label →
    stream agent → clear flag),共用 _record_bu_option_choice / _stream_agent_reply。
    """
    from app.graph.shared.prompts import render

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # top3 候選給 prompt 當素材(若沒有則空 list,prompt 容錯)
    top3 = []
    for c in state.scored_candidates[:3]:
        top3.append(c.model_dump() if hasattr(c, "model_dump") else c)

    # 1. 寫 BU 選項標籤 trace + 發 bu_turn_recorded
    bu_label = "再聊一下，我想想"
    bu_turn_id, state = await _record_bu_option_choice(graph, config, state, bu_label)

    # 2. render prompt with current dialog context
    prompt_text = render(
        "stage5_keep_talking",
        bu=state.bu,
        sme_role=state.sme_role,
        stage_5_rounds=state.stage_5_rounds,
        top3_candidates=top3,
        recent_pain_signals=_recent_pain_signals(state),
        last_bu_text=_last_bu_text(state),
    )

    # 3. stream agent reply
    agent_turn_id = bu_turn_id + 1
    agent_text = await _stream_agent_reply(
        str(session.session_id),
        agent_turn_id,
        state.llm_model,
        prompt_text,
        fallback_text=(
            "能停下來重新評估比硬選更好。我們換個切角,"
            "從你最在意的指標(例如負擔減量 / 準確率)重新評分這幾個候選看看,"
            "你目前最想優先解決的是準確率還是負擔減量?"
        ),
    )

    # 4. write agent trace + clear pending flag + 標 acked
    agent_trace = TraceEntry(
        turn_id=agent_turn_id,
        mode=state.mode,
        role="agent",
        raw_text=agent_text,
        timestamp=_now_iso(),
    )
    new_history = list(state.history) + [agent_trace]
    await graph.aupdate_state(
        config,
        {
            "history": new_history,
            "stage_5_stuck_acked": True,
            "pending_stage5_decision": False,
            # 彈窗決策結束 → 清空本輪候選卡片,讓使用者跟 agent 繼續對話、下輪再重評分。
            "scored_candidates": [],
            "candidate_directions": [],
        },
    )
    await bus.publish(
        str(session.session_id), "candidate_updated", {"candidates": []}
    )

    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)


async def quick_handoff(
    db: Session, session: SessionRow, rank: int
) -> GraphState:
    """BU 在 stage 5 卡關 modal 點「先用 #N 試試 BRD」:
    記 BU 標籤 trace(讓 history 完整) → patch select + handoff + clear flags →
    ainvoke 觸發 emit_dual_output。**不 stream agent reply**,直接走 handoff 流程。
    """
    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # 寫 BU 選項標籤 trace(history 完整;reload 後對話順序保留)
    bu_label = f"先用 #{rank} 試試 BRD"
    _, state = await _record_bu_option_choice(graph, config, state, bu_label)

    await graph.aupdate_state(
        config,
        {
            "selected_candidate": rank,
            "ready_to_handoff": True,
            "stage_5_stuck_acked": True,
            "pending_stage5_decision": False,
        },
    )
    # ainvoke({}): 從 START 跑新 super-step,subgraph entry 看到 ready_to_handoff 直接走 emit_dual_output
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


async def reject_candidate(
    db: Session, session: SessionRow, rank: int
) -> GraphState:
    """BU 在工作區對某張候選卡按「不採用」:移除該卡、記下被拒方向。

    - 還有剩餘候選 → 卡片更新即可,agent 不主動講話(等 BU 繼續決策)。
    - 全部被拒 → stream 一段「換切角重新發想」的 agent 回覆,引導 BU 補新脈絡;
      被拒方向會餵進評分 prompt,下輪 BU 回覆時產出發散的新候選。
    """
    from app.graph.shared.state import CandidateDirection

    graph = await get_graph()
    config = {"configurable": {"thread_id": str(session.session_id)}}
    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    # normalize 成 CandidateDirection(state 內可能是 dict)
    scored = [
        c if isinstance(c, CandidateDirection)
        else CandidateDirection.model_validate(c)
        for c in state.scored_candidates
    ]
    removed = next((c for c in scored if c.rank == rank), None)
    remaining = [c for c in scored if c.rank != rank]

    # 找不到該 rank → 視為已移除,直接 republish 現況、回傳
    if removed is None:
        await bus.publish(
            str(session.session_id),
            "candidate_updated",
            {"candidates": [c.model_dump() for c in remaining]},
        )
        return state

    rejected = list(state.rejected_directions)
    if removed.direction not in rejected:
        rejected.append(removed.direction)

    await graph.aupdate_state(
        config,
        {
            "scored_candidates": remaining,
            "candidate_directions": remaining,
            "rejected_directions": rejected,
            # 清殘留選擇:被否決的卡可能正是先前 selected 的,殘留值會誤觸 handoff
            "selected_candidate": None,
        },
    )
    # 前端卡片消失(republish 剩餘清單)
    await bus.publish(
        str(session.session_id),
        "candidate_updated",
        {"candidates": [c.model_dump() for c in remaining]},
    )

    # 還有剩餘 → 不講話,等 BU 繼續決策
    if remaining:
        snap = await graph.aget_state(config)
        return GraphState.model_validate(snap.values)

    # 全部被拒 → stream「換切角重新發想」的 agent 回覆
    from app.graph.shared.prompts import render

    snap = await graph.aget_state(config)
    state = GraphState.model_validate(snap.values)

    bu_label = f"不採用 #{rank}：{removed.direction}"
    bu_turn_id, state = await _record_bu_option_choice(graph, config, state, bu_label)

    prompt_text = render(
        "reject_reexplore",
        bu=state.bu,
        sme_role=state.sme_role,
        rejected_directions=list(state.rejected_directions),
        recent_pain_signals=_recent_pain_signals(state),
        last_bu_text=_last_bu_text(state),
    )
    agent_turn_id = bu_turn_id + 1
    agent_text = await _stream_agent_reply(
        str(session.session_id),
        agent_turn_id,
        state.llm_model,
        prompt_text,
        fallback_text=(
            "謝謝你明確說不,這樣我們能更快找到對的方向。剛剛那些切角看來都不貼合,"
            "我們換個角度:你在這個流程裡,覺得最花時間或最常出錯的環節是哪一段?"
            "從那裡重新想,可能會找到更實際的方向。"
        ),
    )

    agent_trace = TraceEntry(
        turn_id=agent_turn_id,
        mode=state.mode,
        role="agent",
        raw_text=agent_text,
        timestamp=_now_iso(),
    )
    new_history = list(state.history) + [agent_trace]
    reject_patch: dict = {"history": new_history}
    # 在 stage 5 反覆「全否決卡片」也算卡關:累加 stage_5_rounds,
    # 讓收斂彈窗能在後續對話輪(converge_check)正常觸發。
    # 這裡只累計、不直接 emit 彈窗,避免與本輪剛 stream 的重新發想回覆搶話。
    from app.graph.explore.nodes import MAX_STAGE

    if state.stage >= MAX_STAGE and not state.stage_5_stuck_acked:
        reject_patch["stage_5_rounds"] = state.stage_5_rounds + 1
    await graph.aupdate_state(config, reject_patch)

    snap = await graph.aget_state(config)
    return GraphState.model_validate(snap.values)
