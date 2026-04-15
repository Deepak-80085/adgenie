"use client";

import { motion } from "framer-motion";

type GeneratingLoaderProps = {
  currentIndex: number;
  steps: string[];
};

export function GeneratingLoader({ currentIndex, steps }: GeneratingLoaderProps) {
  const progress = Math.min(((currentIndex + 1) / steps.length) * 100, 100);
  const currentLabel = steps[currentIndex] ?? steps[0];

  return (
    <div className="grid min-h-[420px] place-items-center border border-[var(--border)] bg-[var(--card)] p-6">
      <div className="space-y-8 text-center">
        <motion.h3
          key={currentLabel}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="font-[var(--font-instrument-serif)] text-4xl italic tracking-tight"
        >
          {currentLabel}
        </motion.h3>

        <div className="mx-auto h-px w-[200px] overflow-hidden bg-[var(--border)]">
        <motion.div
          className="h-full bg-[var(--foreground)]"
          initial={{ width: 0 }}
          animate={{ width: `${progress}%` }}
          transition={{ duration: 0.4, ease: "easeOut" }}
        />
        </div>

        <p data-meta className="text-[11px]">
          STEP {String(currentIndex + 1).padStart(2, "0")} / {String(steps.length).padStart(2, "0")}
        </p>
      </div>
    </div>
  );
}
