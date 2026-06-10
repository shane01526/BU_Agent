'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ChatPanel, historyToMessages, type ChatMessage } from '@/components/chat/ChatPanel';
import { ConsultFullscreenLayout } from '@/components/consult/ConsultFullscreenLayout';
import { ProgressBar } from '@/components/layout/ProgressBar';
import { HandoffConfirmModal } from '@/components/modal/HandoffConfirmModal';
import { Stage5StuckModal } from '@/components/modal/Stage5StuckModal';
import { AiNecessityWarningModal } from '@/components/modal/AiNecessityWarningModal';
import { CandidateCards, type Candidate } from '@/components/workspace/CandidateCards';
import { PainTimeline, type PainSignalItem } from '@/components/workspace/PainTimeline';
import { api, type SectionAction, type SectionState, type SessionFullState } from '@/lib/api';
import { useSessionEvents, type SseEvent } from '@/lib/sse';

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id;
  const router = useRouter();
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['session', sessionId],
    queryFn: () => api.getSession(sessionId),
    refetchOnMount: 'always',
  });

  // 對話訊息：先從 REST 的 history 抽出，再疊加 SSE streaming chunk
  const [liveMessages, setLiveMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState<{ turnId: number; text: string } | null>(null);
  const [awaitingAgent, setAwaitingAgent] = useState(false);
  const [liveCandidates, setLiveCandidates] = useState<Candidate[] | null>(null);
  const [livePains, setLivePains] = useState<PainSignalItem[] | null>(null);
  const [handoff, setHandoff] = useState<{ paragraph: string } | null>(null);
  const [selectedRank, setSelectedRank] = useState<number | null>(null);
  const [liveSections, setLiveSections] = useState<SectionState[] | null>(null);
  const [pendingSectionId, setPendingSectionId] = useState<string | null>(null);
  const [generatingHandoff, setGeneratingHandoff] = useState(false);
  const [generatingOutline, setGeneratingOutline] = useState(false);
  const [stage5Stuck, setStage5Stuck] = useState<{
    rounds: number;
    candidates: Candidate[];
  } | null>(null);
  const lastStuckEventIdRef = useRef<number>(0);
  const [aiNecessityWarn, setAiNecessityWarn] = useState<{
    solutionClass: string;
    rationale: string;
  } | null>(null);
  const lastAiNecessityEventIdRef = useRef<number>(0);
  // SSE replay 會把舊 handoff_ready 重送一遍;用 ref 保存當前 mode,
  // 已進 consult 後忽略再來的 handoff_ready
  const modeRef = useRef<string>(data?.mode ?? 'explore');
  useEffect(() => {
    modeRef.current = data?.mode ?? 'explore';
  }, [data?.mode]);
  // 記下最後處理過的 handoff event id;replay 來相同或更舊就略過
  const lastHandoffEventIdRef = useRef<number>(0);

  // SSE replay 防呆:reload 後 backend ring buffer 會 replay 過去的 ai_necessity_warning
  // 與 stage5_stuck。SSE handler 從 react-query cache 同步讀 graph state 旗標決定是否略過,
  // 比 useEffect 同步 ref 更接近真實狀態(useEffect 有 microtask 延遲)。
  // 額外搭 cleanup effect 兜底:若 SSE replay 比 useQuery 還快、modal 已開,
  // useQuery settle 後若旗標已 acked 就強制關 modal(最壞情況閃一下,不殘留)。
  useEffect(() => {
    if (
      data?.stage_5_stuck_acked &&
      !data?.pending_stage5_decision &&
      stage5Stuck
    ) {
      setStage5Stuck(null);
    }
    if (
      data?.ai_necessity_warned &&
      !data?.pending_ai_necessity_decision &&
      aiNecessityWarn
    ) {
      setAiNecessityWarn(null);
    }
  }, [
    data?.stage_5_stuck_acked,
    data?.pending_stage5_decision,
    data?.ai_necessity_warned,
    data?.pending_ai_necessity_decision,
    stage5Stuck,
    aiNecessityWarn,
  ]);

  // 對話訊息來源切換：
  // - 首次 mount（liveMessages 空）→ 用 REST history 還原（resume 用）
  // - 一旦 SSE 有事件 → 改以 liveMessages 為單一來源，避免 refetch 重抓造成 BU 訊息重複
  const chatMessages = useMemo<ChatMessage[]>(() => {
    // 一旦本 session 有 SSE 事件進來 → 改以 liveMessages 為單一來源,
    // 避免 GET /sessions 的 history 與 SSE 重抓造成重複。
    const base = liveMessages.length > 0 ? [] : historyToMessages(data);
    const merged = [...base, ...liveMessages];
    if (streaming) {
      merged.push({
        turn_id: streaming.turnId,
        role: 'agent',
        text: streaming.text,
        streaming: true,
      });
    }
    return dedupe(merged);
  }, [data, liveMessages, streaming]);

  const candidates = liveCandidates ?? data?.candidates ?? [];
  const painSignals = livePains ?? data?.pain_signals ?? [];
  const sections: SectionState[] = liveSections ?? (data?.sections as SectionState[]) ?? [];

  const onEvent = useCallback(
    (ev: SseEvent) => {
      const d = ev.data as Record<string, unknown>;
      switch (ev.type) {
        case 'agent_reply_delta': {
          const turnId = Number(d.turn_id ?? 0);
          const delta = String(d.text_delta ?? '');
          setStreaming((prev) =>
            prev && prev.turnId === turnId
              ? { turnId, text: prev.text + delta }
              : { turnId, text: delta },
          );
          setAwaitingAgent(false);
          break;
        }
        case 'agent_reply_done': {
          const turnId = Number(d.turn_id ?? 0);
          const fullText = String(d.full_text ?? '');
          // 把 streaming 的最終文字「定版」進 liveMessages，避免靠 refetch 才看得到
          setLiveMessages((prev) => [
            ...prev,
            { turn_id: turnId, role: 'agent', text: fullText },
          ]);
          setStreaming(null);
          // Consult Step 2：agent 是針對某章節提問,記下來給 OutlineTree 標 pending
          if (d.section_id) {
            setPendingSectionId(String(d.section_id));
          }
          // 重抓最新 state（含新 trace）；refetch 回來後 dedupe 會擋掉重複
          qc.invalidateQueries({ queryKey: ['session', sessionId] });
          break;
        }
        case 'bu_turn_recorded': {
          // backend 落了 BU trace；append 到 liveMessages（dedupe 會擋掉重複）
          const turnId = Number(d.turn_id ?? Date.now());
          const text = String(d.text ?? '');
          setLiveMessages((prev) => [
            ...prev,
            { turn_id: turnId, role: 'bu', text },
          ]);
          break;
        }
        case 'candidate_updated': {
          setLiveCandidates((d.candidates as Candidate[]) ?? []);
          break;
        }
        case 'pain_signal_added': {
          setLivePains((prev) => {
            const arr = prev ?? (data?.pain_signals ?? []);
            return [...arr, d.signal as PainSignalItem];
          });
          break;
        }
        case 'handoff_ready': {
          setGeneratingHandoff(false);
          // 已進 consult 後不再彈 modal,且同一個 event id 不重彈(避開 replay)
          if (modeRef.current === 'explore' && ev.id > lastHandoffEventIdRef.current) {
            lastHandoffEventIdRef.current = ev.id;
            setHandoff({ paragraph: String(d.paragraph ?? '') });
          }
          break;
        }
        case 'mode_changed': {
          qc.invalidateQueries({ queryKey: ['session', sessionId] });
          break;
        }
        case 'cold_exit': {
          qc.invalidateQueries({ queryKey: ['session', sessionId] });
          break;
        }
        case 'stage5_stuck': {
          // SSE replay 防護:同一 event id 不重彈
          if (modeRef.current !== 'explore') break;
          if (ev.id <= lastStuckEventIdRef.current) break;
          // 從 react-query cache 同步讀 graph state:
          //  - acked && !pending → BU 已選過,replay 來的 stuck 略過
          //  - acked && pending  → 上次離開時 BU 還沒選,reload 後仍要彈讓他完成決策
          const cur = qc.getQueryData<SessionFullState>(['session', sessionId]);
          if (cur?.stage_5_stuck_acked && !cur?.pending_stage5_decision) break;
          lastStuckEventIdRef.current = ev.id;
          setStage5Stuck({
            rounds: Number(d.rounds ?? 0),
            candidates: (d.candidates as Candidate[]) ?? [],
          });
          break;
        }
        case 'ai_necessity_warning': {
          if (modeRef.current !== 'explore') break;
          if (ev.id <= lastAiNecessityEventIdRef.current) break;
          // SSE 連線重新建立時 backend ring buffer 會 replay 整段歷史。
          // 從 react-query cache 同步讀 graph state:
          //  - warned && !pending → BU 已選過,replay 來的 warning 略過
          //  - warned && pending  → 上次離開時 BU 還沒選,reload 後仍要彈讓他完成決策
          //  - !warned            → 第一次發,該彈
          const cur = qc.getQueryData<SessionFullState>(['session', sessionId]);
          if (cur?.ai_necessity_warned && !cur?.pending_ai_necessity_decision) break;
          lastAiNecessityEventIdRef.current = ev.id;
          setAiNecessityWarn({
            solutionClass: String(d.solution_class ?? 'rpa'),
            rationale: String(d.rationale ?? ''),
          });
          break;
        }
        case 'outline_ready': {
          setGeneratingOutline(false);
          const incoming = (d.sections as Array<Record<string, unknown>>) ?? [];
          // backend section state 內容欄位是 draft_content;前端統一用 content_md
          setLiveSections(
            incoming.map((s) => ({
              section_id: String(s.section_id ?? ''),
              title: String(s.title ?? ''),
              status: s.status as SectionState['status'],
              content_md: String(s.draft_content ?? ''),
              last_edit_by: (s.last_edit_by as 'agent' | 'bu' | null) ?? null,
            })),
          );
          // outline 出現後第一個 needs_round2 由 section_loop 提問
          // section_id 由後續 agent_reply_done(section_id=...) 設置
          break;
        }
        case 'section_updated': {
          const sec = d.section as Record<string, unknown> | undefined;
          if (!sec) break;
          setLiveSections((prev) => {
            const base = prev ?? (data?.sections as SectionState[]) ?? [];
            return base.map((s) =>
              s.section_id === sec.section_id
                ? {
                    ...s,
                    status: sec.status as SectionState['status'],
                    content_md: String(sec.draft_content ?? s.content_md),
                    last_edit_by:
                      (sec.last_edit_by as 'agent' | 'bu' | null) ?? s.last_edit_by,
                  }
                : s,
            );
          });
          break;
        }
        case 'current_section_changed': {
          // backend 已決定切到下一章;立刻 set pendingSectionId,
          // 讓 Strip / SectionInlineHeader 立刻跳到新章,不必等 agent_reply_done
          const sid = String(d.section_id ?? '');
          if (sid) setPendingSectionId(sid);
          break;
        }
        case 'deliverables_ready': {
          // 跳到完成畫面
          router.push(`/sessions/${sessionId}/done`);
          break;
        }
        case 'turn_done': {
          // 兜底:有些 graph 路徑(stage>=4 silent END、cold_exit、ai_necessity 警示)
          // 不會發 agent_reply_delta,只能靠這個事件解鎖輸入框。
          setAwaitingAgent(false);
          break;
        }
        case 'conflict_detected': {
          const cs = (d.conflicts as Array<{ section_ids: string[]; description: string }>) ?? [];
          if (cs.length) {
            alert(
              `章節間發現 ${cs.length} 處可能矛盾,請檢視:\n\n` +
                cs
                  .map(
                    (c, i) =>
                      `${i + 1}. [${c.section_ids.join(', ')}] ${c.description}`,
                  )
                  .join('\n'),
            );
          }
          break;
        }
        case 'heartbeat':
          break;
      }
    },
    [qc, sessionId, data?.pain_signals],
  );

  useSessionEvents(sessionId, onEvent);

  const sendMutation = useMutation({
    mutationFn: (text: string) => api.postMessage(sessionId, text),
  });

  function handleSend(text: string) {
    // 不做 optimistic：等 backend 的 bu_turn_recorded SSE 回來再 append。
    // backend 通常 < 100ms 就 publish，使用者體感差異很小，但不會有重複訊息。
    setAwaitingAgent(true);
    sendMutation.mutate(text);
  }

  async function handleSelectCandidate(rank: number) {
    setSelectedRank(rank);
    setGeneratingHandoff(true);
    try {
      await api.selectCandidate(sessionId, rank);
    } catch (e) {
      setGeneratingHandoff(false);
      throw e;
    }
    // 不在這裡關 generatingHandoff:由 handoff_ready SSE 事件抵達時關閉
  }

  async function handleRejectCandidate(rank: number) {
    // 只有「最後一張卡」被否決時,後端才會 stream agent 回覆 → 才顯示思考中。
    // 否決其中一張(還有剩)時不顯示 thinking;卡片移除由 candidate_updated SSE 驅動。
    const isLast = candidates.length <= 1;
    if (isLast) setAwaitingAgent(true);
    try {
      await api.rejectCandidate(sessionId, rank);
    } catch (e) {
      if (isLast) setAwaitingAgent(false);
      throw e;
    }
    setSelectedRank(null); // 否決後清高亮,避免殘留選擇
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleConfirm() {
    setHandoff(null);
    setGeneratingOutline(true);
    try {
      await api.confirmHandoff(sessionId);
    } finally {
      qc.invalidateQueries({ queryKey: ['session', sessionId] });
      // 大綱出來會由 outline_ready 事件關閉;這裡兜底
      setGeneratingOutline(false);
    }
  }

  async function handleDismissHandoff() {
    await api.dismissHandoff(sessionId);
    setHandoff(null);
    setSelectedRank(null); // 清前端高亮,與後端清 selected_candidate 一致
  }

  async function handleEditSection(sectionId: string, content: string) {
    await api.editSection(sessionId, sectionId, content);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleSectionAction(sectionId: string, action: SectionAction) {
    await api.sectionAction(sessionId, sectionId, action);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleSelectSection(sectionId: string) {
    // BU 主動切到某章 → backend reset 為 needs_round2 + 推 graph 重訪
    setAwaitingAgent(true);
    try {
      await api.selectSection(sessionId, sectionId);
    } catch (e) {
      setAwaitingAgent(false);
      throw e;
    }
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
    // awaitingAgent 由 agent_reply_delta 收到時自動關閉
  }

  async function handleSubmitSession() {
    if (!confirm('確定送 BA review？送出後就無法再修改 BRD。')) return;
    await api.submitSession(sessionId);
    router.push(`/sessions/${sessionId}/done`);
  }

  async function handleAiExplain() {
    // BU 標籤走 SSE bu_turn_recorded、agent reply 走 agent_reply_delta/done
    // 由後端 _spawn 背景跑;awaitingAgent 由第一個 agent_reply_delta 自動關
    setAwaitingAgent(true);
    setAiNecessityWarn(null);
    await api.explainAiNecessity(sessionId);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleAiOverride() {
    setAwaitingAgent(true);
    setAiNecessityWarn(null);
    await api.overrideAiNecessity(sessionId);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleAiAcknowledge() {
    setAwaitingAgent(true);
    setAiNecessityWarn(null);
    await api.acknowledgeAiNecessity(sessionId);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleAiResetExplore() {
    setAiNecessityWarn(null);
    await handleResetExplore();
  }

  async function handleStuckKeepTalking() {
    // BU 標籤走 SSE bu_turn_recorded、agent reply 走 agent_reply_delta/done
    // 由後端 _spawn 背景跑;awaitingAgent 由第一個 agent_reply_delta 自動關
    setAwaitingAgent(true);
    setStage5Stuck(null);
    await api.dismissStage5Stuck(sessionId);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  async function handleStuckQuickHandoff(rank: number) {
    // 不 stream agent reply,直接走 handoff 流程
    setStage5Stuck(null);
    setSelectedRank(rank);
    setGeneratingHandoff(true);
    try {
      await api.quickHandoff(sessionId, rank);
      qc.invalidateQueries({ queryKey: ['session', sessionId] });
    } catch (e) {
      setGeneratingHandoff(false);
      throw e;
    }
  }

  async function handleStuckResetExplore() {
    setStage5Stuck(null);
    await handleResetExplore();
  }

  async function handleResetExplore() {
    if (!confirm('確定要回到 Explore 重新探索嗎？目前的對話紀錄、候選方向、BRD 大綱都會被清空，agent 會重新出第一題。')) return;
    await api.resetExplore(sessionId);
    // 清光所有 client-side live state；refetch 後 history 也會是空
    setLiveMessages([]);
    setStreaming(null);
    setAwaitingAgent(false);
    setLiveCandidates(null);
    setLivePains(null);
    setLiveSections(null);
    setPendingSectionId(null);
    setSelectedRank(null);
    setHandoff(null);
    setStage5Stuck(null);
    setAiNecessityWarn(null);
    setGeneratingHandoff(false);
    setGeneratingOutline(false);
    qc.invalidateQueries({ queryKey: ['session', sessionId] });
  }

  if (isLoading || !data) {
    return <main className="p-6 text-neutral-500">載入 session…</main>;
  }

  const mode = data.mode;
  const canSubmit =
    sections.length > 0 &&
    !sections.some((s) => s.status === 'needs_round2');
  const isConsultMode = mode === 'consult_step1' || mode === 'consult_step2';

  // 彈窗(AI 必要性 / stage5 卡關)pending 時,先不顯示候選卡片,讓使用者專心跟 agent 對話。
  const modalPending =
    !!aiNecessityWarn ||
    !!stage5Stuck ||
    data.pending_ai_necessity_decision ||
    data.pending_stage5_decision;
  const exploreCandidates = modalPending ? [] : candidates;
  // 只要有未決定的候選卡片(且非生成 handoff 中),就鎖聊天輸入框,逼使用者先逐一抉擇。
  const cardsLocking = exploreCandidates.length > 0 && !generatingHandoff;

  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b bg-white px-6 py-3">
        <Link href="/sessions" className="text-sm text-neutral-500 hover:underline">
          ← sessions
        </Link>
        <div className="flex items-center gap-3">
          <ProgressBar mode={mode} />
          <span className="text-xs text-neutral-500">
            {data.bu} · stage {data.stage ?? 1}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isConsultMode && (
            <button
              onClick={handleResetExplore}
              className="text-xs rounded border px-2 py-1 hover:bg-neutral-50 text-neutral-600"
              title="回到 Explore 重選方向"
            >
              ← 重新探索
            </button>
          )}
          {isConsultMode && (
            <button
              onClick={handleSubmitSession}
              disabled={!canSubmit}
              title={canSubmit ? '送 BA review' : '還有 needs_round2 章節未處理'}
              className={
                canSubmit
                  ? 'text-xs rounded bg-accent px-3 py-1 font-medium text-white hover:bg-accent-muted'
                  : 'text-xs rounded bg-neutral-200 px-3 py-1 font-medium text-neutral-400 cursor-not-allowed'
              }
            >
              送 BA →
            </button>
          )}
        </div>
      </header>

      {mode === 'explore' || mode === 'cold' ? (
        <div className="flex flex-1 overflow-hidden">
          <section className="flex w-1/2 flex-col border-r">
            <ChatPanel
              messages={chatMessages}
              disabled={
                awaitingAgent ||
                !!aiNecessityWarn ||
                !!stage5Stuck ||
                cardsLocking ||
                data.status !== 'active'
              }
              disabledHint={
                cardsLocking
                  ? '請先在右側對每個候選方向選擇「採用」或「不採用」才能繼續對話'
                  : undefined
              }
              thinking={
                !streaming &&
                (awaitingAgent ||
                  // 剛進新 session 還沒收到 agent 開場時也顯示
                  (chatMessages.length === 0 && mode === 'explore'))
              }
              onSend={handleSend}
            />
          </section>
          <section className="w-1/2 overflow-y-auto bg-neutral-50 p-6">
            <ExploreWorkspace
              candidates={exploreCandidates}
              selectedRank={selectedRank}
              onSelectCandidate={handleSelectCandidate}
              onRejectCandidate={handleRejectCandidate}
              painSignals={painSignals}
              mode={mode}
              coldReason={data.mode === 'cold' ? '建議離線找 BA 對焦' : null}
              generatingHandoff={generatingHandoff}
            />
          </section>
        </div>
      ) : (
        <ConsultFullscreenLayout
          sections={sections}
          pendingSectionId={pendingSectionId}
          generatingOutline={sections.length === 0 || generatingOutline}
          messages={chatMessages}
          chatDisabled={awaitingAgent || data.status !== 'active'}
          thinking={!streaming && awaitingAgent}
          onSend={handleSend}
          onEditSection={handleEditSection}
          onSectionAction={handleSectionAction}
          onSelectSection={handleSelectSection}
        />
      )}

      <HandoffConfirmModal
        open={!!handoff}
        paragraph={handoff?.paragraph ?? ''}
        onConfirm={handleConfirm}
        onDiscuss={handleDismissHandoff}
      />

      <Stage5StuckModal
        open={!!stage5Stuck}
        rounds={stage5Stuck?.rounds ?? 0}
        candidates={stage5Stuck?.candidates ?? []}
        onKeepTalking={handleStuckKeepTalking}
        onQuickHandoff={handleStuckQuickHandoff}
        onResetExplore={handleStuckResetExplore}
      />

      <AiNecessityWarningModal
        open={!!aiNecessityWarn}
        solutionClass={aiNecessityWarn?.solutionClass ?? ''}
        rationale={aiNecessityWarn?.rationale ?? ''}
        onExplain={handleAiExplain}
        onOverride={handleAiOverride}
        onAcknowledge={handleAiAcknowledge}
        onResetExplore={handleAiResetExplore}
      />
    </main>
  );
}

function ExploreWorkspace({
  candidates,
  selectedRank,
  onSelectCandidate,
  onRejectCandidate,
  painSignals,
  mode,
  coldReason,
  generatingHandoff,
}: {
  candidates: Candidate[];
  selectedRank: number | null;
  onSelectCandidate: (rank: number) => void;
  onRejectCandidate: (rank: number) => void;
  painSignals: PainSignalItem[];
  mode: string;
  coldReason: string | null;
  generatingHandoff: boolean;
}) {
  if (mode === 'cold') {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-900 space-y-3">
        <h2 className="text-base font-semibold">這次的探索先到這裡</h2>
        <p>{coldReason || '建議離線找 BA 對焦,把方向釐清後再回來開新諮詢。'}</p>
        <ul className="list-disc pl-5 text-amber-800 space-y-1">
          <li>已暫存對話紀錄;BA 可從 sessions 列表查到本次脈絡</li>
          <li>之後若想嘗試其他方向,請點頂部「← sessions」回首頁開新諮詢</li>
        </ul>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      {generatingHandoff && (
        <div className="flex items-center gap-3 rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-accent">
          <span className="inline-block h-2 w-2 animate-ping rounded-full bg-accent" />
          <div>
            <div className="font-medium">正在彙整本次探索的綜整描述…</div>
            <div className="text-xs text-neutral-500">
              通常需要 5–15 秒;產出後會跳出確認視窗。
            </div>
          </div>
        </div>
      )}
      {candidates.length > 0 && !generatingHandoff && (
        <div className="rounded-lg border border-accent/30 bg-accent/5 px-4 py-3 text-sm text-accent">
          <div className="font-medium">
            請對下方每個候選方向都做出選擇，才能進下一步
          </div>
          <div className="mt-0.5 text-xs text-neutral-600">
            點各維度方塊可看評分理由。採用任一方向 → 進入 BRD 諮詢；
            全部不採用 → 我會換個切角重新發想。這段期間聊天輸入框會暫時鎖定。
          </div>
        </div>
      )}
      <section>
        <h2 className="mb-2 text-sm font-semibold text-neutral-700">候選方向</h2>
        <CandidateCards
          candidates={candidates}
          selected={selectedRank}
          onSelect={onSelectCandidate}
          onReject={onRejectCandidate}
          generatingHandoff={generatingHandoff}
        />
      </section>
      <section>
        <h2 className="mb-2 text-sm font-semibold text-neutral-700">Pain signals</h2>
        <PainTimeline signals={painSignals} />
      </section>
    </div>
  );
}

function dedupe(messages: ChatMessage[]): ChatMessage[] {
  // 兩個來源都使用 backend 真實 turn_id：
  //   - SSE bu_turn_recorded.turn_id == backend 認可
  //   - GET /sessions 的 history.turn_id == backend 認可
  // 所以 (role, turn_id) 即可唯一識別一條訊息;
  // 同一輪同一 role 之間若 SSE 與 refetch 都送來,turn_id 也會相同 → dedupe 成功。
  // BU 即使連送相同文字,turn_id 不同 → 各自保留。
  const seen = new Set<string>();
  const out: ChatMessage[] = [];
  for (const m of messages) {
    const key = `${m.role}::${m.turn_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(m);
  }
  return out;
}
