'use client';

import clsx from 'clsx';
import { useState } from 'react';

import type { SectionState } from '@/lib/api';
import {
  SectionEditor,
  getStatusBadge,
} from '@/components/workspace/section-primitives';

interface Props {
  section: SectionState | null;
  isPending: boolean;
  onEdit: (content: string) => Promise<void> | void;
}

export function SectionInlineHeader({ section, isPending, onEdit }: Props) {
  const [editing, setEditing] = useState(false);

  if (section === null) {
    return (
      <div className="h-full bg-white px-6 py-4">
        <div className="text-sm text-neutral-400">
          選擇上方章節以瀏覽 / 編輯內容,或等 agent 開始訪談。
        </div>
      </div>
    );
  }

  const status = getStatusBadge(section.status);
  const isPlaceholder = section.status === 'placeholder';

  return (
    <div
      className={clsx(
        'h-full overflow-y-auto bg-white px-6 py-4',
        isPending && 'border-l-2 border-amber-300',
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-xl font-semibold text-neutral-900">
            {section.title}
          </h2>
          <span className={clsx('rounded px-2 py-0.5 text-xs', status.cls)}>
            {status.label}
          </span>
          {isPending && (
            <span className="text-xs text-amber-600 font-medium">
              ● agent 正在訪談這章
            </span>
          )}
        </div>
        {!isPlaceholder && !editing && (
          <button
            onClick={() => setEditing(true)}
            className="shrink-0 rounded border px-3 py-1 text-xs hover:bg-neutral-50"
          >
            編輯本章
          </button>
        )}
      </div>

      {editing ? (
        <SectionEditor
          content={section.content_md}
          onSave={async (newContent) => {
            await onEdit(newContent);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
          minHeight="min-h-[160px]"
        />
      ) : (
        <div className="whitespace-pre-wrap rounded-md bg-neutral-50 p-3 text-sm leading-relaxed text-neutral-700 border">
          {section.content_md || (
            <span className="text-neutral-400">（無內容）</span>
          )}
        </div>
      )}
    </div>
  );
}
