"use client";

import Link from "next/link";
import { Camera, Copy, Home, Users } from "lucide-react";
import { toast } from "sonner";
import { track } from "@/lib/api";
import type { Me } from "@/lib/api/types";
import { HavesChecklist } from "./haves-checklist";
import type { PublishSummary } from "./review-step";

const short = (name: string) => name.split(" (")[0] ?? name;

function audience(s: PublishSummary, me: Me | undefined): string {
  if (s.visibility === "dorm") return me?.dorm ? short(me.dorm.name) : "your dorm";
  if (s.visibility === "campus") return "campus";
  if (s.visibility === "groups") return s.groupNames.length ? s.groupNames.join(", ") : "your groups";
  return "nobody yet";
}

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch { /* fall through */ }
  // http://<laptop-ip>:3000 on a phone isn't a secure context, so the Clipboard API is missing there.
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function SuccessStep({ summary, me, onScanMore, homeLabel = "See requests you can help with" }: {
  summary: PublishSummary; me: Me | undefined; onScanMore: () => void; homeLabel?: string;
}) {
  const n = summary.published;
  const shared = n - summary.privateCount;
  const dorm = me?.dorm;

  async function invite() {
    if (!dorm) return;
    const params = new URLSearchParams({ dorm: dorm.slug });
    if (me) params.set("ref", String(me.id));
    const url = `${window.location.origin}/signup?${params}`;
    track("invite_copied", { source: "scan_success", community_id: dorm.id });
    if (await copyText(url)) toast.success("Invite link copied. Send it to your roommates!");
    else toast(url, { description: "Copy this link and send it to your roommates.", duration: 10_000 });
  }

  const headline = shared > 0
    ? `${shared} ${shared === 1 ? "item" : "items"} shared with ${audience(summary, me)}`
    : `${n} ${n === 1 ? "thing" : "things"} saved privately`;

  return (
    <div className="space-y-5">
      <section className="rounded-3xl bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-700 p-5 text-white shadow-lg shadow-emerald-600/20">
        <p className="text-4xl" aria-hidden>🎉</p>
        <h2 className="mt-2 text-[22px] leading-7 font-semibold">{headline}</h2>
        <p className="mt-1 text-emerald-50">
          {summary.points > 0 && <span className="mr-1 inline-flex rounded-full bg-points px-2 py-0.5 text-[13px] font-semibold text-foreground">+{summary.points} points</span>}
          {shared > 0 && summary.privateCount > 0 && `${summary.privateCount} kept private. `}
          {shared > 0 ? "We'll tell you when someone asks." : "Only you see them. We'll ping you quietly if someone nearby needs one."}
        </p>
      </section>

      <div className="space-y-2">
        <Link href="/home" className="flex h-12 items-center justify-center gap-2 rounded-full bg-primary px-5 text-[15px] font-semibold text-primary-foreground active:bg-primary-hover">
          <Home className="size-5" /> {homeLabel}
        </Link>
        {dorm && (
          <button type="button" onClick={invite}
            className="flex h-12 w-full items-center justify-center gap-2 rounded-full bg-card px-5 text-[15px] font-semibold ring-1 ring-border active:bg-muted">
            <Users className="size-5" /> Invite your roommates <Copy className="size-4 text-muted-foreground" aria-hidden />
          </button>
        )}
        <button type="button" onClick={onScanMore}
          className="flex h-12 w-full items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold text-primary active:bg-primary-soft">
          <Camera className="size-5" /> Snap another area
        </button>
      </div>

      <HavesChecklist title="Anything else you have?" />
    </div>
  );
}
