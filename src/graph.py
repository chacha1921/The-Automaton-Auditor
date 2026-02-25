from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.nodes.detectives import repo_investigator, doc_analyst

def evidence_aggregator(state: AgentState) -> Dict[str, Any]:
    """
    Pass-through node to synchronize evidence collection.
    The state is automatically updated by the returned values from previous nodes via reducers.
    """
    return {}

# --- Graph Construction ---

builder = StateGraph(AgentState)

# Nodes
builder.add_node("repo_investigator", repo_investigator)
builder.add_node("doc_analyst", doc_analyst)
builder.add_node("evidence_aggregator", evidence_aggregator)

# Edges
# START -> [Repo, Doc] (Parallel Fan-out)
builder.add_edge(START, "repo_investigator")
builder.add_edge(START, "doc_analyst")

# [Repo, Doc] -> Aggregator (Sync Fan-in)
builder.add_edge("repo_investigator", "evidence_aggregator")
builder.add_edge("doc_analyst", "evidence_aggregator")

# Aggregator -> END
builder.add_edge("evidence_aggregator", END)

# Compile
graph = builder.compile()
