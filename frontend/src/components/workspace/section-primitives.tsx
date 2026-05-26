'use client';

import clsx from 'clsx';
import { useEffect, useState } from 'react';

import type { SectionAction, SectionState } from '@/lib/api';

export const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  auto_filled: { label: '已預填', cls: 'bg-emerald-100 text-emerald-700' },
  needs_round2: { label: '待訪談', cls: 'bg-amber-100 text-amber-700' },
  placeholder: { label: 'AI/CD 科', cls: 'bg-neutral-100 text-neutral-500' },
  accepted: { label: '已 Accept', cls: 'bg-sky-100 text-sky-700' },
  skipped: { label: 'Skipped', cls: 'bg-neutral-200 text-neutral-600' },
  flagged_for_ba: { label: 'Flag → BA', cls: 'bg-rose-100 text-rose-700' },
};

export type ActionVariant = 'default' | 'primary' | 'warn';

export function ActionBtn({
  label,
  onClick,
  variant = 'default',
  disabled = false,
}: {
  label: string;
  onClick: () => void;
  variant?: ActionVariant;
  disabled?: boolean;
}) {
  const cls =
    variant === 'primary'
      ? 'bg-emerald-600 text-white hover:bg-emerald-500'
      : variant === 'warn'
        ? 'bg-rose-50 text-rose-700 border border-rose-200 hover:bg-rose-100'
        : 'border hover:bg-neutral-50 text-neutral-700';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={clsx(
        'rounded px-3 py-1 text-xs transition',
        cls,
        disabled && 'opacity-50 cursor-not-allowed',
      )}
    >
      {label}
    </button>
  );
}

/** 同步 server 端 content_md 進 local draft;BU 編輯中時不覆蓋。 */
export function useSectionDraft(serverContent: string, editing: boolean) {
  const [draft, setDraft] = useState(serverContent);
  useEffect(() => {
    if (!editing) {
      setDraft(serverContent);
    }
  }, [serverContent, editing]);
  return [draft, setDraft] as const;
}

/**
 * 章節編輯器:textarea + 儲存 / 取消按鈕。
 * 與 server 內容透過 useSectionDraft 雙向同步,BU 編輯時不被 SSE 覆蓋。
 */
export function SectionEditor({
  content,
  onSave,
  onCancel,
  minHeight = 'min-h-[120px]',
}: {
  content: string;
  onSave: (newContent: string) => Promise<void> | void;
  onCancel: () => void;
  minHeight?: string;
}) {
  const [draft, setDraft] = useSectionDraft(content, true);

  return (
    <div className="space-y-2">
      <textarea
        className={clsx(
          'w-full rounded-md border bg-white p-3 text-sm leading-relaxed',
          minHeight,
        )}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          onClick={async () => {
            await onSave(draft);
          }}
          className="rounded bg-accent px-3 py-1 text-xs text-white hover:bg-accent-muted"
        >
          儲存
        </button>
        <button
          onClick={() => {
            setDraft(content);
            onCancel();
          }}
          className="rounded border px-3 py-1 text-xs hover:bg-neutral-50"
        >
          取消
        </button>
      </div>
    </div>
  );
}

/** 共用 helper:section 是否可被 Accept/Refine/Skip/Flag 操作。 */
export function isSectionActionable(status: SectionState['status']): boolean {
  return (
    status === 'auto_filled' ||
    status === 'needs_round2' ||
    status === 'flagged_for_ba'
  );
}

export function getStatusBadge(status: SectionState['status']) {
  return STATUS_LABELS[status] || { label: status, cls: 'bg-neutral-100' };
}

export type { SectionAction, SectionState };
