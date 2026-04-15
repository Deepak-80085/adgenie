"use client";

import { createContext, useContext, useState } from "react";

import {
  getMediaVideoById,
  sampleVideos,
  type SampleVideo,
} from "@/lib/mock-data";

type CreateVideoInput = {
  productName: string;
  style: string;
  mediaId?: string | null;
  thumbnailPath?: string | null;
};

type AdGenieContextType = {
  videos: SampleVideo[];
  createVideoFromMock: (input: CreateVideoInput) => SampleVideo;
  deleteVideo: (id: string) => void;
  getVideoById: (id: string) => SampleVideo | undefined;
};

const AdGenieContext = createContext<AdGenieContextType | null>(null);

export function AdGenieProvider({ children }: { children: React.ReactNode }) {
  const [videos, setVideos] = useState<SampleVideo[]>(sampleVideos);

  const getDeterministicBaseVideo = (seed: string) => {
    const normalized = seed.trim().toLowerCase();
    const hash = Array.from(normalized).reduce((acc, char) => acc + char.charCodeAt(0), 0);
    return sampleVideos[hash % sampleVideos.length];
  };

  const createVideoFromMock = (input: CreateVideoInput) => {
    const preferredVideoPath = getMediaVideoById(input.mediaId);
    const matchedVideo = preferredVideoPath
      ? sampleVideos.find((video) => video.videoPath === preferredVideoPath)
      : undefined;

    const base = matchedVideo ?? getDeterministicBaseVideo(`${input.productName}-${input.style}`);
    const now = new Date();
    const newVideo: SampleVideo = {
      ...base,
      id: String(now.getTime()),
      title: `${input.productName} - ${input.style}`,
      createdAt: now.toISOString().slice(0, 10),
      style: input.style,
      productName: input.productName,
      thumbnailPath: input.thumbnailPath ?? base.thumbnailPath,
    };

    setVideos((prev) => [newVideo, ...prev]);
    return newVideo;
  };

  const deleteVideo = (id: string) => {
    setVideos((prev) => prev.filter((video) => video.id !== id));
  };

  const getVideoById = (id: string) => videos.find((video) => video.id === id);

  const value = { videos, createVideoFromMock, deleteVideo, getVideoById };

  return <AdGenieContext.Provider value={value}>{children}</AdGenieContext.Provider>;
}

export function useAdGenie() {
  const context = useContext(AdGenieContext);
  if (!context) {
    throw new Error("useAdGenie must be used within AdGenieProvider");
  }
  return context;
}
