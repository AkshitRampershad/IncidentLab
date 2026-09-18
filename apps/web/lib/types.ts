// Mirrors apps/api's Pydantic response models field-for-field (snake_case,
// no aliasing configured on the backend) — kept hand-written rather than
// codegen'd since the API surface is still small and changing per phase.

export interface IncidentPublic {
  incident_id: string;
  service: string;
  severity: string;
  description: string;
  start_time: string;
  end_time: string;
}

export interface Provenance {
  table: string;
  row_id: string;
  incident_id: string;
  retrieved_at: string;
}

export interface Evidence {
  evidence_id: string;
  source_type: string;
  source: string;
  timestamp: string;
  content: string;
  relevance: number;
  provenance: Provenance;
}

export interface TimeWindow {
  start: string;
  end: string;
}

export interface TriageFinding {
  affected_services: string[];
  time_window: TimeWindow;
  investigation_targets: string[];
  initial_hypotheses: string[];
  summary: string;
}

export interface HypothesisSignal {
  hypothesis: string;
  evidence_ids: string[];
}

export interface InvestigatorFinding {
  agent_name: string;
  findings: string[];
  evidence: Evidence[];
  hypotheses_supported: HypothesisSignal[];
  summary: string;
}

export interface Hypothesis {
  hypothesis_id: string;
  description: string;
  supporting_evidence: Evidence[];
  contradicting_evidence: Evidence[];
  source_diversity: number;
  temporal_alignment: number;
  confidence: number;
}

export interface AdjudicationResult {
  selected_hypothesis: string | null;
  confidence: number;
  reasoning_summary: string;
  supporting_evidence: Evidence[];
  contradicting_evidence: Evidence[];
  recommended_action: string;
  needs_human_review: boolean;
}

export interface InvestigationResponse {
  incident_id: string;
  triage: TriageFinding;
  agents: Record<string, InvestigatorFinding>;
  hypotheses: Hypothesis[];
  adjudication: AdjudicationResult;
}

export interface AggregateMetrics {
  architecture: string;
  n: number;
  root_cause_accuracy: number;
  evidence_recall: number;
  evidence_precision: number;
  unsupported_claim_rate: number;
  false_confidence_rate: number;
  human_escalation_rate: number;
  avg_latency_seconds: number;
}

export interface BenchmarkReport {
  dataset_size: number;
  architectures: AggregateMetrics[];
}

export interface EvaluationResponse {
  evaluation_id: string;
  report: BenchmarkReport;
}

export interface ReviewDecision {
  status: string;
  incident_id: string;
  note: string;
}
