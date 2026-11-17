"use client";

import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { endSession } from "@/lib/auth";

export function LogoutButton() {
  const qc = useQueryClient();
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => { endSession(qc); router.replace("/login"); }}
      className="flex h-11 items-center gap-2 rounded-full px-4 font-semibold text-muted-foreground ring-1 ring-border active:bg-muted"
    >
      <LogOut className="size-4" /> Log out
    </button>
  );
}
