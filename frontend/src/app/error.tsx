"use client";

import { useEffect } from "react";

export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-red-900">
      <h1 className="text-lg font-semibold">This page failed to load</h1>
      <p className="mt-1 text-sm">An unexpected error occurred while rendering. You can try again.</p>
      <button
        type="button"
        onClick={() => retry()}
        className="mt-4 rounded-md bg-white px-3 py-1.5 text-sm font-medium ring-1 ring-red-300 hover:bg-red-100"
      >
        Try again
      </button>
    </div>
  );
}
