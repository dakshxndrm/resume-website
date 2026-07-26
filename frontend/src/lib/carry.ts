/**
 * One-shot handoff between screens (report → editor, upload → editor).
 *
 * sessionStorage, not a query param: a job description is far too long for a URL.
 * Read once and cleared, so a stale resume can never reappear on a later visit.
 *
 * Note: the upload flow can only hand over the job description. `/score/upload`
 * returns the report, not the parsed resume fields, and its JSON shape is fixed —
 * so there is no structured resume on the client to carry.
 */
import type { Resume } from "@/types/resume";

const KEY = "resumeai:carry";

export interface Carry {
  resume?: Resume;
  jobDescription?: string;
}

export function setCarry(carry: Carry): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(carry));
  } catch {
    // private mode / storage full — the editor just opens empty
  }
}

/** Returns the pending handoff and clears it. */
export function takeCarry(): Carry | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return raw ? (JSON.parse(raw) as Carry) : null;
  } catch {
    return null;
  }
}
