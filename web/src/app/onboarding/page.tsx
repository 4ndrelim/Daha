import { Suspense } from "react";
import { AuthGate } from "@/components/layout/auth-gate";
import { OnboardingScreen } from "./onboarding-screen";

export default function OnboardingPage() {
  return (
    <Suspense fallback={<div className="min-h-dvh bg-background" />}>
      <AuthGate>
        <OnboardingScreen />
      </AuthGate>
    </Suspense>
  );
}
