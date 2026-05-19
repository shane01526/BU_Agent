'use client';

import type { Candidate } from '@/components/workspace/CandidateCards';

interface Props {
  open: boolean;
  rounds: number;
  candidates: Candidate[];
  onKeepTalking: () => void;
  onQuickHandoff: (rank: number) => void;
  onResetExplore: () => void;
}

export function Stage5StuckModal({
  open,
  rounds,
  candidates,
  onKeepTalking,
  onQuickHandoff,
  onResetExplore,
}: Props) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold">看起來方向還沒完全收斂</h2>
        <p className="mt-1 text-sm text-neutral-500">
          已經在收斂階段聊了 {rounds} 輪;先看看你想怎麼往下走。
        </p>

        <div className="mt-5 space-y-3">
          {/* 選項 1：再聊一下 */}
          <button
            onClick={onKeepTalking}
            className="w-full rounded-lg border bg-white p-4 text-left hover:border-neutral-300"
          >
            <div className="font-medium">我還想多聊一下</div>
            <div className="mt-1 text-xs text-neutral-500">
              關閉這個提示,繼續對話。Agent 會換個切角聊,不再催促選擇。
            </div>
          </button>

          {/* 選項 2：先試試 #N（每個 candidate 一顆按鈕） */}
          {candidates.length > 0 && (
            <div className="rounded-lg border bg-white p-4">
              <div className="font-medium">先用其中一個寫 BRD 試試</div>
              <div className="mt-1 text-xs text-neutral-500">
                BRD 寫一寫覺得偏了,可以隨時點頂部「重新探索」回來。
              </div>
              <div className="mt-3 space-y-2">
                {candidates.map((c) => (
                  <button
                    key={c.rank}
                    onClick={() => onQuickHandoff(c.rank)}
                    className="flex w-full items-center justify-between rounded-md border bg-neutral-50 px-3 py-2 text-sm hover:bg-accent/5 hover:border-accent"
                  >
                    <span className="font-medium">
                      #{c.rank}. {c.direction}
                    </span>
                    <span className="text-xs text-neutral-500">
                      {c.process_target} · {c.project_type}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* 選項 3：重新探索 */}
          <button
            onClick={onResetExplore}
            className="w-full rounded-lg border bg-white p-4 text-left hover:border-neutral-300"
          >
            <div className="font-medium">換個角度重新發想</div>
            <div className="mt-1 text-xs text-neutral-500">
              清空目前的對話與候選方向,重新從工作日常開始聊。
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
