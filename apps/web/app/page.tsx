"use client";

import { useEffect, useState } from "react";

type HealthStatus = "checking" | "ok" | "unreachable";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => (res.ok ? setStatus("ok") : setStatus("unreachable")))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "3rem" }}>
      <h1>IncidentLab</h1>
      <p>Open-source multi-agent incident investigation &amp; evaluation lab.</p>
      <p>
        API status: <strong>{status}</strong>
      </p>
    </main>
  );
}
