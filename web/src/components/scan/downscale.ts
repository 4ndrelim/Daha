/**
 * Client-side downscale before upload: phones produce 4–12 MB photos and campus Wi-Fi is slow.
 * Decoded image → canvas ≤ 1600 px on the long side → JPEG 0.85, upright (EXIF orientation applied).
 * If the browser can't decode the file (e.g. HEIC on Chrome/Android), the original goes up unchanged and
 * the server converts it.
 */
export const MAX_SIDE = 1600;
const QUALITY = 0.85;

export interface Prepared {
  blob: Blob;
  filename: string;
  /** Pixel size of `blob`, or null when the original couldn't be decoded here. */
  width: number | null;
  height: number | null;
  /** Something the browser can show as a thumbnail (null for undecodable HEIC). */
  previewable: boolean;
}

type Source = { draw: CanvasImageSource; width: number; height: number; release: () => void };

async function decodeBitmap(file: Blob): Promise<Source | null> {
  if (typeof createImageBitmap !== "function") return null;
  let bmp: ImageBitmap | null = null;
  try {
    bmp = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // Older Safari throws on the options bag; modern browsers apply EXIF orientation by default anyway.
    try {
      bmp = await createImageBitmap(file);
    } catch {
      return null;
    }
  }
  const b = bmp;
  return { draw: b, width: b.width, height: b.height, release: () => b.close() };
}

async function decodeImg(file: Blob): Promise<Source | null> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = "async";
    img.src = url;
    await img.decode();
    if (!img.naturalWidth || !img.naturalHeight) return null;
    // <img> honours EXIF orientation (CSS image-orientation: from-image is the default).
    return { draw: img, width: img.naturalWidth, height: img.naturalHeight, release: () => URL.revokeObjectURL(url) };
  } catch {
    URL.revokeObjectURL(url);
    return null;
  }
}

function toBlob(canvas: HTMLCanvasElement): Promise<Blob | null> {
  return new Promise((resolve) => {
    try {
      canvas.toBlob((b) => resolve(b), "image/jpeg", QUALITY);
    } catch {
      resolve(null);
    }
  });
}

function jpegName(name: string): string {
  const base = name.replace(/\.[^.]+$/, "") || "photo";
  return `${base.slice(0, 60)}.jpg`;
}

function looksLikeImage(file: File): boolean {
  return file.type.startsWith("image/") || /\.(jpe?g|png|webp|heic|heif|gif|avif)$/i.test(file.name);
}

export function isImageFile(file: File): boolean {
  return looksLikeImage(file);
}

export async function downscale(file: File): Promise<Prepared> {
  const original: Prepared = {
    blob: file, filename: file.name || "photo.jpg", width: null, height: null,
    previewable: /^image\/(jpeg|png|webp|gif|avif)$/.test(file.type),
  };
  const src = (await decodeBitmap(file)) ?? (await decodeImg(file));
  if (!src) return original;

  try {
    const scale = Math.min(1, MAX_SIDE / Math.max(src.width, src.height));
    const width = Math.max(1, Math.round(src.width * scale));
    const height = Math.max(1, Math.round(src.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return { ...original, previewable: true };
    ctx.fillStyle = "#ffffff"; // transparent PNGs → white, not black, in JPEG
    ctx.fillRect(0, 0, width, height);
    ctx.drawImage(src.draw, 0, 0, width, height);
    const blob = await toBlob(canvas);
    canvas.width = 0; // frees the backing store right away (matters on iOS)
    canvas.height = 0;
    if (!blob || blob.size === 0) return { ...original, previewable: true };
    // Always send the re-encoded copy, even when no resize was needed: it's upright and has no EXIF/GPS metadata.
    return { blob, filename: jpegName(file.name), width, height, previewable: true };
  } catch {
    return original;
  } finally {
    src.release();
  }
}
