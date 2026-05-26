'use client';

interface Props {
  open: boolean;
  sectionTitle: string;
  status: 'accepted' | 'skipped' | 'flagged_for_ba' | string;
  onConfirm: () => void;
  onCancel: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  accepted: '已 Accept',
  skipped: '已 Skip',
  flagged_for_ba: '已 Flag → BA',
};

export function RevisitSectionConfirmModal({
  open,
  sectionTitle,
  status,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;
  const statusLabel = STATUS_LABEL[status] || status;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold">這章已 {statusLabel},還要繼續討論嗎?</h2>
        <p className="mt-2 text-sm text-neutral-600 leading-relaxed">
          章節「<strong>{sectionTitle}</strong>」目前狀態為「{statusLabel}」。
          再次訪談會把它改回「<strong>待訪談</strong>」狀態,
          並請 agent 從你之前聊過的內容延伸提問。
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="rounded-md border px-4 py-2 text-sm hover:bg-neutral-50"
          >
            取消
          </button>
          <button
            onClick={onConfirm}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-muted"
          >
            繼續訪談
          </button>
        </div>
      </div>
    </div>
  );
}
