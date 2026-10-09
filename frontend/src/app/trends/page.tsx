import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/page-skeleton";
import { TrendsView } from "@/views/trends";

export const metadata: Metadata = { title: "Trends" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <TrendsView />
    </Suspense>
  );
}
