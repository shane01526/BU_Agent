'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useParams } from 'next/navigation';

import { api, type SessionFullState } from '@/lib/api';

export default function DonePage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id;

  const { data, isLoading } = useQuery<SessionFullState>({
    queryKey: ['session', sessionId],
    queryFn: () => api.getSession(sessionId),
  });

  if (isLoading || !data) {
    return <main className="p-6 text-neutral-500">載入完成資訊…</main>;
  }

  const direction =
    data.candidates.find((c) => true)?.direction ?? '初版 BRD';
  const flagged = data.sections.filter(
    (s) => s.status === 'flagged_for_ba',
  );

  return (
    <main className="min-h-screen bg-neutral-50 px-6 py-10">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="rounded-lg border bg-emerald-50 border-emerald-200 p-6">
          <h1 className="text-xl font-semibold text-emerald-900">
            ✓ 已完成初版 BRD：{direction}
          </h1>
          <p className="mt-2 text-sm text-emerald-800">
            BU Agent 階段告一段落。BA 將接手 review 與後續會議錄音增量更新。
            如有後續修訂需求,BA 會用 BA Agent 介面處理(不在這個 session)。
          </p>
        </header>

        {flagged.length > 0 && (
          <section className="rounded-lg border bg-amber-50 border-amber-200 p-4">
            <h2 className="text-sm font-semibold text-amber-900">
              標記給 BA 補洞的章節（{flagged.length}）
            </h2>
            <ul className="mt-2 space-y-1 text-sm text-amber-800">
              {flagged.map((s) => (
                <li key={s.section_id}>· {s.title}</li>
              ))}
            </ul>
          </section>
        )}

        <section className="rounded-lg border bg-white p-4">
          <h2 className="text-sm font-semibold text-neutral-700 mb-3">
            BRD 預覽
          </h2>
          <div className="space-y-4">
            {data.sections.map((s) => (
              <article key={s.section_id} className="border-l-2 pl-4 border-neutral-200">
                <h3 className="text-base font-medium text-neutral-800">
                  {s.title}{' '}
                  <span className="ml-2 text-xs text-neutral-400">
                    [{s.status}]
                  </span>
                </h3>
                <div className="mt-1 whitespace-pre-wrap text-sm text-neutral-700">
                  {s.content_md || (
                    <span className="text-neutral-400">（未填）</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>

        <div className="flex justify-between">
          <Link
            href="/sessions"
            className="rounded-md border px-4 py-2 text-sm hover:bg-neutral-50"
          >
            ← 返回 sessions 列表
          </Link>
          <button
            onClick={() => window.print()}
            className="rounded-md border px-4 py-2 text-sm hover:bg-neutral-50"
          >
            列印 / 另存 PDF
          </button>
        </div>
      </div>
    </main>
  );
}
