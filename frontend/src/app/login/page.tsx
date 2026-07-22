"use client";
import { useRouter } from "next/navigation";
import { Section, Container } from "@/components/ui/Section";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth-context";
import { useToast } from "@/components/ui/Toast";

export default function LoginPage() {
  const { login, enabled } = useAuth();
  const toast = useToast();
  const router = useRouter();

  const handle = async () => {
    if (!enabled) {
      toast("error", "Firebase not configured yet — add NEXT_PUBLIC_FIREBASE_* to .env.local");
      return;
    }
    try {
      await login();
      toast("success", "Signed in");
      router.push("/dashboard");
    } catch {
      toast("error", "Sign-in failed. Please try again.");
    }
  };

  return (
    <Section>
      <Container className="flex justify-center">
        <Card className="flex w-full max-w-sm flex-col items-center gap-6 py-10 text-center">
          <div>
            <h1 className="text-2xl font-bold">Welcome back</h1>
            <p className="mt-1 text-sm text-neutral">Sign in to save resumes and track your scores over time.</p>
          </div>
          <Button onClick={handle} className="w-full">Continue with Google</Button>
          <p className="max-w-xs text-xs text-neutral">
            We only use Google for identity. Your resume data is stored securely and never shared or sold.
          </p>
        </Card>
      </Container>
    </Section>
  );
}
