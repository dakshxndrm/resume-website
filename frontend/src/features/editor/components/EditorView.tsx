"use client";
/**
 * Full resume editor: every section editable, debounced live re-scoring, save to
 * Postgres, and ATS-friendly PDF export.
 *
 * Signed-out users get the whole editor. Work is never discarded — an unsaved
 * draft is kept in localStorage, and Save prompts for Google sign-in instead of
 * failing silently.
 */
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Download, LogIn, Save } from "lucide-react";
import { Section, Container } from "@/components/ui/Section";
import { Input, Textarea } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { useAuth } from "@/lib/auth-context";
import { ApiError, api } from "@/lib/api";
import { takeCarry } from "@/lib/carry";
import { isBlankResume } from "@/lib/resume-text";
import { emptyResume, type EducationItem, type ProjectItem, type Resume, type WorkItem } from "@/types/resume";
import { useLiveScore } from "../hooks/useLiveScore";
import { RepeatableList } from "./RepeatableList";
import { ResumePreview } from "./ResumePreview";
import { ScorePanel } from "./ScorePanel";
import { SkillChips } from "./SkillChips";

const DRAFT_KEY = "resumeai:editor-draft";

const blankWork = (): WorkItem => ({ company: "", position: "", startDate: "", endDate: "", highlights: [] });
const blankEducation = (): EducationItem => ({ institution: "", area: "", studyType: "", startDate: "", endDate: "" });
const blankProject = (): ProjectItem => ({ name: "", description: "", highlights: [] });

/** Bullets are edited as one-per-line text — no nested repeatable UI needed.
 *  Blank lines are kept while typing (filtering them here would eat the newline
 *  the moment you press Enter); they're dropped on save and at render time. */
const linesToList = (text: string) => text.split("\n");

const pruneBullets = (resume: Resume): Resume => ({
  ...resume,
  work: resume.work.map((w) => ({ ...w, highlights: w.highlights.filter((h) => h.trim()) })),
  projects: resume.projects.map((p) => ({ ...p, highlights: p.highlights.filter((h) => h.trim()) })),
});

