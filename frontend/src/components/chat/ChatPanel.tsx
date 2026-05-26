'use client';

import clsx from 'clsx';
import { useEffect, useRef, useState } from 'react';

import type { SessionFullState } from '@/lib/api';

export interface ChatMessage {
  turn_id: number;
  role: 'agent' | 'bu' | 'system';
  text: string;
  streaming?: boolean;
}

export function ChatPanel({
  messages,
  disabled,
  thinking = false,
  onSend,
  actionBarSlot,
  innerMaxWidthClass,
}: {
  messages: ChatMessage[];
  disabled: boolean;
  thinking?: boolean;
  onSend: (text: string) => void;
  /** textarea 上方插槽。Consult 全寬版用來放 InlineActionBar。 */
  actionBarSlot?: React.ReactNode;
  /** 訊息列 / 輸入框 inner wrapper 的 max-width(全寬下置中限寬用)。預設無限。 */
  innerMaxWidthClass?: string;
}) {
  const [draft, setDraft] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: 'smooth',
    });
  }, [messages, thinking]);

  function submit() {
    const text = draft.trim();
    if (!text || disabled) return;
    onSend(text);
    setDraft('');
  }

  const innerCls = clsx(innerMaxWidthClass, innerMaxWidthClass && 'mx-auto');

  return (
    <div className="flex h-full flex-col">
      <div ref={listRef} className="flex-1 overflow-y-auto p-4">
        <div className={clsx('space-y-3', innerCls)}>
          {messages.length === 0 && !thinking && (
            <div className="text-sm text-neutral-400">等待 agent 開場…</div>
          )}
          {messages.map((m) => (
            <MessageBubble key={`${m.turn_id}-${m.role}`} msg={m} />
          ))}
          {thinking && <ThinkingBubble />}
        </div>
      </div>
      <div className="border-t bg-white">
        <div className={clsx('p-3', innerCls)}>
          {actionBarSlot && <div className="mb-2">{actionBarSlot}</div>}
          <textarea
            className="w-full rounded-md border px-3 py-2 text-sm"
            rows={2}
            placeholder={disabled ? '等 agent 回覆中…' : '輸入你的回覆，Enter 送出'}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            disabled={disabled}
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={submit}
              disabled={disabled || !draft.trim()}
              className="rounded-md bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-muted disabled:opacity-50"
            >
              送出
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl border bg-white px-4 py-3 text-sm text-neutral-500 flex items-center gap-2">
        <span className="text-xs text-neutral-400">Agent 正在思考</span>
        <span className="flex gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-neutral-400 animate-bounce" />
        </span>
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isAgent = msg.role === 'agent';
  return (
    <div className={clsx('flex', isAgent ? 'justify-start' : 'justify-end')}>
      <div
        className={clsx(
          'max-w-[85%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap',
          isAgent
            ? 'bg-white border text-neutral-800'
            : 'bg-accent text-white',
        )}
      >
        {msg.text}
        {msg.streaming && <span className="ml-1 animate-pulse">▊</span>}
      </div>
    </div>
  );
}

export function historyToMessages(state: SessionFullState | undefined): ChatMessage[] {
  if (!state) return [];
  return state.history.map((h) => ({
    turn_id: h.turn_id,
    role: h.role,
    text: h.raw_text,
  }));
}
