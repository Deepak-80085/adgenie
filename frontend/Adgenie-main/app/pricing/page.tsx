import { Footer } from "@/components/shared/footer";
import { PageTransition } from "@/components/shared/page-transition";
import { Button } from "@/components/ui/button";

const plans = [
  { name: "Starter", subtitle: "For first campaigns", price: "$19/mo" },
  { name: "Growth", subtitle: "For weekly publishing", price: "$79/mo", highlighted: true },
  { name: "Pro", subtitle: "For high-volume teams", price: "$249/mo" },
];

export default function PricingPage() {
  return (
    <PageTransition>
      <div className="mx-auto w-full max-w-[1200px] space-y-16 px-5 py-12 md:px-8">
        <div className="max-w-3xl space-y-4">
          <p data-meta>Pricing</p>
          <h1 className="text-[36px] tracking-tight sm:text-[48px]">Pick the plan that matches your pace</h1>
          <p className="text-[var(--muted-foreground)]">
            One consistent ad format, with flexible plans for different publishing needs.
          </p>
        </div>

        <div className="grid gap-8 border-t border-[var(--border)] pt-10 md:grid-cols-3">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className="space-y-4 border-t border-[var(--border)] pt-6 first:border-t-0 first:pt-0 md:border-l md:border-t-0 md:pl-6 md:pt-0 md:first:border-l-0 md:first:pl-0"
            >
              <p data-meta>{plan.name}</p>
              <p className="font-[var(--font-instrument-serif)] text-[48px]">{plan.price}</p>
              <p className="text-sm text-[var(--muted-foreground)]">{plan.subtitle}</p>
              <Button variant={plan.highlighted ? "default" : "secondary"} size="sm">Choose plan</Button>
            </div>
          ))}
        </div>

        <div className="space-y-5 border-t border-[var(--border)] pt-10 text-sm">
          <p data-meta>FAQ</p>
          <div>
            <p className="font-medium">What ad format is included?</p>
            <p className="text-[var(--muted-foreground)]">All plans use one standard ad generation format.</p>
          </div>
          <div>
            <p className="font-medium">Can I regenerate a video?</p>
            <p className="text-[var(--muted-foreground)]">Yes. You can regenerate and refine your output anytime.</p>
          </div>
          <div>
            <p className="font-medium">Can I upgrade later?</p>
            <p className="text-[var(--muted-foreground)]">Yes. You can move to a higher plan when your volume increases.</p>
          </div>
        </div>
      </div>
      <Footer />
    </PageTransition>
  );
}
