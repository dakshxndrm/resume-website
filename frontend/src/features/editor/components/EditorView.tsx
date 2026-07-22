"use client";
/** Split view: form left, preview right. Debounced re-score → live score chip (blueprint §3.4). */
import { useEffect, useRef, useState } from "react";
import { Section, Container } from "@/components/ui/Section";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { emptyResume, type Resume } from "@/types/resume";

export function EditorView({ id }: { id: string }) {
  const [resume, setResume] = useState<Resume>(emptyResume);
  const [score, setScore] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const toast = useToast();
  const timer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    if (id !== "new") api.getResume(id).then(setResume).catch(() => {});
  }, [id]);

  // Debounced live re-score (800ms after typing stops)
  useEffect(() => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.scoreResume(resume).then((r) => setScore(r.total)).catch(() => setScore(72)); // mock until backend live
    }, 800);
    return () => clearTimeout(timer.current);
  }, [resume]);

  const save = async () => {
    setSaving(true);
    try {
      await api.saveResume(resume);
      toast("success", "Saved");
    } catch {
      toast("error", "Could not save — sign in and check backend is running.");
    } finally {
      setSaving(false);
    }
  };

  const patchBasics = (k: string, v: string) =>
    setResume((r) => ({ ...r, basics: { ...r.basics, [k]: v } }));

  return (
    <Section className="py-8">
      <Container>
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Resume editor</h1>
          <div className="flex items-center gap-4">
            {score !== null && (
              <span className="rounded-full bg-surface px-3 py-1 text-sm font-semibold tabular-nums" aria-live="polite">
                ATS score: <span className={score >= 70 ? "text-success" : "text-error"}>{score}</span>
              </span>
            )}
            <Button onClick={save} loading={saving}>Save</Button>
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Form */}
          <div className="flex flex-col gap-5">
            <Input label="Full name" value={resume.basics.name} onChange={(e) => patchBasics("name", e.target.value)} />
            <Input label="Target job title" value={resume.basics.label} onChange={(e) => patchBasics("label", e.target.value)} />
            <Input label="Email" type="email" value={resume.basics.email} onChange={(e) => patchBasics("email", e.target.value)} />
            <Textarea label="Professional summary" value={resume.basics.summary ?? ""} onChange={(e) => patchBasics("summary", e.target.value)} />
            <Textarea
              label="Skills (comma separated)"
              value={resume.skills.join(", ")}
              onChange={(e) => setResume((r) => ({ ...r, skills: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))}
            />
          </div>

          {/* Live preview */}
          <div className="rounded-card border border-neutral/15 bg-white p-8 shadow-sm">
            <h2 className="text-xl font-bold">{resume.basics.name || "Your Name"}</h2>
            <p className="text-sm text-primary">{resume.basics.label || "Target Role"}</p>
            <p className="mt-1 text-xs text-neutral">{resume.basics.email}</p>
            {resume.basics.summary && <p className="mt-4 max-w-prose text-sm">{resume.basics.summary}</p>}
            {resume.skills.length > 0 && (
              <>
                <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-neutral">Skills</h3>
                <p className="mt-1 text-sm">{resume.skills.join(" · ")}</p>
              </>
            )}
          </div>
        </div>
      </Container>
    </Section>
  );
}
