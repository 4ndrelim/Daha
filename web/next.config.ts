import type { NextConfig } from "next";

const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  cacheComponents: true,
  partialPrefetching: true,
  // The logged-in app renders in the browser (token in localStorage), so skip automatic
  // "instant navigation" checks; pages can still opt in with `export const instant = true`.
  experimental: {
    instantInsights: {
      validationLevel: "manual-warning",
    },
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // The browser only ever talks to this app; Next proxies API and photo calls to the backend.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` },
      { source: "/uploads/:path*", destination: `${API_PROXY_TARGET}/uploads/:path*` },
    ];
  },
};

export default nextConfig;
