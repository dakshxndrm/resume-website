import Link from "next/link";
import { Section, Container } from "@/components/ui/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

const templates = [
  { id: "clean", name: "Clean", desc: "Single column, ATS-safe. Best default." },
  { id: "modern", name: "Modern", desc: "Accent color header, still parser-friendly." },
  { id: "compact", name: "Compact", desc: "Fits more in one page for senior resumes." },
];

export default function TemplatesPage() {
  return (
    <Section>
      <Container>
        <h1 className="mb-2 text-3xl font-bold">Templates</h1>
        <p className="mb-10 max-w-prose text-neutral">Every template is single-column and ATS-parser-safe. Your content carries over — switching is free.</p>
        <div className="grid gap-6 md:grid-cols-3">
          {templates.map((t) => (
            <Card key={t.id} className="flex flex-col gap-4">
              <div className="aspect-[3/4] rounded-btn bg-surface" aria-hidden />
              <div>
                <h2 className="font-semibold">{t.name}</h2>
                <p className="text-sm text-neutral">{t.desc}</p>
              </div>
              <Link href={`/builder?template=${t.id}`}><Button className="w-full">Use This Template</Button></Link>
            </Card>
          ))}
        </div>
      </Container>
    </Section>
  );
}
