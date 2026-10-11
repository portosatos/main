// A labelled bar for 0..100 percent; a value over 100 (a goal passed) fills the bar.
export default function ProgressBar({ label, value }: { label: string; value: number }) {
  value = Math.min(Math.max(value, 0), 100);
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value}
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
    >
      <div className="h-full bg-primary transition-[width]" style={{ width: `${value}%` }} />
    </div>
  );
}
