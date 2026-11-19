import type { MetadataRoute } from "next";
import { BACKGROUND, THEME } from "@/lib/theme";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "DAHA · share stuff across campus",
    short_name: "DAHA",
    description: "Lend, borrow, give away and swap everyday things with people in your dorm.",
    id: "/home",
    start_url: "/home",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: BACKGROUND[THEME],
    theme_color: BACKGROUND[THEME],
    categories: ["lifestyle", "social", "education"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
