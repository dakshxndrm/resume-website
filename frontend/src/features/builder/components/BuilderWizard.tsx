"use client";
import { AnimatePresence, motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { Section, Container } from "@/components/ui/Section";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { useToast } from "@/components/ui/Toast";
import { useWizardState } from "../hooks/useWizardState";
import { steps } from "../steps.config";
import { roleSkillSuggestions } from "@/lib/mock";
import { api } from "@/lib/api";
import { useState } from "react";

export function BuilderWizard() {
  const { resume, patch, step, setStep, clear, hydrated } = useWizardState();
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const router = useRouter();
  if (!hydrated) return null;

  const current = steps[step];
  const next = () => setStep(Math.min(step + 1, steps.length - 1));
  const back = () => setStep(Math.max(step - 1, 0));

  const suggested =
    roleSkillSuggestions[resume.basics.label.toLowerCase()] ?? roleSkillSuggestions.default;

  const finish = async () => {
    setBusy(true);
    try {
      const report = await api.scoreResume(resume);
      clear();
      router.push(`/report/${report.id}`);
    } catch {
      clear();
      router.push("/report/demo"); // backend not wired yet
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section>
      <Container className="max-w-xl">
        {/* Progress */}
        <div className="mb-10">
          <div className="mb-2 flex justify-between text-sm text-neutral">
            <span>Step {step + 1} of {steps.length}</span>
            <span>{current.title}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-neutral/10">
            <motion.div
              className="h-full rounded-full bg-primary"
              animate={{ width: `${((step + 1) / steps.length) * 100}%` }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={current.key}
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -16 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-5"
          >
            {current.key === "role" && (
              <Input
                label="Target job title"
                placeholder="e.g. Frontend Developer"
                value={resume.basics.label}
                onChange={(e) => patch({ basics: { ...resume.basics, label: e.target.value } })}
              />
            )}

            {current.key === "contact" && (
              <>
                <Input label="Full name" value={resume.basics.name}
                  onChange={(e) => patch({ basics: { ...resume.basics, name: e.target.value } })} />
                <Input label="Email" type="email" value={resume.basics.email}
                  onChange={(e) => patch({ basics: { ...resume.basics, email: e.target.value } })} />
                <Input label="Location (optional)" value={resume.basics.location ?? ""}
                  onChange={(e) => patch({ basics: { ...resume.basics, location: e.target.value } })} />
              </>
            )}

            {current.key === "experience" && (
              <Textarea
                label="Describe your most recent role (we'll structure it for you)"
                placeholder="Company, position, dates, what you achieved…"
                value={resume.work[0]?.highlights.join("\n") ?? ""}
                onChange={(e) =>
                  patch({ work: [{ company: "", position: "", startDate: "", highlights: e.target.value.split("\n") }] })
                }
              />
            )}

            {current.key === "education" && (
              <>
                <Input label="Institution" value={resume.education[0]?.institution ?? ""}
                  onChange={(e) => patch({ education: [{ ...(resume.education[0] ?? { area: "", studyType: "", startDate: "" }), institution: e.target.value }] })} />
                <Input label="Degree / field" value={resume.education[0]?.area ?? ""}
                  onChange={(e) => patch({ education: [{ ...(resume.education[0] ?? { institution: "", studyType: "", startDate: "" }), area: e.target.value }] })} />
              </>
            )}

            {current.key === "skills" && (
              <div>
                <p className="mb-3 text-sm text-neutral">
                  Suggested for <strong className="text-secondary">{resume.basics.label || "your role"}</strong> — tap to add:
                </p>
                <div className="mb-5 flex flex-wrap gap-2">
                  {suggested.filter((s) => !resume.skills.includes(s)).map((s) => (
                    <button key={s} onClick={() => patch({ skills: [...resume.skills, s] })}
                      className="focus-ring rounded-full border border-neutral/30 px-3 py-1 text-sm transition-colors hover:border-primary hover:text-primary">
                      + {s}
                    </button>
                  ))}
                </div>
                <div className="flex flex-wrap gap-2">
                  {resume.skills.map((s) => (
                    <button key={s} onClick={() => patch({ skills: resume.skills.filter((x) => x !== s) })}
                      className="focus-ring" aria-label={`Remove ${s}`}>
                      <Badge tone="medium">{s} ✕</Badge>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {current.key === "review" && (
              <div className="rounded-card border border-neutral/15 bg-surface p-6 text-sm">
                <p><strong>{resume.basics.name || "Unnamed"}</strong> — {resume.basics.label || "no target role"}</p>
                <p className="mt-1 text-neutral">{resume.skills.length} skills · {resume.work.length} role(s) · {resume.education.length} education entries</p>
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        <div className="mt-10 flex justify-between">
          <Button variant="ghost" onClick={back} disabled={step === 0}>Back</Button>
          {current.key === "review" ? (
            <Button onClick={finish} loading={busy}>Score My Resume →</Button>
          ) : (
            <Button onClick={next}>Continue</Button>
          )}
        </div>
      </Container>
    </Section>
  );
}
