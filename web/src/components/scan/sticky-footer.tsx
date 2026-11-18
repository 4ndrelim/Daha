"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * How much of the layout viewport the on-screen keyboard covers (0 when closed).
 * iOS Safari and Android Chrome shrink only the *visual* viewport when the keyboard opens,
 * so a plain `position: fixed; bottom: 0` bar would end up hidden behind it.
 */
function subscribe(cb: () => void) {
  const vv = typeof window !== "undefined" ? window.visualViewport : null;
  if (!vv) return () => {};
  vv.addEventListener("resize", cb);
  vv.addEventListener("scroll", cb);
  return () => {
    vv.removeEventListener("resize", cb);
    vv.removeEventListener("scroll", cb);
  };
}

function keyboardInset(): number {
  const vv = window.visualViewport;
  if (!vv) return 0;
  const covered = Math.round(window.innerHeight - vv.height - vv.offsetTop);
  return covered > 80 ? covered : 0; // ignore toolbar wobble; a keyboard is always taller
}

export function useKeyboardInset(): number {
  return useSyncExternalStore(subscribe, keyboardInset, () => 0);
}

/**
 * Bottom action bar. `aboveNav` lifts it over the app's bottom nav (h-16 + safe area);
 * while the keyboard is open it sits right on top of the keyboard instead.
 */
export function StickyFooter({ children, aboveNav, className }: { children: ReactNode; aboveNav: boolean; className?: string }) {
  const kb = useKeyboardInset();
  const style = kb > 0
    ? { bottom: kb }
    : { bottom: aboveNav ? "calc(4rem + env(safe-area-inset-bottom))" : 0 };
  return (
    <div
      style={style}
      className={cn(
        "fixed inset-x-0 z-40 border-t border-border/60 bg-background/95 backdrop-blur",
        kb === 0 && !aboveNav && "pb-safe",
        className,
      )}
    >
      <div className="mx-auto max-w-md px-4 py-3">{children}</div>
    </div>
  );
}
