"use client";

import { useId } from "react";

import { useUrlState } from "@/lib/url-state";

export function useWeeks(defaultWeeks: number, options: number[]) {
  const { searchParams, setParams } = useUrlState();
  const raw = Number(searchParams.get("weeks"));
  const weeks = options.includes(raw) ? raw : defaultWeeks;
  return { weeks, setWeeks: (w: number) => setParams({ weeks: w === defaultWeeks ? null : String(w) }) };
}

export function WeeksSelect({
  value,
  options,
  onChange,
}: {
  value: number;
  options: number[];
  onChange: (w: number) => void;
}) {
  const id = useId();
  return (
    <div className="flex items-center gap-2 text-sm">
      <label htmlFor={id} className="text-slate-600">
        Window
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="rounded-md border border-slate-300 bg-white px-2 py-1"
      >
        {options.map((w) => (
          <option key={w} value={w}>
            Last {w} weeks
          </option>
        ))}
      </select>
    </div>
  );
}
