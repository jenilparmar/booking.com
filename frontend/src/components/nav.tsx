"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { hrefWithGlobals } from "@/lib/url-state";

import { cx } from "./ui";

export const NAV_ITEMS = [
  { href: "/", label: "Overview" },
  { href: "/properties", label: "Properties" },
  { href: "/reviews", label: "Reviews" },
  { href: "/trends", label: "Trends" },
  { href: "/insights", label: "Insights" },
  { href: "/data", label: "Data & import" },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function NavLinks({ orientation = "vertical" }: { orientation?: "vertical" | "horizontal" }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  return (
    <ul className={cx(orientation === "vertical" ? "space-y-1" : "flex gap-1 overflow-x-auto")}>
      {NAV_ITEMS.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <li key={item.href} className="shrink-0">
            <Link
              href={hrefWithGlobals(item.href, searchParams)}
              aria-current={active ? "page" : undefined}
              className={cx(
                "block rounded-md px-3 py-2 text-sm font-medium",
                active ? "bg-brand-50 text-brand-700" : "text-slate-700 hover:bg-slate-100",
              )}
            >
              {item.label}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

export function StaticNavLinks({ orientation = "vertical" }: { orientation?: "vertical" | "horizontal" }) {
  return (
    <ul className={cx(orientation === "vertical" ? "space-y-1" : "flex gap-1 overflow-x-auto")}>
      {NAV_ITEMS.map((item) => (
        <li key={item.href} className="shrink-0">
          <Link href={item.href} className="block rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
            {item.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}
