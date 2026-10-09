import Link from "next/link";
import { Suspense, type ReactNode } from "react";

import { NavLinks, StaticNavLinks } from "./nav";
import { PropertyFilter, SyntheticDataBanner } from "./property-filter";
import { Skeleton } from "./ui";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[14rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>
      <aside className="hidden border-r border-slate-200 bg-white lg:block">
        <div className="sticky top-0 p-4">
          <Link href="/" className="mb-6 block px-3 text-lg font-semibold text-brand-700">
            Review Insights
          </Link>
          <nav aria-label="Main">
            <Suspense fallback={<StaticNavLinks />}>
              <NavLinks />
            </Suspense>
          </nav>
          <p className="mt-6 px-3 text-xs text-slate-500">Weeks run Monday–Sunday, Australia/Sydney time.</p>
        </div>
      </aside>
      <div className="min-w-0">
        <SyntheticDataBanner />
        <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
          <div className="mb-2 flex items-center justify-between lg:hidden">
            <Link href="/" className="text-lg font-semibold text-brand-700">
              Review Insights
            </Link>
          </div>
          <nav aria-label="Main" className="mb-3 lg:hidden">
            <Suspense fallback={<StaticNavLinks orientation="horizontal" />}>
              <NavLinks orientation="horizontal" />
            </Suspense>
          </nav>
          <Suspense fallback={<Skeleton className="h-7 w-80" />}>
            <PropertyFilter />
          </Suspense>
        </header>
        <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
