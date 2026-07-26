/**
 * DEVELOPER DRAFT — NOT LEGAL ADVICE.
 *
 * Written by the developer to describe accurately what the system actually does
 * today, so users are not misled while the product is in early use. It is not a
 * lawyer-reviewed privacy policy and does not claim GDPR/CCPA compliance. Have a
 * qualified person review this before any real marketing push, and keep it in sync
 * with the code: every claim below maps to something in backend/app.
 */
import Link from "next/link";
import { Section, Container } from "@/components/ui/Section";

export const metadata = { title: "Privacy" };

export default function PrivacyPage() {
  return (
    <Section>
      <Container className="max-w-prose">
        <h1 className="text-3xl font-bold">Privacy</h1>
        <p className="mt-2 text-sm text-neutral">
          A plain description of what this app stores and who else sees it. Developer
          draft, written to be accurate rather than reassuring — not a lawyer-reviewed
          policy.
        </p>

        <h2 className="mt-10 text-xl font-semibold">What is stored</h2>
        <p className="mt-2 text-neutral">When you upload or build a resume, we store:</p>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-neutral">
          <li>
            <strong className="text-secondary">The resume text itself</strong> — the full
            text extracted from your PDF/DOCX, or the structured resume you build in the
            editor.
          </li>
          <li>
            <strong className="text-secondary">Parsed details</strong> — the skills,
            work-experience and education entries we detect.
          </li>
          <li>
            <strong className="text-secondary">Scores and feedback</strong> — your overall
            score, each category score, the missing-skills list and the suggestions shown
            to you.
          </li>
          <li>
            <strong className="text-secondary">The job description</strong> you pasted, if
            you pasted one.
          </li>
          <li>
            <strong className="text-secondary">Account basics</strong> — your name, email
            and profile photo URL from Google sign-in.
          </li>
        </ul>
        <p className="mt-3 text-neutral">
          Scoring without signing in still sends your resume to the server to be scored,
          and the resulting report is saved so it can be opened by link. It is not
          attached to any account.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Where it is stored</h2>
        <p className="mt-2 text-neutral">
          In a Neon-hosted PostgreSQL database. That is a third-party cloud service, not a
          machine we own and not your device. Neon can technically access the data it
          hosts, as any database provider can.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Who else sees your resume</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-neutral">
          <li>
            <strong className="text-secondary">Groq</strong> — to generate the written
            suggestions, your resume text and the job description are sent to Groq&apos;s
            API, a third-party AI provider. This happens on every scored resume while AI
            suggestions are enabled. If Groq is unavailable you get rule-based suggestions
            instead, and nothing is sent.
          </li>
          <li>
            <strong className="text-secondary">Google Firebase</strong> — handles sign-in.
            Google sees your identity; we receive only your name, email and photo URL. We
            never see or store your Google password.
          </li>
        </ul>
        <p className="mt-3 text-neutral">
          We do not sell your data, and we do not send your resume to employers or
          recruiters.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Training our own model</h2>
        <p className="mt-2 text-neutral">
          We are building our own scoring model so that scoring does not depend on a
          third-party AI provider forever. That needs training examples.
        </p>
        <p className="mt-3 text-neutral">
          <strong className="text-secondary">This only happens if you tick the box.</strong>{" "}
          The consent checkbox on your dashboard is off by default. Nothing you upload is
          used for training unless you turn it on, and turning it off stops all future
          collection immediately. Everything works identically either way — there is no
          better score and no extra feature for saying yes.
        </p>
        <p className="mt-3 text-neutral">
          When it is on, we store an anonymised copy: your name, email address, phone
          number and profile links are stripped out first. Be aware this is pattern-based
          redaction, not perfect — a name in the body of your resume, such as a referee or
          a former manager, may survive it.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Retention and deletion</h2>
        <p className="mt-2 text-neutral">
          Data is kept until you delete it — there is no automatic expiry yet. The{" "}
          <Link href="/dashboard" className="focus-ring underline hover:text-primary">
            “Delete my data” button on your dashboard
          </Link>{" "}
          permanently removes your saved resumes, score reports, any training records and
          your account row in one step. It is immediate rather than a request queue, and
          it cannot be undone.
        </p>
        <p className="mt-3 text-neutral">
          Two honest caveats. Deletion covers this application&apos;s database; it does not
          reach data already sent to Groq for suggestion generation, which is governed by
          Groq&apos;s own retention policy, nor your Google account, which you control at
          Google. And reports created while signed out are not linked to any account, so
          deletion cannot find them — treat a shared report link as public.
        </p>

        <h2 className="mt-10 text-xl font-semibold">Questions</h2>
        <p className="mt-2 text-neutral">
          This is a solo-built project. If something here is unclear or wrong, raising it
          directly is the fastest fix — and if you would rather not have your resume in a
          hosted database at all, that is a completely reasonable position.
        </p>
      </Container>
    </Section>
  );
}
