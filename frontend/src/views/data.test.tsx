import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { importResult } from "@/test/fixtures";
import { json, mockFetch, renderWithSWR, setUrl } from "@/test/utils";

import { ImportForm, MAX_UPLOAD_BYTES, validateFile } from "./data";

beforeEach(() => setUrl("/data"));

function file(name: string, size = 10, type = "text/csv") {
  const f = new File(["x".repeat(Math.min(size, 10))], name, { type });
  Object.defineProperty(f, "size", { value: size });
  return f;
}

test("validateFile checks presence, type and size", () => {
  expect(validateFile(null)).toMatch(/Choose a CSV or JSON/);
  expect(validateFile(file("a.txt"))).toMatch(/Only .csv and .json/);
  expect(validateFile(file("a.csv", 0))).toMatch(/empty/);
  expect(validateFile(file("a.csv", MAX_UPLOAD_BYTES + 1))).toMatch(/too large/);
  expect(validateFile(file("A.JSON", 100, "application/json"))).toBeNull();
});

test("rejects unsupported files without calling the API", async () => {
  const fetch = mockFetch({});
  const user = userEvent.setup({ applyAccept: false });
  renderWithSWR(<ImportForm />);
  await user.upload(screen.getByLabelText("Review file"), file("notes.txt", 10, "text/plain"));
  expect(screen.getByRole("alert")).toHaveTextContent("Only .csv and .json files are supported.");
  await user.click(screen.getByRole("button", { name: "Import reviews" }));
  expect(fetch).not.toHaveBeenCalled();
});

test("successful import shows the returned counts", async () => {
  const fetch = mockFetch({ "/api/import/reviews": () => importResult });
  const user = userEvent.setup();
  renderWithSWR(<ImportForm />);
  await user.upload(screen.getByLabelText("Review file"), file("reviews.csv"));
  await user.click(screen.getByRole("button", { name: "Import reviews" }));
  const status = await screen.findByText(/Import complete/);
  expect(status).toHaveTextContent("reviews.csv");
  const [, init] = fetch.mock.calls[0];
  expect(init?.method).toBe("POST");
  expect(init?.body).toBeInstanceOf(FormData);
  for (const [label, value] of [["Rows read", "5"], ["Inserted", "4"], ["Duplicates skipped", "1"], ["Invalid rows", "0"]]) {
    expect(screen.getByText(label).nextElementSibling).toHaveTextContent(value);
  }
});

test("server rejection is shown to the user", async () => {
  mockFetch({
    "/api/import/reviews": () =>
      json({ error: { code: "invalid_file", message: "Missing required column: review_text", details: null } }, 400),
  });
  const user = userEvent.setup();
  renderWithSWR(<ImportForm />);
  await user.upload(screen.getByLabelText("Review file"), file("reviews.csv"));
  await user.click(screen.getByRole("button", { name: "Import reviews" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Missing required column: review_text");
});
