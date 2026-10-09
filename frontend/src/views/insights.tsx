"use client";

import { Badge, Card, DataSourceBadge, EmptyState, ErrorState, InfoTip, LoadingBlock, PageHeader, ProvenanceNote } from "@/components/ui";
import { useWeeks, WeeksSelect } from "@/components/weeks-select";
import { formatDate, formatPct, formatPeriod, formatRating, formatSigned, plural } from "@/lib/format";
import { useTopics } from "@/lib/hooks";
import { useGlobalFilters } from "@/lib/url-state";

const WEEK_OPTIONS = [1, 2, 4, 8, 12];

export function InsightsView() {
  const { query } = useGlobalFilters();
  const { weeks, setWeeks } = useWeeks(4, WEEK_OPTIONS);
  const { data, error, mutate } = useTopics({ ...query, weeks });

  return (
    <>
      <PageHeader
        title="Complaint insights"
        description={data ? `Window: ${formatPeriod(data.window)}. ${plural(data.negative_reviews, "negative review")} out of ${plural(data.total_reviews, "review")}.` : "What guests complain about, by topic."}
      >
        <WeeksSelect value={weeks} options={WEEK_OPTIONS} onChange={setWeeks} />
      </PageHeader>

      <div role="note" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <strong className="font-semibold">Approximate.</strong> Topics are detected with keyword rules and
        sentiment is estimated from review text (VADER). Expect some misses and false matches; use the
        example reviews to sanity-check.
        {data && <span className="ml-1 text-amber-800">Method: {data.method}.</span>}
      </div>

      {error ? (
        <ErrorState error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <LoadingBlock label="Loading insights" rows={4} />
      ) : data.total_reviews === 0 ? (
        <EmptyState title="No reviews in this window" />
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Top complaint topics" className="lg:col-span-2">
              {data.top_negative_topics.length === 0 ? (
                <EmptyState title="No topics detected in negative reviews" />
              ) : (
                <ol className="space-y-2">
                  {data.top_negative_topics.map((t) => (
                    <li key={t.topic}>
                      <div className="flex justify-between text-sm">
                        <span className="font-medium text-slate-800">{t.topic}</span>
                        <span className="tabular-nums text-slate-600">
                          {t.count} of {data.negative_reviews} · {formatPct(t.pct_of_negative)}
                        </span>
                      </div>
                      <div className="mt-1 h-2 rounded-full bg-slate-100" aria-hidden="true">
                        <div className="h-2 rounded-full bg-negative" style={{ width: `${t.pct_of_negative ?? 0}%` }} />
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </Card>

            <Card
              title={
                <span className="inline-flex items-center gap-1.5">
                  Cleanliness share
                  <InfoTip label="cleanliness share">Share of negative reviews that mention cleanliness. N/A when there are no negative reviews.</InfoTip>
                </span>
              }
            >
              <p className="text-3xl font-semibold tabular-nums">{formatPct(data.cleanliness_share_of_negative.pct)}</p>
              <p className="mt-1 text-xs text-slate-500">
                {data.cleanliness_share_of_negative.negative_with_cleanliness} of{" "}
                {plural(data.cleanliness_share_of_negative.negative_reviews, "negative review")}
              </p>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Worst topic per property">
              <ul className="divide-y divide-slate-100 text-sm">
                {data.worst_topic_by_property.map((w) => (
                  <li key={w.property_id} className="flex justify-between gap-3 py-2">
                    <span className="font-medium text-slate-800">{w.name}</span>
                    <span className="text-right text-slate-600">
                      {w.topic ? `${w.topic} · ${w.count} of ${w.negative_reviews} negative` : w.negative_reviews ? "No topic detected" : "No negative reviews"}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>

            <Card
              title={
                <span className="inline-flex items-center gap-1.5">
                  Rising complaints
                  <InfoTip label="rising complaints">
                    Topics mentioned more often in negative reviews in the last 14 days ({formatPeriod(data.rising_periods.recent)}) than in the 14 days before. Requires at least 2 recent mentions.
                  </InfoTip>
                </span>
              }
            >
              {data.rising_topics.length === 0 ? (
                <EmptyState title="No rising topics" >Nothing increased meaningfully versus the prior 14 days.</EmptyState>
              ) : (
                <ul className="divide-y divide-slate-100 text-sm">
                  {data.rising_topics.map((r) => (
                    <li key={r.topic} className="flex justify-between gap-3 py-2">
                      <span className="font-medium text-slate-800">{r.topic}</span>
                      <span className="tabular-nums text-slate-600">
                        {r.prior_count} → {r.recent_count} <Badge tone="red">{formatSigned(r.change, 0)}</Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          {data.examples.length > 0 && (
            <Card title="Example negative reviews">
              <div className="grid gap-4 md:grid-cols-2">
                {data.examples.map((group) => (
                  <section key={group.topic}>
                    <h3 className="mb-2 text-sm font-semibold text-slate-800">{group.topic}</h3>
                    <ul className="space-y-2">
                      {group.reviews.map((r) => (
                        <li key={r.id} className="rounded-md bg-slate-50 p-3 text-sm">
                          <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            <span>{formatDate(r.published_at)}</span>
                            <span>Rating {formatRating(r.rating)}</span>
                            <DataSourceBadge value={r.data_source} />
                          </div>
                          {r.review_title && <p className="font-medium text-slate-800">{r.review_title}</p>}
                          <p className="text-slate-700">{r.review_text}</p>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            </Card>
          )}
          <ProvenanceNote sources={data.data_sources} excludedUndated={data.excluded_undated} />
        </div>
      )}
    </>
  );
}
