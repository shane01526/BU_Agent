'use client';

import { useEffect, useState } from 'react';
import { Panel, PanelGroup, PanelResizeHandle } from 'react-resizable-panels';

import { ChatPanel, type ChatMessage } from '@/components/chat/ChatPanel';
import { RevisitSectionConfirmModal } from '@/components/modal/RevisitSectionConfirmModal';
import type { SectionAction, SectionState } from '@/lib/api';

import { InlineActionBar } from './InlineActionBar';
import { SectionInlineHeader } from './SectionInlineHeader';
import { SectionStrip } from './SectionStrip';

const REVISIT_CONFIRM_STATUSES: ReadonlyArray<SectionState['status']> = [
  'accepted',
  'skipped',
  'flagged_for_ba',
];

interface Props {
  sections: SectionState[];
  pendingSectionId: string | null;
  generatingOutline: boolean;
  // chat
  messages: ChatMessage[];
  chatDisabled: boolean;
  thinking: boolean;
  onSend: (text: string) => void;
  // section operations
  onEditSection: (sectionId: string, content: string) => Promise<void> | void;
  onSectionAction: (sectionId: string, action: SectionAction) => Promise<void> | void;
  onSelectSection: (sectionId: string) => Promise<void> | void;
}

const CHAT_INNER = 'max-w-[760px]';

export function ConsultFullscreenLayout({
  sections,
  pendingSectionId,
  generatingOutline,
  messages,
  chatDisabled,
  thinking,
  onSend,
  onEditSection,
  onSectionAction,
  onSelectSection,
}: Props) {
  // BU 點章節時樂觀切;backend SSE 回 pending 後以 pendingSectionId 為準
  const [localSelectedId, setLocalSelectedId] = useState<string | null>(null);
  // 點 accepted/skipped/flagged 章節時先彈 confirm modal,確認後才送 select_section
  const [revisitTarget, setRevisitTarget] = useState<SectionState | null>(null);

  // pendingSectionId 變動 → 同步 localSelectedId(避免兩者長期不一致)
  useEffect(() => {
    if (pendingSectionId) {
      setLocalSelectedId(pendingSectionId);
    }
  }, [pendingSectionId]);

  // 計算 currentId:pending 優先 > BU 樂觀選 > 第一個非 placeholder 章節
  const currentId =
    pendingSectionId ??
    localSelectedId ??
    sections.find((s) => s.status !== 'placeholder')?.section_id ??
    sections[0]?.section_id ??
    null;

  const currentSection = currentId
    ? sections.find((s) => s.section_id === currentId) ?? null
    : null;

  // ActionBar 只在 currentId === pendingSectionId(BU 點過 = 確實在訪談這章)時出現
  const showActionBar =
    currentSection !== null &&
    pendingSectionId === currentSection.section_id &&
    currentSection.status !== 'placeholder';

  async function handleSelect(sectionId: string) {
    // 如果剛好 = pending,不必再呼叫 backend(已在訪談這章);只更新 local 視覺
    if (sectionId === pendingSectionId) {
      setLocalSelectedId(sectionId);
      return;
    }
    // 找對應章節決定是否要先 confirm
    const target = sections.find((s) => s.section_id === sectionId);
    if (
      target !== undefined &&
      (REVISIT_CONFIRM_STATUSES as ReadonlyArray<string>).includes(target.status)
    ) {
      // 先彈 modal,不立刻切 localSelectedId(避免使用者點取消後視覺殘留)
      setRevisitTarget(target);
      return;
    }
    setLocalSelectedId(sectionId);
    await onSelectSection(sectionId);
  }

  async function handleRevisitConfirm() {
    const target = revisitTarget;
    setRevisitTarget(null);
    if (!target) return;
    setLocalSelectedId(target.section_id);
    await onSelectSection(target.section_id);
  }

  function handleRevisitCancel() {
    setRevisitTarget(null);
    // 不動 localSelectedId(沒切過)
  }

  async function handleEdit(content: string) {
    if (!currentSection) return;
    await onEditSection(currentSection.section_id, content);
  }

  async function handleAction(action: SectionAction) {
    if (!currentSection) return;
    await onSectionAction(currentSection.section_id, action);
  }

  if (generatingOutline) {
    return (
      <div className="flex flex-1 items-center justify-center bg-neutral-50">
        <div className="flex flex-col items-center text-center">
          <div className="mb-4 h-3 w-3 animate-pulse rounded-full bg-accent" />
          <div className="text-sm font-medium text-neutral-700">
            正在依你選的方向建立 BRD 大綱…
          </div>
          <div className="mt-2 max-w-xs text-xs text-neutral-500">
            Agent 會依你聊過的脈絡填好需求背景與分析等章節,通常需要 15–30 秒。
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col overflow-hidden bg-neutral-50">
      <SectionStrip
        sections={sections}
        currentId={currentId}
        pendingSectionId={pendingSectionId}
        onSelect={handleSelect}
      />

      <PanelGroup
        direction="horizontal"
        autoSaveId="bu-agent.consult-split-v2"
        className="flex-1"
      >
        <Panel defaultSize={50} minSize={30}>
          <ChatPanel
            messages={messages}
            disabled={chatDisabled}
            thinking={thinking}
            onSend={onSend}
            innerMaxWidthClass={CHAT_INNER}
            actionBarSlot={
              showActionBar && currentSection ? (
                <InlineActionBar
                  sectionTitle={currentSection.title}
                  status={currentSection.status}
                  onAction={handleAction}
                  disabled={chatDisabled}
                />
              ) : null
            }
          />
        </Panel>

        <PanelResizeHandle className="w-1 bg-neutral-200 transition hover:bg-accent data-[resize-handle-active]:bg-accent cursor-col-resize" />

        <Panel defaultSize={50} minSize={30}>
          <SectionInlineHeader
            section={currentSection}
            isPending={
              currentSection !== null &&
              pendingSectionId === currentSection.section_id
            }
            onEdit={handleEdit}
          />
        </Panel>
      </PanelGroup>

      <RevisitSectionConfirmModal
        open={revisitTarget !== null}
        sectionTitle={revisitTarget?.title ?? ''}
        status={revisitTarget?.status ?? ''}
        onConfirm={handleRevisitConfirm}
        onCancel={handleRevisitCancel}
      />
    </div>
  );
}
