"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function AppError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <span className="text-4xl" aria-hidden>😵‍💫</span>
      <h1 className="mt-3 text-[22px] font-semibold">Something went wrong</h1>
      <p className="mt-1 text-muted-foreground">It&apos;s us, not you. Try again, or head home.</p>
      <div className="mt-6 flex w-full max-w-xs flex-col gap-2">
        <button type="button" onClick={reset} className="h-12 rounded-full bg-primary font-semibold text-primary-foreground">Try again</button>
        <Link href="/home" className="flex h-12 items-center justify-center rounded-full font-semibold ring-1 ring-border">Go home</Link>
      </div>
    </div>
  );
}
