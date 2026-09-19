import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "IncidentLab",
  description: "Open-source multi-agent incident investigation & evaluation lab",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <div className="topbar">
            <Link href="/" className="brand">
              Incident<span>Lab</span>
            </Link>
            <nav className="nav">
              <Link href="/">Incidents</Link>
              <Link href="/evaluation">Evaluation</Link>
              <a
                className="nav-cta"
                href="https://github.com/AkshitRampershad/incidentlab"
                target="_blank"
                rel="noopener noreferrer"
              >
                View on GitHub
              </a>
            </nav>
          </div>
          {children}
        </div>
      </body>
    </html>
  );
}
