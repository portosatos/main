// A labelled bar for 0..100 percent.
export default function ProgressBar({ label, value }: { label: string; value: number }) {
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
