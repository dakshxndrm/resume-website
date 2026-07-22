const tones = {
  high: "bg-error/10 text-error",
  medium: "bg-primary/10 text-primary",
  low: "bg-neutral/10 text-neutral",
  success: "bg-success/10 text-success",
} as const;

export function Badge({ tone = "low", children }: { tone?: keyof typeof tones; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
