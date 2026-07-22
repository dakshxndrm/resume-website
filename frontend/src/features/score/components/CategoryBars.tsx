"use client";
import { motion } from "framer-motion";
import type { CategoryScore } from "@/types/resume";

function barColor(score: number) {
  if (score < 45) return "bg-error";
  if (score < 70) return "bg-[#F59E0B]";
  return "bg-success";
}

export function CategoryBars({ categories }: { categories: CategoryScore[] }) {
  return (
    <ul className="flex flex-col gap-4">
      {categories.map((c, i) => (
        <li key={c.key}>
          <div className="mb-1 flex items-baseline justify-between text-sm">
            <span className="font-medium">{c.label}</span>
            <span className="tabular-nums text-neutral">{c.score} · {Math.round(c.weight * 100)}% weight</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-neutral/10">
            <motion.div
              className={`h-full rounded-full ${barColor(c.score)}`}
              initial={{ width: 0 }}
              whileInView={{ width: `${c.score}%` }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.06, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
