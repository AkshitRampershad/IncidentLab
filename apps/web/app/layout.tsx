import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "IncidentLab",
  description: "Open-source multi-agent incident investigation & evaluation lab",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
