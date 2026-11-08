import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "don't die",
  description:
    "A public knowledge base for life-extension medical science: the evidence, gathered and organized.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
