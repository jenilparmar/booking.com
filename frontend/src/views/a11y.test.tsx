import { screen } from "@testing-library/react";
import axe from "axe-core";
import type { ReactElement } from "react";

import { NavLinks } from "@/components/nav";
import { PropertyFilter, SyntheticDataBanner } from "@/components/property-filter";
import { emptyStats, importResult, review, reviewPage, summary } from "@/test/fixtures";
import { mockFetch, renderWithSWR, setUrl } from "@/test/utils";
import type { CollectionHealth, Comparison, PropertiesResponse, Topics, Trends } from "@/lib/types";

import { DataView } from "./data";
import { InsightsView } from "./insights";
import { OverviewView } from "./overview";
import { PropertiesView } from "./properties";
import { ReviewsView } from "./reviews";
import { TrendsView } from "./trends";

const period = { start: "2026-09-13T14:00:00Z", end: "2026-10-09T06:00:00Z" };
const provenance = { data_sources: ["synthetic" as const], contains_synthetic: true };
const stats = { reviews: 10, avg_rating: 7.5, rated_reviews: 9, positive: 6, neutral: 2, negative: 2, pct_negative: 20 };

const properties: PropertiesResponse = {
  ...provenance,
  items: [
    { id: "chateau-de-venus", name: "Darling Harbour", source_url: null, review_count: 10, last_review_at: period.end },
    { id: "venus-surry-hills", name: "Central Sydney", source_url: null, review_count: 8, last_review_at: period.end },
  ],
};

const comparison: Comparison = {
  ...provenance,
  timezone: "Australia/Sydney",
  as_of: period.end,
  window: period,
  window_weeks: 4,
  current_period: period,
  previous_period: period,
  properties: [
    { property_id: "chateau-de-venus", name: "Darling Harbour", window: stats, current_week: stats, previous_week: emptyStats, avg_rating_change: null, top_complaint: { topic: "Noise", count: 2, negative_reviews: 2, pct_of_negative: 100 } },
  ],
  excluded_undated: 1,
};

const point = { week_start: "2026-09-28", ...stats };
const trends: Trends = {
  ...provenance,
  timezone: "Australia/Sydney",
  as_of: period.end,
  weeks: 2,
  current_week_partial: true,
  overall: [point, { ...point, week_start: "2026-10-05" }],
  by_property: [{ property_id: "chateau-de-venus", name: "Darling Harbour", points: [point, { ...point, week_start: "2026-10-05" }] }],
  excluded_undated: 0,
};

export const topics: Topics = {
  ...provenance,
  timezone: "Australia/Sydney",
  as_of: period.end,
  window: period,
  window_weeks: 4,
  method: "approximate keyword-based topics; VADER text sentiment",
  total_reviews: 10,
  negative_reviews: 2,
  top_negative_topics: [{ topic: "Noise", count: 2, pct_of_negative: 100 }],
  cleanliness_share_of_negative: { negative_with_cleanliness: 0, negative_reviews: 2, pct: 0, available: true },
  worst_topic_by_property: [{ property_id: "chateau-de-venus", name: "Darling Harbour", topic: "Noise", count: 2, negative_reviews: 2, pct_of_negative: 100 }],
  rising_topics: [{ topic: "Noise", recent_count: 2, prior_count: 0, change: 2, recent_pct_of_negative: 100, prior_pct_of_negative: null }],
  rising_periods: { recent: period, prior: period },
  examples: [{ topic: "Noise", reviews: [{ id: 1, property_id: "chateau-de-venus", review_title: "Loud", review_text: "Very noisy at night.", rating: 4, published_at: period.end, sentiment_score: -0.5, data_source: "synthetic" }] }],
  excluded_undated: 0,
};

const health: CollectionHealth = {
  ...provenance,
  adapter: "manual",
  live_collection_supported: false,
  live_collection_note: "Live collection is disabled.",
  properties: [
    {
      property_id: "chateau-de-venus",
      name: "Darling Harbour",
      last_success_at: period.end,
      latest_run: { id: 1, property_id: "chateau-de-venus", adapter: "import", started_at: period.end, finished_at: period.end, status: "partial", discovered_count: 5, inserted_count: 4, duplicate_count: 0, error_count: 1, error_summary: "1 invalid row" },
      review_count: 10,
      recent_errors: ["1 invalid row"],
    },
  ],
};

function mockAll() {
  mockFetch({
    "/api/properties": () => properties,
    "/api/analytics/summary": () => summary(),
    "/api/analytics/properties": () => comparison,
    "/api/analytics/trends": () => trends,
    "/api/analytics/topics": () => topics,
    "/api/reviews": () => reviewPage([review(1), review(2, { sentiment_label: "negative", language: "fr" })]),
    "/api/collection/health": () => health,
    "/api/import/reviews": () => importResult,
  });
}

async function expectNoViolations(ui: ReactElement, ready: string) {
  const { container } = renderWithSWR(<main>{ui}</main>);
  await screen.findAllByText(ready);
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false } } });
  const summaryText = results.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  expect(summaryText).toEqual([]);
}

beforeEach(() => {
  setUrl("/");
  mockAll();
});

test.each([
  ["overview", <OverviewView key="o" />, "Darling Harbour"],
  ["properties", <PropertiesView key="p" />, "Comparison table"],
  ["reviews", <ReviewsView key="r" />, "Title 2"],
  ["trends", <TrendsView key="t" />, "Show data table"],
  ["insights", <InsightsView key="i" />, "Very noisy at night."],
  ["data", <DataView key="d" />, "1 invalid row"],
])("%s view has no axe violations", async (_name, ui, ready) => {
  await expectNoViolations(ui, ready);
});

test("navigation and global filters have no axe violations", async () => {
  await expectNoViolations(
    <>
      <SyntheticDataBanner />
      <nav aria-label="Main">
        <NavLinks />
      </nav>
      <PropertyFilter />
    </>,
    "Central Sydney",
  );
  expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("button", { name: "All properties" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("note")).toHaveTextContent(/Synthetic demo data/);
});

test("insights shows N/A when there are no negative reviews", async () => {
  mockFetch({
    "/api/analytics/topics": () => ({
      ...topics,
      negative_reviews: 0,
      top_negative_topics: [],
      cleanliness_share_of_negative: { negative_with_cleanliness: 0, negative_reviews: 0, pct: null, available: false },
      rising_topics: [],
      examples: [],
    }),
  });
  renderWithSWR(<InsightsView />);
  expect(await screen.findByText("N/A")).toBeInTheDocument();
  expect(screen.getByText("0 of 0 negative reviews")).toBeInTheDocument();
  expect(screen.getByText("No topics detected in negative reviews")).toBeInTheDocument();
  expect(screen.getByText(/Approximate\./)).toBeInTheDocument();
});

test("property filter toggles update the URL", async () => {
  const { default: userEvent } = await import("@testing-library/user-event");
  setUrl("/reviews", "page=3&sentiment=negative");
  renderWithSWR(<PropertyFilter />);
  await userEvent.click(await screen.findByRole("button", { name: "Central Sydney" }));
  const { lastReplaceParams } = await import("@/test/utils");
  const params = lastReplaceParams();
  expect(params.get("properties")).toBe("venus-surry-hills");
  expect(params.get("sentiment")).toBe("negative");
  expect(params.get("page")).toBeNull();
});
