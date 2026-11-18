"use client";

import { useRef, useState, type DragEvent } from "react";
import { AlertCircle, Camera, ImagePlus, Loader2, RotateCw, X } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { PhotoTile } from "./thumbs";
import { MAX_PHOTOS, type Photo } from "./use-photos";

export function CaptureStep({ photos, full, onAdd, onRemove, onRetry }: {
  photos: Photo[];
  full: boolean;
  onAdd: (files: File[]) => { added: number; skipped: number };
  onRemove: (key: string) => void;
  onRetry: (key: string) => void;
}) {
  const cameraRef = useRef<HTMLInputElement>(null);
  const libraryRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function take(list: FileList | null) {
    const files = list ? Array.from(list) : [];
    if (files.length === 0) return;
    const { added, skipped } = onAdd(files);
    if (skipped > 0) {
      toast(added === 0 && full ? `That's ${MAX_PHOTOS} photos already — remove one to add another.`
        : `Added ${added}. ${skipped} skipped (photos only, ${MAX_PHOTOS} max).`);
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDragging(false);
    take(e.dataTransfer.files);
  }

  const bigBtn = "flex h-12 flex-1 items-center justify-center gap-2 rounded-full px-4 text-[15px] font-semibold transition active:scale-[0.99] disabled:opacity-50";

  return (
    <section
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        "rounded-3xl bg-card p-4 shadow-sm ring-1 ring-border/60 transition",
        dragging && "ring-2 ring-primary bg-primary-soft",
      )}
    >
      {/* Two inputs: `capture` opens the camera straight away on phones; the other opens the photo library. */}
      <input ref={cameraRef} type="file" accept="image/*" capture="environment" multiple className="sr-only" tabIndex={-1}
        aria-hidden onChange={(e) => { take(e.currentTarget.files); e.currentTarget.value = ""; }} />
      <input ref={libraryRef} type="file" accept="image/*,.heic,.heif" multiple className="sr-only" tabIndex={-1}
        aria-hidden onChange={(e) => { take(e.currentTarget.files); e.currentTarget.value = ""; }} />

      {photos.length === 0 ? (
        <div className="flex flex-col items-center px-2 pt-3 pb-1 text-center">
          <span className="text-5xl" aria-hidden>📸</span>
          <p className="mt-3 font-semibold">Snap a desk, shelf or closet</p>
          <p className="mt-1 text-[13px] text-muted-foreground">Up to {MAX_PHOTOS} photos. We&apos;ll spot the things and list them for you to check.</p>
          <p className="mt-1 hidden text-[13px] text-muted-foreground md:block">Or drop photos here.</p>
        </div>
      ) : (
        <ul className="grid grid-cols-3 gap-2">
          {photos.map((p, i) => (
            <li key={p.key} className="relative">
              <PhotoTile url={p.previewUrl ?? p.upload?.url ?? null} className="rounded-2xl">
                {(p.state === "preparing" || p.state === "uploading") && (
                  <span className="absolute inset-0 flex items-center justify-center bg-black/25">
                    <Loader2 className="size-6 animate-spin text-white" aria-label="Uploading" />
                  </span>
                )}
                {p.state === "failed" && (
                  <button type="button" onClick={() => onRetry(p.key)}
                    className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-rose-600/80 px-1 text-center text-[12px] font-medium text-white">
                    <AlertCircle className="size-5" aria-hidden />
                    <span className="line-clamp-2">{p.error ?? "Upload failed"}</span>
                    <span className="inline-flex items-center gap-1 underline"><RotateCw className="size-3" /> Retry</span>
                  </button>
                )}
              </PhotoTile>
              <button type="button" onClick={() => onRemove(p.key)} aria-label={`Remove photo ${i + 1}`}
                className="absolute -top-1.5 -right-1.5 flex size-11 items-center justify-center">
                <span className="flex size-7 items-center justify-center rounded-full bg-foreground/80 text-white shadow ring-2 ring-card">
                  <X className="size-4" />
                </span>
              </button>
            </li>
          ))}
          {!full && (
            <li>
              <button type="button" onClick={() => libraryRef.current?.click()}
                className="flex aspect-square w-full flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-border text-[13px] font-medium text-muted-foreground active:bg-muted">
                <ImagePlus className="size-6" /> Add
              </button>
            </li>
          )}
        </ul>
      )}

      <div className="mt-4 flex flex-col gap-2">
        <button type="button" onClick={() => cameraRef.current?.click()} disabled={full}
          className={cn(bigBtn, "bg-primary text-primary-foreground hover:bg-primary-hover")}>
          <Camera className="size-5" /> Take photos
        </button>
        <button type="button" onClick={() => libraryRef.current?.click()} disabled={full}
          className={cn(bigBtn, "bg-muted text-foreground ring-1 ring-border/60")}>
          <ImagePlus className="size-5" /> Choose from library
        </button>
      </div>

      <p className="mt-3 flex items-start gap-2 rounded-xl bg-points-soft px-3 py-2 text-[13px] text-amber-900">
        <span aria-hidden>💡</span>
        <span>One area per photo — open the drawer or closet. Leave out people and documents.</span>
      </p>
      <p className="mt-2 text-right text-[12px] text-muted-foreground tabular-nums">{photos.length}/{MAX_PHOTOS} photos</p>
    </section>
  );
}
