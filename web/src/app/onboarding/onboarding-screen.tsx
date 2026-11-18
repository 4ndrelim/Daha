"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, track } from "@/lib/api";
import { meKey, useMe } from "@/lib/queries/me";
import { firstName } from "@/lib/format";
import { HavesChecklist } from "@/components/scan/haves-checklist";
import { ScanFlow } from "@/components/scan/scan-flow";

/** First run (C4): the scan flow under a hero, plus "Tick what you have" (C5), plus "Skip for now". */
export function OnboardingScreen() {
  const router = useRouter();
  const qc = useQueryClient();
  const { data: me } = useMe();
  const [savedHaves, setSavedHaves] = useState(0);

  const finish = useMutation({
    mutationFn: () => api.me.update({ onboarded: true }),
    onSuccess: (updated) => qc.setQueryData(meKey, updated),
    // Never trap someone on onboarding: go home even if the PATCH fails.
    onSettled: () => router.replace("/home"),
  });

  function leave() {
    if (finish.isPending) return;
    if (savedHaves === 0) track("onboarding_skipped", { step: "scan" });
    finish.mutate();
  }

  return (
    <main className="mx-auto min-h-dvh w-full max-w-md px-4 pt-[calc(0.75rem+env(safe-area-inset-top))] pb-[calc(1.5rem+env(safe-area-inset-bottom))]">
      <div className="flex h-12 items-center justify-between">
        <p className="text-[22px] font-extrabold tracking-tight text-primary">daha</p>
        <button type="button" onClick={leave} disabled={finish.isPending}
          className="-mr-2 h-11 rounded-full px-3 text-[15px] font-semibold text-muted-foreground active:bg-muted disabled:opacity-60">
          {savedHaves > 0 ? "Done" : "Skip for now"}
        </button>
      </div>
      <div className="mt-3">
        <ScanFlow
          mode="onboarding"
          intro={
            <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-700 p-5 text-white shadow-lg shadow-emerald-600/20">
              <span aria-hidden className="absolute -top-6 -right-4 text-[96px] opacity-20 select-none">📸</span>
              <p className="text-[13px] font-semibold tracking-wide text-emerald-100 uppercase">
                {me ? `Welcome, ${firstName(me.name)}` : "Welcome"}
              </p>
              <h1 className="mt-1 text-[22px] leading-7 font-semibold">Show us what you have</h1>
              <p className="mt-1 max-w-[18rem] text-emerald-50">Snap your desk, shelf or closet. We&apos;ll list what we see — you choose what to share.</p>
            </div>
          }
          besideCapture={
            <>
              <div className="flex items-center gap-3 text-[13px] text-muted-foreground" aria-hidden>
                <span className="h-px flex-1 bg-border" /> or <span className="h-px flex-1 bg-border" />
              </div>
              <HavesChecklist onSaved={(n) => setSavedHaves((s) => s + n)} />
              <button type="button" onClick={leave} disabled={finish.isPending}
                className="h-11 w-full rounded-full text-[15px] font-semibold text-muted-foreground active:bg-muted">
                {savedHaves > 0 ? "Done — take me home" : "Skip for now"}
              </button>
            </>
          }
        />
      </div>
    </main>
  );
}
