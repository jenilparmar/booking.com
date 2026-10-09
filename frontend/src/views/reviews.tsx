"use client";

import { useEffect, useId, useMemo, useState, type ReactNode } from "react";

import { Badge, Card, DataSourceBadge, EmptyState, ErrorState, LoadingBlock, PageHeader, ProvenanceNote, SentimentBadge } from "@/components/ui";
import { formatDate, formatRating, plural } from "@/lib/format";
import { useReviews } from "@/lib/hooks";
import { TOPICS, type Review } from "@/lib/types";
import { useGlobalFilters, useUrlState } from "@/lib/url-state";

export const PAGE_SIZE = 20;
export const SEARCH_DEBOUNCE_MS = 300;

/** Review-specific URL params (the property selection is global and kept on clear). */
export const REVIEW_FILTER_KEYS = ["q", "sentiment", "topic", "rating_min", "rating_max", "date_from", "date_to", "data_source", "sort", "page"] as const;

const inputCls = "w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm";

function Field({ label, children, id }: { label: string; id: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-600">
        {label}
      </label>
      {children}
    </div>
  );
}

function SearchBox({ initial, onCommit }: { initial: string; onCommit: (q: string) => void }) {
  const [draft, setDraft] = useState(initial);
  const id = useId();
  useEffect(() => {
    if (draft.trim() === initial) return;
    const t = setTimeout(() => onCommit(draft.trim()), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [draft, initial, onCommit]);
  return (
    <Field label="Search reviews" id={id}>
      <input
        id={id}
        type="search"
        value={draft}
        maxLength={200}
        placeholder="e.g. noisy, breakfast, check-in"
        onChange={(e) => setDraft(e.target.value)}
        className={inputCls}
      />
    </Field>
  );
}

function ReviewItem({ review }: { review: Review }) {
  return (
    <li className="py-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span className="font-medium text-slate-700">{review.property_name}</span>
        <span aria-hidden="true">·</span>
        <time dateTime={review.published_at ?? undefined}>{formatDate(review.published_at)}</time>
        <span aria-hidden="true">·</span>
        <span>
          Rating <span className="font-semibold text-slate-800">{formatRating(review.rating)}</span>
          {review.rating !== null && "/10"}
        </span>
        <SentimentBadge value={review.sentiment_label} />
        <DataSourceBadge value={review.data_source} />
        {review.language && review.language !== "en" && <Badge>{review.language}</Badge>}
      </div>
      {review.review_title && <h3 className="mt-1 font-medium text-slate-900">{review.review_title}</h3>}
      <p className="mt-1 whitespace-pre-line text-sm text-slate-700">{review.review_text}</p>
      {review.topic_labels.length > 0 && (
        <ul className="mt-2 flex flex-wrap gap-1" aria-label="Topics">
          {review.topic_labels.map((t) => (
            <li key={t}>
              <Badge tone="purple">{t}</Badge>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function ReviewsView() {
  const { searchParams, setParams } = useUrlState();
  const { properties } = useGlobalFilters();
  const [searchKey, setSearchKey] = useState(0);
  const ids = {
    sentiment: useId(),
    topic: useId(),
    ratingMin: useId(),
    ratingMax: useId(),
    from: useId(),
    to: useId(),
    source: useId(),
    sort: useId(),
  };

  const get = (k: string) => searchParams.get(k) ?? "";
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const q = get("q");

  const query = useMemo(
    () => ({
      property_ids: properties,
      q: searchParams.get("q"),
      sentiment: searchParams.get("sentiment"),
      topic: searchParams.get("topic"),
      rating_min: searchParams.get("rating_min"),
      rating_max: searchParams.get("rating_max"),
      date_from: searchParams.get("date_from"),
      date_to: searchParams.get("date_to"),
      data_source: searchParams.get("data_source"),
      sort: searchParams.get("sort"),
      page,
      page_size: PAGE_SIZE,
    }),
    [properties, searchParams, page],
  );
  const { data, error, isLoading, isValidating, mutate } = useReviews(query);

  const setFilter = (key: string, value: string) => setParams({ [key]: value || null, page: null });
  const commitSearch = useMemo(
    () => (value: string) => setParams({ q: value || null, page: null }),
    [setParams],
  );
  const activeFilters = REVIEW_FILTER_KEYS.filter((k) => k !== "page" && k !== "sort" && searchParams.get(k));
  const clearFilters = () => {
    setParams(Object.fromEntries(REVIEW_FILTER_KEYS.map((k) => [k, null])));
    setSearchKey((k) => k + 1);
  };
  const goTo = (p: number) => setParams({ page: p > 1 ? String(p) : null });

  return (
    <>
      <PageHeader title="Reviews" description="Search and filter every review. Filters are kept in the URL, so you can share or bookmark a view." />

      <Card className="mb-4">
        <h2 className="sr-only">Filters</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="col-span-2">
            <SearchBox key={searchKey} initial={q} onCommit={commitSearch} />
          </div>
          <Field label="Sentiment" id={ids.sentiment}>
            <select id={ids.sentiment} value={get("sentiment")} onChange={(e) => setFilter("sentiment", e.target.value)} className={inputCls}>
              <option value="">Any</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </Field>
          <Field label="Topic" id={ids.topic}>
            <select id={ids.topic} value={get("topic")} onChange={(e) => setFilter("topic", e.target.value)} className={inputCls}>
              <option value="">Any</option>
              {TOPICS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </Field>
          <Field label="Min rating" id={ids.ratingMin}>
            <select id={ids.ratingMin} value={get("rating_min")} onChange={(e) => setFilter("rating_min", e.target.value)} className={inputCls}>
              <option value="">Any</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </Field>
          <Field label="Max rating" id={ids.ratingMax}>
            <select id={ids.ratingMax} value={get("rating_max")} onChange={(e) => setFilter("rating_max", e.target.value)} className={inputCls}>
              <option value="">Any</option>
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </Field>
          <Field label="From date" id={ids.from}>
            <input id={ids.from} type="date" value={get("date_from")} onChange={(e) => setFilter("date_from", e.target.value)} className={inputCls} />
          </Field>
          <Field label="To date" id={ids.to}>
            <input id={ids.to} type="date" value={get("date_to")} onChange={(e) => setFilter("date_to", e.target.value)} className={inputCls} />
          </Field>
          <Field label="Data source" id={ids.source}>
            <select id={ids.source} value={get("data_source")} onChange={(e) => setFilter("data_source", e.target.value)} className={inputCls}>
              <option value="">Any</option>
              <option value="live">Live</option>
              <option value="imported">Imported</option>
              <option value="synthetic">Synthetic</option>
            </select>
          </Field>
          <Field label="Sort by" id={ids.sort}>
            <select id={ids.sort} value={get("sort") || "newest"} onChange={(e) => setFilter("sort", e.target.value === "newest" ? "" : e.target.value)} className={inputCls}>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
              <option value="rating">Highest rating</option>
            </select>
          </Field>
          <div className="flex items-end">
            <button
              type="button"
              onClick={clearFilters}
              disabled={activeFilters.length === 0 && !get("sort")}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Clear filters{activeFilters.length ? ` (${activeFilters.length})` : ""}
            </button>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="sr-only">Results</h2>
        {error ? (
          <ErrorState error={error} onRetry={() => mutate()} />
        ) : !data || isLoading ? (
          <LoadingBlock label="Loading reviews" rows={5} />
        ) : data.total === 0 ? (
          <EmptyState title="No reviews match these filters">
            {activeFilters.length > 0 && (
              <button type="button" onClick={clearFilters} className="font-medium text-brand-600 hover:underline">
                Clear filters
              </button>
            )}
          </EmptyState>
        ) : (
          <>
            <p className="text-sm text-slate-600" aria-live="polite">
              {plural(data.total, "review")} · page {data.page} of {data.total_pages}
              {isValidating && <span className="ml-2 text-slate-500">Updating…</span>}
            </p>
            <ul className="divide-y divide-slate-100">
              {data.items.map((r) => (
                <ReviewItem key={r.id} review={r} />
              ))}
            </ul>
            <nav aria-label="Pagination" className="mt-2 flex items-center justify-between border-t border-slate-100 pt-3">
              <button type="button" onClick={() => goTo(page - 1)} disabled={page <= 1} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50">
                Previous
              </button>
              <span className="text-sm text-slate-600">
                Page {data.page} of {data.total_pages}
              </span>
              <button type="button" onClick={() => goTo(page + 1)} disabled={page >= data.total_pages} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-50">
                Next
              </button>
            </nav>
            <ProvenanceNote sources={data.data_sources} />
          </>
        )}
      </Card>
    </>
  );
}
