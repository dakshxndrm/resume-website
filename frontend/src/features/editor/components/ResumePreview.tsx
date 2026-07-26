TASK: Extend ml/data/prepare.py toward real pretraining scale. Work ONLY inside ml/
and data/ — another session may be editing eval/ and backend/.

CONTEXT: ml/README.md states pretraining needs 50k-100k documents for any signal.
Current sample is ~24 fake records. The datasets below total under 3,000 real resumes,
which is NOT enough — document this gap honestly rather than pretending otherwise.

1) Add loaders for:
   - CareerCorpus (Mendeley wzzwn37gmd, .xlsx, 302)
   - Kaggle snehaanbhawal/resume-dataset (2,482)
   - HuggingFace jensjorisdecorte/anonymous-working-histories
   - Investigate the ~70,000-resume corpus referenced in arxiv 1607.07657 and report
     whether it is actually downloadable and under what licence. This is the only source
     in the right size range — if it is not obtainable, say so plainly.
   Normalize all into the existing JSONL format. Document licences per source.

2) Update ml/README.md with a data-inventory table: source, count, licence, and whether
   it is real or synthetic. State the running total against the 50k target.

3) Report honestly: with the data actually obtainable today, is pretraining worth running
   at all, or should the JEPA track stay parked until live consented traffic arrives?

Do not commit any downloaded data. Do not touch backend/, frontend/, or eval/.
"use client";
/** On-screen preview. Mirrors the single-column layout of the exported PDF so
 *  what you see here is what an ATS parser gets. */
import type { Resume } from "@/types/resume";

export function ResumePreview({ resume }: { resume: Resume }) {
  const { basics } = resume;
  const contact = [basics.email, basics.phone, basics.location, basics.url].filter(Boolean);

  return (
    <div className="rounded-card border border-neutral/15 bg-white p-8 text-secondary shadow-sm">
      <h2 className="text-xl font-bold text-black">{basics.name || "Your Name"}</h2>
      {basics.label && <p className="text-sm text-primary">{basics.label}</p>}
      {contact.length > 0 && <p className="mt-1 text-xs text-neutral">{contact.join(" | ")}</p>}
      {(basics.links ?? []).length > 0 && (
        <p className="text-xs text-neutral">{(basics.links ?? []).join(" | ")}</p>
      )}

      {basics.summary && (
        <PreviewSection title="Summary">
          <p className="max-w-prose text-sm">{basics.summary}</p>
        </PreviewSection>
      )}

      {resume.work.length > 0 && (
        <PreviewSection title="Experience">
          {resume.work.map((job, i) => (
            <div key={i} className="mb-3">
              <p className="text-sm font-semibold text-black">
                {[job.position, job.company].filter(Boolean).join(" — ")}
              </p>
              {(job.startDate || job.endDate) && (
                <p className="text-xs italic text-neutral">
                  {job.startDate} - {job.endDate || "Present"}
                </p>
              )}
              <Bullets items={job.highlights} />
            </div>
          ))}
        </PreviewSection>
      )}

      {resume.education.length > 0 && (
        <PreviewSection title="Education">
          {resume.education.map((edu, i) => (
            <div key={i} className="mb-2">
              <p className="text-sm font-semibold text-black">
                {[[edu.studyType, edu.area].filter(Boolean).join(" in "), edu.institution]
                  .filter(Boolean)
                  .join(" — ")}
              </p>
              <p className="text-xs italic text-neutral">
                {[[edu.startDate, edu.endDate].filter(Boolean).join(" - "), edu.score]
                  .filter(Boolean)
                  .join(" | ")}
              </p>
            </div>
          ))}
        </PreviewSection>
      )}

      {resume.projects.length > 0 && (
        <PreviewSection title="Projects">
          {resume.projects.map((proj, i) => (
            <div key={i} className="mb-3">
              <p className="text-sm font-semibold text-black">
                {[proj.name, proj.url].filter(Boolean).join(" — ")}
              </p>
              {proj.description && <p className="text-sm">{proj.description}</p>}
              <Bullets items={proj.highlights} />
            </div>
          ))}
        </PreviewSection>
      )}

      {resume.skills.length > 0 && (
        <PreviewSection title="Skills">
          <p className="text-sm">{resume.skills.join(", ")}</p>
        </PreviewSection>
      )}

      {resume.certifications.length > 0 && (
        <PreviewSection title="Certifications">
          <p className="text-sm">{resume.certifications.join(", ")}</p>
        </PreviewSection>
      )}
    </div>
  );
}

function PreviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <>
      <h3 className="mb-1 mt-5 border-b border-neutral/25 pb-1 text-xs font-bold uppercase tracking-wide text-black">
        {title}
      </h3>
      {children}
    </>
  );
}

function Bullets({ items }: { items: string[] }) {
  // Strip any bullet marker the user pasted in — the list renders its own.
  const visible = items.map((b) => b.replace(/^[-•*]\s*/, "").trim()).filter(Boolean);
  if (visible.length === 0) return null;
  return (
    <ul className="ml-4 list-disc text-sm">
      {visible.map((b, i) => <li key={i}>{b}</li>)}
    </ul>
  );
}