export function EditorView({ id }: { id: string }) {
  const [resume, setResume] = useState<Resume>(emptyResume);
  const [loading, setLoading] = useState(id !== "new");
  const [loadError, setLoadError] = useState<string | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [tab, setTab] = useState<"score" | "preview">("score");

  const { user, login, enabled: authEnabled } = useAuth();
  const router = useRouter();
  const toast = useToast();
  const { report, status, error, retry } = useLiveScore(resume, jobDescription.trim() || undefined);

  // ---- load: saved resume, or the local draft for a fresh one
  useEffect(() => {
    if (id === "new") {
      // Arrived from a report via "Fix My Resume": the scored resume and the target
      // role win over any older draft, since that's the work the user just looked at.
      const carry = takeCarry();
      if (carry?.jobDescription) setJobDescription(carry.jobDescription);
      if (carry?.resume) {
        setResume(carry.resume);
        return;
      }
      const draft = typeof window !== "undefined" ? window.localStorage.getItem(DRAFT_KEY) : null;
      if (draft) {
        try { setResume(JSON.parse(draft) as Resume); } catch { /* corrupt draft — start blank */ }
      }
      return;
    }
    let cancelled = false;
    api.getResume(id)
      .then((r) => { if (!cancelled) { setResume(r); setLoadError(null); } })
      .catch((e: unknown) => {
        if (!cancelled) setLoadError(e instanceof Error ? e.message : "Could not load this resume.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [id]);

  // ---- keep an unsaved draft so a refresh or a sign-in popup can't lose work
  useEffect(() => {
    if (id === "new" && !isBlankResume(resume)) {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify(resume));
    }
  }, [id, resume]);

  const patchBasics = (field: string, value: string) =>
    setResume((r) => ({ ...r, basics: { ...r.basics, [field]: value } }));

  // ---- save
  const persist = useCallback(async () => {
    setSaving(true);
    try {
      const { id: savedId } = await api.saveResume(pruneBullets(resume));
      window.localStorage.removeItem(DRAFT_KEY);
      toast("success", "Saved");
      if (id === "new") router.replace(`/editor/${savedId}`);
      else setResume((r) => ({ ...r, id: savedId }));
    } catch (e: unknown) {
      toast("error", e instanceof ApiError ? `Could not save — ${e.message}` : "Could not save. Is the backend running?");
    } finally {
      setSaving(false);
    }
  }, [resume, id, router, toast]);

  const save = () => (user ? persist() : setNeedsAuth(true));

  const signInThenSave = async () => {
    try {
      await login();
    } catch {
      toast("error", "Sign-in was cancelled — your work is still here.");
      return;
    }
    setNeedsAuth(false);
    await persist();
  };

  // ---- export
  const exportPdf = async () => {
    setExporting(true);
    try {
      const blob = await api.exportResumePdf(resume);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${resume.basics.name.trim() || "resume"}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e: unknown) {
      toast("error", e instanceof ApiError ? e.message : "Could not export the PDF.");
    } finally {
      setExporting(false);
    }
  };

  if (loading)
    return <Section><Container><Skeleton className="h-96 w-full" /></Container></Section>;

  if (loadError)
    return (
      <Section><Container className="flex flex-col items-center gap-4 text-center">
        <h1 className="text-2xl font-bold">We couldn&apos;t load this resume</h1>
        <p className="text-neutral">{loadError}</p>
        <Button onClick={() => router.push("/editor/new")}>Start a new one</Button>
      </Container></Section>
    );

  return (
    <Section className="py-8">
      <Container>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold">Resume editor</h1>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={exportPdf} loading={exporting} disabled={isBlankResume(resume)}>
              <Download className="h-4 w-4" aria-hidden />
              Export PDF
            </Button>
            <Button onClick={save} loading={saving}>
              <Save className="h-4 w-4" aria-hidden />
              Save
            </Button>
          </div>
        </div>

        {needsAuth && !user && (
          <Card className="mb-6 flex flex-wrap items-center justify-between gap-4 border-primary/40">
            <div>
              <p className="font-semibold">Sign in to save this resume</p>
              <p className="text-sm text-neutral">
                Your edits are safe in this browser meanwhile — nothing is lost.
                {!authEnabled && " (Sign-in is not configured on this deployment.)"}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" onClick={() => setNeedsAuth(false)}>Keep editing</Button>
              <Button onClick={signInThenSave} disabled={!authEnabled}>
                <LogIn className="h-4 w-4" aria-hidden />
                Sign in with Google
              </Button>
            </div>
          </Card>
        )}

        <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr]">
          {/* ---------------- form ---------------- */}
          <div className="flex flex-col gap-10">
            <fieldset className="flex flex-col gap-4">
              <legend className="mb-2 text-lg font-semibold">Contact</legend>
              <div className="grid gap-4 sm:grid-cols-2">
                <Input label="Full name" value={resume.basics.name} onChange={(e) => patchBasics("name", e.target.value)} />
                <Input label="Target job title" value={resume.basics.label} onChange={(e) => patchBasics("label", e.target.value)} />
                <Input label="Email" type="email" value={resume.basics.email} onChange={(e) => patchBasics("email", e.target.value)} />
                <Input label="Phone" type="tel" value={resume.basics.phone ?? ""} onChange={(e) => patchBasics("phone", e.target.value)} />
                <Input label="Location" value={resume.basics.location ?? ""} onChange={(e) => patchBasics("location", e.target.value)} />
                <Input label="Website" value={resume.basics.url ?? ""} onChange={(e) => patchBasics("url", e.target.value)} />
              </div>
              <SkillChips
                label="Profile links"
                hint="LinkedIn, GitHub, portfolio — press Enter to add each one."
                skills={resume.basics.links ?? []}
                onChange={(links) => setResume((r) => ({ ...r, basics: { ...r.basics, links } }))}
              />
            </fieldset>

            <fieldset className="flex flex-col gap-4">
              <legend className="mb-2 text-lg font-semibold">Summary</legend>
              <Textarea
                label="Professional summary"
                value={resume.basics.summary ?? ""}
                onChange={(e) => patchBasics("summary", e.target.value)}
              />
            </fieldset>

            <RepeatableList<WorkItem>
              legend="Experience"
              items={resume.work}
              onChange={(work) => setResume((r) => ({ ...r, work }))}
              blank={blankWork}
              addLabel="Add experience"
              emptyHint="No roles yet. Add internships and part-time work too — they count."
              describe={(job, i) => job.company || job.position || `Experience ${i + 1}`}
            >
              {(job, patch) => (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input label="Company" value={job.company} onChange={(e) => patch({ company: e.target.value })} />
                    <Input label="Role" value={job.position} onChange={(e) => patch({ position: e.target.value })} />
                    <Input label="Start date" placeholder="Jan 2022" value={job.startDate} onChange={(e) => patch({ startDate: e.target.value })} />
                    <Input label="End date" placeholder="Leave blank for Present" value={job.endDate ?? ""} onChange={(e) => patch({ endDate: e.target.value })} />
                  </div>
                  <Textarea
                    label="Bullet points (one per line)"
                    placeholder={"Cut p95 latency 40% by adding Redis caching\nShipped the billing API used by 12k users"}
                    value={job.highlights.join("\n")}
                    onChange={(e) => patch({ highlights: linesToList(e.target.value) })}
                  />
                </>
              )}
            </RepeatableList>

            <RepeatableList<EducationItem>
              legend="Education"
              items={resume.education}
              onChange={(education) => setResume((r) => ({ ...r, education }))}
              blank={blankEducation}
              addLabel="Add education"
              emptyHint="Add your degree, bootcamp or diploma."
              describe={(edu, i) => edu.institution || `Education ${i + 1}`}
            >
              {(edu, patch) => (
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input label="School" value={edu.institution} onChange={(e) => patch({ institution: e.target.value })} />
                  <Input label="Degree" placeholder="B.Tech" value={edu.studyType} onChange={(e) => patch({ studyType: e.target.value })} />
                  <Input label="Field of study" placeholder="Computer Science" value={edu.area} onChange={(e) => patch({ area: e.target.value })} />
                  <Input label="Grade (optional)" placeholder="8.7 CGPA" value={edu.score ?? ""} onChange={(e) => patch({ score: e.target.value })} />
                  <Input label="Start year" placeholder="2019" value={edu.startDate} onChange={(e) => patch({ startDate: e.target.value })} />
                  <Input label="End year" placeholder="2023" value={edu.endDate ?? ""} onChange={(e) => patch({ endDate: e.target.value })} />
                </div>
              )}
            </RepeatableList>

            <RepeatableList<ProjectItem>
              legend="Projects"
              items={resume.projects}
              onChange={(projects) => setResume((r) => ({ ...r, projects }))}
              blank={blankProject}
              addLabel="Add project"
              emptyHint="Projects carry real weight when your work history is short."
              describe={(proj, i) => proj.name || `Project ${i + 1}`}
            >
              {(proj, patch) => (
                <>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Input label="Project name" value={proj.name} onChange={(e) => patch({ name: e.target.value })} />
                    <Input label="Link (optional)" placeholder="github.com/you/project" value={proj.url ?? ""} onChange={(e) => patch({ url: e.target.value })} />
                  </div>
                  <Textarea label="Description" value={proj.description} onChange={(e) => patch({ description: e.target.value })} />
                  <Textarea
                    label="Highlights and tech used (one per line)"
                    placeholder={"Built with Next.js, FastAPI and PostgreSQL\nParsed 10k resumes in the first month"}
                    value={proj.highlights.join("\n")}
                    onChange={(e) => patch({ highlights: linesToList(e.target.value) })}
                  />
                </>
              )}
            </RepeatableList>

            <fieldset className="flex flex-col gap-4">
              <legend className="mb-2 text-lg font-semibold">Skills</legend>
              <SkillChips
                label="Skills"
                hint="Comma-separated pastes are split into separate chips."
                skills={resume.skills}
                onChange={(skills) => setResume((r) => ({ ...r, skills }))}
              />
              <SkillChips
                label="Certifications"
                skills={resume.certifications}
                onChange={(certifications) => setResume((r) => ({ ...r, certifications }))}
              />
            </fieldset>

            <fieldset className="flex flex-col gap-4">
              <legend className="mb-2 text-lg font-semibold">Target job</legend>
              <Textarea
                label="Job description (optional)"
                placeholder="Paste the posting here to score against it and see which required skills you're missing."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </fieldset>
          </div>

          {/* ---------------- score / preview ---------------- */}
          <div className="lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:self-start lg:overflow-y-auto">
            <div role="tablist" aria-label="Editor side panel" className="mb-4 inline-flex rounded-btn bg-surface p-1">
              {(["score", "preview"] as const).map((key) => (
                <button
                  key={key}
                  role="tab"
                  type="button"
                  aria-selected={tab === key}
                  onClick={() => setTab(key)}
                  className={`focus-ring rounded-btn px-4 py-1.5 text-sm font-semibold capitalize transition-colors ${
                    tab === key ? "bg-white text-primary shadow-sm" : "text-neutral hover:text-secondary"
                  }`}
                >
                  {key}
                </button>
              ))}
            </div>

            {tab === "score" ? (
              <ScorePanel report={report} status={status} error={error} onRetry={retry} />
            ) : (
              <ResumePreview resume={resume} />
            )}
          </div>
        </div>
      </Container>
    </Section>
  );
}
