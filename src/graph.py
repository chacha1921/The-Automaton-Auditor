from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from src.state import AgentState, AuditReport, CriterionResult
from src.nodes.detectives import repo_investigator, doc_analyst
from src.judges.bench import prosecutor_node, defense_node, tech_lead_node


def evidence_aggregator(state: AgentState) -> Dict[str, Any]:
    """Aggregate evidence and detect missing artifacts or failures.

    Returns an update with an `errors` flag and a `missing_artifacts` list when applicable.
    """
    evidences = state.get("evidences", {}) or {}
    errors = False
    missing: List[str] = []

    # Check for missing inputs
    if not state.get("repo_url"):
        errors = True
        missing.append("repo_url")
    if not state.get("pdf_path"):
        errors = True
        missing.append("pdf_path")

    # Heuristic: any evidence item explicitly found==False signals a problem
    for cat, ev_list in evidences.items():
        try:
            for ev in ev_list:
                if getattr(ev, "found", None) is False:
                    errors = True
        except Exception:
            # skip malformed entries
            continue

    return {"errors": errors, "missing_artifacts": missing}


def error_handler(state: AgentState) -> Dict[str, Any]:
    """Handle errors by creating a short remediation evidence entry and flagging manual review."""
    if not state.get("errors"):
        return {}

    # Add a low-confidence evidence item to indicate failure and request manual review
    from src.state import Evidence

    evid = Evidence(
        goal="Error Handling",
        found=False,
        content="One or more pipeline errors detected; manual review required.",
        location="Runtime",
        rationale=f"Missing artifacts: {state.get('missing_artifacts', [])}",
        confidence=0.0,
    )

    return {"manual_review": True, "evidences": {"system": [evid]}}


def chief_justice_node(state: AgentState) -> Dict[str, Any]:
    """Deterministic synthesis of opinions into an AuditReport.

    This avoids depending on an LLM for the interim submission: it averages scores
    and produces a short summary. Later we will replace this with an LLM-based
    structured synthesis.
    """
    opinions = state.get("opinions", []) or []
    repo = state.get("repo_url", "unknown")

    if not opinions:
        report = AuditReport(
            repo_name=repo,
            total_score=0.0,
            criterion_results=[],
            summary="No judicial opinions were produced; manual review required.",
            recommendations=["Rerun with all artifacts present."],
        )
        return {"final_report": report}

    scores = [getattr(o, "score", 0) for o in opinions]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    # Create simple criterion results placeholder
    criterion_results: List[CriterionResult] = [
        CriterionResult(
            criterion="Overall",
            score=avg_score,
            reasoning="Aggregated from judicial opinions",
            evidence_summary=f"{len(opinions)} opinions considered",
        )
    ]

    summary = (
        f"Synthesized {len(opinions)} opinions. Average score: {avg_score:.2f}."
        + (" Errors were present; see manual review evidence." if state.get("errors") else "")
    )

    report = AuditReport(
        repo_name=repo,
        total_score=avg_score,
        criterion_results=criterion_results,
        summary=summary,
        recommendations=([] if avg_score >= 3.0 else ["Address major issues identified by judges."]),
    )

    return {"final_report": report}


# --- Graph Construction ---

builder = StateGraph(AgentState)

# Core detective nodes
builder.add_node("repo_investigator", repo_investigator)
builder.add_node("doc_analyst", doc_analyst)

# Aggregator and error handler
builder.add_node("evidence_aggregator", evidence_aggregator)
builder.add_node("error_handler", error_handler)

# Judicial nodes (they should inspect state and no-op if errors present)
builder.add_node("prosecutor", prosecutor_node)
builder.add_node("defense", defense_node)
builder.add_node("tech_lead", tech_lead_node)

# Synthesis
builder.add_node("chief_justice", chief_justice_node)

# Edges: START -> detectives (fan-out)
builder.add_edge(START, "repo_investigator")
builder.add_edge(START, "doc_analyst")

# Detectives -> aggregator (fan-in)
builder.add_edge("repo_investigator", "evidence_aggregator")
builder.add_edge("doc_analyst", "evidence_aggregator")

# Aggregator -> error handler (conditional by node logic) and -> judges
builder.add_edge("evidence_aggregator", "error_handler")
builder.add_edge("evidence_aggregator", "prosecutor")
builder.add_edge("evidence_aggregator", "defense")
builder.add_edge("evidence_aggregator", "tech_lead")

# Judges -> Chief Justice (fan-in synthesis)
builder.add_edge("prosecutor", "chief_justice")
builder.add_edge("defense", "chief_justice")
builder.add_edge("tech_lead", "chief_justice")

# Chief Justice -> END
builder.add_edge("chief_justice", END)

# Compile graph
graph = builder.compile()
