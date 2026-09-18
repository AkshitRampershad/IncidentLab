import type {
  AdjudicationResult,
  Evidence,
  EvaluationResponse,
  Hypothesis,
  IncidentPublic,
  InvestigationResponse,
  ReviewDecision,
} from "./types";

// NOT `process.env.NEXT_PUBLIC_API_URL` read directly here: Next.js
// inlines every `NEXT_PUBLIC_*` reference into the client bundle at
// `docker build` time, so a value set on a PaaS host (known only once
// that host creates the container, long after the image was built)
// would never reach it. Instead, this is resolved once per page load by
// asking this app's own server (same-origin, always reachable, no CORS)
// via /api/config, which reads the real env var live at request time.
// See apps/web/app/api/config/route.ts and docs/design-decisions.md.
let cachedApiUrl: string | null = null;

async function resolveApiUrl(): Promise<string> {
  if (cachedApiUrl) return cachedApiUrl;
  const response = await fetch("/api/config");
  const { apiUrl } = (await response.json()) as { apiUrl: string };
  cachedApiUrl = apiUrl;
  return apiUrl;
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiUrl = await resolveApiUrl();
  const response = await fetch(`${apiUrl}${path}`, {
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
