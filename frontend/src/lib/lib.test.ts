import { buildQuery } from "./api";
import { formatDate, formatPct, formatRating, formatSigned, formatWeek, NA } from "./format";
import { hrefWithGlobals, mergeParams, splitList } from "./url-state";

describe("format", () => {
  test("null values render as N/A", () => {
    expect(formatRating(null)).toBe(NA);
    expect(formatPct(undefined)).toBe(NA);
    expect(formatSigned(null)).toBe(NA);
    expect(formatDate(null)).toBe(NA);
  });

  test("numbers are formatted with fixed precision and sign", () => {
    expect(formatRating(7.25)).toBe("7.3");
    expect(formatPct(15.384)).toBe("15.4%");
    expect(formatSigned(1.2)).toBe("+1.2");
    expect(formatSigned(-0.3)).toBe("-0.3");
    expect(formatSigned(0)).toBe("±0.0");
    expect(formatSigned(-2, 1, " pts")).toBe("-2.0 pts");
  });

  test("dates use the Sydney business timezone regardless of the host", () => {
    // 2026-10-04T14:30Z is already Monday 5 Oct in Sydney (UTC+11).
    expect(formatDate("2026-10-04T14:30:00Z")).toBe("5 Oct 2026");
    expect(formatWeek("2026-10-05")).toBe("5 Oct");
  });
});

describe("url state", () => {
  test("mergeParams sets, joins and deletes keys", () => {
    const next = mergeParams(new URLSearchParams("a=1&b=2"), { a: null, c: ["x", "y"], d: "" });
    expect(next.toString()).toBe("b=2&c=x%2Cy");
  });

  test("hrefWithGlobals keeps only the global params", () => {
    const sp = new URLSearchParams("properties=a,b&q=noise&page=3&as_of=2026-10-09");
    expect(hrefWithGlobals("/trends", sp)).toBe("/trends?properties=a%2Cb&as_of=2026-10-09");
    expect(hrefWithGlobals("/trends", new URLSearchParams("q=x"))).toBe("/trends");
  });

  test("splitList ignores blanks", () => {
    expect(splitList(" a, ,b ")).toEqual(["a", "b"]);
    expect(splitList(null)).toEqual([]);
  });
});

test("buildQuery skips empty values and joins lists", () => {
  expect(buildQuery({ a: null, b: "", c: [], d: ["x", "y"], e: 2 })).toBe("?d=x%2Cy&e=2");
  expect(buildQuery({})).toBe("");
});
