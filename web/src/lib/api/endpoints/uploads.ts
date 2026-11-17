import { call, http } from "../client";
import { notMocked } from "../mock";
import type { Upload } from "../types";

export const uploads = {
  create: (file: Blob, filename = "photo.jpg") => {
    const form = new FormData();
    form.append("file", file, filename);
    return call("uploads", () => http<Upload>("POST", "/uploads", { form }), () => notMocked<Upload>("uploads.create"));
  },
};
