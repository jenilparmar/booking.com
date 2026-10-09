import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/page-skeleton";
import { DataView } from "@/views/data";

export const metadata: Metadata = { title: "Data & import" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <DataView />
    </Suspense>
  );
}
