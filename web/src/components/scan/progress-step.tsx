"use client";

import { AlertCircle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { PhotoTile } from "./thumbs";

export interface ProgressPhoto {
  key: string;
  url: string | null;
  state: "uploading" | "scanning" | "done" | "failed";
  found: number;
  error: string | null;
}

const LABEL: Record<ProgressPhoto["state"], string> = {
  uploading: "Uploading…",
  scanning: "Looking for things…",
  done: "",
  failed: "",
};

export function ProgressStep({ photos, title }: { photos: ProgressPhoto[]; title: string }) {
  const finished = photos.filter((p) => p.state === "done" || p.state === "failed").length;
  const pct = photos.length ? Math.max(8, Math.round((finished / photos.length) * 100)) : 8;
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[22px] leading-7 font-semibold">{title}</h2>
        <p className="mt-1 text-muted-foreground">Usually a few seconds per photo. You can start reviewing as soon as one is ready.</p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={photos.length} aria-valuenow={finished}>
          <div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <ul className="space-y-2" aria-live="polite">
        {photos.map((p, i) => {
          const working = p.state === "uploading" || p.state === "scanning";
          return (
            <li key={p.key} className="flex items-center gap-3 rounded-2xl bg-card p-2.5 shadow-sm ring-1 ring-border/60">
              <PhotoTile url={p.url} className="size-16 shrink-0 rounded-xl">
                {working && <span className="absolute inset-0 animate-pulse bg-gradient-to-r from-transparent via-white/50 to-transparent" aria-hidden />}
              </PhotoTile>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] text-muted-foreground">Photo {i + 1}</p>
                {working && (
                  <>
                    <p className="font-medium">{LABEL[p.state]}</p>
                    <div className="mt-1.5 h-2 w-3/4 animate-pulse rounded-full bg-muted" aria-hidden />
                  </>
                )}
                {p.state === "done" && (
                  <p className={cn("flex items-center gap-1.5 font-semibold", p.found > 0 ? "text-primary" : "text-muted-foreground")}>
                    <CheckCircle2 className="size-4" aria-hidden />
                    {p.found > 0 ? `Found ${p.found} ${p.found === 1 ? "item" : "items"}` : "Nothing to list here"}
                  </p>
                )}
                {p.state === "failed" && (
                  <p className="flex items-start gap-1.5 text-[14px] font-medium text-rose-700">
                    <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                    {p.error ?? "Couldn't read this photo"}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
