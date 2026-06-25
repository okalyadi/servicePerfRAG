import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "servicePerfRAG",
  description: "AI Performance Testing Assistant",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
