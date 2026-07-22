import Link from "next/link";
import { site } from "@/config/site";

export function Footer() {
  return (
    <footer className="border-t border-neutral/10 py-10">
      <div className="mx-auto flex w-full max-w-container flex-col items-center justify-between gap-4 px-6 text-sm text-neutral md:flex-row">
        <p>© {new Date().getFullYear()} {site.name}. Free forever.</p>
        <div className="flex gap-6">
          <Link href="/privacy" className="focus-ring hover:text-secondary">Privacy</Link>
          <Link href="/about" className="focus-ring hover:text-secondary">About</Link>
          <a href="mailto:maheradaksh1@gmail.com" className="focus-ring hover:text-secondary">Contact</a>
        </div>
      </div>
    </footer>
  );
}
