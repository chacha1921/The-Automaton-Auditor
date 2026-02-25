from typing import Dict, List, Any
import statistics
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.state import AgentState, AuditReport, CriterionResult, JudicialOpinion
from src.detectives.repo_investigator import repo_investigator_node
from src.detectives.doc_analyst import doc_analyst_node
from src.judges.bench import prosecutor_node, defense_node, tech_lead_node

def evidence_aggregator_node(state: AgentState) -> Dict:
    """
    Pass-through node to synchronize evidence collection before judicial review.
    In a more complex system, this might summarize or filter evidence.
    """
    return {} # State update is additive via reducers, so we return empty dict to just pass through

def chief_justice_node(state: AgentState) -> Dict:
    """
    Chief Justice Node: Synthesize opinions and generate final report.
    Resolves conflicts if score variance > 2.
    """
    opinions = state.get("opinions", [])
    if not opinions:
        # Fallback if no opinions
        return {
            "final_report": AuditReport(
                repo_name=state.get("repo_url", "Unknown Repo"),
                total_score=0.0,
                criterion_results=[],
                summary="No judicial opinions were generated.",
                recommendations=["Rerun analysis."]
            )
        }

    # Calculate variance to see if we have significant disagreement
    scores = [o.score for o in opinions]
    variance = statistics.variance(scores) if len(scores) > 1 else 0
    
    # diverse opinions -> simpler LLM synthesis
    # high variance -> we might ask it to specifically address the conflict
    
    model = ChatOpenAI(model="gpt-4o", temperature=0)
    report_model = model.with_structured_output(AuditReport)
    
    formatted_opinions = "JUDICIAL OPINIONS:\n"
    for op in opinions:
        formatted_opinions += f"--- Judge: {op.judge} ---\n"
        formatted_opinions += f"Score: {op.score}/5\n"
        formatted_opinions += f"Argument: {op.argument}\n"
        formatted_opinions += f"Cited Evidence: {op.cited_evidence}\n\n"
        
    system_prompt = (
        "You are the Chief Justice. Your job is to synthesize the dissenting opinions of the Prosecutor, Defense, and Tech Lead.\n"
        "Review their arguments and scores. Resolve any conflicts.\n"
        "If variance in scores is high (> 2), explicitly address the controversy in your summary.\n"
        "Generate a final, balanced Audit Report."
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Repo: {state.get('repo_url')}\n\nVariance: {variance}\n\n{formatted_opinions}")
    ]
    
    final_report = report_model.invoke(messages)
    
    return {"final_report": final_report}

# --- Graph Construction ---

builder = StateGraph(AgentState)

# Nodes
builder.add_node("repo_investigator", repo_investigator_node)
builder.add_node("doc_analyst", doc_analyst_node)
builder.add_node("evidence_aggregator", evidence_aggregator_node)
builder.add_node("prosecutor", prosecutor_node)
builder.add_node("defense", defense_node)
builder.add_node("tech_lead", tech_lead_node)
builder.add_node("chief_justice", chief_justice_node)

# Edges
# START -> [Repo, Doc] (Parallel)
builder.add_edge(START, "repo_investigator")
builder.add_edge(START, "doc_analyst")

# [Repo, Doc] -> Aggregator (Sync)
builder.add_edge("repo_investigator", "evidence_aggregator")
builder.add_edge("doc_analyst", "evidence_aggregator")

# Aggregator -> [Judges] (Parallel)
builder.add_edge("evidence_aggregator", "prosecutor")
builder.add_edge("evidence_aggregator", "defense")
builder.add_edge("evidence_aggregator", "tech_lead")

# [Judges] -> Chief Justice (Sync/Synthesis)
builder.add_edge("prosecutor", "chief_justice")
builder.add_edge("defense", "chief_justice")
builder.add_edge("tech_lead", "chief_justice")

# Chief Justice -> END
builder.add_edge("chief_justice", END)

# Compile
graph = builder.compile()
