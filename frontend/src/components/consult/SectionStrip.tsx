'use client';

import clsx from 'clsx';

import type { SectionState } from '@/lib/api';
import { getStatusBadge } from '@/components/workspace/section-primitives';

interface Props {
  sections: SectionState[];
  currentId: string | null;
  pendingSectionId: string | null;
  onSelect: (sectionId: string) => void;
}

/**
 * 章節列(同一行,寬度不夠時 horizontal scroll)。
 * 「送 BA」按鈕已上提到 page.tsx top bar,本元件不再含。
 */
export function SectionStrip({
  sections,
  currentId,
  pendingSectionId,
  onSelect,
}: Props) {
  return (
    <div className="border-b bg-white px-4 py-3">
      <div className="flex flex-nowrap items-center gap-2 overflow-x-auto">
        {sections.map((sec) => (
          <SectionChip
            key={sec.section_id}
            section={sec}
            isCurrent={currentId === sec.section_id}
            isPending={pendingSectionId === sec.section_id}
            onClick={() => onSelect(sec.section_id)}
          />
        ))}
      </div>
    </div>
  );
}

function SectionChip({
  section,
  isCurrent,
  isPending,
  onClick,
}: {
  section: SectionState;
  isCurrent: boolean;
  isPending: boolean;
  onClick: () => void;
}) {
  const isPlaceholder = section.status === 'placeholder';
  const statusLabel = getStatusBadge(section.status).label;
  const fullTitle = `${section.title} · ${statusLabel}`;

  return (
    <button
      onClick={onClick}
      disabled={isPlaceholder}
      title={isPlaceholder ? `${section.title} · AI 科 / CD 科後續補充` : fullTitle}
      className={clsx(
        'shrink-0 whitespace-nowrap flex items-center gap-2 rounded-md border px-3.5 py-2 text-sm transition',
        isCurrent
          ? 'border-accent bg-accent text-white'
          : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300',
        isPending && !isCurrent && 'ring-2 ring-amber-300',
        isPlaceholder && 'opacity-50 cursor-not-allowed',
      )}
    >
      <span
        className={clsx(
          'h-2 w-2 rounded-full',
          isCurrent ? 'bg-white' : statusDotCls(section.status),
        )}
      />
      <span className="font-medium">{truncateTitle(section.title)}</span>
      {isPending && !isCurrent && (
        <span className="text-xs text-amber-600">●</span>
      )}
    </button>
  );
}

/** 中文字超過 12 個才截斷;多數章節標題在限制內,完整字仍掛 title attr。 */
function truncateTitle(title: string): string {
  const max = 12;
  if (title.length <= max) return title;
  return title.slice(0, max) + '…';
}

function statusDotCls(status: SectionState['status']): string {
  switch (status) {
    case 'auto_filled':
      return 'bg-emerald-400';
    case 'needs_round2':
      return 'bg-amber-400';
    case 'accepted':
      return 'bg-sky-400';
    case 'skipped':
      return 'bg-neutral-400';
    case 'flagged_for_ba':
      return 'bg-rose-400';
    case 'placeholder':
      return 'bg-neutral-300';
    default:
      return 'bg-neutral-300';
  }
}
