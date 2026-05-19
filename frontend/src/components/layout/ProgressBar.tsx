import clsx from 'clsx';

const STEPS = [
  { key: 'explore', label: 'Explore', matches: ['explore', 'cold'] },
  { key: 'consult', label: 'Consult', matches: ['consult_step1', 'consult_step2'] },
  { key: 'done', label: 'Done', matches: ['done'] },
] as const;

export function ProgressBar({ mode }: { mode: string }) {
  const activeIdx = STEPS.findIndex((s) => (s.matches as readonly string[]).includes(mode));
  return (
    <div className="flex items-center gap-2 text-sm">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <span
            className={clsx(
              'h-2 w-2 rounded-full',
              i <= activeIdx ? 'bg-accent' : 'bg-neutral-300',
            )}
          />
          <span
            className={clsx(
              i === activeIdx ? 'font-medium text-neutral-800' : 'text-neutral-500',
            )}
          >
            {s.label}
          </span>
          {i < STEPS.length - 1 && <span className="text-neutral-300">──</span>}
        </div>
      ))}
    </div>
  );
}
