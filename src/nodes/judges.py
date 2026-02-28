from typing import Dict, List, Any
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, JudicialOpinion, Evidence

def _get_model():
    return ChatOpenAI(model="gpt-4o", temperature=0)

def _load_rubric():
    try:
        with open("rubric.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: rubric.json not found, using default.")
        return {"dimensions": []}

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
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Prosecutor. Your role is: Trust No One. Assume Vibe Coding. Look for flaws. "
        "Analyze the provided evidence critically against the following Rubric Criteria:\n"
        f"{str(rubric.get('dimensions', []))}\n\n"
        "Protocol 1 (Statute of Orchestration): If the StateGraph implies linear flow, charge 'Orchestration Fraud' (Score 1).\n"
        "Protocol 2: If evidence mentions lack of typed state or Pydantic models, charge 'Hallucination Liability'.\n"
        "You MUST output a JudicialOpinion with judge='Prosecutor'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for the 'Overall' criterion or a specific relevant one:\n\n{evidence_text}")
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
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Defense Attorney. Your role is: Reward Effort and Intent. Highlight workarounds. "
        "Find the good in the code and documentation. Use the following Rubric for context:\n"
        f"{str(rubric.get('dimensions', []))}\n\n"
        "Protocol 3 (Statute of Effort): If syntax errors exist but AST parsing shows sophisticated logic, argue for 'Forensic Accuracy' score 3.\n"
        "If distinct personas exist but synthesis is weak, argue for 'Judicial Nuance' checks.\n"
        "You MUST output a JudicialOpinion with judge='Defense'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for 'Overall' or specific criteria:\n\n{evidence_text}")
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
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Tech Lead. Your role is: Does it actually work? Evaluate architectural soundness. "
        "Be practical and objective. Use the Rubric below:\n"
        f"{str(rubric.get('dimensions', []))}\n\n"
        "Protocol 2 (Statute of Engineering): If dicts are used instead of Pydantic, ruling is 'Technical Debt' (Score 3).\n"
        "If os.system is used without sandboxing, ruling is 'Security Negligence' (Score 1).\n"
        "You MUST output a JudicialOpinion with judge='TechLead'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for 'Overall' or specific criteria:\n\n{evidence_text}")
    ]
    
    opinion = judge_model.invoke(messages)
    if opinion.judge != "TechLead":
        opinion.judge = "TechLead"
        
    return {"opinions": [opinion]}
