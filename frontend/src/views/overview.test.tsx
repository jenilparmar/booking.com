import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { emptyStats, summary } from "@/test/fixtures";
import { json, mockFetch, renderWithSWR, setUrl } from "@/test/utils";
import type { Comparison } from "@/lib/types";

import { OverviewView } from "./overview";

const comparison: Comparison = {
  data_sources: ["synthetic"],
  contains_synthetic: true,
  timezone: "Australia/Sydney",
  as_of: "2026-10-09T06:00:00Z",
  window: { start: "2026-09-13T14:00:00Z", end: "2026-10-09T06:00:00Z" },
  window_weeks: 4,
  current_period: { start: "2026-10-04T13:00:00Z", end: "2026-10-09T06:00:00Z" },
  previous_period: { start: "2026-09-27T14:00:00Z", end: "2026-10-02T06:00:00Z" },
  properties: [
    {
      property_id: "chateau-de-venus",
      name: "Darling Harbour",
      window: { reviews: 39, avg_rating: 7.8, rated_reviews: 38, positive: 35, neutral: 3, negative: 1, pct_negative: 2.6 },
      current_week: emptyStats,
      previous_week: emptyStats,
      avg_rating_change: null,
      top_complaint: null,
    },
  ],
  excluded_undated: 0,
};

beforeEach(() => setUrl("/"));

test("renders KPIs and the property comparison", async () => {
  mockFetch({ "/api/analytics/summary": () => summary(), "/api/analytics/properties": () => comparison });
  renderWithSWR(<OverviewView />);
  expect(await screen.findByText("8.0")).toBeInTheDocument();
  expect(await screen.findByText("Darling Harbour")).toBeInTheDocument();
  expect(screen.getByText("No topic detected")).toBeInTheDocument();
});

test("shows N/A for a property with no reviews this week", async () => {
  mockFetch({ "/api/analytics/summary": () => summary(), "/api/analytics/properties": () => comparison });
  renderWithSWR(<OverviewView />);
  await screen.findByText("Darling Harbour");
  expect(screen.getAllByText("N/A").length).toBeGreaterThanOrEqual(2);
});

test("summary error can be retried independently", async () => {
  let calls = 0;
  mockFetch({
    "/api/analytics/summary": () => {
      calls += 1;
      return calls === 1 ? json({ error: { code: "x", message: "Temporarily unavailable", details: null } }, 500) : summary();
    },
    "/api/analytics/properties": () => comparison,
  });
  renderWithSWR(<OverviewView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Temporarily unavailable");
  expect(await screen.findByText("Darling Harbour")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("8.0")).toBeInTheDocument();
});

test("network failure shows a helpful message", async () => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
  renderWithSWR(<OverviewView />);
  const alerts = await screen.findAllByRole("alert");
  expect(alerts[0]).toHaveTextContent(/Could not reach the API/);
});
