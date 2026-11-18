"use client";

import { useRef, useState } from "react";
import { Camera, Loader2, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { Upload } from "@/lib/api/types";
import { downscaleImage } from "@/lib/image";

export interface PickedPhoto { key: string; preview: string; upload: Upload | null }

/** Up to `max` photos; each is shrunk and uploaded as soon as it's picked. The first one is the thumbnail. */
export function PhotoPicker({ photos, onChange, max = 6 }: {
  photos: PickedPhoto[]; onChange: (update: (prev: PickedPhoto[]) => PickedPhoto[]) => void; max?: number;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(0);

  async function add(files: FileList | null) {
    if (!files) return;
    const room = max - photos.length;
    const chosen = Array.from(files).slice(0, room);
    if (files.length > room) toast.message(`Up to ${max} photos.`);
    setBusy((n) => n + chosen.length);
    await Promise.all(chosen.map(async (file) => {
      const key = `${file.name}-${file.size}-${Math.random()}`;
      const preview = URL.createObjectURL(file);
      onChange((prev) => [...prev, { key, preview, upload: null }]);
      try {
        const upload = await api.uploads.create(await downscaleImage(file), "photo.jpg");
        onChange((prev) => prev.map((p) => (p.key === key ? { ...p, upload } : p)));
      } catch {
        toast.error("A photo didn't upload. Try that one again?");
        onChange((prev) => prev.filter((p) => p.key !== key));
      } finally {
        setBusy((n) => n - 1);
      }
    }));
  }

  return (
    <div className="no-scrollbar -mx-4 flex gap-2.5 overflow-x-auto px-4">
      {photos.map((p, i) => (
        <div key={p.key} className="relative size-24 shrink-0 overflow-hidden rounded-2xl bg-muted ring-1 ring-border">
          {/* eslint-disable-next-line @next/next/no-img-element -- local preview */}
          <img src={p.upload?.url ?? p.preview} alt="" className="size-full object-cover" />
          {!p.upload && <div className="absolute inset-0 flex items-center justify-center bg-black/30"><Loader2 className="size-5 animate-spin text-white" /></div>}
          {i === 0 && <span className="absolute bottom-1 left-1 rounded-full bg-black/60 px-1.5 text-[11px] font-medium text-white">Cover</span>}
          <button
            type="button"
            aria-label="Remove photo"
            onClick={() => onChange((prev) => prev.filter((x) => x.key !== p.key))}
            className="absolute top-1 right-1 flex size-7 items-center justify-center rounded-full bg-black/60 text-white"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
      {photos.length < max && (
        <button
          type="button"
          onClick={() => input.current?.click()}
          className="flex size-24 shrink-0 flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-border text-[13px] font-medium text-muted-foreground active:bg-muted"
        >
          {busy > 0 ? <Loader2 className="size-6 animate-spin" /> : <Camera className="size-6" />}
          {photos.length ? "Add more" : "Add photos"}
        </button>
      )}
      <input ref={input} type="file" accept="image/*" multiple hidden onChange={(e) => { add(e.target.files); e.target.value = ""; }} />
    </div>
  );
}
