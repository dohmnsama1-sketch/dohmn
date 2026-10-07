import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CultureOS — Cultural Launch Intelligence",
  description:
    "A Qloo-grounded cultural intelligence agent for stress-testing product and brand launch concepts."
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
