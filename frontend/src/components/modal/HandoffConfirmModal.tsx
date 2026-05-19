'use client';

export function HandoffConfirmModal({
  open,
  paragraph,
  onConfirm,
  onDiscuss,
}: {
  open: boolean;
  paragraph: string;
  onConfirm: () => void;
  onDiscuss: () => void;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-xl bg-white p-6 shadow-xl">
        <h2 className="text-lg font-semibold">我把這次討論整理成這段</h2>
        <p className="mt-1 text-sm text-neutral-500">
          確認沒有偏離就進入 Consult mode,開始建立 BRD 大綱。
        </p>
        <div className="mt-4 max-h-60 overflow-y-auto rounded-md border bg-neutral-50 p-3 text-sm whitespace-pre-wrap leading-relaxed">
          {paragraph}
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button
            onClick={onDiscuss}
            className="rounded-md border px-4 py-2 text-sm hover:bg-neutral-50"
          >
            再討論一下
          </button>
          <button
            onClick={onConfirm}
            className="rounded-md bg-accent px-4 py-2 text-sm text-white hover:bg-accent-muted"
          >
            進入 Consult mode
          </button>
        </div>
      </div>
    </div>
  );
}
