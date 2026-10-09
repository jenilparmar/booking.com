"use client";

import { formatPct, formatRating, formatSigned, NA, plural } from "@/lib/format";
import type { Comparison, PeriodStats } from "@/lib/types";

import { cx } from "./ui";

function SentimentBar({ stats }: { stats: PeriodStats }) {
  const total = stats.positive + stats.neutral + stats.negative;
  if (!total) return <div className="h-2 rounded-full bg-slate-100" aria-hidden="true" />;
  const pct = (n: number) => `${(n / total) * 100}%`;
  return (
    <div
      className="flex h-2 overflow-hidden rounded-full bg-slate-100"
      role="img"
      aria-label={`${stats.positive} positive, ${stats.neutral} neutral, ${stats.negative} negative`}
    >
      <div className="bg-positive" style={{ width: pct(stats.positive) }} />
      <div className="bg-slate-300" style={{ width: pct(stats.neutral) }} />
      <div className="bg-negative" style={{ width: pct(stats.negative) }} />
    </div>
  );
}

function Stat({ label, value, sub, muted }: { label: string; value: string; sub?: string; muted?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className={cx("text-lg font-semibold tabular-nums", muted || value === NA ? "text-slate-400" : "text-slate-900")}>
        {value}
      </dd>
      {sub && <dd className="text-xs text-slate-500">{sub}</dd>}
    </div>
  );
}

export function ComparisonGrid({ data }: { data: Comparison }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {data.properties.map((row) => {
        const change = row.avg_rating_change;
        return (
          <article key={row.property_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h3 className="font-semibold text-slate-900">{row.name}</h3>
            <p className="text-xs text-slate-500">
              Last {data.window_weeks} weeks · {plural(row.window.reviews, "review")}
            </p>
            <dl className="mt-3 grid grid-cols-2 gap-3">
              <Stat
                label="Avg rating"
                value={formatRating(row.window.avg_rating)}
                sub={`${row.window.rated_reviews} rated`}
              />
              <Stat
                label="Negative"
                value={formatPct(row.window.pct_negative)}
                sub={`${row.window.negative} of ${row.window.reviews}`}
              />
              <Stat
                label="This week"
                value={formatRating(row.current_week.avg_rating)}
                sub={`${plural(row.current_week.reviews, "review")}`}
              />
              <div>
                <dt className="text-xs text-slate-500">Week-on-week</dt>
                <dd
                  className={cx(
                    "text-lg font-semibold tabular-nums",
                    change === null ? "text-slate-400" : change > 0 ? "text-positive" : change < 0 ? "text-negative" : "text-slate-900",
                  )}
                >
                  {formatSigned(change)}
                </dd>
                <dd className="text-xs text-slate-500">vs {formatRating(row.previous_week.avg_rating)} last week</dd>
              </div>
            </dl>
            <div className="mt-3">
              <SentimentBar stats={row.window} />
            </div>
            <p className="mt-3 text-xs text-slate-600">
              <span className="font-medium text-slate-700">Top complaint: </span>
              {row.top_complaint
                ? `${row.top_complaint.topic} (${row.top_complaint.count} of ${row.top_complaint.negative_reviews} negative)`
                : row.window.negative
                  ? "No topic detected"
                  : "No negative reviews"}
            </p>
          </article>
        );
      })}
    </div>
  );
}
