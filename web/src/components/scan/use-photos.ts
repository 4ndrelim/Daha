"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { scans } from "@/lib/api/endpoints/scans";
import type { Upload } from "@/lib/api/types";
import { downscale, isImageFile, type Prepared } from "./downscale";

export const MAX_PHOTOS = 6;

export interface Photo {
  key: string;
  /** Local thumbnail (object URL of the downscaled JPEG); null while preparing or for undecodable HEIC. */
  previewUrl: string | null;
  width: number | null;
  height: number | null;
  state: "preparing" | "uploading" | "ready" | "failed";
  upload: Upload | null;
  error: string | null;
}

export interface UploadedPhoto { key: string; upload: Upload }

let seq = 0;
const newKey = () => `p${Date.now().toString(36)}${(seq++).toString(36)}`; // crypto.randomUUID needs https; phones test over http://<ip>

function uploadError(e: unknown): string {
  if (e instanceof ApiError) return e.status === 413 ? "That photo is too big" : e.detail;
  return "Upload failed — check your connection";
}

/**
 * Selected photos: each one is downscaled (one at a time, to spare phone memory) and uploaded in the
 * background as soon as it's picked, so "Find my stuff" usually starts the scan instantly.
 */
export function usePhotos() {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const order = useRef<string[]>([]);
  const prepared = useRef(new Map<string, Prepared>());
  const jobs = useRef(new Map<string, Promise<Upload | null>>());
  const urls = useRef(new Map<string, string>());
  const chain = useRef<Promise<unknown>>(Promise.resolve());

  const patch = useCallback((key: string, p: Partial<Photo>) => {
    setPhotos((ps) => ps.map((x) => (x.key === key ? { ...x, ...p } : x)));
  }, []);

  useEffect(() => {
    const map = urls.current;
    return () => {
      for (const url of map.values()) URL.revokeObjectURL(url);
      map.clear();
    };
  }, []);

  const uploadOne = useCallback(async (key: string): Promise<Upload | null> => {
    const prep = prepared.current.get(key);
    if (!prep || !order.current.includes(key)) return null;
    patch(key, { state: "uploading", error: null });
    try {
      const upload = await scans.uploadPhoto(prep.blob, prep.filename);
      if (order.current.includes(key)) patch(key, { state: "ready", upload });
      return upload;
    } catch (e) {
      if (order.current.includes(key)) patch(key, { state: "failed", error: uploadError(e) });
      return null;
    }
  }, [patch]);

  const prepare = useCallback(async (key: string, file: File): Promise<boolean> => {
    if (!order.current.includes(key)) return false;
    const prep = await downscale(file);
    if (!order.current.includes(key)) return false;
    prepared.current.set(key, prep);
    let previewUrl: string | null = null;
    if (prep.previewable) {
      previewUrl = URL.createObjectURL(prep.blob);
      urls.current.set(key, previewUrl);
    }
    patch(key, { previewUrl, width: prep.width, height: prep.height });
    return true;
  }, [patch]);

  /** Adds up to the remaining slots; returns how many files were skipped (not images, or over the limit). */
  const add = useCallback((files: File[]): { added: number; skipped: number } => {
    const images = files.filter(isImageFile);
    const room = Math.max(0, MAX_PHOTOS - order.current.length);
    const accepted = images.slice(0, room);
    const fresh: Photo[] = accepted.map(() => ({
      key: newKey(), previewUrl: null, width: null, height: null, state: "preparing", upload: null, error: null,
    }));
    order.current = [...order.current, ...fresh.map((p) => p.key)];
    setPhotos((ps) => [...ps, ...fresh]);
    fresh.forEach((p, i) => {
      const file = accepted[i]!;
      const ready = chain.current.then(() => prepare(p.key, file)).catch(() => false);
      chain.current = ready;
      jobs.current.set(p.key, ready.then((ok) => (ok ? uploadOne(p.key) : null)));
    });
    return { added: accepted.length, skipped: files.length - accepted.length };
  }, [prepare, uploadOne]);

  const remove = useCallback((key: string) => {
    order.current = order.current.filter((k) => k !== key);
    prepared.current.delete(key);
    jobs.current.delete(key);
    const url = urls.current.get(key);
    if (url) {
      URL.revokeObjectURL(url);
      urls.current.delete(key);
    }
    setPhotos((ps) => ps.filter((p) => p.key !== key));
  }, []);

  const retry = useCallback((key: string) => {
    jobs.current.set(key, uploadOne(key));
  }, [uploadOne]);

  /** Waits for every pending upload (retrying failures once) and returns the ones that made it, in order. */
  const waitAll = useCallback(async (): Promise<UploadedPhoto[]> => {
    const keys = [...order.current];
    const results = await Promise.all(keys.map(async (key) => {
      let upload = (await jobs.current.get(key)) ?? null;
      if (!upload && prepared.current.has(key) && order.current.includes(key)) {
        const again = uploadOne(key);
        jobs.current.set(key, again);
        upload = await again;
      }
      return upload ? { key, upload } : null;
    }));
    return results.filter((r): r is UploadedPhoto => r !== null && order.current.includes(r.key));
  }, [uploadOne]);

  const reset = useCallback(() => {
    for (const url of urls.current.values()) URL.revokeObjectURL(url);
    urls.current.clear();
    prepared.current.clear();
    jobs.current.clear();
    order.current = [];
    setPhotos([]);
  }, []);

  return { photos, add, remove, retry, waitAll, reset, full: photos.length >= MAX_PHOTOS };
}
