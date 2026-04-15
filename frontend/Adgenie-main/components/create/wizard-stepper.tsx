type WizardStepperProps = {
  steps: string[];
  currentStep: number;
};

export function WizardStepper({ steps, currentStep }: WizardStepperProps) {
  return (
    <div className="overflow-x-auto border-y border-[var(--border)] py-3">
      <div className="flex min-w-max items-center gap-4">
        {steps.map((step, index) => {
          const stepNumber = index + 1;
          const isActive = currentStep === stepNumber;

          return (
            <p
              key={step}
              data-meta
              className={`border-b pb-1 text-[11px] ${isActive ? "border-[var(--foreground)] text-[var(--foreground)]" : "border-transparent text-[var(--muted-foreground)]"}`}
            >
              {String(stepNumber).padStart(2, "0")} — {step.toUpperCase()}
            </p>
          );
        })}
      </div>
    </div>
  );
}
