import type {
  ApiErrorBody,
  CollectionHealth,
  Comparison,
  ImportResult,
  PropertiesResponse,
  ReviewPage,
  Summary,
  Topics,
  Trends,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export type Query = Record<string, string | number | string[] | null | undefined>;

export function buildQuery(params: Query = {}): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) {
      if (value.length) sp.set(key, value.join(","));
    } else {
      sp.set(key, String(value));
    }
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  if (!res.ok) {
    const err = (body as ApiErrorBody | null)?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "http_error",
      err?.message ?? `Request failed (${res.status})`,
      err?.details,
    );
  }
  return body as T;
}

export async function getJson<T>(path: string, params?: Query): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}${buildQuery(params)}`, {
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the API. Is the backend running?");
  }
  return parse<T>(res);
}

export async function uploadReviews(file: File): Promise<ImportResult> {
  const form = new FormData();
  form.append("file", file);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/import/reviews`, { method: "POST", body: form });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach the API. Is the backend running?");
  }
  return parse<ImportResult>(res);
}

export const api = {
  properties: () => getJson<PropertiesResponse>("/api/properties"),
  reviews: (q: Query) => getJson<ReviewPage>("/api/reviews", q),
  summary: (q: Query) => getJson<Summary>("/api/analytics/summary", q),
  comparison: (q: Query) => getJson<Comparison>("/api/analytics/properties", q),
  trends: (q: Query) => getJson<Trends>("/api/analytics/trends", q),
  topics: (q: Query) => getJson<Topics>("/api/analytics/topics", q),
  collectionHealth: () => getJson<CollectionHealth>("/api/collection/health"),
};
