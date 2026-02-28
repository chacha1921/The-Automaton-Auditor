from typing import Dict, List, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, JudicialOpinion, Evidence

def _get_model():
    return ChatOpenAI(model="gpt-4o", temperature=0)

def _format_evidence(evidences: Dict[str, Evidence]) -> str:
    """Formats the evidence into a string for the LLM."""
    if not evidences:
        return "No evidence found."
    
    formatted = "EVIDENCE FOUND:\n"
    # evidences is Dict[str, List[Evidence]] or just Dict[str, Evidence] ?
    # In state.py: evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    # So we iterate lists.
    for category, evidence_list in evidences.items():
        if isinstance(evidence_list, list):
            for evidence in evidence_list:
                formatted += f"--- Evidence: {category} ---\n"
                formatted += f"Goal: {evidence.goal}\n"
                formatted += f"Found: {evidence.found}\n"
                formatted += f"Content: {evidence.content}\n"
                formatted += f"Location: {evidence.location}\n"
                formatted += f"Rationale: {evidence.rationale}\n"
                formatted += f"Confidence: {evidence.confidence}\n\n"
        else:
            # Fallback if it's not a list (shouldn't happen with correct state)
            evidence = evidence_list
            formatted += f"--- Evidence: {category} ---\n"
            formatted += f"Goal: {evidence.goal}\n"
            formatted += f"Found: {evidence.found}\n"
            formatted += f"Content: {evidence.content}\n"
            formatted += f"Location: {evidence.location}\n"
            formatted += f"Rationale: {evidence.rationale}\n"
            formatted += f"Confidence: {evidence.confidence}\n\n"
            
    return formatted

def prosecutor_node(state: AgentState) -> Dict[str, List[JudicialOpinion]]:
    """
    Prosecutor Node: Looks for flaws and assumes 'Vibe Coding'.
    """
    model = _get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    
    system_prompt = (
        "You are the Prosecutor. Your role is: Trust No One. Assume Vibe Coding. Look for flaws. "
        "Analyze the provided evidence critically. "
        "You MUST output a JudicialOpinion with judge='Prosecutor'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion:\n\n{evidence_text}")
    ]
    
    opinion = judge_model.invoke(messages)
    if opinion.judge != "Prosecutor":
        opinion.judge = "Prosecutor"
        
    return {"opinions": [opinion]}

def defense_node(state: AgentState) -> Dict[str, List[JudicialOpinion]]:
    """
    Defense Node: Rewards effort and intent.
    """
    model = _get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    
    system_prompt = (
        "You are the Defense Attorney. Your role is: Reward Effort and Intent. Highlight workarounds. "
        "Find the good in the code and documentation. "
        "You MUST output a JudicialOpinion with judge='Defense'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion:\n\n{evidence_text}")
    ]
    
    opinion = judge_model.invoke(messages)
    if opinion.judge != "Defense":
        opinion.judge = "Defense"
        
    return {"opinions": [opinion]}

def tech_lead_node(state: AgentState) -> Dict[str, List[JudicialOpinion]]:
    """
    Tech Lead Node: Evaluates architectural soundness.
    """
    model = _get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    
    system_prompt = (
        "You are the Tech Lead. Your role is: Does it actually work? Evaluate architectural soundness. "
        "Be practical and objective. "
        "You MUST output a JudicialOpinion with judge='TechLead'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion:\n\n{evidence_text}")
    ]
    
    opinion = judge_model.invoke(messages)
    if opinion.judge != "TechLead":
        opinion.judge = "TechLead"
        
    return {"opinions": [opinion]}
