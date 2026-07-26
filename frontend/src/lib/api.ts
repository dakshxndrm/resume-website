/**
 * Single API client — ALL backend calls go through here.
 * Automatically attaches the Firebase ID token when the user is signed in,
 * so the FastAPI backend can verify identity and key data to the Firebase UID.
 */
import { getIdTokenSafe } from "@/lib/firebase";
import { toScorePayload } from "@/lib/resume-text";
import type { Resume, ScoreReport } from "@/types/resume";

const BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getIdTokenSafe();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.json();
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

/* ---- Endpoints (backend stubs exist for each; real logic lands per PROJECT_PLAN) ---- */

export const api = {
  /** Upload resume file for parsing + scoring. Returns the full report plus its id. */
  scoreResumeFile(file: File, jobDescription?: string) {
    const form = new FormData();
    form.append("file", file);
    if (jobDescription) form.append("job_description", jobDescription);
    return requestForm<ScoreReport & { report_id: string }>("/score/upload", form);
  },
  /** Score structured resume (from builder/editor) against a job title/description.
   *  toScorePayload adds raw_text/word_count so the backend's semantic + formatting
   *  signals see real content; the request/response shapes are unchanged. */
  scoreResume(resume: Resume, jobDescription?: string) {
    return request<ScoreReport>("/score", {
      method: "POST",
      body: JSON.stringify({ resume: toScorePayload(resume), job_description: jobDescription }),
    });
  },
  /** Render the resume to an ATS-friendly PDF. Works signed out. */
  exportResumePdf(resume: Resume) {
    return requestBlob("/resumes/export", resume);
  },
  getReport(id: string) {
    return request<ScoreReport>(`/report/${id}`);
  },
  saveResume(resume: Resume) {
    return request<{ id: string }>("/resumes", { method: "POST", body: JSON.stringify(resume) });
  },
  getResume(id: string) {
    return request<Resume>(`/resumes/${id}`);
  },
  listResumes() {
    return request<Resume[]>("/resumes");
  },
  /** Role-based skill suggestions (RAG over O*NET/ESCO — stubbed until Phase 2). */
  suggestSkills(role: string) {
    return request<{ skills: string[] }>(`/skills/suggest?role=${encodeURIComponent(role)}`);
  },
  /** Register/sync the Firebase user with our Postgres users table. */
  syncUser() {
    return request<{ id: string }>("/auth/sync", { method: "POST" });
  },

  /* ---- Account, consent and deletion (Phase 0) ---- */
  /** Account row including the stored consent value — the checkbox renders from this. */
  getMe() {
    return request<Account>("/users/me");
  },
  /** Opt in or out of using this resume data to train the scoring model. */
  setTrainingConsent(trainingConsent: boolean) {
    return request<{ trainingConsent: boolean }>("/users/consent", {
      method: "PATCH",
      body: JSON.stringify({ training_consent: trainingConsent }),
    });
  },
  /** Permanently erase resumes, reports, training examples and the account row. */
  deleteAccount() {
    return request<{ deleted: DeletionSummary }>("/users/me", { method: "DELETE" });
  },
};

export interface Account {
  id: string;
  email: string;
  name: string | null;
  trainingConsent: boolean;
}

export interface DeletionSummary {
  trainingExamples: number;
  scoreReports: number;
  resumes: number;
}

/** Like request(), but the response is a file. Errors still arrive as JSON. */
async function requestBlob(path: string, body: unknown): Promise<Blob> {
  const token = await getIdTokenSafe();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new ApiError(res.status, detail?.detail ?? res.statusText);
  }
  return res.blob();
}

async function requestForm<T>(path: string, form: FormData): Promise<T> {
  const token = await getIdTokenSafe();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body?.detail ?? res.statusText);
  }
  return res.json();
}
