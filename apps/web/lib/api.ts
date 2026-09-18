import type {
  AdjudicationResult,
  Evidence,
  EvaluationResponse,
  Hypothesis,
  IncidentPublic,
  InvestigationResponse,
  ReviewDecision,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listScenarios: () => request<string[]>("/scenarios"),
  listIncidents: () => request<IncidentPublic[]>("/incidents"),
  getIncident: (incidentId: string) => request<IncidentPublic>(`/incidents/${incidentId}`),
  createIncident: (scenarioId: string) =>
    request<IncidentPublic>("/incidents", {
      method: "POST",
      body: JSON.stringify({ scenario_id: scenarioId }),
    }),
  investigate: (incidentId: string, useLlm: boolean) =>
    request<InvestigationResponse>(`/incidents/${incidentId}/investigate?llm=${useLlm}`, {
      method: "POST",
    }),
  approve: (incidentId: string) =>
    request<ReviewDecision>(`/investigations/${incidentId}/approve`, { method: "POST" }),
  reject: (incidentId: string) =>
    request<ReviewDecision>(`/investigations/${incidentId}/reject`, { method: "POST" }),
  runEvaluation: (instancesPerScenario: number) =>
    request<EvaluationResponse>("/evaluations/run", {
      method: "POST",
      body: JSON.stringify({ instances_per_scenario: instancesPerScenario }),
    }),
};

export type { AdjudicationResult, Evidence, Hypothesis };
export { ApiError };
