"use client";

import Link from "next/link";
import Image from "next/image";
import { useMemo, useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import type { SampleVideo } from "@/lib/mock-data";

type VideoCardProps = {
  video: SampleVideo;
  href?: string;
};

export function VideoCard({ video, href = `/video/${video.id}` }: VideoCardProps) {
  const [hovered, setHovered] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const formattedDate = useMemo(
    () => new Date(video.createdAt).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
    [video.createdAt]
  );
  const meta = `${video.style.toUpperCase()} · ${formattedDate.toUpperCase()}`;

  return (
    <Link href={href} onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
      <Card className="group overflow-hidden transition duration-200 ease-out hover:-translate-y-0.5 hover:border-[var(--foreground)]">
        <div className="relative aspect-video w-full overflow-hidden bg-[var(--secondary)]">
          {hovered ? (
            <video
              src={video.videoPath}
              className="h-full w-full object-cover"
              autoPlay
              muted
              loop
              playsInline
            />
          ) : (
            <Image
              src={video.thumbnailPath}
              alt={video.title}
              fill
              onLoad={() => setImageLoaded(true)}
              className={`object-cover transition duration-200 ease-out ${imageLoaded ? "opacity-100" : "opacity-0"}`}
            />
          )}
          <div className="pointer-events-none absolute inset-0 grid place-items-center opacity-0 transition duration-200 ease-out group-hover:opacity-100">
            <span className="rounded-[999px] border border-white px-3 py-1 text-[11px] uppercase tracking-[0.08em] text-white">
              Play
            </span>
          </div>
        </div>
        <CardContent className="space-y-3 p-4">
          <p className="line-clamp-1 font-[var(--font-instrument-serif)] text-[20px] leading-tight">{video.title}</p>
          <p data-meta className="text-[11px]">{meta}</p>
        </CardContent>
      </Card>
    </Link>
  );
}
