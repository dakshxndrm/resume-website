import { Section, Container } from "@/components/ui/Section";

export default function AboutPage() {
  return (
    <Section>
      <Container className="max-w-prose">
        <h1 className="mb-6 text-3xl font-bold">About ResumeAI</h1>
        <p className="mb-4 text-neutral">
          ResumeAI scores your resume the way real applicant tracking systems do — parsing, skill
          extraction, and semantic matching built on published ATS research — then tells you exactly
          what to fix. Free, for everyone.
        </p>
        <p className="text-neutral">
          Built by Daksh, a computer science engineer, as an open exploration of modern ML
          (embedding models, retrieval-grounded suggestions) applied to a problem every job seeker has.
        </p>
      </Container>
    </Section>
  );
}
