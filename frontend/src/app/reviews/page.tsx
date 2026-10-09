import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/page-skeleton";
import { ReviewsView } from "@/views/reviews";

export const metadata: Metadata = { title: "Reviews" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ReviewsView />
    </Suspense>
  );
}
