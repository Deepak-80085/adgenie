import Link from "next/link";
import { ArrowRight, FileText, Sparkles, Upload } from "lucide-react";

import { Footer } from "@/components/shared/footer";
import { PageTransition } from "@/components/shared/page-transition";
import { VideoCard } from "@/components/shared/video-card";
import { Button } from "@/components/ui/button";
import { sampleVideos } from "@/lib/mock-data";

export default function Home() {
  return (
    <PageTransition>
      <div className="flex flex-col">
        <section className="mx-auto w-full max-w-[1200px] px-5 pb-14 pt-14 sm:px-6 sm:pb-16 sm:pt-16 md:px-8 md:pb-24 md:pt-24">
          <div className="grid gap-8 md:gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-start xl:gap-12">
            <div className="space-y-6 sm:space-y-8">
              <p data-meta>Creative studio workflow</p>
              <h1 className="max-w-[780px] text-[42px] leading-[0.98] tracking-tight sm:text-[50px] md:text-[62px] lg:text-[74px] xl:text-[82px]">
                Turn your product into a <em className="italic">scroll-stopping</em> ad in sixty seconds.
              </h1>
              <p className="max-w-[520px] text-[17px] text-[var(--muted-foreground)] sm:text-[18px]">
                Pick a product from your media library, choose a direction, and publish a clean campaign cut.
              </p>
              <div className="flex flex-wrap items-center gap-3 sm:gap-5">
                <Button asChild size="lg">
                  <Link href="/create">Start creating</Link>
                </Button>
                <Link href="/dashboard" className="text-sm hover:underline">
                  See examples <ArrowRight size={14} className="ml-1 inline" />
                </Link>
              </div>
            </div>

            <div className="mx-auto w-full max-w-[520px] border border-[var(--border)] bg-[var(--card)] p-3 sm:p-4 lg:mx-0 lg:max-w-none" style={{ boxShadow: "var(--surface-shadow)" }}>
              <video
                src="/media/landing-page-vertical.mp4"
                className="aspect-[4/5] w-full rounded-[4px] object-cover max-md:landscape:aspect-[16/10]"
                autoPlay
                muted
                loop
                playsInline
              />
            </div>
          </div>
        </section>

        <section className="mx-auto w-full max-w-[1200px] space-y-8 border-t border-[var(--border)] px-5 py-20 sm:px-6 sm:py-20 md:px-8 md:py-24">
          <h2 className="text-[32px] sm:text-[36px]">How it works</h2>
          <div className="grid gap-4 sm:gap-6 md:grid-cols-2 lg:grid-cols-3 lg:gap-8">
            {[
              {
                n: "01",
                title: "Upload your image",
                body: "Drag, drop, or choose your product image.",
                icon: <Upload size={16} />,
              },
              {
                n: "02",
                title: "Add a quick description",
                body: "Describe your product and target audience.",
                icon: <FileText size={16} />,
              },
              {
                n: "03",
                title: "Get your ad instantly",
                body: "Generate ready-to-use ad copy and visuals.",
                icon: <Sparkles size={16} />,
              },
            ].map((item, index) => (
              <div
                key={item.n}
                className="relative space-y-4 border border-[var(--border)] bg-[var(--card)] p-6 shadow-[0_2px_12px_rgba(10,10,10,0.04)] sm:p-7"
              >
                <p data-meta>{item.n}</p>
                <h3 className="text-[50px] italic leading-[1.02] sm:text-[56px]">{item.title}</h3>
                <p className="max-w-[34ch] text-[16px] text-[var(--muted-foreground)]">{item.body}</p>
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--secondary)] text-[var(--foreground)]">
                  {item.icon}
                </span>
                {index < 2 && <span className="absolute -right-4 top-8 hidden h-[calc(100%-4rem)] w-px bg-[var(--border)] lg:block" />}
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-[1200px] space-y-8 border-t border-[var(--border)] px-5 py-24 md:px-8">
          <div className="space-y-2">
            <p data-meta>Gallery</p>
            <h2 className="text-[32px]">See what AdGenie can do</h2>
          </div>
          <div className="grid gap-8 md:grid-cols-2">
            {sampleVideos.slice(0, 2).map((video) => (
              <div key={video.id}>
                <VideoCard video={video} />
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto w-full max-w-[1200px] border-t border-[var(--border)] px-5 py-20 md:px-8 md:py-24">
          <div className="grid gap-8 md:grid-cols-2">
            <div className="space-y-4 md:pr-6">
              <p data-meta>STANDARD</p>
              <p className="font-[var(--font-instrument-serif)] text-[40px] sm:text-[48px]">One streamlined workflow</p>
              <p className="text-[var(--muted-foreground)]">Create product ads with one consistent generation format.</p>
            </div>
            <div className="space-y-4 border-t border-[var(--border)] pt-6 md:border-l md:border-t-0 md:pl-6 md:pt-0">
              <p data-meta>OUTPUT</p>
              <p className="font-[var(--font-instrument-serif)] text-[40px] sm:text-[48px]">Built for social campaigns</p>
              <p className="text-[var(--muted-foreground)]">Generate and export polished edits from your media library.</p>
            </div>
          </div>
        </section>

        <Footer />
      </div>
    </PageTransition>
  );
}
