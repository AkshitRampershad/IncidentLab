from typing import TypedDict

from agents.adjudicator import AdjudicationResult
from agents.models import InvestigatorFinding, TriageFinding
from core.llm import LLMProvider
from hypotheses.models import Hypothesis


class InvestigationState(TypedDict, total=False):
    """Shared state threaded through the LangGraph (spec §5's orchestrator).

    Each investigator node writes to its own distinct key
    (logs_finding/metrics_finding/code_finding/knowledge_finding), so they
    can run in parallel with no key conflicts and no reducer needed —
    LangGraph's default per-key "last write wins" is exactly correct here
    because only one node ever writes each key.
    """

    incident_id: str
    llm: LLMProvider | None

    triage: TriageFinding
    logs_finding: InvestigatorFinding
    metrics_finding: InvestigatorFinding
    code_finding: InvestigatorFinding
    knowledge_finding: InvestigatorFinding

    hypotheses: list[Hypothesis]
    adjudication: AdjudicationResult
