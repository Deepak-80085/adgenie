"use client";

import { useRef, useState } from "react";
import { Download, Pause, Play, Volume2, VolumeX } from "lucide-react";

import { Button } from "@/components/ui/button";

type VideoPlayerProps = {
  src: string;
  title: string;
};

export function VideoPlayer({ src, title }: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      void videoRef.current.play();
      setIsPlaying(true);
      return;
    }
    videoRef.current.pause();
    setIsPlaying(false);
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(videoRef.current.muted);
  };

  return (
    <div className="overflow-hidden rounded-[4px] border border-[var(--border)] bg-[var(--card)]">
      <div className="relative aspect-video w-full bg-black">
        <video
          ref={videoRef}
          src={src}
          className="h-full w-full object-contain"
          controls={false}
          playsInline
          onEnded={() => setIsPlaying(false)}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] p-3">
        <div className="flex gap-2">
          <Button type="button" variant="ghost" onClick={togglePlay}>
            {isPlaying ? <Pause size={16} className="mr-2" /> : <Play size={16} className="mr-2" />}
            {isPlaying ? "Pause" : "Play"}
          </Button>
          <Button type="button" variant="ghost" onClick={toggleMute}>
            {isMuted ? <VolumeX size={16} className="mr-2" /> : <Volume2 size={16} className="mr-2" />}
            {isMuted ? "Unmute" : "Mute"}
          </Button>
        </div>
        <Button type="button" variant="default" asChild>
          <a href={src} download={`${title}.mp4`}>
            <Download size={16} className="mr-2" />
            Download
          </a>
        </Button>
      </div>
    </div>
  );
}
