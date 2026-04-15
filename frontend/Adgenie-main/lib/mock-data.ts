export const APP_NAME = "AdGenie";

export type SampleVideo = {
  id: string;
  title: string;
  thumbnailPath: string;
  videoPath: string;
  style: string;
  createdAt: string;
  productName: string;
};

export type VibePreset = {
  id: string;
  name: string;
  description: string;
  icon: string;
  previewPath: string;
};

export type MediaLibraryItem = {
  id: "titon" | "gulli" | "deandrip";
  name: string;
  category: string;
  productCategory: string;
  image: string;
  video: string;
};

export const mediaLibrary: MediaLibraryItem[] = [
  {
    id: "titon",
    name: "Titon",
    category: "Luxury Watch",
    productCategory: "Fashion",
    image: "/media/titon.webp",
    video: "/media/titon.mp4",
  },
  {
    id: "gulli",
    name: "Gulli Labs",
    category: "Premium Sneakers",
    productCategory: "Fashion",
    image: "/media/gulli.png",
    video: "/media/gulli.mp4",
  },
  {
    id: "deandrip",
    name: "DeanDrip",
    category: "Streetwear",
    productCategory: "Fashion",
    image: "/media/dean.webp",
    video: "/media/dean.mp4",
  },
];

export function getMediaVideoById(mediaId?: string | null) {
  if (!mediaId) return null;
  return mediaLibrary.find((item) => item.id === mediaId)?.video ?? null;
}

export const sampleVideos: SampleVideo[] = [
  {
    id: "v1",
    title: "Titon Holiday Campaign",
    thumbnailPath: "/media/titon.webp",
    videoPath: "/media/titon.mp4",
    style: "Luxury",
    createdAt: "2026-04-10",
    productName: "Titon",
  },
  {
    id: "v2",
    title: "Gulli Labs Launch Ad",
    thumbnailPath: "/media/gulli.png",
    videoPath: "/media/gulli.mp4",
    style: "Energetic",
    createdAt: "2026-04-11",
    productName: "Gulli Labs",
  },
  {
    id: "v3",
    title: "DeanDrip Product Feature",
    thumbnailPath: "/media/dean.webp",
    videoPath: "/media/dean.mp4",
    style: "Cinematic",
    createdAt: "2026-04-12",
    productName: "DeanDrip",
  },
];

export const vibePresets: VibePreset[] = [
  {
    id: "energetic",
    name: "Energetic",
    description: "Fast cuts, bold typography, and punchy transitions.",
    icon: "Zap",
    previewPath: "/media/gulli.png",
  },
  {
    id: "luxury",
    name: "Luxury",
    description: "Premium tones, soft camera moves, polished pacing.",
    icon: "Gem",
    previewPath: "/media/titon.webp",
  },
  {
    id: "playful",
    name: "Playful",
    description: "Bright visuals and upbeat storytelling for social.",
    icon: "Sparkles",
    previewPath: "/media/gulli.png",
  },
  {
    id: "minimalist",
    name: "Minimalist",
    description: "Clean composition, calm rhythm, modern aesthetic.",
    icon: "Shapes",
    previewPath: "/media/titon.webp",
  },
  {
    id: "cinematic",
    name: "Cinematic",
    description: "Dramatic reveals with immersive scene progression.",
    icon: "Film",
    previewPath: "/media/titon.webp",
  },
];

export const musicOptions = [
  "No music",
  "Energetic Beat",
  "Luxury Ambient",
  "Playful Pop",
  "Cinematic Rise",
];

export const productCategories = [
  "Fashion",
  "Electronics",
  "Beauty",
  "Food",
  "Home",
  "Other",
];

export const mockUser = {
  name: "Sabari K",
  avatarFallback: "SK",
};
