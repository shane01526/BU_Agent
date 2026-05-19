export interface PainSignalItem {
  turn_id: number;
  raw_text: string;
  source: 'bu_explicit' | 'agent_reframe';
}

export function PainTimeline({ signals }: { signals: PainSignalItem[] }) {
  if (signals.length === 0) {
    return (
      <div className="text-sm text-neutral-400">
        Pain signals 會隨你回答累積在這裡。
      </div>
    );
  }
  return (
    <ol className="space-y-2 border-l pl-4">
      {signals.map((s, i) => (
        <li key={i} className="relative text-sm">
          <span className="absolute -left-[19px] top-2 h-2 w-2 rounded-full bg-accent" />
          <div className="rounded bg-neutral-50 p-2">
            <div className="text-xs text-neutral-500">
              turn #{s.turn_id} · {s.source === 'bu_explicit' ? '你明說的' : 'agent 推斷的'}
            </div>
            <div className="mt-0.5 text-neutral-800">{s.raw_text}</div>
          </div>
        </li>
      ))}
    </ol>
  );
}
