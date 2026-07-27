"use client";
/** Live score + suggestions beside the form.
 *
 *  Four honest states, no fifth: nothing typed yet, re-scoring, a real score, or
 *  a real error. On error the panel shows the failure and a retry — never a
 *  placeholder number, and never a stale score dressed up as current. */
import { AlertCircle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ScoreGauge } from "@/features/score/components/ScoreGauge";
import { SuggestionCard } from "@/features/score/components/SuggestionCard";
import type { ScoreStatus } from "../hooks/useLiveScore";
import type { ScoreReport } from "@/types/resume";

/** "cache" is still AI-written advice, just not paid for twice — saying "cached"
 *  is more honest than calling it fresh, and less confusing than "rule-based". */
const SUGGESTION_SOURCE_LABEL: Record<NonNullable<ScoreReport["suggestionsSource"]>, string> = {
  ai: "by AI",
  cache: "by AI (cached)",
  rules: "rule-based",
};

export function ScorePanel({
  report, status, error, onRetry,
}: {
  report: ScoreReport | null;
  status: ScoreStatus;
  error: string | null;
  onRetry: () => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col items-center gap-3 text-center">
        <h2 className="self-start text-lg font-semibold">Live ATS score</h2>

        {status === "blank" && (
          <p className="py-8 text-sm text-neutral">
            Start filling in your resume — your score appears here as you type.
          </p>
        )}

        {status === "error" && (
          <div className="flex flex-col items-center gap-3 py-6">
            <AlertCircle className="h-8 w-8 text-error" aria-hidden />
            <p className="font-semibold">Couldn&apos;t score this resume</p>
            <p className="max-w-prose text-sm text-neutral">{error}</p>
            <Button variant="ghost" onClick={onRetry}>Try again</Button>
          </div>
        )}

        {(status === "scoring" || status === "ready") && (
          <>
            {/* No report yet = first score in flight. Show the spinner alone rather
                than a zero, which would read as a real (terrible) score. */}
            {report ? (
              <div
                className={status === "scoring" ? "opacity-50 transition-opacity" : "transition-opacity"}
                aria-busy={status === "scoring"}
              >
                <ScoreGauge score={report.total} size={150} />
                <p className="mt-1 text-sm font-medium">{report.verdict}</p>
              </div>
            ) : (
              <div className="flex h-[150px] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-neutral" aria-hidden />
              </div>
            )}

            <p className="flex h-5 items-center gap-2 text-xs text-neutral" role="status" aria-live="polite">
              {status === "scoring" ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                  Re-scoring…
                </>
              ) : (
                report && `Updated · suggestions ${SUGGESTION_SOURCE_LABEL[report.suggestionsSource ?? "rules"]}`
              )}
            </p>
          </>
        )}
      </Card>

      {report && report.missingSkills.length > 0 && (
        <Card>
          <h3 className="mb-2 text-sm font-semibold">Missing role-critical skills</h3>
          <div className="flex flex-wrap gap-2">
            {report.missingSkills.map((s) => <Badge key={s} tone="medium">{s}</Badge>)}
          </div>
        </Card>
      )}

      {report && report.suggestions.length > 0 && (
        <div className="flex flex-col gap-3">
          <h3 className="text-lg font-semibold">Suggestions</h3>
          {report.suggestions.map((s, i) => <SuggestionCard key={s.id} s={s} index={i} />)}
        </div>
      )}
    </div>
  );
}
