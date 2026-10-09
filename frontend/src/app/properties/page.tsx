import type { Metadata } from "next";
import { Suspense } from "react";

import { PageSkeleton } from "@/components/page-skeleton";
import { PropertiesView } from "@/views/properties";

export const metadata: Metadata = { title: "Properties" };

export default function Page() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <PropertiesView />
    </Suspense>
  );
}
