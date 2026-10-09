"use client";

import { useId, useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api";
import type { DataSource, Sentiment } from "@/lib/types";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

export function Card({
  title,
  action,
  children,
  className,
}: {
  title?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cx("rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5", className)}>
      {(title || action) && (
        <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
          {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, description, children }: { title: string; description?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-slate-600">{description}</p>}
      </div>
      {children}
    </header>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx("animate-pulse rounded-md bg-slate-200", className)} />;
}

export function LoadingBlock({ label = "Loading", rows = 3 }: { label?: string; rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function ErrorState({
  error,
  onRetry,
  title = "Couldn't load data",
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-medium">{title}</p>
      <p className="mt-1">{errorMessage(error)}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md bg-white px-3 py-1.5 font-medium text-red-900 ring-1 ring-red-300 hover:bg-red-100"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-sm text-slate-600">
      <p className="font-medium text-slate-800">{title}</p>
      {children && <div className="mt-1">{children}</div>}
    </div>
  );
}

/** Small "i" button that reveals help text on hover, focus or click. */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className="relative inline-flex">
      <button
        type="button"
        aria-label={`About ${label}`}
        aria-describedby={open ? id : undefined}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-slate-400 text-[10px] font-semibold leading-none text-slate-500 hover:border-slate-600 hover:text-slate-700"
      >
        i
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          className="absolute left-1/2 top-6 z-20 w-64 -translate-x-1/2 rounded-md bg-slate-900 px-3 py-2 text-xs font-normal leading-snug text-white shadow-lg"
        >
          {children}
        </span>
      )}
    </span>
  );
}

export function Badge({ children, tone = "slate", className }: { children: ReactNode; tone?: "slate" | "green" | "red" | "amber" | "blue" | "purple"; className?: string }) {
  const tones = {
    slate: "bg-slate-100 text-slate-700 ring-slate-200",
    green: "bg-green-50 text-green-800 ring-green-200",
    red: "bg-red-50 text-red-800 ring-red-200",
    amber: "bg-amber-50 text-amber-900 ring-amber-200",
    blue: "bg-brand-50 text-brand-700 ring-brand-100",
    purple: "bg-purple-50 text-purple-800 ring-purple-200",
  } as const;
  return (
    <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", tones[tone], className)}>
      {children}
    </span>
  );
}

export function SentimentBadge({ value }: { value: Sentiment }) {
  const tone = value === "positive" ? "green" : value === "negative" ? "red" : "slate";
  return <Badge tone={tone}>{value[0].toUpperCase() + value.slice(1)}</Badge>;
}

export function DataSourceBadge({ value }: { value: DataSource }) {
  if (value === "synthetic") return <Badge tone="amber">Synthetic</Badge>;
  if (value === "imported") return <Badge tone="blue">Imported</Badge>;
  return <Badge tone="green">Live</Badge>;
}

export function ProvenanceNote({ sources, excludedUndated }: { sources: DataSource[]; excludedUndated?: number }) {
  return (
    <p className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
      <span>Data source:</span>
      {sources.length ? sources.map((s) => <DataSourceBadge key={s} value={s} />) : <span>none</span>}
      {!!excludedUndated && <span>· {excludedUndated} undated review(s) excluded from time-based metrics</span>}
    </p>
  );
}
