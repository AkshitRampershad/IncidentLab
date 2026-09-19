"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { SeverityBadge } from "@/components/SeverityBadge";
import { api, ApiError } from "@/lib/api";
import type { IncidentPublic } from "@/lib/types";

function scrollToGenerate(e: React.MouseEvent) {
  e.preventDefault();
  document.getElementById("generate")?.scrollIntoView({ behavior: "smooth" });
}

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
      <section className="hero-block">
        <h1>When something breaks in production, someone has to explain why — fast, and correctly.</h1>
        <p className="lede">
          IncidentLab investigates production incidents automatically: it reads the real logs,
          metrics, and deployment history, and hands your team a root cause with the evidence
          behind it — so the person on call isn&apos;t starting from a blank dashboard at 2am.
        </p>
        <div className="hero-actions">
          <a href="#generate" className="btn" onClick={scrollToGenerate}>
            ▶ Generate an incident
          </a>
          <Link href="/evaluation" className="btn secondary">
            See the evaluation results
          </Link>
        </div>
      </section>

      <section className="story-block">
        <div className="story-label problem">The problem</div>
        <h2 className="story-title">
          Every minute spent figuring out &quot;why&quot; is a minute the outage keeps costing
          you.
        </h2>
        <p className="story-body">
          When production breaks, the hard part usually isn&apos;t a lack of data — it&apos;s
          finding the one signal, buried across logs, metrics, and deploy history, that actually
          explains what happened. That work happens under pressure, often by whoever&apos;s on
          call that week, while stakeholders are asking for an update.
        </p>
        <p className="story-body">
          <strong>
            A wrong, confidently-stated guess doesn&apos;t just waste time — it sends the response
            down the wrong path while the outage keeps running.
          </strong>
        </p>
      </section>

      <section className="story-block">
        <div className="story-label status-quo">How teams handle this today</div>
        <h2 className="story-title">
          Most teams stitch the answer together by hand, under pressure, every time.
        </h2>
        <div className="quo-grid">
          <div className="quo-card">
            <div className="ic">📓</div>
            <h4>Tribal knowledge &amp; runbooks</h4>
            <p>
              Institutional memory that lives in a wiki, a Slack thread, or one engineer&apos;s
              head — only as good as whoever last updated it.
            </p>
          </div>
          <div className="quo-card">
            <div className="ic">🪟</div>
            <h4>Manual correlation across tools</h4>
            <p>
              Tabbing between a log aggregator, a metrics dashboard, and a deploy history by hand,
              while the clock on the outage keeps running.
            </p>
          </div>
          <div className="quo-card">
            <div className="ic">💬</div>
            <h4>A chatbot pointed at the incident</h4>
            <p>
              Increasingly, teams ask an LLM to summarize what&apos;s wrong — but a model that
              free-associates a plausible cause from a text summary can sound certain and still be
              wrong.
            </p>
          </div>
        </div>
      </section>

      <section className="story-block">
        <div className="story-label solution">Our solution</div>
        <h2 className="story-title">Automate the correlation. Never automate the judgment.</h2>
        <p className="story-body">
          IncidentLab runs several specialized investigators in parallel — over logs, metrics,
          recent deploys, and past runbooks — each pulling real, citable evidence instead of
          summarizing from memory. That evidence is combined by a fixed, deterministic scoring
          system into one ranked root cause with a confidence number attached to it.
        </p>
        <div className="flow">
          <div className="flow-step">Real evidence in</div>
          <div className="flow-arrow">→</div>
          <div className="flow-step">Deterministic scoring</div>
          <div className="flow-arrow">→</div>
          <div className="flow-step result">Root cause + confidence out</div>
        </div>
        <p className="story-body">
          If a language model is involved anywhere in the pipeline, it only writes the
          plain-English summary sentence — <strong>it never gets a vote on the actual verdict.</strong>{" "}
          And when the evidence genuinely doesn&apos;t support a confident answer, IncidentLab says
          so and flags it for a human, instead of forcing a guess.
        </p>
      </section>

      <section className="story-block">
        <div className="story-label">How it fits into your systems</div>
        <h2 className="story-title">Built on the same evidence your stack already produces.</h2>
        <p className="story-body">
          IncidentLab reasons over three data types nearly every engineering org already
          generates today:
        </p>
        <div className="stack-row">
          <div className="stack-chip">🪵 Application &amp; service logs</div>
          <div className="stack-chip">📈 Metrics &amp; alerting data</div>
          <div className="stack-chip">🚀 Deployment / CI history</div>
          <div className="stack-chip">📚 Runbooks &amp; past incidents</div>
        </div>
        <p className="story-body">
          Each investigator talks to its evidence source through a small, swappable tool
          interface — so pointing it at a real log platform, metrics system, or CI pipeline
          instead of this project&apos;s own reproducible incident simulator is an integration,
          not a rewrite of the reasoning engine underneath.
        </p>
        <div className="honesty-note">
          Today, IncidentLab is a research/evaluation build: it&apos;s exercised against a
          deterministic incident simulator (and, separately, real telemetry imported from public
          chaos-engineering datasets) — not yet wired into a live Datadog/Splunk/PagerDuty stack.
          The architecture is built for that integration; it hasn&apos;t shipped yet.
        </div>
      </section>

      <section className="story-block">
        <div className="story-label">Proof, not just a promise</div>
        <h2 className="story-title">We also measure whether the added complexity is worth it.</h2>
        <p className="story-body">
          A multi-agent system is more expensive to run than a single model call. IncidentLab
          ships a benchmark comparing three architectures — a direct LLM call, a single agent, and
          the full multi-agent pipeline — against the same held-out incidents, scored on real
          metrics instead of a demo that only shows the best case.
        </p>
        <div className="proof-stats">
          <div className="pstat">
            <div className="n">3</div>
            <div className="l">architectures benchmarked head-to-head</div>
          </div>
          <div className="pstat">
            <div className="n">↓</div>
            <div className="l">false-confidence rate is a scored metric, not an afterthought</div>
          </div>
          <div className="pstat">
            <div className="n">✓</div>
            <div className="l">results published even where multi-agent doesn&apos;t win</div>
          </div>
        </div>
      </section>

      <div className="story-label" style={{ marginTop: 46, marginBottom: 4 }}>
        Try it yourself — no setup, no API key
      </div>

      <div className="panel" id="generate">
        <div className="panel-title">Generate an incident</div>
        <p className="small faint" style={{ marginTop: 0, marginBottom: 14 }}>
          Creates a realistic, reproducible incident so you can see the full investigation, start
          to finish — see <code>simulator/failure_injector/</code>. Ground truth is never exposed
          here.
        </p>
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
          <div className="empty-state">
            <div className="icon">◎</div>
            <strong>No incidents yet</strong>
            <p>Generate one above to see it investigated live — takes about 10 seconds.</p>
          </div>
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
