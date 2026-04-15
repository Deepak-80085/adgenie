"use client";

import { ImagePlus, UploadCloud } from "lucide-react";
import { useRef } from "react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type UploadZoneProps = {
  previewUrl: string | null;
  onFileChange: (file: File | null) => void;
};

export function UploadZone({ previewUrl, onFileChange }: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return;
    onFileChange(file);
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={(event) => event.preventDefault()}
      className={cn(
        "border border-dashed border-[var(--border)] bg-[var(--surface)] p-6",
        "transition-colors hover:border-[var(--foreground)]"
      )}
    >
      <input
        ref={inputRef}
        className="hidden"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
      />

      {previewUrl ? (
        <div className="space-y-3">
          <div className="relative h-56 w-full overflow-hidden border border-[var(--border)] md:h-72">
            <Image
              src={previewUrl}
              alt="Uploaded product preview"
              fill
              className="object-cover"
              unoptimized
            />
          </div>
          <Button variant="secondary" onClick={() => inputRef.current?.click()}>
            <ImagePlus size={16} className="mr-2" />
            Replace Image
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="grid w-full place-items-center gap-3 py-12 text-center"
        >
          <div className="grid h-12 w-12 place-items-center border border-[var(--border)] bg-[var(--secondary)]">
            <UploadCloud size={20} />
          </div>
          <div>
            <p className="font-medium">Drag and drop your product image</p>
            <p className="text-sm text-[var(--muted-foreground)]">JPG, PNG, or WEBP supported</p>
          </div>
        </button>
      )}
    </div>
  );
}
