import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { json, lastReplaceParams, mockFetch, nav, renderWithSWR, setUrl } from "@/test/utils";
import { review, reviewPage } from "@/test/fixtures";

import { ReviewsView, SEARCH_DEBOUNCE_MS } from "./reviews";

beforeEach(() => setUrl("/reviews"));

test("shows a loading state, then the reviews", async () => {
  let release!: () => void;
  const gate = new Promise<void>((r) => (release = r));
  mockFetch({
    "/api/reviews": async () => {
      await gate;
      return reviewPage([review(1), review(2, { sentiment_label: "negative", review_title: "Noisy" })]);
    },
  });
  renderWithSWR(<ReviewsView />);
  expect(screen.getByRole("status")).toHaveTextContent(/Loading reviews/);
  release();
  expect(await screen.findByText("Noisy")).toBeInTheDocument();
  expect(screen.getByText(/2 reviews · page 1 of 1/)).toBeInTheDocument();
  expect(screen.getAllByText("Synthetic").length).toBeGreaterThan(0);
});

test("sends URL filters to the API", async () => {
  setUrl("/reviews", "properties=venus-surry-hills&sentiment=negative&topic=Noise&page=2");
  const fetch = mockFetch({ "/api/reviews": () => reviewPage([review(1)], { page: 2, total: 21, total_pages: 2 }) });
  renderWithSWR(<ReviewsView />);
  await screen.findByText("Title 1");
  const url = new URL(String(fetch.mock.calls[0][0]), "http://localhost");
  expect(url.searchParams.get("property_ids")).toBe("venus-surry-hills");
  expect(url.searchParams.get("sentiment")).toBe("negative");
  expect(url.searchParams.get("topic")).toBe("Noise");
  expect(url.searchParams.get("page")).toBe("2");
  expect(url.searchParams.get("page_size")).toBe("20");
});

test("empty state offers to clear filters", async () => {
  setUrl("/reviews", "sentiment=negative");
  mockFetch({ "/api/reviews": () => reviewPage([]) });
  renderWithSWR(<ReviewsView />);
  expect(await screen.findByText("No reviews match these filters")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /Clear filters/ })).toHaveLength(2);
});

test("error state retries the request", async () => {
  let calls = 0;
  mockFetch({
    "/api/reviews": () => {
      calls += 1;
      return calls === 1
        ? json({ error: { code: "internal_error", message: "Database unavailable.", details: null } }, 503)
        : reviewPage([review(7)]);
    },
  });
  renderWithSWR(<ReviewsView />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable.");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("Title 7")).toBeInTheDocument();
  expect(calls).toBe(2);
});

test("clear filters resets review filters but keeps the property selection", async () => {
  setUrl("/reviews", "properties=chateau-de-venus&q=noise&sentiment=negative&rating_min=3&sort=oldest&page=3");
  mockFetch({ "/api/reviews": () => reviewPage([review(1)]) });
  renderWithSWR(<ReviewsView />);
  await screen.findByText("Title 1");
  await userEvent.click(screen.getByRole("button", { name: "Clear filters (3)" }));
  const params = lastReplaceParams();
  expect(nav.replace.mock.calls.at(-1)?.[0]).toBe("/reviews?properties=chateau-de-venus");
  expect(params.get("q")).toBeNull();
  expect(params.get("page")).toBeNull();
});

test("changing a filter resets to page 1", async () => {
  setUrl("/reviews", "sentiment=negative&page=4");
  mockFetch({ "/api/reviews": () => reviewPage([review(1)]) });
  renderWithSWR(<ReviewsView />);
  await screen.findByText("Title 1");
  fireEvent.change(screen.getByLabelText("Topic"), { target: { value: "Noise" } });
  const params = lastReplaceParams();
  expect(params.get("topic")).toBe("Noise");
  expect(params.get("sentiment")).toBe("negative");
  expect(params.get("page")).toBeNull();
});

test("pagination keeps the active filters", async () => {
  setUrl("/reviews", "properties=venus-surry-hills&sentiment=negative&q=dirty");
  mockFetch({
    "/api/reviews": () => reviewPage([review(1)], { total: 45, total_pages: 3 }),
  });
  renderWithSWR(<ReviewsView />);
  await screen.findByText("Page 1 of 3");
  expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
  const params = lastReplaceParams();
  expect(params.get("page")).toBe("2");
  expect(params.get("sentiment")).toBe("negative");
  expect(params.get("q")).toBe("dirty");
  expect(params.get("properties")).toBe("venus-surry-hills");
});

test("search is debounced before updating the URL", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  mockFetch({ "/api/reviews": () => reviewPage([review(1)]) });
  renderWithSWR(<ReviewsView />);
  await screen.findByText("Title 1");
  fireEvent.change(screen.getByLabelText("Search reviews"), { target: { value: "noi" } });
  fireEvent.change(screen.getByLabelText("Search reviews"), { target: { value: "noisy" } });
  expect(nav.replace).not.toHaveBeenCalled();
  await act(async () => {
    vi.advanceTimersByTime(SEARCH_DEBOUNCE_MS + 10);
  });
  await waitFor(() => expect(nav.replace).toHaveBeenCalledTimes(1));
  expect(lastReplaceParams().get("q")).toBe("noisy");
});
