"use client";

import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, cx, EmptyState, ErrorState, LoadingBlock, PageHeader, ProvenanceNote } from "@/components/ui";
import { useWeeks, WeeksSelect } from "@/components/weeks-select";
import { formatRating, formatWeek } from "@/lib/format";
import { useTrends } from "@/lib/hooks";
import type { Trends } from "@/lib/types";
import { useGlobalFilters } from "@/lib/url-state";

const WEEK_OPTIONS = [4, 8, 12, 26, 52];
const PROPERTY_COLORS = ["#2f6bdb", "#c2410c", "#7c3aed", "#0f766e"];
const POSITIVE = "#15803d";
const NEGATIVE = "#b91c1c";
const NEUTRAL = "#94a3b8";

type Mode = "overall" | "property";

function labelFor(data: Trends, weekStart: string, i: number, total: number) {
  const label = formatWeek(weekStart);
  return data.current_week_partial && i === total - 1 ? `${label}*` : label;
}

function overallRows(data: Trends) {
  return data.overall.map((p, i) => ({
    week: labelFor(data, p.week_start, i, data.overall.length),
    avg_rating: p.avg_rating,
    reviews: p.reviews,
    positive: p.positive,
    neutral: p.neutral,
    negative: p.negative,
  }));
}

function propertyRows(data: Trends, metric: "avg_rating" | "reviews" | "negative") {
  return data.overall.map((p, i) => {
    const row: Record<string, string | number | null> = {
      week: labelFor(data, p.week_start, i, data.overall.length),
    };
    for (const prop of data.by_property) row[prop.property_id] = prop.points[i]?.[metric] ?? null;
    return row;
  });
}

function ChartCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <Card title={title}>
      <p className="-mt-2 mb-3 text-xs text-slate-500">{description}</p>
      <div className="h-64 w-full" role="img" aria-label={`${title} chart. ${description}`}>
        {children}
      </div>
    </Card>
  );
}

export function TrendsView() {
  const { query } = useGlobalFilters();
  const { weeks, setWeeks } = useWeeks(12, WEEK_OPTIONS);
  const [mode, setMode] = useState<Mode>("overall");
  const { data, error, mutate } = useTrends({ ...query, weeks });

  const hasData = !!data && data.overall.some((p) => p.reviews > 0);
  const props = data?.by_property ?? [];

  return (
    <>
      <PageHeader title="Trends" description="Weekly metrics (Monday–Sunday, Australia/Sydney). Weeks with no reviews show gaps, not zeros, for rating.">
        <div className="flex flex-wrap items-center gap-3">
          <div role="group" aria-label="Chart breakdown" className="inline-flex rounded-md ring-1 ring-slate-300">
            {(["overall", "property"] as const).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
                className={cx("px-3 py-1 text-sm first:rounded-l-md last:rounded-r-md", mode === m ? "bg-brand-600 text-white" : "bg-white text-slate-700 hover:bg-slate-100")}
              >
                {m === "overall" ? "Overall" : "By property"}
              </button>
            ))}
          </div>
          <WeeksSelect value={weeks} options={WEEK_OPTIONS} onChange={setWeeks} />
        </div>
      </PageHeader>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <LoadingBlock label="Loading trends" rows={4} />
      ) : !hasData ? (
        <EmptyState title="No dated reviews in this window" />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard title="Average rating" description="Mean rating (1–10) of rated reviews per week.">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={mode === "overall" ? overallRows(data) : propertyRows(data, "avg_rating")}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                  <YAxis domain={[1, 10]} tick={{ fontSize: 12 }} width={32} />
                  <Tooltip formatter={(v) => formatRating(typeof v === "number" ? v : null)} />
                  <Legend />
                  {mode === "overall" ? (
                    <Line isAnimationActive={false} type="monotone" dataKey="avg_rating" name="Average rating" stroke={PROPERTY_COLORS[0]} strokeWidth={2} connectNulls={false} />
                  ) : (
                    props.map((p, i) => (
                      <Line isAnimationActive={false} key={p.property_id} type="monotone" dataKey={p.property_id} name={p.name} stroke={PROPERTY_COLORS[i % PROPERTY_COLORS.length]} strokeWidth={2} connectNulls={false} />
                    ))
                  )}
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Review volume" description="Number of reviews published per week.">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={mode === "overall" ? overallRows(data) : propertyRows(data, "reviews")}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
                  <Tooltip />
                  <Legend />
                  {mode === "overall" ? (
                    <Bar isAnimationActive={false} dataKey="reviews" name="Reviews" fill={PROPERTY_COLORS[0]} />
                  ) : (
                    props.map((p, i) => (
                      <Bar isAnimationActive={false} key={p.property_id} dataKey={p.property_id} name={p.name} fill={PROPERTY_COLORS[i % PROPERTY_COLORS.length]} />
                    ))
                  )}
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <ChartCard
            title={mode === "overall" ? "Positive vs negative" : "Negative reviews by property"}
            description={mode === "overall" ? "Reviews per week by text sentiment (VADER)." : "Count of negative-sentiment reviews per week."}
          >
            <ResponsiveContainer width="100%" height="100%">
              {mode === "overall" ? (
                <BarChart data={overallRows(data)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
                  <Tooltip />
                  <Legend />
                  <Bar isAnimationActive={false} dataKey="positive" name="Positive" stackId="s" fill={POSITIVE} />
                  <Bar isAnimationActive={false} dataKey="neutral" name="Neutral" stackId="s" fill={NEUTRAL} />
                  <Bar isAnimationActive={false} dataKey="negative" name="Negative" stackId="s" fill={NEGATIVE} />
                </BarChart>
              ) : (
                <LineChart data={propertyRows(data, "negative")}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 12 }} width={32} />
                  <Tooltip />
                  <Legend />
                  {props.map((p, i) => (
                    <Line isAnimationActive={false} key={p.property_id} type="monotone" dataKey={p.property_id} name={p.name} stroke={PROPERTY_COLORS[i % PROPERTY_COLORS.length]} strokeWidth={2} />
                  ))}
                </LineChart>
              )}
            </ResponsiveContainer>
          </ChartCard>

          {data.current_week_partial && (
            <p className="text-xs text-slate-500">* The current week is still in progress.</p>
          )}

          <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-700">Show data table</summary>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[32rem] text-left text-sm">
                <caption className="sr-only">Weekly totals across selected properties</caption>
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th scope="col" className="py-2 pr-4">Week starting</th>
                    <th scope="col" className="py-2 pr-4 text-right">Reviews</th>
                    <th scope="col" className="py-2 pr-4 text-right">Avg rating (rated)</th>
                    <th scope="col" className="py-2 pr-4 text-right">Positive</th>
                    <th scope="col" className="py-2 pr-4 text-right">Neutral</th>
                    <th scope="col" className="py-2 text-right">Negative</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 tabular-nums">
                  {data.overall.map((p, i) => (
                    <tr key={p.week_start}>
                      <th scope="row" className="py-1.5 pr-4 font-normal">{labelFor(data, p.week_start, i, data.overall.length)}</th>
                      <td className="py-1.5 pr-4 text-right">{p.reviews}</td>
                      <td className="py-1.5 pr-4 text-right">{formatRating(p.avg_rating)} ({p.rated_reviews})</td>
                      <td className="py-1.5 pr-4 text-right">{p.positive}</td>
                      <td className="py-1.5 pr-4 text-right">{p.neutral}</td>
                      <td className="py-1.5 text-right">{p.negative}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <ProvenanceNote sources={data.data_sources} excludedUndated={data.excluded_undated} />
        </div>
      )}
    </>
  );
}
