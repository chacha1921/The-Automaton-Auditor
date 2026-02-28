from typing import Dict, List, Any
import json
import os
from langchain_openai import ChatOpenAI
try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, JudicialOpinion, Evidence

def _get_model():
    """
    Returns a configured Chat Model (OpenAI or Ollama) with optional fallback.
    Reads from environment variables:
    - JUDGE_PROVIDER: 'openai' (default) or 'ollama'
    - JUDGE_MODEL: Model name
    - JUDGE_FALLBACK_PROVIDER: Optional fallback provider
    - JUDGE_FALLBACK_MODEL: Optional fallback model name
    """
    provider = os.getenv("JUDGE_PROVIDER", "openai").lower()
    model_name = os.getenv("JUDGE_MODEL")
    
    primary_model = None

    # Determine Ollama Base URL (default is http://localhost:11434)
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    if provider == "ollama":
        if not ChatOllama:
            raise ImportError("langchain-ollama is not installed. Please run `pip install langchain-ollama`.")
        target_model = model_name if model_name else "llama3.2:latest"
        print(f"Using Primary Model: Ollama / {target_model} at {ollama_base_url}")
        primary_model = ChatOllama(model=target_model, base_url=ollama_base_url, temperature=0)
    else:
        # Default to OpenAI
        target_model = model_name if model_name else "gpt-4o"
        print(f"Using Primary Model: OpenAI / {target_model}")
        primary_model = ChatOpenAI(model=target_model, temperature=0)

    # Configure Fallback
    fallback_provider = os.getenv("JUDGE_FALLBACK_PROVIDER")
    fallback_model_name = os.getenv("JUDGE_FALLBACK_MODEL")

    if fallback_provider:
        fallback_model = None
        if fallback_provider.lower() == "ollama":
             if ChatOllama:
                fb_model = fallback_model_name if fallback_model_name else "llama3.2:latest"
                print(f"Configuring Fallback Model: Ollama / {fb_model} at {ollama_base_url}")
                fallback_model = ChatOllama(model=fb_model, base_url=ollama_base_url, temperature=0)
        elif fallback_provider.lower() == "openai":
            fb_model = fallback_model_name if fallback_model_name else "gpt-4o-mini"
            print(f"Configuring Fallback Model: OpenAI / {fb_model}")
            fallback_model = ChatOpenAI(model=fb_model, temperature=0)
            
        if fallback_model:
            return primary_model.with_fallbacks([fallback_model])

    return primary_model

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
    Philosophy: The burden of proof is on the developer. Ambiguity = Guilt.
    """
    model = _get_model()
    # Retry/Fallback logic is inherent in the configured model (see get_model)
    # But strictly typed output is enforced here.
    judge_model = model.with_structured_output(JudicialOpinion)
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Prosecutor. Your role is: Trust No One. Assume Vibe Coding. Look for flaws. "
        "But adhere STRICTLY to the Evidence provided. Do not invent flaws.\n"
        f"RUBRIC:\n{json.dumps(rubric.get('dimensions', []), indent=2)}\n\n"
        "INSTRUCTIONS:\n"
        "1. Walk through EACH criterion explicitly.\n"
        "2. Protocol 1 (Statute of Orchestration): If valid 'StateGraph' AND 'conditional_edges' are found in evidence, DO NOT charge 'Orchestration Fraud'. Only charge if evidence says 'No conditional edges found'.\n"
        "3. Protocol 2 (Security): If evidence says 'No unsafe constructs (os.system) found', you MUST clear the defendant of 'Security Negligence'. Only charge if 'Unsafe os.system identified' appears in evidence.\n"
        "4. Protocol 3: If distinct Pydantic models (BaseModel) are found, clear 'Hallucination Liability'.\n"
        "5. Output a SINGLE JudicialOpinion with judge='Prosecutor'. If you clear all charges, a score of 4 or 5 is permitted."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for the 'Overall' criterion or a specific relevant one:\n\n{evidence_text}")
    ]
    
    # Simple retry logic for malformed output
    try:
        opinion = judge_model.invoke(messages)
    except Exception as e:
        print(f"Prosecutor failed structured output: {e}. Retrying with simplified prompt.")
        messages.append(HumanMessage(content="Previous output was malformed. Please verify JSON structure matches JudicialOpinion schema."))
        opinion = judge_model.invoke(messages)

    if opinion.judge != "Prosecutor":
        opinion.judge = "Prosecutor"
        
    return {"opinions": [opinion]}

def defense_node(state: AgentState) -> Dict[str, List[JudicialOpinion]]:
    """
    Defense Node: Rewards effort and intent.
    Philosophy: Code is hard. If it runs, it's a feature. Ambiguity = Benefit of Doubt.
    """
    model = _get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Defense Attorney. Your role is: Reward Effort and Intent. Highlight workarounds. "
        "Find the good in the code and documentation. Use the following Rubric for context:\n"
        f"{json.dumps(rubric.get('dimensions', []), indent=2)}\n\n"
        "INSTRUCTIONS:\n"
        "1. Walk through EACH criterion in the Rubric above explicitly to find mitigating factors.\n"
        "2. Protocol 3 (Statute of Effort): If syntax errors exist but AST parsing shows sophisticated logic, argue for 'Forensic Accuracy' score 3.\n"
        "3. If distinct personas exist but synthesis is weak, argue for 'Judicial Nuance'.\n"
        "4. Output a JudicialOpinion with judge='Defense'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for 'Overall' or specific criteria:\n\n{evidence_text}")
    ]
    
    try:
        opinion = judge_model.invoke(messages)
    except Exception as e:
        print(f"Defense failed structured output: {e}. Retrying.")
        messages.append(HumanMessage(content="Previous output was malformed. Return valid schema."))
        opinion = judge_model.invoke(messages)

    if opinion.judge != "Defense":
        opinion.judge = "Defense"
        
    return {"opinions": [opinion]}

def tech_lead_node(state: AgentState) -> Dict[str, List[JudicialOpinion]]:
    """
    Tech Lead Node: Evaluates architectural soundness.
    Philosophy: Scalability, Maintainability, and Pragmatism. Neither overly critical nor overly lenient.
    """
    model = _get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    rubric = _load_rubric()
    
    system_prompt = (
        "You are the Tech Lead. Your role is: Does it actually work? Evaluate architectural soundness. "
        "Be practical and objective. Use the Rubric below:\n"
        f"{json.dumps(rubric.get('dimensions', []), indent=2)}\n\n"
        "INSTRUCTIONS:\n"
        "1. Walk through EACH criterion in the Rubric above explicitly.\n"
        "2. Protocol 2 (Statute of Engineering): If dicts are used instead of Pydantic, ruling is 'Technical Debt' (Score 3).\n"
        "3. If os.system is used without sandboxing, ruling is 'Security Negligence' (Score 1).\n"
        "4. Output a JudicialOpinion with judge='TechLead'."
    )
    
    evidence_text = _format_evidence(state.get("evidences", {}))
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Review the following evidence and provide your judicial opinion for 'Overall' or specific criteria:\n\n{evidence_text}")
    ]
    
    try:
        opinion = judge_model.invoke(messages)
    except Exception as e:
        print(f"TechLead failed structured output: {e}. Retrying.")
        messages.append(HumanMessage(content="Previous output was malformed. Return valid schema."))
        opinion = judge_model.invoke(messages)

    if opinion.judge != "TechLead":
        opinion.judge = "TechLead"
        
    return {"opinions": [opinion]}
