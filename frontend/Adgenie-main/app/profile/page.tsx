import { Footer } from "@/components/shared/footer";
import { PageTransition } from "@/components/shared/page-transition";
import { mockUser } from "@/lib/mock-data";

export default function ProfilePage() {
  return (
    <PageTransition>
      <div className="mx-auto w-full max-w-[1200px] px-5 py-16 md:px-8">
        <p data-meta>Profile</p>
        <h1 className="mt-2 text-[44px] tracking-tight">{mockUser.name}</h1>
        <p className="mt-4 text-[var(--muted-foreground)]">Personal workspace settings.</p>
      </div>
      <Footer />
    </PageTransition>
  );
}
