import { call, http } from "../client";
import type { EventIn, EventsBody } from "../types";

export const events = {
  send: (body: EventsBody) => call("events", () => http<void>("POST", "/events", { body }), () => Promise.resolve()),
};

/** Fire-and-forget analytics (PLAN.md §7.6). Never throws, never blocks the UI. */
export function track(type: string, payload?: EventIn["payload"]): void {
  events.send({ events: [{ type, payload, ts: new Date().toISOString() }] }).catch(() => {});
}
