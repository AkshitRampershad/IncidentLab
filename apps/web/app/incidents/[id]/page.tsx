"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { ConfidenceBar } from "@/components/ConfidenceBar";
import { SeverityBadge } from "@/components/SeverityBadge";
import { api, ApiError } from "@/lib/api";
import type {
  Evidence,
  IncidentPublic,
  InvestigationResponse,
  ReviewDecision,
} from "@/lib/types";

const AGENT_LABELS: Record<string, string> = {
  logs: "Log Investigator",
  metrics: "Metrics Investigator",
  code: "Code Investigator",
  knowledge: "Knowledge Investigator",
};

const EVIDENCE_PREVIEW_LENGTH = 220;

function EvidenceItem({ e }: { e: Evidence }) {
  const isLong = e.content.length > EVIDENCE_PREVIEW_LENGTH;
  return (
    <div className="evidence-item">
      <div className="evidence-meta mono">
        {e.evidence_id} · {e.source_type} · {e.source} · relevance {e.relevance.toFixed(2)}
      </div>
      {isLong ? (
        <details>
          <summary style={{ cursor: "pointer" }}>
            {e.content.slice(0, EVIDENCE_PREVIEW_LENGTH)}…{" "}
            <span className="faint">(expand full document)</span>
          </summary>
          <div style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>{e.content}</div>
        </details>
      ) : (
        <div>{e.content}</div>
      )}
    </div>
  );
}

export default function IncidentPage() {
  const params = useParams<{ id: string }>();
  const incidentId = params.id;

  const [incident, setIncident] = useState<IncidentPublic | null>(null);
  const [investigation, setInvestigation] = useState<InvestigationResponse | null>(null);
  const [useLlm, setUseLlm] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewNote, setReviewNote] = useState<ReviewDecision | null>(null);

  useEffect(() => {
    api
      .getIncident(incidentId)
      .then(setIncident)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load incident."));
  }, [incidentId]);

  async function runInvestigation() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.investigate(incidentId, useLlm);
      setInvestigation(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Investigation failed.");
    } finally {
      setRunning(false);
    }
  }

  async function review(action: "approve" | "reject") {
    const decision = action === "approve" ? await api.approve(incidentId) : await api.reject(incidentId);
    setReviewNote(decision);
  }

  if (error && !incident) {
    return <div className="error-box">{error}</div>;
  }

  return (
    <div>
      <div className="panel">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div>
            <div className="row" style={{ marginBottom: 6 }}>
              <span className="mono" style={{ fontSize: 18, fontWeight: 700 }}>
                {incidentId}
              </span>
              {incident && <SeverityBadge severity={incident.severity} />}
            </div>
            {incident && <div className="dim">{incident.description}</div>}
            {incident && (
              <div className="small faint" style={{ marginTop: 6 }}>
                {incident.service} · {new Date(incident.start_time).toLocaleString()} →{" "}
                {new Date(incident.end_time).toLocaleString()}
              </div>
            )}
          </div>
          <div className="stack" style={{ alignItems: "flex-end" }}>
            <label className="row small dim" style={{ cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(e) => setUseLlm(e.target.checked)}
              />
              Use LLM for prose summaries (falls back if unreachable)
            </label>
            <button onClick={runInvestigation} disabled={running}>
              {running ? "Investigating…" : "Run Investigation"}
            </button>
          </div>
        </div>
      </div>

      {error && investigation === null && <div className="error-box">{error}</div>}

      {investigation && (
        <>
          <div className="panel">
            <div className="panel-title">Agent Activity</div>
            <div className="grid-2">
              {Object.entries(investigation.agents).map(([key, finding]) => (
                <div className="agent-card" key={key}>
                  <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
                    <strong>{AGENT_LABELS[key] ?? key}</strong>
                    {finding.degraded ? (
                      <span className="badge badge-warning">degraded</span>
                    ) : (
                      <span className="badge badge-success">✓</span>
                    )}
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {finding.findings.map((f, i) => (
                      <li key={i} className="small" style={{ marginBottom: 4 }}>
                        {f}
                      </li>
                    ))}
                  </ul>
                  <div className="small dim" style={{ marginTop: 8 }}>
                    {finding.summary}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Hypotheses</div>
            {investigation.hypotheses.length === 0 && (
              <p className="dim">No hypotheses were generated from the available evidence.</p>
            )}
            {investigation.hypotheses.map((h) => (
              <div className="hypothesis-row" key={h.hypothesis_id}>
                <ConfidenceBar confidence={h.confidence} label={h.description} />
                <div className="small faint" style={{ marginTop: 4 }}>
                  {h.supporting_evidence.length} supporting · {h.contradicting_evidence.length}{" "}
                  contradicting · {h.source_diversity} source type(s)
                </div>
              </div>
            ))}
          </div>

          <div className="panel">
            <div className="panel-title">Root Cause Analysis</div>
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>
                {investigation.adjudication.selected_hypothesis ?? "Insufficient evidence"}
              </div>
              <ConfidenceBar confidence={investigation.adjudication.confidence} />
            </div>

            {investigation.adjudication.needs_human_review && (
              <div className="badge badge-warning" style={{ marginBottom: 14 }}>
                Human review required
              </div>
            )}

            <p>{investigation.adjudication.reasoning_summary}</p>

            <div className="grid-2" style={{ marginTop: 10 }}>
              <div>
                <div className="panel-title">Supporting Evidence</div>
                {investigation.adjudication.supporting_evidence.length === 0 && (
                  <p className="dim small">None.</p>
                )}
                {investigation.adjudication.supporting_evidence.map((e) => (
                  <EvidenceItem e={e} key={e.evidence_id} />
                ))}
              </div>
              <div>
                <div className="panel-title">Contradicting Evidence</div>
                {investigation.adjudication.contradicting_evidence.length === 0 && (
                  <p className="dim small">None detected.</p>
                )}
                {investigation.adjudication.contradicting_evidence.map((e) => (
                  <EvidenceItem e={e} key={e.evidence_id} />
                ))}
              </div>
            </div>

            <div className="panel-title" style={{ marginTop: 14 }}>
              Recommended Action
            </div>
            <p style={{ marginTop: 0 }}>{investigation.adjudication.recommended_action}</p>

            <div className="row" style={{ marginTop: 12 }}>
              <button className="secondary" onClick={() => review("approve")}>
                Approve
              </button>
              <button className="secondary danger" onClick={() => review("reject")}>
                Reject
              </button>
              {reviewNote && (
                <span className="small dim">
                  {reviewNote.status === "approved" ? "Approved." : "Rejected."} (acknowledgment only —
                  see recommended_action note)
                </span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
