"use client";
import Link from "next/link";
import { site } from "@/config/site";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/Button";

export function Nav() {
  const { user, login, logout, loading } = useAuth();
  return (
    <header className="sticky top-0 z-40 border-b border-neutral/10 bg-white/80 backdrop-blur">
      <nav className="mx-auto flex h-16 w-full max-w-container items-center justify-between px-6" aria-label="Main">
        <Link href="/" className="focus-ring text-lg font-bold tracking-tight">
          Resume<span className="text-primary">AI</span>
        </Link>
        <div className="hidden items-center gap-8 md:flex">
          {site.nav.map((item) => (
            <Link key={item.href} href={item.href} className="focus-ring text-sm font-medium text-neutral transition-colors hover:text-secondary">
              {item.label}
            </Link>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {!loading && user ? (
            <>
              <Link href="/dashboard" className="focus-ring">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={user.photoURL ?? ""} alt={user.displayName ?? "Profile"} className="h-8 w-8 rounded-full border border-neutral/20" referrerPolicy="no-referrer" />
              </Link>
              <Button variant="ghost" onClick={logout} className="px-3 py-1.5 text-xs">Sign out</Button>
            </>
          ) : (
            <Button variant="ghost" onClick={login} className="px-4 py-2 text-xs">Sign in with Google</Button>
          )}
        </div>
      </nav>
    </header>
  );
}
