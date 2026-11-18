import { toast } from "sonner";
import { track } from "@/lib/api";
import type { Community, ID } from "@/lib/api/types";

/** Dorm invites pre-select the dorm on signup; group links open the group page. */
export function inviteUrl(c: Pick<Community, "kind" | "slug"> | null, meId: ID): string {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  if (c && c.kind === "group") return `${origin}/communities/${c.slug}`;
  const q = new URLSearchParams({ ref: String(meId) });
  if (c?.kind === "dorm") q.set("dorm", c.slug);
  return `${origin}/signup?${q}`;
}

export async function copyInvite(url: string, where: string) {
  track("invite_copied", { where });
  try {
    if (navigator.share) { await navigator.share({ title: "Join me on DAHA", url }); return; }
    await navigator.clipboard.writeText(url);
    toast.success("Invite link copied!");
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") return;
    toast.message(url, { description: "Copy this link to invite people" });
  }
}
