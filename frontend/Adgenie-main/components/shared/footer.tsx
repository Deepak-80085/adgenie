import { APP_NAME } from "@/lib/mock-data";

export function Footer() {
  return (
    <footer className="border-t border-[var(--border)]">
      <div className="mx-auto w-full max-w-[1200px] px-5 pb-8 pt-12 md:px-8">
        <div className="flex items-center justify-center border-t border-[var(--border)] pt-6 text-sm text-[var(--muted-foreground)]">
          <p>© 2026 {APP_NAME}</p>
        </div>
      </div>
    </footer>
  );
}
