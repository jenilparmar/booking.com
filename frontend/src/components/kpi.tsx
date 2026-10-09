"use client";

import type { ReactNode } from "react";

import { formatPct, formatRating, formatSigned, NA, plural } from "@/lib/format";
import type { Summary } from "@/lib/types";

import { cx, InfoTip, Skeleton } from "./ui";

type Trend = "good" | "bad" | "flat" | "none";

export function KpiCard({
  label,
  value,
  denominator,
  change,
  trend = "none",
  help,
}: {
  label: string;
  value: string;
  denominator?: ReactNode;
  change?: string;
  trend?: Trend;
  help: ReactNode;
}) {
  const color =
    trend === "good" ? "text-positive" : trend === "bad" ? "text-negative" : "text-slate-500";
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-1.5 text-sm font-medium text-slate-600">
        <span>{label}</span>
        <InfoTip label={label}>{help}</InfoTip>
      </div>
      <p className={cx("mt-2 text-3xl font-semibold tabular-nums", value === NA ? "text-slate-500" : "text-slate-900")}>
        {value}
      </p>
      {denominator && <p className="mt-1 text-xs text-slate-500">{denominator}</p>}
      {change && (
        <p className={cx("mt-1 text-xs font-medium", color)}>
          <span className="sr-only">Change versus previous week: </span>
          {change}
        </p>
      )}
    </div>
  );
}

export function KpiSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" role="status" aria-label="Loading KPIs">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={i} className="rounded-xl border border-slate-200 bg-white p-4">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="mt-3 h-8 w-20" />
          <Skeleton className="mt-2 h-3 w-36" />
        </div>
      ))}
    </div>
  );
}

function direction(v: number | null, higherIsBetter: boolean): Trend {
  if (v === null) return "none";
  if (v === 0) return "flat";
  return v > 0 === higherIsBetter ? "good" : "bad";
}

export function SummaryKpis({ summary }: { summary: Summary }) {
  const { current, previous } = summary;
  const top = summary.top_negative_topic;
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiCard
        label="Average rating"
        value={formatRating(current.avg_rating)}
        denominator={`out of 10 · from ${plural(current.rated_reviews, "rated review")}`}
        change={
          summary.avg_rating_change === null
            ? previous.avg_rating === null
              ? "No rated reviews last week"
              : "No change data"
            : `${formatSigned(summary.avg_rating_change)} vs last week (${formatRating(previous.avg_rating)})`
        }
        trend={direction(summary.avg_rating_change, true)}
        help="Mean of review ratings (normalised to a 1–10 scale) published this week. Reviews without a rating are excluded."
      />
      <KpiCard
        label="Reviews this week"
        value={String(current.reviews)}
        denominator={`${previous.reviews} last week`}
        change={`${formatSigned(summary.review_count_change, 0)} vs last week`}
        trend={summary.review_count_change === 0 ? "flat" : "none"}
        help="Reviews published since Monday 00:00 (Australia/Sydney) up to now."
      />
      <KpiCard
        label="Negative reviews"
        value={formatPct(current.pct_negative)}
        denominator={`${current.negative} of ${plural(current.reviews, "review")}`}
        change={
          summary.pct_negative_change === null
            ? "No comparison available"
            : `${formatSigned(summary.pct_negative_change, 1, " pts")} vs last week (${formatPct(previous.pct_negative)})`
        }
        trend={direction(summary.pct_negative_change, false)}
        help="Share of this week's reviews whose text sentiment (VADER) is negative. Sentiment is estimated from text and can differ from the star rating."
      />
      <KpiCard
        label="Top complaint"
        value={top ? top.topic : NA}
        denominator={
          top
            ? `${top.count} of ${plural(top.negative_reviews, "negative review")} (${formatPct(top.pct_of_negative)})`
            : current.negative === 0
              ? "No negative reviews this week"
              : "No topic detected"
        }
        help="Topic mentioned most often in this week's negative reviews (keyword-based, approximate)."
      />
    </div>
  );
}
