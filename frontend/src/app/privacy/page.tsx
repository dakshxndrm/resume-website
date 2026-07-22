import { Section, Container } from "@/components/ui/Section";

export default function PrivacyPage() {
  return (
    <Section>
      <Container className="max-w-prose">
        <h1 className="mb-6 text-3xl font-bold">Privacy Policy</h1>
        <p className="mb-4 text-neutral">Draft — replace with a reviewed policy before public launch.</p>
        <ul className="list-disc space-y-2 pl-5 text-neutral">
          <li>Your resume is processed to generate your score and suggestions.</li>
          <li>We never sell or share your resume with employers or third parties.</li>
          <li>With your explicit consent, anonymized resume data may be used to improve our scoring models. You can withdraw consent and delete your data at any time.</li>
          <li>Authentication is handled by Google via Firebase; we store only your name, email, and avatar.</li>
        </ul>
      </Container>
    </Section>
  );
}
