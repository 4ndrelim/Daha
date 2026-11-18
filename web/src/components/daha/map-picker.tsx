"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import type * as Leaflet from "leaflet";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { CAMPUS, roughly } from "@/lib/near";

// Free OpenStreetMap tiles: fine for light use with the attribution shown on the map
// (https://operations.osmfoundation.org/policies/tiles/). The browser fetches them only while this
// map is open, so OpenStreetMap sees the area being looked at, as with any map on the web.
const TILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
const PIN_HTML =
  '<span style="display:block;font-size:34px;line-height:1;filter:drop-shadow(0 2px 2px rgb(0 0 0 / .35))">📍</span>';

export type Spot = { lat: number; lng: number };

/** One draggable pin on a map. Leaflet touches `window`, so it's loaded in the browser only. */
function PinMap({ start, onMove }: { start: Spot; onMove: (spot: Spot) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const moved = useEffectEvent((latLng: Leaflet.LatLng) => {
    const wrapped = latLng.wrap(); // panning past the date line keeps longitudes in -180..180
    onMove({ lat: wrapped.lat, lng: wrapped.lng });
  });

  useEffect(() => {
    let map: Leaflet.Map | undefined;
    let observer: ResizeObserver | undefined;
    let gone = false;
    void import("leaflet").then((L) => {
      if (gone || !box.current) return;
      map = L.map(box.current, { center: [start.lat, start.lng], zoom: 13 });
      L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);
      const icon = L.divIcon({ className: "daha-map-pin", html: PIN_HTML, iconSize: [34, 34], iconAnchor: [17, 32] });
      const pin = L.marker([start.lat, start.lng], { draggable: true, autoPan: true, icon, title: "Drag me" }).addTo(map);
      pin.on("dragend", () => moved(pin.getLatLng()));
      map.on("click", (e: Leaflet.LeafletMouseEvent) => {
        pin.setLatLng(e.latlng);
        moved(e.latlng);
      });
      // The sheet slides in, so the map's final size is only known after it opens.
      observer = new ResizeObserver(() => map?.invalidateSize());
      observer.observe(box.current);
    });
    return () => {
      gone = true;
      observer?.disconnect();
      map?.remove();
    };
  }, [start.lat, start.lng]);

  return (
    <div
      ref={box}
      role="application"
      aria-label="Map. Drag the pin, or tap the map where you are."
      className="h-72 w-full overflow-hidden rounded-2xl bg-muted ring-1 ring-border"
    />
  );
}

/**
 * "Pick a spot on the map" for people who keep location services off (or are somewhere
 * Stanford campus isn't): a pin they drag, used like the phone's location but only to ~1 km.
 * Give it a new `key` each time it opens, so it starts from `start` again.
 */
export function MapPickerSheet({ open, onOpenChange, start, onUse }: {
  open: boolean; onOpenChange: (open: boolean) => void; start: Spot | null; onUse: (spot: Spot) => void;
}) {
  const origin = start ?? CAMPUS;
  const [spot, setSpot] = useState<Spot>(origin);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="bottom" className="mx-auto max-h-[92dvh] max-w-md overflow-y-auto rounded-t-3xl pb-[calc(1rem+env(safe-area-inset-bottom))]">
        <SheetHeader>
          <SheetTitle className="text-[17px]">Pick a spot on the map</SheetTitle>
          <SheetDescription>
            Drag the pin, or tap where you are. No location permission needed, and only a rough spot (about 1 km) is used.
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-3 px-4">
          {open && <PinMap start={origin} onMove={setSpot} />}
          <p className="text-[13px] text-muted-foreground">
            Pin at {roughly(spot.lat).toFixed(2)}, {roughly(spot.lng).toFixed(2)}
          </p>
          <button
            type="button"
            onClick={() => onUse({ lat: roughly(spot.lat), lng: roughly(spot.lng) })}
            className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground active:bg-primary-hover"
          >
            Use this spot
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
