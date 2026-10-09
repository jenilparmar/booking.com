"use client";

import { useProperties } from "@/lib/hooks";
import { useGlobalFilters } from "@/lib/url-state";

import { cx, Skeleton } from "./ui";

const chip = "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors";
const on = "bg-brand-600 text-white ring-brand-600";
const off = "bg-white text-slate-700 ring-slate-300 hover:bg-slate-100";

export function PropertyFilter() {
  const { data, error } = useProperties();
  const { properties, setProperties } = useGlobalFilters();

  if (error) return null;
  if (!data) return <Skeleton className="h-7 w-80" />;

  const toggle = (id: string) =>
    setProperties(properties.includes(id) ? properties.filter((p) => p !== id) : [...properties, id]);

  return (
    <div role="group" aria-label="Filter by property" className="flex flex-wrap items-center gap-1.5">
      <button type="button" aria-pressed={properties.length === 0} onClick={() => setProperties([])} className={cx(chip, properties.length === 0 ? on : off)}>
        All properties
      </button>
      {data.items.map((p) => {
        const active = properties.includes(p.id);
        return (
          <button key={p.id} type="button" aria-pressed={active} onClick={() => toggle(p.id)} className={cx(chip, active ? on : off)}>
            {p.name}
          </button>
        );
      })}
    </div>
  );
}

export function SyntheticDataBanner() {
  const { data } = useProperties();
  if (!data?.contains_synthetic) return null;
  return (
    <div role="note" className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-900 sm:px-6">
      <strong className="font-semibold">Synthetic demo data.</strong> Some or all reviews shown were
      generated for demonstration and are not real guest reviews. Each record is labelled with its
      data source.
    </div>
  );
}
