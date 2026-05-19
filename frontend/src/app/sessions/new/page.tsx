'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { api } from '@/lib/api';

const BU_OPTIONS = ['產險', '壽險', '銀行', '證券', '投信'];

export default function NewSessionPage() {
  const router = useRouter();
  const [bu, setBu] = useState(BU_OPTIONS[0]);
  const [smeRole, setSmeRole] = useState('');
  const [hint, setHint] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!smeRole.trim()) {
      setError('請填角色簡述');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const s = await api.createSession({
        bu,
        sme_role: smeRole.trim(),
        raw_hint: hint.trim() || undefined,
      });
      router.push(`/sessions/${s.session_id}`);
    } catch (err) {
      setError((err as Error).message);
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-6 py-10">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg space-y-4 rounded-xl border bg-white p-6 shadow-sm"
      >
        <h1 className="text-xl font-semibold">開始新諮詢</h1>

        <label className="block space-y-1">
          <span className="text-sm">BU 別</span>
          <select
            className="w-full rounded-md border px-3 py-2"
            value={bu}
            onChange={(e) => setBu(e.target.value)}
          >
            {BU_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        </label>

        <label className="block space-y-1">
          <span className="text-sm">角色簡述（1–2 句）</span>
          <textarea
            className="w-full rounded-md border px-3 py-2"
            rows={2}
            placeholder="例：產險核保部 SME,主責商業火險核保"
            value={smeRole}
            onChange={(e) => setSmeRole(e.target.value)}
          />
        </label>

        <label className="block space-y-1">
          <span className="text-sm">第一句 hint（選填）</span>
          <textarea
            className="w-full rounded-md border px-3 py-2"
            rows={2}
            placeholder="最近最困擾我的是……"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
          />
        </label>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-muted disabled:opacity-50"
        >
          {submitting ? '建立中…' : '開始'}
        </button>
      </form>
    </main>
  );
}
