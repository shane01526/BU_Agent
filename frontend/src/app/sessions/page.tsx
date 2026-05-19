'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';

export default function SessionsPage() {
  const { userId } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (userId === null && typeof document !== 'undefined') {
      router.replace('/login');
    }
  }, [userId, router]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['sessions', userId],
    queryFn: api.listSessions,
    enabled: !!userId,
  });

  return (
    <main className="min-h-screen bg-neutral-50 px-6 py-10">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold">我的諮詢</h1>
            <p className="text-sm text-neutral-500">{userId}</p>
          </div>
          <Link
            href="/sessions/new"
            className="rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-muted"
          >
            + 開始新諮詢
          </Link>
        </header>

        {isLoading && <p className="text-neutral-500">載入中…</p>}
        {error && (
          <p className="text-red-600">載入失敗：{(error as Error).message}</p>
        )}
        {data && data.length === 0 && (
          <div className="rounded-lg border bg-white p-8 text-center text-neutral-500">
            還沒有諮詢；點「開始新諮詢」起第一份 BRD。
          </div>
        )}
        {data && data.length > 0 && (
          <ul className="divide-y rounded-lg border bg-white">
            {data.map((s) => (
              <li key={s.session_id}>
                <Link
                  href={`/sessions/${s.session_id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-neutral-50"
                >
                  <div>
                    <div className="font-medium">{s.bu} · {s.mode}</div>
                    <div className="text-xs text-neutral-500">
                      更新於 {new Date(s.updated_at).toLocaleString('zh-TW')}
                    </div>
                  </div>
                  <span className="text-xs rounded bg-neutral-100 px-2 py-1 text-neutral-600">
                    {s.status}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
