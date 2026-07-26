/**
 * Flatten a structured resume into plain text.
 *
 * The backend scorer reads `raw_text` / `word_count` for its semantic (BM25) and
 * formatting signals — an uploaded file supplies those from the parser. A resume
 * typed into the editor has no file behind it, so we build the same two fields
 * here. Without this the editor's semantic score would sit at the neutral 60 and
 * formatting at 50 no matter what you typed.
 *
 * This adds keys to the `resume` object only. The /score request and response
 * shapes are unchanged, and scoring.py is untouched.
 */
import type { Resume } from "@/types/resume";

export function resumeToText(resume: Resume): string {
  const { basics } = resume;
  const lines: string[] = [
    basics.name,
    basics.label,
    [basics.email, basics.phone, basics.location, basics.url].filter(Boolean).join(" | "),
    ...(basics.links ?? []),
    basics.summary ?? "",
  ];

  for (const job of resume.work) {
    lines.push(`${job.position} ${job.company} ${job.startDate} ${job.endDate || "Present"}`);
    lines.push(...job.highlights);
  }
  for (const edu of resume.education) {
    lines.push(`${edu.studyType} ${edu.area} ${edu.institution} ${edu.startDate} ${edu.endDate ?? ""} ${edu.score ?? ""}`);
  }
  for (const proj of resume.projects) {
    lines.push(`${proj.name} ${proj.url ?? ""}`, proj.description, ...proj.highlights);
  }
  lines.push(resume.skills.join(", "), resume.certifications.join(", "));

  return lines.map((l) => l.trim()).filter(Boolean).join("\n");
}

/** The exact payload POST /score expects for an editor-authored resume. */
export function toScorePayload(resume: Resume) {
  const rawText = resumeToText(resume);
  return {
    ...resume,
    raw_text: rawText,
    word_count: rawText.split(/\s+/).filter(Boolean).length,
  };
}

/** Nothing typed yet — don't spend a Groq call scoring a blank form. */
export function isBlankResume(resume: Resume): boolean {
  return resumeToText(resume).trim() === "";
}
