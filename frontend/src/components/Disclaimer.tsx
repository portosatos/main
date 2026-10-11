import { DISCLAIMER } from "@/lib/rules";

// Recommendations are information, not medical advice (SPEC §10).
export default function Disclaimer() {
  return (
    <p role="note" className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
      {DISCLAIMER}
    </p>
  );
}
