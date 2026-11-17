import { call, http } from "../client";
import { notMocked } from "../mock";
import type { Place } from "../types";

export const places = {
  list: () => call("places", () => http<Place[]>("GET", "/places"), () => notMocked<Place[]>("places.list")),
};
