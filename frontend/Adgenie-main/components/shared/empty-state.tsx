import Link from "next/link";

import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  title: string;
  description: string;
  cta?: string;
  href?: string;
};

export function EmptyState({ title, description, cta, href = "/create" }: EmptyStateProps) {
  return (
    <div className="grid min-h-[260px] place-items-center border border-dashed border-[var(--border)] bg-[var(--surface)] p-8 text-center">
      <div className="max-w-md space-y-3">
        <p data-meta>No entries yet</p>
        <h3 className="text-3xl tracking-tight">{title}</h3>
        <p className="text-[15px] text-[var(--muted-foreground)]">{description}</p>
        {cta && (
          <Button asChild className="mt-2" variant="ghost">
            <Link href={href}>{cta}</Link>
          </Button>
        )}
      </div>
    </div>
  );
}
