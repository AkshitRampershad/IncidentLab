"use client";

import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { BenchmarkReport } from "@/lib/types";

const DISPLAY_NAMES: Record<string, string> = {
  direct_llm: "Direct LLM",
  single_agent: "Single Agent",
  multi_agent: "Multi-Agent",
};

const METRIC_COLUMNS: Array<{
  key: keyof BenchmarkReport["architectures"][number];
  label: string;
  format: (v: number) => string;
}> = [
  { key: "root_cause_accuracy", label: "RCA Accuracy", format: (v) => `${Math.round(v * 100)}%` },
  { key: "evidence_recall", label: "Evidence Recall", format: (v) => `${Math.round(v * 100)}%` },
  {
    key: "evidence_precision",
    label: "Evidence Precision",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "unsupported_claim_rate",
    label: "Unsupported Claims",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "false_confidence_rate",
    label: "False Confidence",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "human_escalation_rate",
    label: "Human Escalation",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  { key: "avg_latency_seconds", label: "Avg Latency", format: (v) => `${v.toFixed(2)}s` },
];

export default function EvaluationPage() {
  const [instancesPerScenario, setInstancesPerScenario] = useState(3);
  const [report, setReport] = useState<BenchmarkReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.runEvaluation(instancesPerScenario);
      setReport(result.report);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Benchmark run failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="panel">
        <div className="panel-title">Run Benchmark</div>
        <p className="dim small" style={{ marginTop: 0 }}>
          Compares Direct LLM (no tools), Single Agent (all tools, no hypothesis correlation), and
          the real Multi-Agent system against the same generated dataset, scored against ground
          truth none of them see. See <code>docs/design-decisions.md</code> (DDR-017) — this
          dataset is small and honestly disclosed as such, not padded to look bigger.
        </p>
        <div className="row">
          <label className="small dim">Instances per scenario</label>
          <input
            type="number"
            min={1}
            max={10}
            value={instancesPerScenario}
            onChange={(e) => setInstancesPerScenario(Number(e.target.value))}
            style={{ width: 60 }}
          />
          <button onClick={run} disabled={running}>
            {running ? "Running…" : "Run Benchmark"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {report && (
        <div className="panel">
          <div className="panel-title">Results — {report.dataset_size} incidents</div>
          <table>
            <thead>
              <tr>
                <th>Architecture</th>
                {METRIC_COLUMNS.map((c) => (
                  <th key={c.key}>{c.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.architectures.map((arch) => (
                <tr key={arch.architecture}>
                  <td style={{ fontWeight: 600 }}>
                    {DISPLAY_NAMES[arch.architecture] ?? arch.architecture}
                  </td>
                  {METRIC_COLUMNS.map((c) => (
                    <td key={c.key} className="mono">
                      {c.format(arch[c.key] as number)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
