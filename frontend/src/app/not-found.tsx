import Link from "next/link";

export default function NotFound() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h1 className="text-lg font-semibold">Page not found</h1>
      <p className="mt-1 text-sm text-slate-600">That page doesn&apos;t exist.</p>
      <Link href="/" className="mt-4 inline-block text-sm font-medium text-brand-600 hover:underline">
        Back to overview
      </Link>
    </div>
  );
}
