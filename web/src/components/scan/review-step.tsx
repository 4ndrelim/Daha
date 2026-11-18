"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Plus } from "lucide-react";
import { toast } from "sonner";
import { ApiError, track } from "@/lib/api";
import type { Detection, Me, Scan, ScanPublishResponse, Visibility } from "@/lib/api/types";
import { usePlaces, usePublishScan } from "@/lib/queries/scans";
import { PrimaryButton } from "@/components/daha/form";
import { Skeleton } from "@/components/ui/skeleton";
import { DefaultsBar } from "./defaults-bar";
import {
  defaultVisibility, effectiveType, effectiveVisibility, manualRow, rowFromDetection, rowProblem, toPublishItem, wasEdited,
  type Defaults, type Row,
} from "./review-model";
import { ReviewRow, visibilityLabel, type PhotoRef } from "./review-row";
import { StickyFooter } from "./sticky-footer";
import { PhotoTile } from "./thumbs";

export interface PublishSummary {
  published: number;
  privateCount: number;
  visibility: Visibility;
  groupNames: string[];
  points: number;
  response: ScanPublishResponse;
}

export function ReviewStep({ scan, photos, me, startedAt, aboveNav, onPublished }: {
  scan: Scan;
  photos: PhotoRef[];
  me: Me | undefined;
  startedAt: number;
  aboveNav: boolean;
  onPublished: (s: PublishSummary) => void;
}) {
  const places = usePlaces();
  const publish = usePublishScan();
  const busy = useRef(false);
  const [edits, setEdits] = useState<Record<string, Row>>({});
  const [extras, setExtras] = useState<Row[]>([]);
  const [visibility, setVisibility] = useState<Visibility | null>(null); // null = My dorm, or Campus without a dorm
  const [rest, setRest] = useState<Omit<Defaults, "visibility">>({ groupIds: [], type: "auto", pickupPlaceId: null });
  const [showProblems, setShowProblems] = useState(false);

  const defaults: Defaults = { ...rest, visibility: visibility ?? defaultVisibility(me) };
  const detectionsById = useMemo(() => new Map(scan.detections.map((d) => [d.id, d])), [scan.detections]);
  const rows = scan.detections.map((d) => edits[`d${d.id}`] ?? rowFromDetection(d));
  const all = [...rows, ...extras];
  const selected = all.filter((r) => r.checked);
  const problems = new Map(selected.map((r) => [r.key, rowProblem(r, defaults, me)]));
  const firstProblem = selected.map((r) => problems.get(r.key)).find(Boolean) ?? null;
  const processing = scan.status === "processing";
  const left = scan.images.filter((i) => i.status === "pending" || i.status === "processing").length;

  // Once per review: how many things the AI found and how long it took to get here (counts only).
  const shown = useRef(false);
  useEffect(() => {
    if (shown.current) return;
    shown.current = true;
    track("scan_review_shown", {
      scan_id: scan.id, detections: scan.detections.length, photos: scan.images.length,
      seconds: Math.round((Date.now() - startedAt) / 1000),
    });
  }, [scan.id, scan.detections.length, scan.images.length, startedAt]);

  // Unsaved review: ask before closing the tab or reloading.
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (!busy.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  function update(row: Row, patch: Partial<Row>) {
    const next = { ...row, ...patch };
    if (row.detectionId === null) setExtras((xs) => xs.map((x) => (x.key === row.key ? next : x)));
    else setEdits((m) => ({ ...m, [row.key]: next }));
  }

  function share() {
    if (busy.current || publish.isPending || processing) return;
    if (selected.length === 0) return;
    if (firstProblem) {
      setShowProblems(true);
      toast.error(firstProblem);
      return;
    }
    busy.current = true;
    const items = selected.map((r) => toPublishItem(r, defaults));
    const published = selected.filter((r) => r.detectionId !== null);
    const edited = published.filter((r) => {
      const d = detectionsById.get(r.detectionId!);
      return d ? wasEdited(r, d, defaults) : false;
    }).length;
    publish.mutate({ id: scan.id, body: { items } }, {
      onSuccess: (response) => {
        track("scan_published", {
          scan_id: scan.id, published: published.length, edited, manual: selected.length - published.length,
          discarded: scan.detections.length - published.length, private: items.filter((i) => i.visibility === "private").length,
          seconds: Math.round((Date.now() - startedAt) / 1000),
        });
        onPublished({
          published: response.items.length,
          privateCount: items.filter((i) => i.visibility === "private").length,
          visibility: defaults.visibility,
          groupNames: (me?.groups ?? []).filter((g) => defaults.groupIds.includes(g.id)).map((g) => g.name),
          points: response.points_awarded,
          response,
        });
      },
      onError: (e) => {
        busy.current = false;
        toast.error(e instanceof ApiError ? e.detail : "Couldn't share right now. Check your connection and try again.");
      },
    });
  }

  const defaultVisText = `Same as above (${visibilityLabel(defaults.visibility, me)})`;

  function renderRow(row: Row, d: Detection | undefined) {
    const photo = row.imageIndex !== null ? photos[row.imageIndex] ?? null : null;
    return (
      <ReviewRow
        key={row.key}
        row={row}
        bbox={d?.bbox ?? null}
        photo={photo}
        type={effectiveType(row, defaults)}
        visibility={effectiveVisibility(row, defaults)}
        defaultVisibilityText={defaultVisText}
        me={me}
        problem={showProblems ? problems.get(row.key) ?? null : null}
        onChange={(patch) => update(row, patch)}
        onRemove={row.detectionId === null ? () => setExtras((xs) => xs.filter((x) => x.key !== row.key)) : undefined}
      />
    );
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-[22px] leading-7 font-semibold">Here&apos;s what we found</h2>
        <p className="mt-1 text-muted-foreground">Tick what you&apos;re happy to share and fix anything we got wrong. Nothing is shared until you tap Share.</p>
      </div>

      <DefaultsBar me={me} places={places.data} defaults={defaults}
        onChange={({ visibility: v, ...patch }) => {
          if (v) setVisibility(v);
          if (Object.keys(patch).length) setRest((r) => ({ ...r, ...patch }));
        }} />

      {scan.images.map((img, i) => {
        const group = rows.filter((r) => r.imageIndex === i);
        const pending = img.status === "pending" || img.status === "processing";
        return (
          <section key={`${img.upload_id}-${i}`} aria-label={`Photo ${i + 1}`}>
            <div className="mb-2 flex items-center gap-2.5">
              <PhotoTile url={photos[i]?.url ?? (img.url || null)} className="size-10 rounded-lg" />
              <p className="text-[15px] font-semibold">Photo {i + 1}</p>
              <p className="text-[13px] text-muted-foreground">
                {pending ? "Still looking…" : img.status === "failed" ? "Couldn't read this one" : `${group.length} ${group.length === 1 ? "thing" : "things"}`}
              </p>
            </div>
            {pending && (
              <div className="space-y-2" aria-busy>
                {[0, 1].map((k) => <Skeleton key={k} className="h-[68px] rounded-2xl" />)}
              </div>
            )}
            {img.status === "failed" && (
              <p className="flex items-start gap-2 rounded-2xl bg-rose-50 px-3 py-2.5 text-[13px] text-rose-700">
                <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
                {img.error ?? "We couldn't read this photo."} The other photos still work.
              </p>
            )}
            {img.status === "done" && group.length === 0 && (
              <p className="rounded-2xl border border-dashed border-border px-3 py-3 text-center text-[13px] text-muted-foreground">
                Nothing we could list here. Add it yourself below.
              </p>
            )}
            <ul className="space-y-2">
              {group.map((r) => renderRow(r, r.detectionId !== null ? detectionsById.get(r.detectionId) : undefined))}
            </ul>
          </section>
        );
      })}

      {extras.length > 0 && (
        <section aria-label="Added by you">
          <p className="mb-2 text-[15px] font-semibold">Added by you</p>
          <ul className="space-y-2">{extras.map((r) => renderRow(r, undefined))}</ul>
        </section>
      )}

      <button type="button" onClick={() => setExtras((xs) => [...xs, manualRow()])}
        className="flex h-12 w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-border font-semibold text-foreground active:bg-muted">
        <Plus className="size-5" /> Add something we missed
      </button>

      <div className="h-28" aria-hidden />

      <StickyFooter aboveNav={aboveNav}>
        {processing && (
          <p className="mb-2 text-center text-[13px] text-muted-foreground">
            Still scanning {left} {left === 1 ? "photo" : "photos"}… you can keep editing.
          </p>
        )}
        <PrimaryButton type="button" onClick={share} loading={publish.isPending}
          disabled={processing || selected.length === 0 || publish.isSuccess}>
          {selected.length === 0 ? "Tick what you want to share" : `Share ${selected.length} ${selected.length === 1 ? "item" : "items"}`}
        </PrimaryButton>
      </StickyFooter>
    </div>
  );
}
