import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/page-skeleton";
import { InsightsView } from "@/views/insights";

export const metadata: Metadata = { title: "Insights" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <InsightsView />
    </Suspense>
  );
}
