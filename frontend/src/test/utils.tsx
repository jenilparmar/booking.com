import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { SWRConfig } from "swr";
import { vi } from "vitest";

/** Shared, mutable state behind the `next/navigation` mock (see setup.ts). */
export const nav = {
  pathname: "/",
  search: new URLSearchParams(),
  replace: vi.fn((href: string) => {
    const [path, qs = ""] = href.split("?");
    nav.pathname = path;
    nav.search = new URLSearchParams(qs);
  }),
};

export function setUrl(pathname: string, search = "") {
  nav.pathname = pathname;
  nav.search = new URLSearchParams(search);
  nav.replace.mockClear();
}

export function lastReplaceParams(): URLSearchParams {
  const href = nav.replace.mock.calls.at(-1)?.[0] ?? "";
  return new URLSearchParams(href.split("?")[1] ?? "");
}

export function renderWithSWR(ui: ReactElement) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0, shouldRetryOnError: false }}>
      {ui}
    </SWRConfig>,
  );
}

type Handler = (url: URL, init?: RequestInit) => unknown | Promise<unknown>;

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** Routes fetch calls by pathname; handlers return a Response or a JSON-able body. */
export function mockFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const handler = routes[url.pathname];
    if (!handler) return json({ error: { code: "not_found", message: `No mock for ${url.pathname}`, details: null } }, 404);
    const out = await handler(url, init);
    return out instanceof Response ? out : json(out);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
