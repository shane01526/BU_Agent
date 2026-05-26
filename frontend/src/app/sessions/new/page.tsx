'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { api } from '@/lib/api';

const BU_OPTIONS = ['產險', '壽險', '銀行', '證券', '投信'];

export default function NewSessionPage() {
  const router = useRouter();
  const [bu, setBu] = useState(BU_OPTIONS[0]);
  const [smeRole, setSmeRole] = useState('');
  const [hint, setHint] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [models, setModels] = useState<string[]>([]);
  const [llmModel, setLlmModel] = useState('');
  const [backends, setBackends] = useState<{ openai: boolean; gemini: boolean }>({
    openai: false,
    gemini: false,
  });
  const [modelsSource, setModelsSource] = useState<'live' | 'fallback' | undefined>();
  const [modelsFailures, setModelsFailures] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .listModels()
      .then((r) => {
        if (cancelled) return;
        setModels(r.models);
        setLlmModel(r.default || r.models[0] || '');
        setBackends(r.backends_available);
        setModelsSource(r.source);
        setModelsFailures(r.failures || []);
      })
      .catch(() => {
        // 後端拿不到 → 留空,送出時走 backend default
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  function modelProvider(m: string): 'openai' | 'gemini' | 'other' {
    if (m.startsWith('gpt-') || m.startsWith('o1') || m.startsWith('o3') ||
        m.startsWith('o4') || m.startsWith('chatgpt-') || m.startsWith('chat-latest')) {
      return 'openai';
    }
    if (m.startsWith('gemini-')) return 'gemini';
    return 'other';
  }

  function modelDisabled(m: string): boolean {
    const p = modelProvider(m);
    if (p === 'openai') return !backends.openai;
    if (p === 'gemini') return !backends.gemini;
    return false;
  }

  const openaiModels = models.filter((m) => modelProvider(m) === 'openai');
  const geminiModels = models.filter((m) => modelProvider(m) === 'gemini');
  const otherModels = models.filter((m) => modelProvider(m) === 'other');

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
        llm_model: llmModel || undefined,
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

        <label className="block space-y-1">
          <span className="text-sm">
            LLM 模型
            {modelsLoading && <span className="ml-2 text-xs text-gray-500">載入中…</span>}
          </span>
          <select
            className="w-full rounded-md border px-3 py-2"
            value={llmModel}
            onChange={(e) => setLlmModel(e.target.value)}
            disabled={models.length === 0}
          >
            {models.length === 0 && <option value="">（無可用模型）</option>}
            {openaiModels.length > 0 && (
              <optgroup label={`OpenAI（${openaiModels.length}）`}>
                {openaiModels.map((m) => (
                  <option key={m} value={m} disabled={modelDisabled(m)}>
                    {m}
                    {modelDisabled(m) ? '（後端 key 未設定）' : ''}
                  </option>
                ))}
              </optgroup>
            )}
            {geminiModels.length > 0 && (
              <optgroup label={`Gemini（${geminiModels.length}）`}>
                {geminiModels.map((m) => (
                  <option key={m} value={m} disabled={modelDisabled(m)}>
                    {m}
                    {modelDisabled(m) ? '（後端 key 未設定）' : ''}
                  </option>
                ))}
              </optgroup>
            )}
            {otherModels.length > 0 && (
              <optgroup label="Other">
                {otherModels.map((m) => (
                  <option key={m} value={m} disabled={modelDisabled(m)}>
                    {m}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
          <span className="text-xs text-gray-500 block">
            整個 session 全程使用此模型；建立後不可更換。
          </span>
          {modelsSource === 'fallback' && (
            <span className="text-xs text-amber-600 block">
              無法即時拉模型清單，目前顯示的是 .env 內的預設清單。
            </span>
          )}
          {modelsSource === 'live' && modelsFailures.length > 0 && (
            <span className="text-xs text-amber-600 block">
              {modelsFailures.join(' / ')} 拉清單失敗，僅顯示其他可用供應商的模型。
            </span>
          )}
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
