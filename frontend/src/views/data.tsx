"use client";

import { useId, useRef, useState, type FormEvent } from "react";
import { useSWRConfig } from "swr";

import { Badge, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, ProvenanceNote } from "@/components/ui";
import { uploadReviews } from "@/lib/api";
import { formatDateTime, plural } from "@/lib/format";
import { useCollectionHealth } from "@/lib/hooks";
import type { ImportResult, RunStatus } from "@/lib/types";

export const MAX_UPLOAD_BYTES = Number(process.env.NEXT_PUBLIC_IMPORT_MAX_BYTES ?? 5 * 1024 * 1024);
const ALLOWED = [".csv", ".json"];

export function validateFile(file: File | null | undefined): string | null {
  if (!file) return "Choose a CSV or JSON file to import.";
  const name = file.name.toLowerCase();
  if (!ALLOWED.some((ext) => name.endsWith(ext))) return "Only .csv and .json files are supported.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > MAX_UPLOAD_BYTES)
    return `The file is too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Maximum is ${(MAX_UPLOAD_BYTES / 1024 / 1024).toFixed(0)} MB.`;
  return null;
}

const STATUS_TONE: Record<RunStatus, "green" | "amber" | "red" | "slate"> = {
  success: "green",
  partial: "amber",
  failed: "red",
  running: "slate",
};

function ImportSummary({ result }: { result: ImportResult }) {
  return (
    <div role="status" className={result.ok ? "rounded-lg border border-green-200 bg-green-50 p-4 text-sm" : "rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm"}>
      <p className="font-medium">
        {result.ok ? "Import complete" : "Import finished with problems"} · {result.filename}
      </p>
      <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {(
          [
            ["Rows read", result.discovered],
            ["Inserted", result.inserted],
            ["Duplicates skipped", result.duplicates],
            ["Invalid rows", result.invalid],
          ] as const
        ).map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-slate-600">{label}</dt>
            <dd className="text-lg font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      {result.failure_message && <p className="mt-2 text-red-800">{result.failure_message}</p>}
      {result.errors.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer font-medium">
            {plural(result.errors.length, "row error")}
            {result.errors_truncated && " (first errors only)"}
          </summary>
          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-xs">
            {result.errors.map((e, i) => (
              <li key={i}>
                Row {e.row}
                {e.field && <> · <code>{e.field}</code></>}: {e.message}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

export function ImportForm() {
  const inputId = useId();
  const hintId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [clientError, setClientError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const { mutate } = useSWRConfig();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = validateFile(file);
    setClientError(problem);
    setSubmitError(null);
    setResult(null);
    if (problem || !file) return;
    setBusy(true);
    try {
      const res = await uploadReviews(file);
      setResult(res);
      if (inputRef.current) inputRef.current.value = "";
      setFile(null);
      await mutate(() => true);
    } catch (err) {
      setSubmitError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-3">
      <div>
        <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-slate-700">
          Review file
        </label>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".csv,.json,text/csv,application/json"
          aria-describedby={hintId}
          aria-invalid={!!clientError}
          onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            setClientError(f ? validateFile(f) : null);
            setResult(null);
            setSubmitError(null);
          }}
          className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:font-medium file:text-brand-700"
        />
        <p id={hintId} className="mt-1 text-xs text-slate-500">
          CSV or JSON, up to {(MAX_UPLOAD_BYTES / 1024 / 1024).toFixed(0)} MB. Required columns: property_id,
          review_text. Optional: source_review_id, review_title, rating, rating_scale_max, published_at,
          language, source (import or synthetic). Duplicates are skipped automatically.
        </p>
      </div>
      {clientError && (
        <p role="alert" className="text-sm text-red-700">
          {clientError}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="rounded-md bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-60"
      >
        {busy ? "Importing…" : "Import reviews"}
      </button>
      {!!submitError && <ErrorState title="Import failed" error={submitError} />}
      {result && <ImportSummary result={result} />}
    </form>
  );
}

export function CollectionHealthPanel() {
  const { data, error, mutate } = useCollectionHealth();
  if (error) return <ErrorState error={error} onRetry={() => mutate()} />;
  if (!data) return <LoadingBlock label="Loading collection health" rows={4} />;
  if (data.properties.length === 0) return <EmptyState title="No properties configured" />;
  return (
    <>
      <div role="note" className="mb-4 rounded-md bg-slate-50 p-3 text-sm text-slate-700">
        <span className="font-medium">
          Live collection: {data.live_collection_supported ? "enabled" : "not available"}
        </span>{" "}
        (adapter <code>{data.adapter}</code>). {data.live_collection_note}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <caption className="sr-only">Collection and import status per property</caption>
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th scope="col" className="py-2 pr-4">Property</th>
              <th scope="col" className="py-2 pr-4 text-right">Reviews stored</th>
              <th scope="col" className="py-2 pr-4">Last successful run</th>
              <th scope="col" className="py-2 pr-4">Latest run</th>
              <th scope="col" className="py-2">Recent errors</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.properties.map((p) => (
              <tr key={p.property_id} className="align-top">
                <th scope="row" className="py-2 pr-4 font-medium text-slate-900">{p.name}</th>
                <td className="py-2 pr-4 text-right tabular-nums">{p.review_count}</td>
                <td className="py-2 pr-4">{p.last_success_at ? formatDateTime(p.last_success_at) : "Never"}</td>
                <td className="py-2 pr-4">
                  {p.latest_run ? (
                    <div className="space-y-0.5">
                      <Badge tone={STATUS_TONE[p.latest_run.status]}>{p.latest_run.status}</Badge>
                      <p className="text-xs text-slate-500">
                        {p.latest_run.adapter} · {formatDateTime(p.latest_run.started_at)}
                      </p>
                      <p className="text-xs text-slate-500">
                        {p.latest_run.inserted_count} new, {p.latest_run.duplicate_count} duplicate, {p.latest_run.error_count} errors
                      </p>
                    </div>
                  ) : (
                    <span className="text-slate-500">No runs yet</span>
                  )}
                </td>
                <td className="py-2 text-xs text-red-800">
                  {p.recent_errors.length ? (
                    <ul className="space-y-0.5">
                      {p.recent_errors.map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-slate-500">None</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ProvenanceNote sources={data.data_sources} />
    </>
  );
}

export function DataView() {
  return (
    <>
      <PageHeader title="Data & import" description="Import review exports and check the status of each data feed." />
      <div className="grid gap-4 xl:grid-cols-[1fr_2fr]">
        <Card title="Import reviews">
          <ImportForm />
        </Card>
        <Card title="Collection health">
          <CollectionHealthPanel />
        </Card>
      </div>
    </>
  );
}
