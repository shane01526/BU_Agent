'use client';

import clsx from 'clsx';

export interface Candidate {
  rank: number;
  direction: string;
  process_target: string;
  project_type: string;
  score_5d: Record<string, number>;
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
  generatingHandoff = false,
}: {
  candidates: Candidate[];
  selected: number | null;
  onSelect: (rank: number) => void;
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
          <button
            key={c.rank}
            disabled={generatingHandoff}
            onClick={() => onSelect(c.rank)}
            className={clsx(
              'w-full rounded-lg border p-4 text-left transition',
              isSelected
                ? 'border-accent bg-accent/5'
                : 'bg-white hover:border-neutral-300',
              generatingHandoff && !isSelected && 'opacity-50 cursor-not-allowed',
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
            <RubricHeatmap score={c.score_5d} />
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
          </button>
        );
      })}
    </div>
  );
}

function RubricHeatmap({ score }: { score: Record<string, number> }) {
  return (
    <div className="mt-3 grid grid-cols-5 gap-2">
      {Object.entries(DIM_LABELS).map(([key, label]) => {
        const v = score[key] ?? 0;
        return (
          <div key={key} className="text-center">
            <div
              className="mx-auto h-6 w-6 rounded"
              style={{ background: `rgba(15, 118, 110, ${0.15 + v * 0.17})` }}
            />
            <div className="mt-1 text-[10px] text-neutral-500">{label}</div>
            <div className="text-xs font-medium text-neutral-700">{v}</div>
          </div>
        );
      })}
    </div>
  );
}
