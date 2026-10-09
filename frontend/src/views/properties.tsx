"use client";

import { ComparisonGrid } from "@/components/comparison";
import { Card, EmptyState, ErrorState, InfoTip, LoadingBlock, PageHeader, ProvenanceNote } from "@/components/ui";
import { useWeeks, WeeksSelect } from "@/components/weeks-select";
import { formatPct, formatPeriod, formatRating, formatSigned } from "@/lib/format";
import { useComparison } from "@/lib/hooks";
import { useGlobalFilters } from "@/lib/url-state";

const WEEK_OPTIONS = [1, 2, 4, 8, 12];

export function PropertiesView() {
  const { query } = useGlobalFilters();
  const { weeks, setWeeks } = useWeeks(4, WEEK_OPTIONS);
  const { data, error, mutate } = useComparison({ ...query, weeks });

  return (
    <>
      <PageHeader
        title="Property comparison"
        description={data ? `Window: ${formatPeriod(data.window)} (${data.timezone}).` : "Side-by-side metrics for each property."}
      >
        <WeeksSelect value={weeks} options={WEEK_OPTIONS} onChange={setWeeks} />
      </PageHeader>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <LoadingBlock label="Loading comparison" rows={4} />
      ) : data.properties.length === 0 ? (
        <EmptyState title="No properties match the current filter" />
      ) : (
        <div className="space-y-6">
          <section aria-labelledby="property-cards">
            <h2 id="property-cards" className="sr-only">Property cards</h2>
            <ComparisonGrid data={data} />
          </section>
          <Card
            title={
              <span className="inline-flex items-center gap-1.5">
                Comparison table
                <InfoTip label="comparison table">
                  Averages use only reviews with a rating; the rated count is shown as the denominator.
                  Negative % uses text sentiment over all reviews in the window.
                </InfoTip>
              </span>
            }
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <caption className="sr-only">Metrics per property for the last {data.window_weeks} weeks</caption>
                <thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th scope="col" className="py-2 pr-4">Property</th>
                    <th scope="col" className="py-2 pr-4 text-right">Reviews</th>
                    <th scope="col" className="py-2 pr-4 text-right">Avg rating (rated)</th>
                    <th scope="col" className="py-2 pr-4 text-right">Negative</th>
                    <th scope="col" className="py-2 pr-4 text-right">This week</th>
                    <th scope="col" className="py-2 pr-4 text-right">Δ vs last week</th>
                    <th scope="col" className="py-2">Top complaint</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.properties.map((r) => (
                    <tr key={r.property_id}>
                      <th scope="row" className="py-2 pr-4 font-medium text-slate-900">{r.name}</th>
                      <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">{r.window.reviews}</td>
                      <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">
                        {formatRating(r.window.avg_rating)} <span className="text-slate-500">({r.window.rated_reviews})</span>
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">
                        {formatPct(r.window.pct_negative)} <span className="text-slate-500">({r.window.negative})</span>
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">
                        {formatRating(r.current_week.avg_rating)} <span className="text-slate-500">({r.current_week.reviews})</span>
                      </td>
                      <td className="whitespace-nowrap py-2 pr-4 text-right tabular-nums">{formatSigned(r.avg_rating_change)}</td>
                      <td className="py-2">{r.top_complaint ? `${r.top_complaint.topic} (${r.top_complaint.count})` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ProvenanceNote sources={data.data_sources} excludedUndated={data.excluded_undated} />
          </Card>
        </div>
      )}
    </>
  );
}
