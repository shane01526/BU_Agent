'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { useAuth } from '@/lib/auth';

const MOCK_USERS = [
  { id: 'dev-bu-001', label: 'Dev BU 001（產險 SME）' },
  { id: 'dev-bu-002', label: 'Dev BU 002（壽險 SME）' },
];

export default function LoginPage() {
  const [selected, setSelected] = useState(MOCK_USERS[0].id);
  const { login } = useAuth();
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    login(selected);
    router.push('/sessions');
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border bg-white p-6 shadow-sm"
      >
        <h1 className="text-xl font-semibold">BU Agent — 登入（Mock）</h1>
        <p className="text-sm text-neutral-500">
          PoC 階段以測試帳號登入；上線後改走 Cathay SSO。
        </p>
        <select
          className="w-full rounded-md border px-3 py-2"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {MOCK_USERS.map((u) => (
            <option key={u.id} value={u.id}>
              {u.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="w-full rounded-md bg-accent px-4 py-2 text-white hover:bg-accent-muted"
        >
          進入
        </button>
      </form>
    </main>
  );
}
