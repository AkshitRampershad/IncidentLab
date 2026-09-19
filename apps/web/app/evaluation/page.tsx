"use client";

import { useState } from "react";

import { Gloss } from "@/components/Gloss";
import { api, ApiError } from "@/lib/api";
import type { AggregateMetrics, BenchmarkReport } from "@/lib/types";

const DISPLAY_NAMES: Record<string, string> = {
  direct_llm: "Direct LLM",
  single_agent: "Single Agent",
  multi_agent: "Multi-Agent",
};

const ARCH_COST_LABELS: Record<string, string> = {
  direct_llm: "No tools · no evidence retrieval",
  single_agent: "Tools, no cross-source correlation",
  multi_agent: "Full pipeline · agents + adjudication",
};

const METRIC_COLUMNS: Array<{
  key: keyof BenchmarkReport["architectures"][number];
  label: string;
  description: string;
  format: (v: number) => string;
}> = [
  {
    key: "root_cause_accuracy",
    label: "RCA Accuracy",
    description: "Exact match to the incident's true, held-out root cause.",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "evidence_recall",
    label: "Evidence Recall",
    description: "Of the incident's real (non-distractor) evidence, how much did it actually cite?",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "evidence_precision",
    label: "Evidence Precision",
    description: "Of the evidence it cited, how much was genuinely real rather than noise it mistook for support?",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "unsupported_claim_rate",
    label: "Unsupported Claims",
    description: "Asserted a root cause with zero supporting evidence behind it.",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "false_confidence_rate",
    label: "False Confidence",
    description: "High confidence in an answer that turned out to be wrong — the dangerous failure mode.",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "human_escalation_rate",
    label: "Human Escalation",
    description: "Flagged for human review instead of forcing a confident guess.",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "avg_latency_seconds",
    label: "Avg Latency",
    description: "Wall-clock time per investigation.",
    format: (v) => `${v.toFixed(2)}s`,
  },
];

function metricClass(
  value: number,
  values: number[],
  higherIsBetter: boolean,
): "good" | "bad" | "" {
  const best = higherIsBetter ? Math.max(...values) : Math.min(...values);
  const worst = higherIsBetter ? Math.min(...values) : Math.max(...values);
  if (values.length < 2 || best === worst) return "";
  if (value === best) return "good";
  if (value === worst) return "bad";
  return "";
}

function ArchitectureCards({ architectures }: { architectures: AggregateMetrics[] }) {
  const accuracies = architectures.map((a) => a.root_cause_accuracy);
  const winner = architectures.reduce((best, a) =>
    a.root_cause_accuracy > best.root_cause_accuracy ? a : best,
  );

  return (
    <div className="arch-cards">
      {architectures.map((arch) => {
        const falseConfidences = architectures.map((a) => a.false_confidence_rate);
        const accClass = metricClass(arch.root_cause_accuracy, accuracies, true);
        const fcClass = metricClass(arch.false_confidence_rate, falseConfidences, false);
        const isWinner = arch === winner;
        return (
          <div className={`arch-card${isWinner ? " winner" : ""}`} key={arch.architecture}>
            {isWinner && <span className="winner-tag">Best on this run</span>}
            <h3>{DISPLAY_NAMES[arch.architecture] ?? arch.architecture}</h3>
            <div className="cost">{ARCH_COST_LABELS[arch.architecture] ?? ""}</div>
            <div className="big-metric">
              <div className={`n ${accClass}`}>{Math.round(arch.root_cause_accuracy * 100)}%</div>
              <div className="l">Correct root cause</div>
            </div>
            <div className="big-metric">
              <div className={`n ${fcClass}`}>{Math.round(arch.false_confidence_rate * 100)}%</div>
              <div className="l">Confidently wrong</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

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
      <div className="story-label">Is the complexity worth it?</div>
      <h1 style={{ fontSize: 24, margin: "0 0 12px", maxWidth: 640 }}>
        A multi-agent system costs more to run. Here&apos;s whether that cost pays for itself.
      </h1>
      <p className="story-body" style={{ marginBottom: 20 }}>
        We run three architectures — a direct LLM call, a single agent with tools, and the full
        multi-agent pipeline — against the same incidents, scored against ground truth none of
        them can see. The two numbers that matter most:{" "}
        <Gloss term="how often it's right">
          Root Cause Accuracy — the selected hypothesis exactly matches the incident&apos;s true,
          held-out root cause.
        </Gloss>
        , and — more importantly —{" "}
        <Gloss term="how often it's confidently wrong">
          False Confidence Rate — the system reported high confidence in an answer that turned out
          to be incorrect. This is the specific failure mode that makes ungrounded AI dangerous
          during a live incident.
        </Gloss>
        .
      </p>

      <div className="panel">
        <div className="panel-title">Run Benchmark</div>
        <p className="dim small" style={{ marginTop: 0 }}>
          Compares Direct LLM (no tools), Single Agent (all tools, no hypothesis correlation), and
          the real Multi-Agent system against the same generated dataset. See{" "}
          <code>docs/design-decisions.md</code> (DDR-017) — this dataset is small and honestly
          disclosed as such, not padded to look bigger.
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
        <>
          <ArchitectureCards architectures={report.architectures} />

          <div className="panel">
            <div className="panel-title">Full results — {report.dataset_size} incidents</div>
            <table>
              <thead>
                <tr>
                  <th>Architecture</th>
                  {METRIC_COLUMNS.map((c) => (
                    <th key={c.key}>
                      <Gloss term={c.label}>{c.description}</Gloss>
                    </th>
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
        </>
      )}
    </div>
  );
}
