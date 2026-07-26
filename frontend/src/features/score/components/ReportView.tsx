"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Section, Container } from "@/components/ui/Section";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ScoreGauge } from "./ScoreGauge";
import { CategoryBars } from "./CategoryBars";
import { SuggestionCard } from "./SuggestionCard";
import { api } from "@/lib/api";
import { mockReport } from "@/lib/mock";
import type { ScoreReport } from "@/types/resume";

export function ReportView({ id }: { id: string }) {
  const [report, setReport] = useState<ScoreReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    // /report/demo is the deliberate sample report. Every other id is real data —
    // never substitute the mock, or a failure looks like a genuine score.
    if (id === "demo") { setReport(mockReport); return; }
    api.getReport(id)
      .then(setReport)
      .catch((e) => setError(e?.message ?? "Could not load this report."));
  }, [id]);

  if (error)
    return (
      <Section><Container className="flex flex-col items-center gap-4 text-center">
        <h1 className="text-2xl font-bold">We couldn&apos;t load this report</h1>
        <p className="text-neutral">{error}</p>
        <Link href="/"><Button>Score a resume</Button></Link>
      </Container></Section>
    );

  if (!report)
    return (
      <Section><Container className="flex flex-col items-center gap-6">
        <Skeleton className="h-48 w-48 rounded-full" />
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-40 w-full max-w-2xl" />
      </Container></Section>
    );

  const visible = showAll ? report.suggestions : report.suggestions.slice(0, 3);

  return (
    <>
      <Section className="pb-8 text-center">
        <Container className="flex flex-col items-center gap-4">
          <ScoreGauge score={report.total} />
          <p className="text-xl font-semibold">{report.verdict}</p>
          {report.jobTitle && <p className="text-sm text-neutral">Scored against: {report.jobTitle}</p>}
        </Container>
      </Section>

      <Section alt className="py-12">
        <Container className="max-w-3xl">
          <h2 className="mb-6 text-2xl font-bold">Category breakdown</h2>
          <CategoryBars categories={report.categories} />
        </Container>
      </Section>

      <Section className="py-12">
        <Container className="max-w-3xl">
          <h2 className="mb-2 text-2xl font-bold">Suggestions, highest impact first</h2>
          {report.missingSkills.length > 0 && (
            <p className="mb-6 flex flex-wrap items-center gap-2 text-sm text-neutral">
              Missing role-critical skills:
              {report.missingSkills.map((s) => <Badge key={s} tone="medium">{s}</Badge>)}
            </p>
          )}
          <div className="flex flex-col gap-4">
            {visible.map((s, i) => <SuggestionCard key={s.id} s={s} index={i} />)}
          </div>
          {!showAll && report.suggestions.length > 3 && (
            <Button variant="ghost" className="mt-6" onClick={() => setShowAll(true)}>
              Show {report.suggestions.length - 3} more
            </Button>
          )}
        </Container>
      </Section>

      {/* Sticky primary action */}
      <div className="sticky bottom-0 border-t border-neutral/10 bg-white/90 py-4 backdrop-blur">
        <Container className="flex justify-center">
          <Link href="/editor/new"><Button>Fix My Resume →</Button></Link>
        </Container>
      </div>
    </>
  );
}
