from typing import List, Dict, Literal, Annotated, Optional, TypedDict
from pydantic import BaseModel, Field
import operator

class Evidence(BaseModel):
    goal: str
    found: bool
    content: str
    location: str
    rationale: str
    confidence: float

class JudicialOpinion(BaseModel):
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: List[str]

class CriterionResult(BaseModel):
    criterion: str
    score: float
    reasoning: str
    evidence_summary: str

class AuditReport(BaseModel):
    repo_name: str
    total_score: float
    criterion_results: List[CriterionResult]
    summary: str
    recommendations: List[str]

class AgentState(TypedDict):
    repo_url: str
    pdf_path: str
    rubric_dimensions: List[str]
    evidences: Annotated[Dict[str, Evidence], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    final_report: Optional[AuditReport]
