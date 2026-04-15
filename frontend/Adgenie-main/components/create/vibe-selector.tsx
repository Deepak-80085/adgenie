"use client";

import type { VibePreset } from "@/lib/mock-data";

type VibeSelectorProps = {
  vibes: VibePreset[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function VibeSelector({ vibes, selectedId, onSelect }: VibeSelectorProps) {
  const selected = vibes.find((vibe) => vibe.id === selectedId);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-6 border-b border-[var(--border)] pb-3">
        {vibes.map((vibe) => {
          const isSelected = vibe.id === selectedId;
          return (
            <button
              key={vibe.id}
              type="button"
              onClick={() => onSelect(vibe.id)}
              className={`border-b pb-1 font-[var(--font-instrument-serif)] text-2xl italic transition duration-200 ease-out ${
                isSelected
                  ? "border-[var(--foreground)] text-[var(--foreground)]"
                  : "border-transparent text-[var(--muted-foreground)] hover:border-[var(--foreground)] hover:text-[var(--foreground)]"
              }`}
            >
              {vibe.name}
            </button>
          );
        })}
      </div>
      <p data-meta className="text-[11px] transition duration-200 ease-out">
        {selected?.description}
      </p>
    </div>
  );
}
