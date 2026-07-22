"use client";
/** Signature moment: animated count-up gauge (blueprint §2.5). role="meter" for a11y. */
import { useEffect, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

function scoreColor(score: number) {
  if (score < 45) return "rgb(239 68 68)";
  if (score < 70) return "rgb(245 158 11)";
  return "rgb(16 185 129)";
}

export function ScoreGauge({ score, size = 200 }: { score: number; size?: number }) {
  const spring = useSpring(0, { stiffness: 60, damping: 20 });
  const dash = useTransform(spring, (v) => `${(v / 100) * 264} 264`);
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    spring.set(score);
    return spring.on("change", (v) => setDisplay(Math.round(v)));
  }, [score, spring]);

  return (
    <div
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`ATS score ${score} out of 100`}
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg viewBox="0 0 100 100" width={size} height={size} className="-rotate-90">
        <circle cx="50" cy="50" r="42" fill="none" stroke="rgb(100 116 139 / 0.15)" strokeWidth="8" />
        <motion.circle
          cx="50" cy="50" r="42" fill="none"
          stroke={scoreColor(score)}
          strokeWidth="8" strokeLinecap="round"
          style={{ strokeDasharray: dash }}
        />
      </svg>
      <div className="absolute text-center">
        <span className="block text-5xl font-bold tabular-nums" style={{ color: scoreColor(score) }}>{display}</span>
        <span className="text-sm text-neutral">/ 100</span>
      </div>
    </div>
  );
}
