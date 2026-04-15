"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { useAdGenie } from "@/components/shared/adgenie-context";
import { EmptyState } from "@/components/shared/empty-state";
import { Footer } from "@/components/shared/footer";
import { PageTransition } from "@/components/shared/page-transition";
import { VideoPlayer } from "@/components/shared/video-player";
import { Button } from "@/components/ui/button";

export default function VideoDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { getVideoById, deleteVideo, createVideoFromMock } = useAdGenie();

  const video = useMemo(() => getVideoById(params.id), [getVideoById, params.id]);

  if (!video) {
    return (
      <PageTransition>
        <div className="mx-auto w-full max-w-7xl px-4 py-10 sm:px-6 sm:py-12">
          <EmptyState
            title="Video not found"
            description="This video might have been deleted from your dashboard."
            cta="Back to Dashboard"
            href="/dashboard"
          />
        </div>
        <Footer />
      </PageTransition>
    );
  }

  return (
    <PageTransition>
      <div className="mx-auto w-full max-w-[1200px] space-y-8 px-4 py-10 sm:px-5 sm:py-12 md:px-8">
        <h1 className="text-[34px] tracking-tight sm:text-[48px]">{video.title}</h1>

        <VideoPlayer src={video.videoPath} title={video.title} />

        <p data-meta>
          {video.productName.toUpperCase()} · {video.style.toUpperCase()} · GENERATED {video.createdAt.toUpperCase()}
        </p>

        <div className="flex flex-wrap items-center gap-6 border-t border-[var(--border)] pt-5 text-sm">
          <a className="cursor-pointer hover:underline" href={video.videoPath} download={`${video.title}.mp4`}>
            Download
          </a>
          <button
            type="button"
            className="hover:underline"
            onClick={() => {
              void navigator.clipboard.writeText(window.location.href);
              toast.success("Link copied.");
            }}
          >
            Share
          </button>
          <button
            type="button"
            className="hover:underline"
            onClick={() => {
              const regenerated = createVideoFromMock({
                productName: video.productName,
                style: video.style,
              });
              toast.success("Done.");
              router.push(`/video/${regenerated.id}`);
            }}
          >
            Generate another
          </button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              deleteVideo(video.id);
              toast.success("Removed.");
              router.push("/dashboard");
            }}
          >
            Delete
          </Button>
        </div>
      </div>
      <Footer />
    </PageTransition>
  );
}
