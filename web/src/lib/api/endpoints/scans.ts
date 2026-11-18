import { call, http, isMocked } from "../client";
import { mockScans, rememberUpload } from "../mock/scans";
import type { ID, Scan, ScanCreate, ScanPublishBody, ScanPublishResponse, Upload } from "../types";
import { uploads } from "./uploads";

export const scans = {
  /** POST /uploads for a scan photo. When uploads are mocked too, the photo stays in the browser. */
  uploadPhoto: async (file: Blob, filename: string): Promise<Upload> => {
    if (isMocked("uploads")) return mockScans.upload(file);
    const upload = await uploads.create(file, filename);
    rememberUpload(upload); // lets the scans mock show the photo even when only scans are mocked
    return upload;
  },
  create: (body: ScanCreate) => call("scans", () => http<Scan>("POST", "/scans", { body }), () => mockScans.create(body)),
  get: (id: ID) => call("scans", () => http<Scan>("GET", `/scans/${id}`), () => mockScans.get(id)),
  publish: (id: ID, body: ScanPublishBody) =>
    call("scans", () => http<ScanPublishResponse>("POST", `/scans/${id}/publish`, { body }), () => mockScans.publish(id, body)),
};
