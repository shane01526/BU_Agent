import { getStoredUserId } from '@/lib/auth';

const BASE = '/api/v1';

function headers(): HeadersInit {
  const userId = getStoredUserId();
  return {
    'Content-Type': 'application/json',
    ...(userId ? { 'X-User-Id': userId } : {}),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers(), ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface SessionSummary {
  session_id: string;
  bu: string;
  mode: string;
  status: string;
  updated_at: string;
}

export interface SessionFullState {
  session_id: string;
  user_id: string;
  bu: string;
  sme_role: string;
  raw_hint: string | null;
  mode: string;
  stage: number | null;
  status: string;
  history: Array<{
    turn_id: number;
    mode: string;
    role: 'agent' | 'bu' | 'system';
    raw_text: string;
    timestamp: string;
  }>;
  candidates: Array<{
    rank: number;
    direction: string;
    process_target: string;
    project_type: string;
    score_5d: Record<string, number>;
    pain_signals: string[];
  }>;
  pain_signals: Array<{
    turn_id: number;
    raw_text: string;
    source: 'bu_explicit' | 'agent_reframe';
  }>;
  sections: SectionState[];
  paragraph_description: string | null;
}

export type SectionStatus =
  | 'auto_filled'
  | 'needs_round2'
  | 'placeholder'
  | 'accepted'
  | 'skipped'
  | 'flagged_for_ba';

export interface SectionState {
  section_id: string;
  title: string;
  status: SectionStatus;
  content_md: string;
  last_edit_by: 'agent' | 'bu' | null;
}

export type SectionAction = 'accept' | 'refine' | 'skip' | 'flag';

export interface Deliverables {
  brd_doc_ref: string;
  summary_json: Record<string, unknown>;
  flag_for_ba_review: Record<string, unknown>;
}

export const api = {
  listSessions: () => request<SessionSummary[]>('/sessions'),
  createSession: (body: { bu: string; sme_role: string; raw_hint?: string }) =>
    request<SessionSummary>('/sessions', { method: 'POST', body: JSON.stringify(body) }),
  getSession: (id: string) => request<SessionFullState>(`/sessions/${id}`),
  postMessage: (id: string, text: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/messages`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  selectCandidate: (id: string, rank: number) =>
    request<{ accepted: boolean }>(`/sessions/${id}/candidates/select`, {
      method: 'POST',
      body: JSON.stringify({ rank }),
    }),
  confirmHandoff: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/handoff/confirm`, { method: 'POST' }),
  dismissHandoff: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/handoff/dismiss`, { method: 'POST' }),
  resetExplore: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/explore/reset`, { method: 'POST' }),
  dismissStage5Stuck: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/stage5/dismiss`, { method: 'POST' }),
  quickHandoff: (id: string, rank: number) =>
    request<{ accepted: boolean }>(`/sessions/${id}/stage5/quick-handoff`, {
      method: 'POST',
      body: JSON.stringify({ rank }),
    }),
  acknowledgeAiNecessity: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/ai-necessity/acknowledge`, { method: 'POST' }),
  overrideAiNecessity: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/ai-necessity/override`, { method: 'POST' }),
  explainAiNecessity: (id: string) =>
    request<{ accepted: boolean }>(`/sessions/${id}/ai-necessity/explain`, { method: 'POST' }),
  listSections: (id: string) =>
    request<SectionState[]>(`/sessions/${id}/sections`),
  editSection: (id: string, sid: string, content: string) =>
    request<SectionState>(`/sessions/${id}/sections/${sid}`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),
  sectionAction: (id: string, sid: string, action: SectionAction) =>
    request<SectionState>(`/sessions/${id}/sections/${sid}/action`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    }),
  submitSession: (id: string) =>
    request<Deliverables>(`/sessions/${id}/submit`, { method: 'POST' }),
};

export const SSE_URL = (sessionId: string, userId: string) =>
  `${BASE}/sessions/${sessionId}/events?user_id=${encodeURIComponent(userId)}`;
