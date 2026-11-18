"use client";

import { useState } from "react";
import { ImageIcon } from "lucide-react";
import type { Category } from "@/lib/api/types";
import { categoryInfo } from "@/lib/categories";
import { cn } from "@/lib/utils";

/** A scan photo: the image, or a neutral tile while it loads / when the browser can't show it (HEIC). */
export function PhotoTile({ url, className, children }: { url: string | null; className?: string; children?: React.ReactNode }) {
  const [broken, setBroken] = useState<string | null>(null);
  const show = url && broken !== url;
  return (
    <div className={cn("relative flex aspect-square items-center justify-center overflow-hidden bg-muted", className)}>
      <ImageIcon className="size-6 text-muted-foreground/60" aria-hidden />
      {show && (
        // eslint-disable-next-line @next/next/no-img-element -- local object URLs / backend photos; no optimizer
        <img src={url} alt="" loading="lazy" decoding="async" onError={() => setBroken(url)} className="absolute inset-0 size-full object-cover" />
      )}
      {children}
    </div>
  );
}

/**
 * The detected thing, cropped out of its photo with the (approximate) bbox; falls back to the category emoji tile.
 * Pure CSS crop: no canvas, no extra download.
 */
export function DetectionThumb({ url, width, height, bbox, category, className }: {
  url: string | null; width: number | null; height: number | null;
  bbox: [number, number, number, number] | null; category: Category; className?: string;
}) {
  const [broken, setBroken] = useState<string | null>(null);
  const c = categoryInfo(category);
  let style: React.CSSProperties | null = null;
  if (url && broken !== url && width && height && bbox) {
    const [x, y, w, h] = bbox;
    const rw = Math.max(0.02, w) * width;
    const rh = Math.max(0.02, h) * height;
    const side = Math.min(Math.max(rw, rh) * 1.15, Math.max(width, height));
    const left = (x * width + rw / 2) - side / 2;
    const top = (y * height + rh / 2) - side / 2;
    style = {
      width: `${(width / side) * 100}%`, height: `${(height / side) * 100}%`,
      left: `${(-left / side) * 100}%`, top: `${(-top / side) * 100}%`, maxWidth: "none",
    };
  }
  return (
    <div className={cn("relative flex aspect-square shrink-0 items-center justify-center overflow-hidden", c.tint, className)}>
      <span className="text-2xl select-none" aria-hidden>{c.emoji}</span>
      {style && url && (
        // eslint-disable-next-line @next/next/no-img-element -- CSS crop of the scan photo
        <img src={url} alt="" loading="lazy" decoding="async" onError={() => setBroken(url)} style={style} className="absolute" />
      )}
    </div>
  );
}
