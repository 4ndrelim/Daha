"use client";

import { useEffect, useState } from "react";
import { Download, Share, SquarePlus, X } from "lucide-react";
import { track } from "@/lib/api";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISS_KEY = "daha_install_dismissed";

function isStandalone(): boolean {
  return window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
}

/**
 * "Install DAHA": a real Install button where the browser supports it (Android/desktop Chrome),
 * a 2-step hint on iPhone/iPad, and nothing once installed. Renders browser-only (inside AuthGate).
 */
export function InstallCard() {
  const [prompt, setPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [hidden, setHidden] = useState(() => isStandalone() || localStorage.getItem(DISMISS_KEY) === "1");
  const ios = /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  useEffect(() => {
    const onPrompt = (e: Event) => { e.preventDefault(); setPrompt(e as BeforeInstallPromptEvent); };
    const onInstalled = () => { setHidden(true); track("app_installed", {}); };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  if (hidden || (!prompt && !ios)) return null;

  const dismiss = () => { localStorage.setItem(DISMISS_KEY, "1"); setHidden(true); };

  return (
    <section className="relative rounded-2xl bg-card p-4 pr-12 shadow-sm ring-1 ring-border/60">
      <button type="button" onClick={dismiss} aria-label="Hide" className="absolute top-1.5 right-1.5 flex size-11 items-center justify-center rounded-full text-muted-foreground active:bg-muted">
        <X className="size-4" />
      </button>
      <div className="flex items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- tiny static icon */}
        <img src="/icons/icon-192.png" alt="" className="size-12 rounded-xl" />
        <div>
          <p className="font-semibold">Put DAHA on your home screen</p>
          <p className="text-[13px] text-muted-foreground">Opens full-screen, like an app. No app store.</p>
        </div>
      </div>
      {prompt ? (
        <button
          type="button"
          onClick={async () => {
            track("install_prompt_shown", {});
            await prompt.prompt();
            const { outcome } = await prompt.userChoice;
            if (outcome === "accepted") setHidden(true);
            setPrompt(null);
          }}
          className="mt-3 flex h-11 w-full items-center justify-center gap-2 rounded-full bg-primary font-semibold text-primary-foreground"
        >
          <Download className="size-4" /> Install DAHA
        </button>
      ) : (
        <ol className="mt-3 space-y-1.5 text-[14px]">
          <li className="flex items-center gap-2">1. Tap <Share className="size-4 text-sky-600" aria-label="Share" /> <span className="font-medium">Share</span> in Safari&apos;s toolbar</li>
          <li className="flex items-center gap-2">2. Choose <SquarePlus className="size-4" aria-hidden /> <span className="font-medium">Add to Home Screen</span></li>
        </ol>
      )}
    </section>
  );
}
