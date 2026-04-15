export const dynamic = 'force-dynamic'

import type { Metadata } from "next";
import type { Viewport } from "next";
import { Inter, Instrument_Serif, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Navbar } from "@/components/shared/navbar";
import { AdGenieProvider } from "@/components/shared/adgenie-context";
import { ThemeProvider } from "@/components/shared/theme-provider";
import { AppToaster } from "@/components/shared/toaster";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const instrumentSerif = Instrument_Serif({
  variable: "--font-instrument-serif",
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: "400",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AdGenie",
  description: "Create product ads in sixty seconds.",
  applicationName: "AdGenie",
  keywords: ["marketing video", "small business", "creative automation"],
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/title-favicon.png",
    shortcut: "/title-favicon.png",
    apple: "/title-favicon.png",
  },
  openGraph: {
    title: "AdGenie",
    description: "Create product ads in sixty seconds.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#FAFAF7",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${instrumentSerif.variable} ${jetbrainsMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full bg-[var(--background)] text-[var(--foreground)]">
        <ThemeProvider>
          <AdGenieProvider>
            <div className="flex min-h-screen flex-col">
              <Navbar />
              <main className="flex-1">{children}</main>
            </div>
            <AppToaster />
          </AdGenieProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
