import { Section, Container } from "@/components/ui/Section";
import { Card } from "@/components/ui/Card";
import { DropZone } from "@/features/upload/components/DropZone";
import { ScoreGauge } from "@/features/score/components/ScoreGauge";
import { UploadCloud, Gauge, Wand2 } from "lucide-react";

const steps = [
  { icon: UploadCloud, title: "Upload", text: "Drop your resume — PDF or Word." },
  { icon: Gauge, title: "Score", text: "ATS score across 6 categories." },
  { icon: Wand2, title: "Improve", text: "Fix issues with guided suggestions." },
];

export default function Landing() {
  return (
    <>
      {/* HERO — one primary action */}
      <Section className="pt-20 md:pt-28">
        <Container className="flex flex-col items-center gap-8 text-center">
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight md:text-6xl">
            Is your resume <span className="text-primary">beating the ATS?</span>
          </h1>
          <p className="max-w-prose text-lg text-neutral md:text-xl">
            Free score in 30 seconds. No sign-up to try.
          </p>
          <DropZone />
        </Container>
      </Section>

      {/* SOCIAL PROOF */}
      <Section alt className="py-10 md:py-10">
        <Container className="flex flex-wrap items-center justify-center gap-x-10 gap-y-3 text-sm text-neutral">
          <span><strong className="text-secondary">12,480</strong> resumes scored</span>
          <span aria-hidden>·</span>
          <span>Your resume is <strong className="text-secondary">never shared or sold</strong></span>
          <span aria-hidden>·</span>
          <span>Built on published ATS research</span>
        </Container>
      </Section>

      {/* HOW IT WORKS — 3 cards, scannable */}
      <Section>
        <Container>
          <h2 className="mb-12 text-center text-3xl font-bold">How it works</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {steps.map(({ icon: Icon, title, text }) => (
              <Card key={title} className="flex flex-col items-center gap-3 text-center">
                <span className="rounded-full bg-primary/10 p-3 text-primary"><Icon className="h-6 w-6" aria-hidden /></span>
                <h3 className="text-lg font-semibold">{title}</h3>
                <p className="text-sm text-neutral">{text}</p>
              </Card>
            ))}
          </div>
        </Container>
      </Section>

      {/* LIVE DEMO — show, don't tell */}
      <Section alt>
        <Container className="grid items-center gap-12 md:grid-cols-2">
          <div>
            <h2 className="mb-4 text-3xl font-bold">See exactly what recruiters' software sees</h2>
            <p className="max-w-prose text-neutral">
              We parse your resume the way an applicant tracking system does — skills, experience,
              education, formatting — then score each category and show you <strong className="text-secondary">precisely what to fix</strong>.
            </p>
          </div>
          <div className="flex justify-center">
            <ScoreGauge score={72} />
          </div>
        </Container>
      </Section>
    </>
  );
}
