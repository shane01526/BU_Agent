'use client';

import type { SectionAction, SectionState } from '@/lib/api';
import { ActionBtn } from '@/components/workspace/section-primitives';

interface Props {
  sectionTitle: string;
  status: SectionState['status'];
  onAction: (action: SectionAction) => Promise<void> | void;
  disabled?: boolean;
}

export function InlineActionBar({
  sectionTitle,
  status,
  onAction,
  disabled = false,
}: Props) {
  // refine 在已是 needs_round2 時意義不大,但保留按鈕讓使用者一致體驗
  return (
    <div className="rounded-md border bg-amber-50/50 px-3 py-2 flex flex-wrap items-center gap-2">
      <span className="text-xs text-neutral-600 mr-1">
        針對 <strong className="font-medium text-neutral-800">「{sectionTitle}」</strong>:
      </span>
      <ActionBtn
        label="Accept"
        onClick={() => onAction('accept')}
        variant="primary"
        disabled={disabled}
      />
      <ActionBtn
        label="Refine"
        onClick={() => onAction('refine')}
        disabled={disabled}
      />
      <ActionBtn
        label="Skip"
        onClick={() => onAction('skip')}
        disabled={disabled}
      />
      <ActionBtn
        label="Flag → BA"
        onClick={() => onAction('flag')}
        variant="warn"
        disabled={disabled}
      />
      <span className="ml-auto text-[10px] text-neutral-400">
        當前 status: {status}
      </span>
    </div>
  );
}
