"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SeverityBadge } from "@/components/SeverityBadge";
import { api, ApiError } from "@/lib/api";
import type { IncidentPublic } from "@/lib/types";

export default function Dashboard() {
  const [incidents, setIncidents] = useState<IncidentPublic[] | null>(null);
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      const rows = await api.listIncidents();
      setIncidents(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API.");
      setIncidents([]);
    }
  }

  useEffect(() => {
    refresh();
    api
      .listScenarios()
      .then((rows) => {
        setScenarios(rows);
        if (rows.length > 0) setSelectedScenario(rows[0]);
      })
      .catch(() => {});
  }, []);

  async function handleCreate() {
    if (!selectedScenario) return;
    setCreating(true);
    try {
      await api.createIncident(selectedScenario);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create incident.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="panel-title">Generate Incident</div>
        <div className="row">
          <select value={selectedScenario} onChange={(e) => setSelectedScenario(e.target.value)}>
            {scenarios.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button onClick={handleCreate} disabled={creating || !selectedScenario}>
            {creating ? "Generating…" : "Generate"}
          </button>
        </div>
        <p className="small dim" style={{ marginTop: 10, marginBottom: 0 }}>
          Deterministically synthesizes a reproducible incident from a failure scenario — see{" "}
          <code>simulator/failure_injector/</code>. Ground truth is never exposed here.
        </p>
      </div>

      <div className="panel">
        <div className="panel-title">Incidents</div>

        {error && (
          <div className="error-box" style={{ marginBottom: 12 }}>
            {error}
          </div>
        )}

        {incidents === null && <p className="dim">Loading…</p>}
        {incidents !== null && incidents.length === 0 && !error && (
          <p className="dim">No incidents yet — generate one above.</p>
        )}

        <div>
          {incidents?.map((incident) => (
            <div className="incident-row" key={incident.incident_id}>
              <div>
                <div className="row" style={{ marginBottom: 4 }}>
                  <span className="mono" style={{ fontWeight: 700 }}>
                    {incident.incident_id}
                  </span>
                  <SeverityBadge severity={incident.severity} />
                  <span className="dim">{incident.service}</span>
                </div>
                <div className="small dim">{incident.description}</div>
              </div>
              <Link href={`/incidents/${incident.incident_id}`} className="btn secondary">
                Investigate →
              </Link>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
