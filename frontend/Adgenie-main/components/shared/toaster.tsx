"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return <Toaster position="top-right" closeButton theme="light" toastOptions={{ className: "!rounded-sm !border !shadow-none" }} />;
}
