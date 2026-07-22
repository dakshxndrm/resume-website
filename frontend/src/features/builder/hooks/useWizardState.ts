"use client";
/** Wizard state with localStorage autosave — Back never loses data (blueprint §3.3). */
import { useCallback, useEffect, useState } from "react";
import { emptyResume, type Resume } from "@/types/resume";

const KEY = "resumeai.builder.draft";

export function useWizardState() {
  const [resume, setResume] = useState<Resume>(emptyResume);
  const [step, setStep] = useState(0);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const saved = JSON.parse(raw);
        setResume(saved.resume ?? emptyResume());
        setStep(saved.step ?? 0);
      }
    } catch {}
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) localStorage.setItem(KEY, JSON.stringify({ resume, step }));
  }, [resume, step, hydrated]);

  const patch = useCallback((p: Partial<Resume>) => setResume((r) => ({ ...r, ...p })), []);
  const clear = useCallback(() => { localStorage.removeItem(KEY); setResume(emptyResume()); setStep(0); }, []);

  return { resume, patch, step, setStep, clear, hydrated };
}
