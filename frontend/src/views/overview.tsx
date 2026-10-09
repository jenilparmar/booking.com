"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ComparisonGrid } from "@/components/comparison";
import { KpiSkeleton, SummaryKpis } from "@/components/kpi";
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader, ProvenanceNote } from "@/components/ui";
import { formatPeriod } from "@/lib/format";
import { useComparison, useSummary } from "@/lib/hooks";
import { hrefWithGlobals, useGlobalFilters } from "@/lib/url-state";

export function OverviewView() {
  const { query } = useGlobalFilters();
  const searchParams = useSearchParams();
  const summary = useSummary(query);
  const comparison = useComparison({ ...query, weeks: 4 });

  return (
    <>
      <PageHeader
        title="This week at a glance"
        description={
          summary.data
            ? `Current week: ${formatPeriod(summary.data.current_period)} (${summary.data.timezone}). Compared with the same span last week.`
            : "Current week (Monday to now, Australia/Sydney) compared with the same span last week."
        }
      />

      <div className="space-y-6">
        <section aria-label="Key metrics">
          {summary.error ? (
            <ErrorState error={summary.error} onRetry={() => summary.mutate()} />
          ) : !summary.data ? (
            <KpiSkeleton />
          ) : (
            <>
              <SummaryKpis summary={summary.data} />
              {summary.data.current.reviews === 0 && (
                <p className="mt-3 text-sm text-slate-600">
                  No reviews have been published yet this week, so this week&apos;s metrics show N/A.
                </p>
              )}
              <ProvenanceNote sources={summary.data.data_sources} excludedUndated={summary.data.excluded_undated} />
            </>
          )}
        </section>

        <Card
          title="Property comparison · last 4 weeks"
          action={
            <Link href={hrefWithGlobals("/properties", searchParams)} className="text-sm font-medium text-brand-600 hover:underline">
              More detail
            </Link>
          }
        >
          {comparison.error ? (
            <ErrorState error={comparison.error} onRetry={() => comparison.mutate()} />
          ) : !comparison.data ? (
            <LoadingBlock label="Loading comparison" rows={2} />
          ) : comparison.data.properties.length === 0 ? (
            <EmptyState title="No properties selected" />
          ) : (
            <ComparisonGrid data={comparison.data} />
          )}
        </Card>
      </div>
    </>
  );
}
