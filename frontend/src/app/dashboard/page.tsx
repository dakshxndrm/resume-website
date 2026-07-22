"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Section, Container } from "@/components/ui/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/lib/auth-context";
import { api } from "@/lib/api";
import type { Resume } from "@/types/resume";

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[] | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (user) api.listResumes().then(setResumes).catch(() => setResumes([]));
  }, [user]);

  if (loading || !user)
    return <Section><Container><Skeleton className="h-40 w-full" /></Container></Section>;

  return (
    <Section>
      <Container>
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold">Your resumes</h1>
          <Link href="/builder"><Button>New Resume</Button></Link>
        </div>
        {resumes === null ? (
          <div className="grid gap-6 md:grid-cols-3">
            <Skeleton className="h-40" /><Skeleton className="h-40" /><Skeleton className="h-40" />
          </div>
        ) : resumes.length === 0 ? (
          <Card className="flex flex-col items-center gap-4 py-16 text-center">
            <p className="text-lg font-semibold">No resumes yet</p>
            <p className="max-w-prose text-sm text-neutral">Build your first role-targeted resume — it takes about 5 minutes.</p>
            <Link href="/builder"><Button>Start Building →</Button></Link>
          </Card>
        ) : (
          <div className="grid gap-6 md:grid-cols-3">
            {resumes.map((r) => (
              <Link key={r.id} href={`/editor/${r.id}`} className="focus-ring rounded-card">
                <Card>
                  <h2 className="font-semibold">{r.basics.name || "Untitled"}</h2>
                  <p className="text-sm text-neutral">{r.basics.label || "No target role"}</p>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </Container>
    </Section>
  );
}
