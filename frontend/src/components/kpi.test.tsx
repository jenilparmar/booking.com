import { render, screen, within } from "@testing-library/react";

import { emptyStats, summary } from "@/test/fixtures";

import { SummaryKpis } from "./kpi";

function card(label: string) {
  return screen.getByText(label, { selector: "span" }).closest("div.rounded-xl") as HTMLElement;
}

test("shows values with their denominators", () => {
  render(<SummaryKpis summary={summary()} />);
  const rating = within(card("Average rating"));
  expect(rating.getByText("8.0")).toBeInTheDocument();
  expect(rating.getByText(/from 23 rated reviews/)).toBeInTheDocument();
  expect(rating.getByText(/\+1\.1 vs last week \(6\.9\)/)).toBeInTheDocument();
  expect(within(card("Negative reviews")).getByText("4 of 26 reviews")).toBeInTheDocument();
  expect(within(card("Top complaint")).getByText("Facilities")).toBeInTheDocument();
});

test("renders N/A instead of zero when there is no data", () => {
  render(
    <SummaryKpis
      summary={summary({
        current: emptyStats,
        previous: emptyStats,
        avg_rating_change: null,
        review_count_change: 0,
        pct_negative_change: null,
        top_negative_topic: null,
      })}
    />,
  );
  expect(within(card("Average rating")).getByText("N/A")).toBeInTheDocument();
  expect(within(card("Average rating")).getByText(/No rated reviews last week/)).toBeInTheDocument();
  expect(within(card("Negative reviews")).getByText("N/A")).toBeInTheDocument();
  expect(within(card("Top complaint")).getByText("N/A")).toBeInTheDocument();
  expect(within(card("Top complaint")).getByText("No negative reviews this week")).toBeInTheDocument();
  expect(within(card("Reviews this week")).getByText("0")).toBeInTheDocument();
});

test("KPI help is reachable from the keyboard", async () => {
  const { default: userEvent } = await import("@testing-library/user-event");
  const user = userEvent.setup();
  render(<SummaryKpis summary={summary()} />);
  await user.tab();
  expect(screen.getByRole("tooltip")).toHaveTextContent(/Mean of review ratings/);
});
