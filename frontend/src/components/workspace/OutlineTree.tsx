'use client';

import clsx from 'clsx';
import { useState } from 'react';

import type { SectionAction, SectionState } from '@/lib/api';

import {
  ActionBtn,
  getStatusBadge,
  isSectionActionable,
  useSectionDraft,
} from './section-primitives';

interface Props {
  sections: SectionState[];
  pendingSectionId: string | null;
  onEdit: (sectionId: string, content: string) => Promise<void> | void;
  onAction: (sectionId: string, action: SectionAction) => Promise<void> | void;
  onSubmit: () => Promise<void> | void;
  canSubmit: boolean;
}

export function OutlineTree({
  sections,
  pendingSectionId,
  onEdit,
  onAction,
  onSubmit,
  canSubmit,
}: Props) {
  const [openId, setOpenId] = useState<string | null>(pendingSectionId);

  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 -mx-6 -mt-6 mb-2 border-b bg-neutral-50/95 px-6 py-3 backdrop-blur">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-neutral-700">
            BRD 大綱（{sections.length} 章節）
          </h2>
          <button
            onClick={onSubmit}
            disabled={!canSubmit}
            className={clsx(
              'rounded-md px-4 py-1.5 text-sm font-medium',
              canSubmit
                ? 'bg-accent text-white hover:bg-accent-muted'
                : 'cursor-not-allowed bg-neutral-200 text-neutral-400',
            )}
            title={canSubmit ? '送 BA review' : '還有 needs_round2 章節未處理'}
          >
            送 BA →
          </button>
        </div>
      </div>

      {sections.length === 0 && (
        <div className="text-sm text-neutral-400">大綱建立中…</div>
      )}

      <ul className="space-y-2">
        {sections.map((sec) => (
          <li key={sec.section_id}>
            <SectionRow
              section={sec}
              expanded={openId === sec.section_id}
              isPending={pendingSectionId === sec.section_id}
              onToggle={() =>
                setOpenId((prev) => (prev === sec.section_id ? null : sec.section_id))
              }
              onEdit={(content) => onEdit(sec.section_id, content)}
              onAction={(action) => onAction(sec.section_id, action)}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function SectionRow({
  section,
  expanded,
  isPending,
  onToggle,
  onEdit,
  onAction,
}: {
  section: SectionState;
  expanded: boolean;
  isPending: boolean;
  onToggle: () => void;
  onEdit: (content: string) => Promise<void> | void;
  onAction: (action: SectionAction) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useSectionDraft(section.content_md, editing);
  const status = getStatusBadge(section.status);
  const isPlaceholder = section.status === 'placeholder';
  const canAct = isSectionActionable(section.status);

  return (
    <div
      className={clsx(
        'overflow-hidden rounded-lg border bg-white transition',
        isPending && 'border-amber-300 ring-2 ring-amber-100',
      )}
    >
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-neutral-50"
      >
        <div className="flex items-center gap-2">
          <span className={clsx('rounded px-2 py-0.5 text-xs', status.cls)}>
            {status.label}
          </span>
          <span className="font-medium text-neutral-800">{section.title}</span>
          {isPending && (
            <span className="text-xs text-amber-600">← agent 正在問這章</span>
          )}
        </div>
        <span className="text-xs text-neutral-400">{expanded ? '收合' : '展開'}</span>
      </button>

      {expanded && (
        <div className="border-t bg-neutral-50/50 p-4 space-y-3">
          {editing ? (
            <textarea
              className="min-h-[120px] w-full rounded-md border bg-white p-3 text-sm leading-relaxed"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
            />
          ) : (
            <div className="whitespace-pre-wrap rounded-md bg-white p-3 text-sm leading-relaxed text-neutral-700 border">
              {section.content_md || (
                <span className="text-neutral-400">（無內容）</span>
              )}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2">
            {!isPlaceholder && !editing && (
              <button
                onClick={() => setEditing(true)}
                className="rounded border px-3 py-1 text-xs hover:bg-neutral-50"
              >
                編輯
              </button>
            )}
            {!isPlaceholder && editing && (
              <>
                <button
                  onClick={async () => {
                    await onEdit(draft);
                    setEditing(false);
                  }}
                  className="rounded bg-accent px-3 py-1 text-xs text-white hover:bg-accent-muted"
                >
                  儲存
                </button>
                <button
                  onClick={() => {
                    setDraft(section.content_md);
                    setEditing(false);
                  }}
                  className="rounded border px-3 py-1 text-xs hover:bg-neutral-50"
                >
                  取消
                </button>
              </>
            )}
            {canAct && !editing && (
              <div className="ml-auto flex gap-1">
                <ActionBtn label="Accept" onClick={() => onAction('accept')} variant="primary" />
                <ActionBtn label="Refine" onClick={() => onAction('refine')} />
                <ActionBtn label="Skip" onClick={() => onAction('skip')} />
                <ActionBtn label="Flag → BA" onClick={() => onAction('flag')} variant="warn" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

