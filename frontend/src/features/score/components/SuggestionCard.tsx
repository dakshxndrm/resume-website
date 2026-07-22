"use client";
import { motion } from "framer-motion";
import { Lightbulb } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import type { Suggestion } from "@/types/resume";

export function SuggestionCard({ s, index }: { s: Suggestion; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.25, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
    >
      <Card className="flex items-start gap-4">
        <span className="mt-0.5 rounded-full bg-primary/10 p-2 text-primary"><Lightbulb className="h-4 w-4" aria-hidden /></span>
        <div className="flex-1">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-semibold">{s.title}</h3>
            <Badge tone={s.severity}>{s.severity}</Badge>
          </div>
          <p className="text-sm text-neutral">{s.why}</p>
        </div>
      </Card>
    </motion.div>
  );
}
