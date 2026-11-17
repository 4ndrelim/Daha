import { Suspense } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { AuthGate } from "@/components/layout/auth-gate";

function ShellSkeleton() {
  return <div className="min-h-dvh bg-background" />;
}

export default function AppLayout({ children }: LayoutProps<"/">) {
  return (
    <Suspense fallback={<ShellSkeleton />}>
      <AuthGate>
        <AppShell>{children}</AppShell>
      </AuthGate>
    </Suspense>
  );
}
