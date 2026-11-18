"use client";

import Link from "next/link";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, track } from "@/lib/api";
import { scans } from "@/lib/api/endpoints/scans";
import type { ID } from "@/lib/api/types";
import { useMe } from "@/lib/queries/me";
import { POLL_GIVE_UP_MS, scanKey, useScan } from "@/lib/queries/scans";
import { PrimaryButton } from "@/components/daha/form";
import { CaptureStep } from "./capture-step";
import { HavesChecklist } from "./haves-checklist";
import { ProgressStep, type ProgressPhoto } from "./progress-step";
import { ReviewStep, type PublishSummary } from "./review-step";
import type { PhotoRef } from "./review-row";
import { StickyFooter } from "./sticky-footer";
import { SuccessStep } from "./success-step";
import { usePhotos, type UploadedPhoto } from "./use-photos";

type Phase = "capture" | "uploading" | "scanning" | "review" | "success" | "limited";

/**
 * The whole photo → items flow (C4): capture → upload + scan (polled) → review → publish → success.
 * Used by /add/scan (`mode="add"`, above the bottom nav) and /onboarding (`mode="onboarding"`, full screen).
 */
export function ScanFlow({ mode, intro, besideCapture }: {
  mode: "add" | "onboarding";
  /** Shown above the capture card only (a hero or a page title). */
  intro?: ReactNode;
  /** Shown under the capture card only (e.g. the "Tick what you have" checklist on /onboarding). */
  besideCapture?: ReactNode;
}) {
  const qc = useQueryClient();
  const { data: me } = useMe();
  const { photos, add, remove, retry, waitAll, reset, full } = usePhotos();
  const [phase, setPhase] = useState<Phase>("capture");
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [scanId, setScanId] = useState<ID | null>(null);
  const [uploaded, setUploaded] = useState<UploadedPhoto[]>([]);
  const [limit, setLimit] = useState<string | null>(null);
  const [summary, setSummary] = useState<PublishSummary | null>(null);
  const starting = useRef(false);
  const scanQ = useScan(scanId, startedAt);
  const scan = scanQ.data;
  const aboveNav = mode === "add";

  const view: Phase = phase === "scanning" && scan?.status === "done" ? "review" : phase;
  useEffect(() => {
    if (view !== "capture") window.scrollTo({ top: 0 });
  }, [view]);

  async function start() {
    if (starting.current || photos.length === 0) return;
    starting.current = true;
    const t0 = Date.now();
    setStartedAt(t0);
    setPhase("uploading");
    track("scan_started", { photos: photos.length, mode });
    try {
      const ok = await waitAll();
      if (ok.length === 0) {
        toast.error("Couldn't upload your photos. Check your connection and try again.");
        setPhase("capture");
        return;
      }
      if (ok.length < photos.length) toast(`${photos.length - ok.length} photo didn't upload — scanning the rest.`);
      const created = await scans.create({ upload_ids: ok.map((u) => u.upload.id) });
      qc.setQueryData(scanKey(created.id), created);
      setUploaded(ok);
      setScanId(created.id);
      setPhase("scanning");
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        setLimit(e.detail);
        setPhase("limited");
      } else {
        toast.error(e instanceof ApiError ? e.detail : "Couldn't start the scan. Check your connection and try again.");
        setPhase("capture");
      }
    } finally {
      starting.current = false;
    }
  }

  function again() {
    reset();
    setScanId(null);
    setUploaded([]);
    setSummary(null);
    setLimit(null);
    setStartedAt(null);
    setPhase("capture");
  }

  const photoRefs: PhotoRef[] = uploaded.map((u) => {
    const p = photos.find((x) => x.key === u.key);
    return {
      url: p?.previewUrl ?? u.upload.url ?? null,
      width: p?.previewUrl ? p.width : u.upload.width || null,
      height: p?.previewUrl ? p.height : u.upload.height || null,
    };
  });

  // ---------- capture ----------
  if (view === "capture") {
    return (
      <div className="space-y-5">
        {intro}
        <CaptureStep photos={photos} full={full} onAdd={add} onRemove={remove} onRetry={retry} />
        {besideCapture}
        <div className="h-24" aria-hidden />
        {photos.length > 0 && (
          <StickyFooter aboveNav={aboveNav}>
            <PrimaryButton type="button" onClick={start}>
              ✨ Find my stuff · {photos.length} {photos.length === 1 ? "photo" : "photos"}
            </PrimaryButton>
          </StickyFooter>
        )}
      </div>
    );
  }

  // ---------- 429: daily or budget limit ----------
  if (view === "limited") {
    return (
      <div className="space-y-5">
        <section className="rounded-3xl bg-card p-5 text-center shadow-sm ring-1 ring-border/60">
          <p className="text-4xl" aria-hidden>⏸️</p>
          <h2 className="mt-2 text-[17px] font-semibold">Photo scanning is paused</h2>
          <p className="mt-1 text-muted-foreground">{limit ?? "AI scanning paused — list items manually."}</p>
          <Link href="/add/item" className="mt-4 flex h-12 items-center justify-center rounded-full bg-primary px-5 text-[15px] font-semibold text-primary-foreground">
            List items manually
          </Link>
          <button type="button" onClick={again} className="mt-2 h-11 w-full rounded-full font-semibold text-primary">Back</button>
        </section>
        <HavesChecklist title="Or just tick what you have" />
      </div>
    );
  }

  // ---------- success ----------
  if (view === "success" && summary) {
    return <SuccessStep summary={summary} me={me} onScanMore={again} />;
  }

  // ---------- review (as soon as one photo is done, or automatically when all are) ----------
  if ((view === "review" || view === "success") && scan && startedAt !== null) {
    return (
      <ReviewStep scan={scan} photos={photoRefs} me={me} startedAt={startedAt} aboveNav={aboveNav}
        onPublished={(s) => { setSummary(s); setPhase("success"); }} />
    );
  }

  // ---------- uploading / scanning ----------
  if (scan?.status === "failed") {
    return (
      <div className="space-y-5">
        <section className="rounded-3xl bg-card p-5 text-center shadow-sm ring-1 ring-border/60">
          <p className="text-4xl" aria-hidden>🙈</p>
          <h2 className="mt-2 text-[17px] font-semibold">We couldn&apos;t read those photos</h2>
          <p className="mt-1 text-muted-foreground">{scan.images.find((i) => i.error)?.error ?? "Try brighter, closer shots of one area at a time."}</p>
          <PrimaryButton type="button" className="mt-4" onClick={again}>Try other photos</PrimaryButton>
          <Link href="/add/item" className="mt-2 flex h-11 items-center justify-center font-semibold text-primary">List items manually</Link>
        </section>
        <HavesChecklist title="Or just tick what you have" />
      </div>
    );
  }

  const progress: ProgressPhoto[] = scan
    ? scan.images.map((img, i) => ({
      key: `${img.upload_id}-${i}`,
      url: photoRefs[i]?.url ?? (img.url || null),
      state: img.status === "done" ? "done" : img.status === "failed" ? "failed" : "scanning",
      found: scan.detections.filter((d) => d.image_index === i).length,
      error: img.error,
    }))
    : photos.map((p) => ({
      key: p.key, url: p.previewUrl ?? p.upload?.url ?? null,
      state: p.state === "failed" ? "failed" : p.state === "ready" ? "scanning" : "uploading",
      found: 0, error: p.error,
    }));
  const doneCount = scan?.images.filter((i) => i.status === "done").length ?? 0;
  const found = scan?.detections.length ?? 0;
  const stalled = !!scan && scan.status === "processing" && startedAt !== null && scanQ.dataUpdatedAt - startedAt > POLL_GIVE_UP_MS;

  return (
    <div className="space-y-5">
      <ProgressStep photos={progress} title={phase === "uploading" ? "Uploading your photos…" : "Finding your stuff…"} />
      {scanQ.isError && !scan && (
        <div className="rounded-2xl bg-rose-50 p-4 text-center">
          <p className="font-medium text-rose-700">Lost the connection to the scan.</p>
          <button type="button" onClick={() => scanQ.refetch()} className="mt-2 h-11 rounded-full bg-card px-5 font-semibold text-rose-700 ring-1 ring-rose-200">Try again</button>
        </div>
      )}
      {stalled && (
        <div className="rounded-2xl bg-points-soft p-4 text-center text-[15px]">
          <p>This is taking longer than usual.</p>
          <button type="button" onClick={() => scanQ.refetch()} className="mt-2 h-11 rounded-full bg-card px-5 font-semibold ring-1 ring-border">Check again</button>
        </div>
      )}
      <div className="h-24" aria-hidden />
      <StickyFooter aboveNav={aboveNav}>
        <PrimaryButton type="button" disabled={doneCount === 0} loading={phase === "uploading"} onClick={() => setPhase("review")}>
          {doneCount === 0 ? "Scanning…" : `Start reviewing · ${found} ${found === 1 ? "item" : "items"} so far`}
        </PrimaryButton>
      </StickyFooter>
    </div>
  );
}
