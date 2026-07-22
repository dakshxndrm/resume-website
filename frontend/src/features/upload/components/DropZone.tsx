"use client";
/** Hero drag-and-drop upload — doubles as the landing page's primary CTA. */
import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { UploadCloud, FileText } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { api, ApiError } from "@/lib/api";
import type { ScoreReport } from "@/types/resume";

export function DropZone() {
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const router = useRouter();

  const accept = (f: File | undefined) => {
    if (!f) return;
    if (!/\.(pdf|docx?)$/i.test(f.name)) {
      toast("error", "Please upload a PDF or Word document.");
      return;
    }
    setFile(f);
  };

  const submit = useCallback(async () => {
    if (!file) return;
    setBusy(true);
    try {
      const report: ScoreReport = await api.scoreResumeFile(file, jobDescription.trim() || undefined);
      // Stash the just-computed report so the report page shows it instantly,
      // even before a database is configured.
      sessionStorage.setItem(`report:${report.id}`, JSON.stringify(report));
      router.push(`/report/${report.id}`);
    } catch (e) {
      if (e instanceof ApiError) {
        toast("error", e.message || "We couldn't score that file. Try another PDF/DOCX.");
      } else {
        toast("error", "Can't reach the server. Is the backend running on port 8000?");
      }
    } finally {
      setBusy(false);
    }
  }, [file, jobDescription, router, toast]);

  return (
    <div id="upload" className="w-full max-w-xl">
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload your resume"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); accept(e.dataTransfer.files[0]); }}
        className={`focus-ring flex cursor-pointer flex-col items-center gap-3 rounded-card border-2 border-dashed p-10 text-center transition-colors duration-150 ${
          drag ? "border-primary bg-primary/5" : "border-neutral/30 bg-white"
        }`}
      >
        {file ? (
          <>
            <FileText className="h-8 w-8 text-primary" aria-hidden />
            <p className="font-medium">{file.name}</p>
            <p className="text-sm text-neutral">Click to choose a different file</p>
          </>
        ) : (
          <>
            <UploadCloud className="h-8 w-8 text-neutral" aria-hidden />
            <p className="font-medium">Drop your resume here</p>
            <p className="text-sm text-neutral">PDF or DOCX · parsed in seconds · never shared</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.doc,.docx"
          className="hidden"
          onChange={(e) => accept(e.target.files?.[0])}
        />
      </div>

      {/* Optional job description — powers the real skill-match + semantic score */}
      <div className="mt-4 text-left">
        <Textarea
          label="Paste the job description (optional — makes your score far more accurate)"
          placeholder="Paste the full job posting here to see how well your resume matches it…"
          rows={4}
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
        />
      </div>

      <Button onClick={submit} loading={busy} disabled={!file} className="mt-4 w-full">
        {busy ? "Scoring…" : "Check My Resume Score →"}
      </Button>
    </div>
  );
}
