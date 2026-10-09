import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Review Insights",
  description: "Weekly guest review analytics for four Sydney properties",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">{children}</body>
    </html>
  );
}
