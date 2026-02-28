from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from src.state import AgentState, AuditReport, CriterionResult, Evidence
from src.nodes.detectives import repo_investigator, doc_analyst, vision_inspector
from src.nodes.judges import prosecutor_node, defense_node, tech_lead_node
from src.nodes.justice import chief_justice_node, debate_node

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

    # Heuristic: Critical failures only
    # We don't error just because evidence was missed, but if required files are gone.
    
    return {"errors": errors, "missing_artifacts": missing}

def error_handler(state: AgentState) -> Dict[str, Any]:
    """Handle errors by creating a short remediation evidence entry and flagging manual review."""
    
    # Add a low-confidence evidence item to indicate failure and request manual review
    evid = Evidence(
        goal="Error Handling",
        found=False,
        content="One or more pipeline errors detected; manual review required.",
        location="Runtime",
        rationale=f"Missing artifacts: {state.get('missing_artifacts', [])}",
        confidence=0.0,
    )

    return {"evidences": {"system": [evid]}}

# --- Graph Definition ---

def create_graph():
    graph_builder = StateGraph(AgentState)

    # Add Nodes
    graph_builder.add_node("RepoInvestigator", repo_investigator)
    graph_builder.add_node("DocAnalyst", doc_analyst)
    graph_builder.add_node("VisionInspector", vision_inspector)
    
    graph_builder.add_node("EvidenceAggregator", evidence_aggregator)
    graph_builder.add_node("ErrorHandler", error_handler)
    
    # Judges
    graph_builder.add_node("Prosecutor", prosecutor_node)
    graph_builder.add_node("Defense", defense_node)
    graph_builder.add_node("TechLead", tech_lead_node)
    
    # Justice
    graph_builder.add_node("ChiefJustice", chief_justice_node)
    graph_builder.add_node("Debate", debate_node)

    # Add Edges
    # Fan-out to Detectives
    graph_builder.add_edge(START, "RepoInvestigator")
    graph_builder.add_edge(START, "DocAnalyst")
    graph_builder.add_edge(START, "VisionInspector")
    
    # Fan-in to Aggregator
    graph_builder.add_edge("RepoInvestigator", "EvidenceAggregator")
    graph_builder.add_edge("DocAnalyst", "EvidenceAggregator")
    graph_builder.add_edge("VisionInspector", "EvidenceAggregator")
    
    # Conditional Routing
    def check_routing(state: AgentState):
        if state.get("errors"):
            return "ErrorHandler"
        return "JudicialFanOut"

    # Solution: Route to a dummy "JudicialStart" node conditionally, then unconditional edges fan out.
    
    def judicial_start_node(state: AgentState):
        return {}
    
    graph_builder.add_node("JudicialStart", judicial_start_node)
    
    # Update conditional edge
    graph_builder.add_conditional_edges(
        "EvidenceAggregator",
        check_routing,
        {
            "ErrorHandler": "ErrorHandler",
            "JudicialFanOut": "JudicialStart" 
        }
    )

    # Fan Out to Judges
    graph_builder.add_edge("JudicialStart", "Prosecutor")
    graph_builder.add_edge("JudicialStart", "Defense")
    graph_builder.add_edge("JudicialStart", "TechLead")
    
    # Fan In to Justice
    graph_builder.add_edge("Prosecutor", "ChiefJustice")
    graph_builder.add_edge("Defense", "ChiefJustice")
    graph_builder.add_edge("TechLead", "ChiefJustice")
    
    graph_builder.add_edge("ErrorHandler", "ChiefJustice")
    
    # New Edge: Debate Loop
    graph_builder.add_edge("Debate", "ChiefJustice")
    
    # Conditional Routing for Conflict
    def check_conflict(state: AgentState):
        opinions = state.get("opinions", [])
        if not opinions:
            return END
            
        scores = [op.score for op in opinions]
        # Calculate variance
        variance = max(scores) - min(scores) if scores else 0
        
        # If variance > 2 and NOT yet debated, route to Debate
        if variance > 2 and not state.get("debated"):
            return "Debate"
            
        return END

    graph_builder.add_conditional_edges(
        "ChiefJustice",
        check_conflict,
        {
            "Debate": "Debate",
            END: END
        }
    )
    
    return graph_builder.compile()

app = create_graph()
