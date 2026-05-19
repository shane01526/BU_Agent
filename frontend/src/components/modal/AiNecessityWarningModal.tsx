'use client';

const SOLUTION_CLASS_LABEL: Record<string, string> = {
  rule: '規則引擎(if-else 條件判斷)',
  rpa: 'RPA(流程自動化機器人)',
  pipeline: 'ETL Pipeline / 排程批次',
  classical_ml: '傳統機器學習(非 LLM)',
  llm_extract: 'LLM 結構化抽取',
  llm_reason: 'LLM 語意推理',
  agent: 'AI Agent(多輪互動)',
};

interface Props {
  open: boolean;
  solutionClass: string;
  rationale: string;
  onExplain: () => void;
  onOverride: () => void;
  onAcknowledge: () => void;
  onResetExplore: () => void;
}

export function AiNecessityWarningModal({
  open,
  solutionClass,
  rationale,
  onExplain,
  onOverride,
  onAcknowledge,
  onResetExplore,
}: Props) {
  if (!open) return null;
  const classLabel = SOLUTION_CLASS_LABEL[solutionClass] ?? solutionClass;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-1 text-xs font-medium text-amber-600">提醒(可忽略)</div>
        <h2 className="text-lg font-semibold">這個需求不一定需要 AI</h2>
        <p className="mt-2 text-sm text-neutral-600 leading-relaxed">
          根據你描述的流程,我們判斷可能用 <strong>{classLabel}</strong> 就能解決。
        </p>
        {rationale && (
          <p className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-900">
            理由:{rationale}
          </p>
        )}

        <p className="mt-4 text-sm text-neutral-600">
          你想怎麼往下走?(這個提醒本 session 只會出現一次)
        </p>

        <div className="mt-3 space-y-2">
          <button
            onClick={onExplain}
            className="w-full rounded-lg border bg-white p-4 text-left hover:border-accent hover:bg-accent/5"
          >
            <div className="font-medium">想了解 {classLabel} 跟 AI 的差別</div>
            <div className="mt-1 text-xs text-neutral-500">
              Agent 會在對話區用白話講優缺點 / 成本 / 適用情境,你再決定。
            </div>
          </button>

          <button
            onClick={onOverride}
            className="w-full rounded-lg border bg-white p-4 text-left hover:border-neutral-300"
          >
            <div className="font-medium">我有理由,還是想用 AI 試試看</div>
            <div className="mt-1 text-xs text-neutral-500">
              繼續對話。BRD 會記下「曾考慮 {classLabel} 但 BU 評估後仍選 AI」,給 AI 科 review 時當 context。
            </div>
          </button>

          <button
            onClick={onAcknowledge}
            className="w-full rounded-lg border bg-white p-4 text-left hover:border-neutral-300"
          >
            <div className="font-medium">我了解了,讓我繼續想想</div>
            <div className="mt-1 text-xs text-neutral-500">
              關閉這個提醒,繼續探索其他可能性,不再彈出。
            </div>
          </button>

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
