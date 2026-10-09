"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** Params shared across every page (kept when navigating between sections). */
export const GLOBAL_PARAMS = ["properties", "as_of"] as const;

export type ParamUpdates = Record<string, string | string[] | null | undefined>;

export function mergeParams(current: URLSearchParams, updates: ParamUpdates): URLSearchParams {
  const next = new URLSearchParams(current.toString());
  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)) {
      next.delete(key);
    } else {
      next.set(key, Array.isArray(value) ? value.join(",") : value);
    }
  }
  return next;
}

export function useUrlState() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const setParams = useCallback(
    (updates: ParamUpdates) => {
      const next = mergeParams(searchParams, updates);
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [router, pathname, searchParams],
  );

  return { searchParams, setParams, pathname };
}

export function splitList(value: string | null): string[] {
  return value ? value.split(",").map((s) => s.trim()).filter(Boolean) : [];
}

/** Property selection + optional as_of shared by all analytics views. */
export function useGlobalFilters() {
  const { searchParams, setParams } = useUrlState();
  const properties = useMemo(() => splitList(searchParams.get("properties")), [searchParams]);
  const asOf = searchParams.get("as_of");
  const query = useMemo(
    () => ({ property_ids: properties, as_of: asOf }),
    [properties, asOf],
  );
  return {
    properties,
    asOf,
    query,
    setProperties: (ids: string[]) => setParams({ properties: ids, page: null }),
  };
}

/** Builds an href that keeps the global params of the current URL. */
export function hrefWithGlobals(path: string, searchParams: URLSearchParams): string {
  const keep = new URLSearchParams();
  for (const key of GLOBAL_PARAMS) {
    const v = searchParams.get(key);
    if (v) keep.set(key, v);
  }
  const qs = keep.toString();
  return qs ? `${path}?${qs}` : path;
}
