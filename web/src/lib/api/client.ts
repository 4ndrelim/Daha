import type { Domain } from "./types";

export const TOKEN_KEY = "daha_token";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

type QueryValue = string | number | boolean | null | undefined;

export interface HttpOptions {
  body?: unknown;
  form?: FormData;
  query?: Record<string, QueryValue>;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_KEY, token);
  else window.localStorage.removeItem(TOKEN_KEY);
}

function buildQuery(query?: Record<string, QueryValue>): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

/** FastAPI errors are `{detail: string}`, or `{detail: [{msg, loc}]}` for 422s. */
function readDetail(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === "string") return first.msg;
    }
  }
  return fallback;
}

function redirectToLogin(): void {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  if (pathname.startsWith("/login") || pathname.startsWith("/signup")) return;
  const next = encodeURIComponent(pathname + search);
  // Outside React on purpose: a full reload also drops every cached query of the old session.
  // eslint-disable-next-line @next/next/no-location-assign-relative-destination
  window.location.assign(`/login?next=${next}`);
}

/** One typed call to the backend. `path` is relative to `/api`, e.g. `/items/3`. Never adds a trailing slash. */
export async function http<T>(method: string, path: string, opts: HttpOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`/api${path}${buildQuery(opts.query)}`, { method, headers, body });

  if (res.status === 204) return undefined as T;

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    // A 401 on login itself means "wrong password", not "session expired".
    if (res.status === 401 && !path.startsWith("/auth/")) {
      setToken(null);
      redirectToLogin();
    }
    throw new ApiError(res.status, readDetail(data, res.statusText || "Something went wrong"));
  }
  return data as T;
}

function mockedDomains(): Set<string> | "all" {
  const raw = (process.env.NEXT_PUBLIC_MOCK ?? "none").trim().toLowerCase();
  if (raw === "all") return "all";
  if (raw === "" || raw === "none") return new Set();
  return new Set(raw.split(",").map((s) => s.trim()).filter(Boolean));
}

export function isMocked(domain: Domain): boolean {
  const mocked = mockedDomains();
  return mocked === "all" || mocked.has(domain);
}

/** Route a call to the live backend or to the in-browser mock, depending on `NEXT_PUBLIC_MOCK`. */
export function call<T>(domain: Domain, live: () => Promise<T>, mock: () => Promise<T>): Promise<T> {
  return isMocked(domain) ? mock() : live();
}
