"use client";
/**
 * Consent + deletion controls (Phase 0 of the project plan).
 *
 * Two rules this component exists to honour:
 *  1. Consent is opt-in. The checkbox renders from the server's stored value and
 *     starts unchecked for every new account. Nothing here pre-ticks it, and
 *     declining changes nothing about scoring, saving or export.
 *  2. Deletion is reachable. It sits next to the consent box rather than three
 *     levels into a settings page, and it asks once before doing anything.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";

export function PrivacyControls({ onDeleted }: { onDeleted: () => void }) {
  const toast = useToast();
  const [consent, setConsent] = useState<boolean | null>(null); // null = not loaded yet
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    // Unreachable backend leaves this null, which renders the box disabled rather
    // than guessing "false" — guessing would misreport a user who had opted in.
    api.getMe()
      .then((me) => setConsent(me.trainingConsent))
      .catch(() => setConsent(null));
  }, []);

  async function toggle(next: boolean) {
    setSaving(true);
    const previous = consent;
    setConsent(next); // optimistic, reverted below if the call fails
    try {
      const { trainingConsent } = await api.setTrainingConsent(next);
      setConsent(trainingConsent);
      toast("success", trainingConsent ? "Thanks — consent recorded." : "Consent withdrawn.");
    } catch {
      setConsent(previous);
      toast("error", "Could not save that. Your setting is unchanged.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      const { deleted } = await api.deleteAccount();
      toast(
        "success",
        `Deleted ${deleted.resumes} resume(s), ${deleted.scoreReports} report(s) and ${deleted.trainingExamples} training record(s).`
      );
      onDeleted();
    } catch {
      toast("error", "Could not delete your data. Nothing was removed — please try again.");
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <Card className="mt-10">
      <h2 className="text-lg font-semibold">Your data</h2>

      <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm">
        <input
          type="checkbox"
          className="focus-ring mt-0.5 h-4 w-4 shrink-0 rounded border-neutral/40"
          checked={consent === true}
          disabled={consent === null || saving}
          onChange={(e) => toggle(e.target.checked)}
        />
        <span className="text-neutral">
          <span className="font-medium text-secondary">
            Use my resumes to help train the scoring model.
          </span>{" "}
          If you tick this, an anonymised copy of your resume (name, email, phone and
          links removed) and the AI feedback it received are stored and used to train
          our own scoring model. This is entirely optional — every feature works the
          same either way, and you can untick it at any time.{" "}
          <Link href="/privacy" className="focus-ring underline hover:text-primary">
            What we store
          </Link>
        </span>
      </label>

      <hr className="my-6 border-neutral/15" />

      {!confirming ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-neutral">
            Delete your account and everything in it. This cannot be undone.
          </p>
          <Button variant="ghost" onClick={() => setConfirming(true)}>
            Delete my data
          </Button>
        </div>
      ) : (
        <div className="rounded-card border border-error/30 bg-error/5 p-4">
          <p className="flex items-start gap-2 text-sm font-medium text-secondary">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-error" aria-hidden />
            Permanently delete every saved resume, score report and training record,
            plus your account row? This cannot be undone.
          </p>
          <div className="mt-4 flex gap-3">
            <Button variant="danger" loading={deleting} onClick={remove}>
              Yes, delete everything
            </Button>
            <Button variant="ghost" disabled={deleting} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
