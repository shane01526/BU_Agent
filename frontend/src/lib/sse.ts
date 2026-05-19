'use client';

import { useEffect, useRef, useState } from 'react';

export type SseEvent = {
  id: number;
  type: string;
  data: Record<string, unknown>;
};

// 瀏覽器直連 backend，跳過 Next.js dev proxy 的 event-stream buffer
const BROWSER_API_BASE =
  typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_BROWSER as string | undefined) ||
      'http://localhost:8000'
    : '';

const KNOWN_EVENTS = [
  'agent_reply_delta',
  'agent_reply_done',
  'bu_turn_recorded',
  'candidate_updated',
  'pain_signal_added',
  'stage_changed',
  'handoff_ready',
  'mode_changed',
  'outline_ready',
  'section_updated',
  'conflict_detected',
  'cold_exit',
  'stage5_stuck',
  'ai_necessity_warning',
  'deliverables_ready',
  'heartbeat',
];

function getCookieUserId(): string | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(/x-dev-user-id=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : null;
}

// React 18 StrictMode 下 useEffect 會跑 mount → unmount → mount 兩次。
// 用 module-level map 確保同一個 sessionId 只有一條 EventSource；
// 第一次 cleanup 不關連線（避開 StrictMode 假性卸載），改用引用計數。
const _activeStreams = new Map<
  string,
  { es: EventSource; refs: number; cleanup: () => void }
>();

export function useSessionEvents(
  sessionId: string | null,
  onEvent: (ev: SseEvent) => void,
) {
  const [connected, setConnected] = useState(false);
  const cbRef = useRef(onEvent);
  cbRef.current = onEvent;

  useEffect(() => {
    if (!sessionId) return;

    let entry = _activeStreams.get(sessionId);
    if (!entry) {
      const userId = getCookieUserId();
      const url = `${BROWSER_API_BASE}/api/v1/sessions/${sessionId}/events${
        userId ? `?user_id=${encodeURIComponent(userId)}` : ''
      }`;
      const es = new EventSource(url, { withCredentials: false });

      es.onerror = (e) => {
        // 連線錯誤暫不彈 toast，等 M4 觀測性整套接起來再做
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[SSE] error', e);
        }
      };

      const handlers: Array<[string, EventListener]> = KNOWN_EVENTS.map((type) => {
        const handler = ((ev: MessageEvent) => {
          let data: Record<string, unknown> = {};
          try {
            data = JSON.parse(ev.data);
          } catch {
            // ignore parse errors
          }
          const id = Number((ev as unknown as { lastEventId?: string }).lastEventId || 0);
          cbRef.current({ id, type, data });
        }) as EventListener;
        es.addEventListener(type, handler);
        return [type, handler];
      });

      entry = {
        es,
        refs: 0,
        cleanup: () => {
          for (const [type, handler] of handlers) {
            es.removeEventListener(type, handler);
          }
          es.close();
        },
      };
      _activeStreams.set(sessionId, entry);
    }

    entry.refs += 1;
    setConnected(entry.es.readyState === EventSource.OPEN);

    return () => {
      const e = _activeStreams.get(sessionId);
      if (!e) return;
      e.refs -= 1;
      // 用 microtask 延遲關閉：StrictMode 假性卸載時下一個 mount 會立刻 ref+1，
      // 真正卸載則 refs 仍為 0，這時才關
      queueMicrotask(() => {
        const cur = _activeStreams.get(sessionId);
        if (cur && cur.refs <= 0) {
          cur.cleanup();
          _activeStreams.delete(sessionId);
        }
      });
    };
  }, [sessionId]);

  return { connected };
}

function parseEvent(block: string): SseEvent | null {
  const lines = block.split('\n');
  let id = 0;
  let type = 'message';
  let data = '';
  for (const line of lines) {
    if (line.startsWith('id:')) id = Number(line.slice(3).trim());
    else if (line.startsWith('event:')) type = line.slice(6).trim();
    else if (line.startsWith('data:')) data += line.slice(5).trim();
  }
  if (!data) return null;
  try {
    return { id, type, data: JSON.parse(data) };
  } catch {
    return null;
  }
}
