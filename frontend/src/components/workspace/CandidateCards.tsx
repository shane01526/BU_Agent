'use client';

import { useState } from 'react';

import clsx from 'clsx';

export interface Candidate {
  rank: number;
  direction: string;
  process_target: string;
  project_type: string;
  score_5d: Record<string, number>;
  score_5d_desc?: Record<string, string>;
  pain_signals: string[];
}

const DIM_LABELS: Record<string, string> = {
  rule_repeat: '規則可重複',
  data_avail: '資料可得',
  reversibility: '可事後覆核',
  scale_roi: '規模/ROI',
  gap: '既有 gap',
};

export function CandidateCards({
  candidates,
  selected,
  onSelect,
  onReject,
  generatingHandoff = false,
}: {
  candidates: Candidate[];
  selected: number | null;
  onSelect: (rank: number) => void;
  onReject: (rank: number) => void;
  generatingHandoff?: boolean;
}) {
  if (candidates.length === 0) {
    return (
      <div className="text-sm text-neutral-400">
        候選方向會隨對話更新出現在這裡。
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {candidates.map((c) => {
        const isSelected = selected === c.rank;
        const isGenerating = generatingHandoff && isSelected;
        return (
          <div
            key={c.rank}
            className={clsx(
              'w-full rounded-lg border p-4 text-left transition',
              isSelected
                ? 'border-accent bg-accent/5'
                : 'bg-white',
              generatingHandoff && !isSelected && 'opacity-50',
              isGenerating && 'ring-2 ring-accent/40',
            )}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-medium">
                #{c.rank}. {c.direction}
                {isGenerating && (
                  <span className="inline-flex items-center gap-1 rounded bg-accent/10 px-2 py-0.5 text-xs text-accent">
                    <span className="h-1.5 w-1.5 animate-ping rounded-full bg-accent" />
                    生成綜整文字中…
                  </span>
                )}
              </div>
              <div className="text-xs text-neutral-500">
                {c.process_target} · {c.project_type}
              </div>
            </div>
            <RubricHeatmap score={c.score_5d} desc={c.score_5d_desc} />
            {c.pain_signals.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {c.pain_signals.map((p) => (
                  <span
                    key={p}
                    className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-600"
                  >
                    {p}
                  </span>
                ))}
              </div>
            )}
            <div className="mt-3 flex gap-2">
              <button
                onClick={() => onSelect(c.rank)}
                disabled={generatingHandoff}
                className={clsx(
                  'flex-1 rounded-md px-3 py-2 text-sm font-medium transition',
                  generatingHandoff
                    ? 'bg-neutral-200 text-neutral-400 cursor-not-allowed'
                    : 'bg-accent text-white hover:bg-accent-muted',
                )}
              >
                採用此方向
              </button>
              <button
                onClick={() => onReject(c.rank)}
                disabled={generatingHandoff}
                className={clsx(
                  'rounded-md border px-3 py-2 text-sm transition',
                  generatingHandoff
                    ? 'text-neutral-300 cursor-not-allowed'
                    : 'text-neutral-600 hover:bg-neutral-50',
                )}
              >
                不採用
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RubricHeatmap({
  score,
  desc,
}: {
  score: Record<string, number>;
  desc?: Record<string, string>;
}) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  return (
    <div className="mt-3">
      <div className="grid grid-cols-5 gap-2">
        {Object.entries(DIM_LABELS).map(([key, label]) => {
          const v = score[key] ?? 0;
          const hasDesc = !!desc?.[key];
          const isOpen = openKey === key;
          return (
            <button
              key={key}
              type="button"
              disabled={!hasDesc}
              onClick={() => setOpenKey(isOpen ? null : key)}
              className={clsx(
                'text-center rounded p-1 transition',
                hasDesc && 'hover:bg-neutral-50 cursor-pointer',
                isOpen && 'bg-neutral-100',
                !hasDesc && 'cursor-default',
              )}
            >
              <div
                className="mx-auto h-6 w-6 rounded"
                style={{ background: `rgba(15, 118, 110, ${0.15 + v * 0.17})` }}
              />
              <div className="mt-1 text-[10px] text-neutral-500">{label}</div>
              <div className="text-xs font-medium text-neutral-700">
                {v}
                {hasDesc && <span className="ml-0.5 text-neutral-400">ⓘ</span>}
              </div>
            </button>
          );
        })}
      </div>
      {openKey && desc?.[openKey] && (
        <div className="mt-2 rounded bg-neutral-50 px-3 py-2 text-xs text-neutral-600">
          <span className="font-medium text-neutral-700">
            {DIM_LABELS[openKey]}：
          </span>
          {desc[openKey]}
        </div>
      )}
    </div>
  );
}
