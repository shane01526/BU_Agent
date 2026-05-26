"""Explore subgraph 節點實作（technical_design.md §3.2.2）。

M4 起改用 Gemini:
- discovery_loop:用 explore_question.j2 產提問（streaming）
- extract_signals:用 extract_signals.j2 + structured output 抽 pain signals
- cluster + score:合併,用 score_candidates.j2 + structured output 一次產候選
- emit_dual_output:用 emit_paragraph.j2 產段落
- converge_check / cold detect:仍用 heuristic（規則明確、不需 LLM）
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from app.core.config import settings
from app.core.logging import get_logger
from app.graph.explore.question_bank import load_bank
from app.graph.shared.events import bus
from app.graph.shared.knowledge_loader import load_card
from app.graph.shared.llm import get_llm
from app.graph.shared.prompts import render
from app.graph.shared.state import (
    CandidateDirection,
    CandidateListOutput,
    GraphState,
    PainSignal,
    PainSignalListOutput,
    TraceEntry,
)

log = get_logger(__name__)

MAX_STAGE = 5


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _as_trace(h) -> TraceEntry:
    """Checkpoint 反序列化後 history 元素可能是 dict；統一 coerce 回 TraceEntry。"""
    if isinstance(h, TraceEntry):
        return h
    return TraceEntry.model_validate(h)


def _history(state: GraphState) -> list[TraceEntry]:
    return [_as_trace(h) for h in state.history]


# ---------- nodes ----------


RECENT_HISTORY_LIMIT = 8


def _recent(state: GraphState, limit: int = RECENT_HISTORY_LIMIT) -> list[dict]:
    return [
        {"role": h.role, "raw_text": h.raw_text}
        for h in _history(state)[-limit:]
    ]


DISSATISFIED_KEYWORDS = (
    # 核心否定
    "不太對", "不對", "都不是", "沒一個對",
    # 軟否定
    "不喜歡", "感覺不準", "不甚適合", "不適合",
    # 認另選
    "再來幾個", "想試別的", "想試試別的", "還有別的", "還有别的",
    "換一個", "換個", "其他",
    # 評論不足
    "太表面", "不夠具體", "別的面向", "别的面向",
)

ACK_GUIDE_MARKER = "整理在右側"


def _bu_mentions_any_candidate(text: str, candidates) -> bool:
    if not candidates:
        return False
    if any(tok in text for tok in ("#1", "#2", "#3", "第一", "第二", "第三")):
        return True
    for c in candidates:
        d = c.model_dump() if hasattr(c, "model_dump") else c
        direction = d.get("direction") or ""
        head = direction[:6]
        if head and head in text:
            return True
    return False


def needs_divergent_question(state: GraphState) -> bool:
    """stage>=4 後路由分流:
    True  → discovery_loop(換切角發散)
    False → acknowledge_and_guide(承接 + 引導選擇)

    觸發條件:
      A. BU 訊息含 DISSATISFIED_KEYWORDS
      B. agent 上一輪已是 acknowledge_and_guide(結尾含 ACK_GUIDE_MARKER)
         且 BU 這輪沒選卡片、訊息也沒提到任何候選
    """
    history = _history(state)
    last_bu = next((h for h in reversed(history) if h.role == "bu"), None)
    if last_bu is None:
        return False
    text = last_bu.raw_text

    if any(k in text for k in DISSATISFIED_KEYWORDS):
        return True

    last_agent = next((h for h in reversed(history) if h.role == "agent"), None)
    if last_agent and ACK_GUIDE_MARKER in last_agent.raw_text:
        if state.selected_candidate is None and not _bu_mentions_any_candidate(
            text, state.scored_candidates
        ):
            return True

    return False


async def discovery_loop(state: GraphState) -> dict:
    """用 prompt 產下一題,streaming 推 SSE。"""
    bank = load_bank()
    stage_def = bank.stage(state.stage)
    kc = load_card(state.bu)

    system = render(
        "system_explore",
        bu=state.bu,
        sme_role=state.sme_role,
        stage=state.stage,
        stage_intent=stage_def.intent,
        kc=kc,
    )
    user = render(
        "explore_question",
        recent_history=_recent(state),
        candidates=[c.model_dump() if hasattr(c, "model_dump") else c
                    for c in state.scored_candidates],
        stage=state.stage,
        seeds=stage_def.seeds,
    )

    llm = get_llm(state.llm_model)
    history = _history(state)
    turn_id = len(history) + 1

    full = ""
    async for chunk in llm.chat_stream(
        [{"role": "system", "content": system}, {"role": "user", "content": user}]
    ):
        full += chunk
        await bus.publish(
            state.session_id,
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": chunk},
        )

    full = full.strip()
    if not full:
        # 萬一 LLM 空回,fallback 到題庫 seed,確保 UI 不卡死
        full = stage_def.seeds[0]
        await bus.publish(
            state.session_id,
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": full},
        )

    await bus.publish(
        state.session_id,
        "agent_reply_done",
        {"turn_id": turn_id, "full_text": full, "stage": state.stage},
    )

    trace = TraceEntry(
        turn_id=turn_id,
        mode="explore",
        role="agent",
        raw_text=full,
        timestamp=_now_iso(),
    )
    return {"pending_question": full, "history": history + [trace]}


async def extract_signals(state: GraphState) -> dict:
    """從最新 BU reply 用 LLM structured output 抽 pain signals。"""
    history = _history(state)
    last_bu = next((h for h in reversed(history) if h.role == "bu"), None)
    if last_bu is None or len(last_bu.raw_text.strip()) < 4:
        return {}

    user = render(
        "extract_signals",
        bu_text=last_bu.raw_text[:600],
        bu=state.bu,
        candidates=[c.model_dump() if hasattr(c, "model_dump") else c
                    for c in state.scored_candidates],
    )

    llm = get_llm(state.llm_model)
    try:
        result = await llm.chat_structured(
            [{"role": "user", "content": user}], PainSignalListOutput
        )
        drafts = result.signals
    except Exception as e:
        log.warning("extract_signals.llm_failed", error=str(e))
        # fallback:把 BU 全段當一條 signal
        drafts = []
        if len(last_bu.raw_text.strip()) >= 4:
            from app.graph.shared.state import PainSignalDraft

            drafts = [
                PainSignalDraft(
                    raw_text=last_bu.raw_text[:200], source="bu_explicit", tags=[]
                )
            ]

    new_signals: list[PainSignal] = []
    for d in drafts:
        sig = PainSignal(
            turn_id=last_bu.turn_id,
            raw_text=d.raw_text[:200],
            source=d.source,
            tags=list(d.tags or []),
        )
        new_signals.append(sig)
        await bus.publish(
            state.session_id,
            "pain_signal_added",
            {"signal": sig.model_dump()},
        )

    if not new_signals:
        return {}

    existing_pains = [
        p if isinstance(p, PainSignal) else PainSignal.model_validate(p)
        for p in state.pain_signals
    ]
    return {"pain_signals": existing_pains + new_signals}


def _heuristic_candidates_fallback(state: GraphState) -> list[CandidateDirection]:
    """**僅 cold-start 用**:LLM 在第一輪就失敗、又無上輪候選時退回的固定 preset。

    一般情況下(已有上輪 scored_candidates)LLM 失敗時 score_candidates
    會走「保留上輪」分支,不再呼叫此 fallback。
    """
    bu = state.bu
    presets: dict[str, list[CandidateDirection]] = {
        "產險": [
            CandidateDirection(
                rank=1,
                direction="理賠文件型別自動分類",
                process_target="理賠文件型別",
                project_type="分類",
                score_5d={
                    "rule_repeat": 5,
                    "data_avail": 4,
                    "reversibility": 5,
                    "scale_roi": 4,
                    "gap": 5,
                },
                pain_signals=["人工歸檔耗時", "月均大量文件"],
            ),
            CandidateDirection(
                rank=2,
                direction="核保問題自動問答助手",
                process_target="核保 FAQ",
                project_type="QA",
                score_5d={
                    "rule_repeat": 4,
                    "data_avail": 3,
                    "reversibility": 4,
                    "scale_roi": 3,
                    "gap": 4,
                },
                pain_signals=["新人訓練成本高"],
            ),
        ],
        "壽險": [
            CandidateDirection(
                rank=1,
                direction="保戶通訊內容風險標記",
                process_target="客訴記錄",
                project_type="分類",
                score_5d={
                    "rule_repeat": 4,
                    "data_avail": 5,
                    "reversibility": 4,
                    "scale_roi": 4,
                    "gap": 4,
                },
                pain_signals=["人工逐筆檢閱量大"],
            ),
        ],
    }
    return presets.get(bu, presets["產險"])


async def cluster_pain_points(state: GraphState) -> dict:
    """M4：cluster 跟 score 合併到 score_candidates 一次完成（LLM 一次出候選+評分）。
    這節點保留以維持 graph 拓撲；不做事。"""
    return {}


async def score_candidates(state: GraphState) -> dict:
    """用 LLM 把 pain signals 聚類 + 5 維評分。

    LLM 失敗策略(避免「override 後突變成不相關 preset」):
    - 失敗 + 已有上一輪 scored_candidates → 保留上輪不更新(只 republish 給新訂閱者)
    - 失敗 + 從未有 scored_candidates(冷啟首輪)→ 才套 _heuristic_candidates_fallback
    """
    # 既存候選(用於 republish 與保留判斷),統一 normalize 成 CandidateDirection
    existing = [
        c if isinstance(c, CandidateDirection) else CandidateDirection.model_validate(c)
        for c in state.scored_candidates
    ]

    # 沒任何 pain signal → 不產新候選;但若已有舊候選 republish 給新訂閱者
    pains = [
        p if isinstance(p, PainSignal) else PainSignal.model_validate(p)
        for p in state.pain_signals
    ]
    if not pains:
        if existing:
            await bus.publish(
                state.session_id,
                "candidate_updated",
                {"candidates": [c.model_dump() for c in existing]},
            )
        return {}

    kc = load_card(state.bu)
    user = render(
        "score_candidates",
        bu=state.bu,
        sme_role=state.sme_role,
        pain_signals=[{"raw_text": p.raw_text, "source": p.source} for p in pains],
        kc=kc,
    )

    llm = get_llm(state.llm_model)
    scored: list[CandidateDirection] = []
    llm_ok = False
    try:
        result = await llm.chat_structured(
            [{"role": "user", "content": user}], CandidateListOutput
        )
        for d in result.candidates:
            scored.append(
                CandidateDirection(
                    rank=d.rank,
                    direction=d.direction,
                    process_target=d.process_target,
                    project_type=d.project_type,
                    score_5d=d.score_5d.model_dump(),
                    pain_signals=list(d.pain_signals or []),
                    solution_class=d.solution_class,
                    ai_necessity=d.ai_necessity,
                    solution_rationale=d.solution_rationale,
                )
            )
        llm_ok = bool(scored)
    except Exception as e:
        log.warning("score_candidates.llm_failed", error=str(e))

    # LLM 失敗(或回空) + 已有上一輪 candidates → 保留不變,避免畫面突然變 preset
    if not llm_ok and existing:
        log.info(
            "score_candidates.keep_previous",
            n_existing=len(existing),
            reason="llm_failed_or_empty_with_prior",
        )
        await bus.publish(
            state.session_id,
            "candidate_updated",
            {"candidates": [c.model_dump() for c in existing]},
        )
        # 不累加 streak、不重發 warning、不改 state
        return {}

    # LLM 失敗 + 從未有候選(冷啟首輪)→ 套 preset 確保 UI 不空白
    if not llm_ok:
        scored = _heuristic_candidates_fallback(state)

    await bus.publish(
        state.session_id,
        "candidate_updated",
        {"candidates": [c.model_dump() for c in scored]},
    )

    # AI 必要性 triage:看 top 1(排序後 rank=1)的 ai_necessity
    patch: dict = {"scored_candidates": scored, "candidate_directions": scored}
    top = next((c for c in scored if c.rank == 1), scored[0] if scored else None)
    top_low = top is not None and top.ai_necessity == "low"
    new_streak = (state.low_ai_necessity_streak + 1) if top_low else 0
    patch["low_ai_necessity_streak"] = new_streak

    AI_NECESSITY_STREAK_THRESHOLD = 2
    if (
        new_streak >= AI_NECESSITY_STREAK_THRESHOLD
        and not state.ai_necessity_warned
        and top is not None
    ):
        await bus.publish(
            state.session_id,
            "ai_necessity_warning",
            {
                "solution_class": top.solution_class,
                "rationale": top.solution_rationale or "",
                "top_candidate": top.model_dump(),
                "candidates": [c.model_dump() for c in scored[:3]],
            },
        )
        # 立即標記已警示,避免 BU 還沒按 modal 又連續送訊息時 streak 累加再次觸發 publish
        # (BU 之後按 modal 三選一 service 仍會冗餘設 True,無害)
        patch["ai_necessity_warned"] = True
        # 鎖住本 super-step,after_converge 看到此 flag 會直接 END,
        # 避免 graph 繼續走 acknowledge_and_guide / discovery_loop 搶話。
        # 三個 modal endpoint(acknowledge/override/explain)的 service 會 clear 此 flag。
        patch["pending_ai_necessity_decision"] = True

    return patch


async def converge_check(state: GraphState) -> dict:
    """Stage 遞進。Stage 5 + 有 selected_candidate 或 2 輪 cold → 終止。"""
    history = _history(state)
    # cold detect：最後 2 個 bu turns 都很短 / 含否定關鍵詞
    bu_turns = [h for h in history if h.role == "bu"]
    cold_hits = 0
    for t in bu_turns[-2:]:
        if any(k in t.raw_text for k in ["不太對", "不對", "沒想法", "no"]):
            cold_hits += 1
    if cold_hits >= 2:
        reason = "兩輪明確否定，建議離線找 BA 對焦"
        await bus.publish(
            state.session_id,
            "cold_exit",
            {"reason": reason},
        )
        return {"mode": "cold", "cold_exit_reason": reason}

    next_stage = min(state.stage + 1, MAX_STAGE)
    # Ready 判斷：用 next_stage（本輪結束後的階段）；若已停在 5 + 選了 candidate 則進 handoff
    ready = next_stage == MAX_STAGE and state.selected_candidate is not None
    patch: dict = {"stage": next_stage}
    if next_stage != state.stage:
        await bus.publish(
            state.session_id,
            "stage_changed",
            {"stage": next_stage},
        )

    # Stage 5 卡關偵測:已在 stage 5、跑滿 N 輪、還沒選 candidate、未 ack 過 → 推 stage5_stuck
    STAGE5_STUCK_THRESHOLD = 3
    if next_stage == MAX_STAGE and state.selected_candidate is None:
        new_s5_rounds = state.stage_5_rounds + 1
        patch["stage_5_rounds"] = new_s5_rounds
        if (
            new_s5_rounds >= STAGE5_STUCK_THRESHOLD
            and not state.stage_5_stuck_acked
        ):
            top_candidates = [
                c.model_dump() if hasattr(c, "model_dump") else c
                for c in state.scored_candidates[:3]
            ]
            await bus.publish(
                state.session_id,
                "stage5_stuck",
                {
                    "rounds": new_s5_rounds,
                    "candidates": top_candidates,
                },
            )
            # 鎖住本 super-step;after_converge 看到此 flag 直接 END,
            # 避免 graph 繼續走 discovery_loop / acknowledge_and_guide 搶話。
            # dismiss_stage5_stuck / quick_handoff service 會 clear 此 flag。
            patch["pending_stage5_decision"] = True

    if ready:
        patch["ready_to_handoff"] = True
    return patch


async def acknowledge_and_guide(state: GraphState) -> dict:
    """v8: stage>=4 + 已有候選時走這條,回應 BU 上一句並引導去看右側候選卡。

    不問新探索性問題(那是 v7 要修的 UX 問題:候選卡剛冒出來就被新提問蓋過)。
    短回應確保 chat 不會在 AI necessity modal 彈完之後卡死、看起來像 agent 不回。
    """
    history = _history(state)
    last_bu = next((h for h in reversed(history) if h.role == "bu"), None)
    if last_bu is None:
        return {}

    user = render(
        "acknowledge_and_guide",
        last_bu_text=last_bu.raw_text,
        candidates=[
            c.model_dump() if hasattr(c, "model_dump") else c
            for c in state.scored_candidates
        ],
    )
    turn_id = len(history) + 1
    full = ""
    try:
        llm = get_llm(state.llm_model)
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": user}]
        ):
            full += chunk
            await bus.publish(
                state.session_id,
                "agent_reply_delta",
                {"turn_id": turn_id, "text_delta": chunk},
            )
        full = full.strip()
    except Exception as e:
        log.warning("acknowledge_and_guide.llm_failed", error=str(e))

    if not full:
        full = "了解,我把幾個可能方向整理在右側,你覺得哪一個最貼近你想推進的?"
        await bus.publish(
            state.session_id,
            "agent_reply_delta",
            {"turn_id": turn_id, "text_delta": full},
        )

    await bus.publish(
        state.session_id,
        "agent_reply_done",
        {"turn_id": turn_id, "full_text": full, "stage": state.stage},
    )

    trace = TraceEntry(
        turn_id=turn_id,
        mode="explore",
        role="agent",
        raw_text=full,
        timestamp=_now_iso(),
    )
    return {"pending_question": full, "history": history + [trace]}


async def emit_dual_output(state: GraphState) -> dict:
    """產雙輸出：(A) structured JSON（deterministic）+ (B) LLM 寫的段落描述。"""
    selected_rank = state.selected_candidate or 1
    candidates = [
        c if isinstance(c, CandidateDirection) else CandidateDirection.model_validate(c)
        for c in state.scored_candidates
    ]
    candidate = next(
        (c for c in candidates if c.rank == selected_rank),
        candidates[0] if candidates else None,
    )
    if candidate is None:
        log.warning("emit_dual_output: no candidates available")
        return {}

    # (A) Structured JSON：deterministic 組裝
    structured = {
        "exploration_id": f"ex_{uuid.uuid4().hex[:10]}",
        "bu": state.bu,
        "sme_role": state.sme_role,
        "candidates": [c.model_dump() for c in candidates],
        "selected_candidate": selected_rank,
        "predicted_consult_fields": {
            "bu": state.bu,
            "process_target": candidate.process_target,
            "project_type": candidate.project_type,
            "one_line_goal": f"以 AI 協助{candidate.direction}",
        },
        # AI 必要性 triage 結果(給 BA Agent / AI 科 review)
        "ai_necessity_triage": {
            "selected_solution_class": candidate.solution_class,
            "selected_ai_necessity": candidate.ai_necessity,
            "selected_rationale": candidate.solution_rationale,
            "bu_overrode": state.bu_overrode_ai_necessity,
        },
        "trace": [t.model_dump() for t in _history(state)],
    }

    # (B) Paragraph：LLM 產 200-400 字
    user = render(
        "emit_paragraph",
        bu=state.bu,
        sme_role=state.sme_role,
        selected=candidate.model_dump(),
        recent_history=_recent(state, limit=8),
    )
    paragraph = ""
    try:
        llm = get_llm(state.llm_model)
        async for chunk in llm.chat_stream(
            [{"role": "user", "content": user}]
        ):
            paragraph += chunk
        paragraph = paragraph.strip()
    except Exception as e:
        log.warning("emit_dual_output.paragraph_llm_failed", error=str(e))

    # 字數守門 + fallback：LLM 失敗或字數過短/過長都退回 deterministic 模板
    if len(paragraph) < 80 or len(paragraph) > 600:
        paragraph = (
            f"{state.bu} SME（{state.sme_role}）目前最希望處理的議題是「{candidate.direction}」。"
            f"痛點集中在 {', '.join(candidate.pain_signals) or '（待補）'}。"
            f"AI 切入位置為 {candidate.process_target} 的{candidate.project_type}任務,"
            f"預期輸入為相關工作文件、輸出為分類或標註結果。"
            f"此方向為 BU 於本次對話中明確選定;候選評分 5 維度顯示具備可重複規則、資料可得、"
            f"可事後覆核、具規模效益的特性。請 BU 確認是否以此為 BRD 初稿核心。"
        )

    await bus.publish(
        state.session_id,
        "handoff_ready",
        {"paragraph": paragraph, "structured": structured},
    )
    return {
        "structured_json": structured,
        "paragraph_description": paragraph,
    }


async def handoff_confirm(state: GraphState) -> dict:
    """等 BU 在前端 modal 決定。interrupt 在 graph builder 中定義。"""
    # 這個節點不做事；interrupt 由 graph 在進入 consult_subgraph 前處理。
    await asyncio.sleep(0)
    return {}
