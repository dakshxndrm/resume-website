"use client";
/**
 * Debounced live re-scoring.
 *
 * POST /score runs a Groq call, and the free tier is token-limited, so the
 * request fires 800ms after typing stops — never per keystroke. A blank resume
 * is skipped entirely. Stale responses are discarded by sequence number, so a
 * slow early request can never overwrite a newer score.
 *
 * There is no fallback score: a failure sets status "error" and leaves the
 * report alone. Showing an invented number would be worse than showing nothing.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { isBlankResume } from "@/lib/resume-text";
import type { Resume, ScoreReport } from "@/types/resume";

export const SCORE_DEBOUNCE_MS = 800;

export type ScoreStatus = "blank" | "scoring" | "ready" | "error";

export function useLiveScore(resume: Resume, jobDescription?: string) {
  const [report, setReport] = useState<ScoreReport | null>(null);
  const [status, setStatus] = useState<ScoreStatus>("blank");
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0); // bumped by retry()
  const seq = useRef(0);

  useEffect(() => {
    if (isBlankResume(resume)) {
      setStatus("blank");
      setReport(null);
      return;
    }

    setStatus("scoring");
    const id = ++seq.current;
    const timer = setTimeout(() => {
      api
        .scoreResume(resume, jobDescription)
        .then((r) => {
          if (id !== seq.current) return; // a newer edit already superseded this
          setReport(r);
          setError(null);
          setStatus("ready");
        })
        .catch((e: unknown) => {
          if (id !== seq.current) return;
          setError(e instanceof Error ? e.message : "Could not reach the scoring service.");
          setStatus("error");
        });
    }, SCORE_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [resume, jobDescription, nonce]);

  const retry = useCallback(() => setNonce((n) => n + 1), []);

  return { report, status, error, retry };
}
