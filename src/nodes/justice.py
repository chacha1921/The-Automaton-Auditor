from typing import Dict, Any, List, Optional
import json
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, AuditReport, CriterionResult, JudicialOpinion
from src.utils.llm import get_model

def calculate_weighted_score(opinions: List[JudicialOpinion]) -> float:
    """
    Calculates the weighted average score based on judge roles.
    Weights: TechLead: 1.5, Others: 1.0.
    Formula: sum(score * weight) / sum(weights)
    """
    if not opinions:
        return 0.0

    # Define weights for specific judge roles
    role_weights = {
        "TechLead": 1.5,
        "Prosecutor": 1.0,
        "Defense": 1.0, 
        "Tech Lead": 1.5,
        "DebateModerator": 2.0 # Higher weight for debate resolution
    }
    
    total_weighted_score = 0.0
    total_weights = 0.0
    
    for op in opinions:
        # Use the judge's role to determine weight, default to 1.0 if unknown
        weight = role_weights.get(op.judge, 1.0)
        total_weighted_score += op.score * weight
        total_weights += weight
        
    if total_weights == 0:
        return 0.0
        
    return total_weighted_score / total_weights

def debate_node(state: AgentState) -> Dict[str, Any]:
    """
    Debate Node: Resolves high variance in judicial scores through dialectic synthesis.
    """
    opinions = state.get("opinions", [])
    model = get_model()
    judge_model = model.with_structured_output(JudicialOpinion)
    
    # Format the conflict
    conflict_summary = "\n".join([f"{op.judge}: {op.score} - {op.argument}" for op in opinions])
    
    system_prompt = (
        "You are the Debate Moderator. A significant conflict exists in the judicial opinions.\n"
        "Your goal is to synthesize a final, binding opinion that resolves the discrepancy.\n"
        "Review the conflicting opinions and the evidence.\n"
        "Output a new JudicialOpinion with judge='DebateModerator' that represents the consensus or the most grounded view."
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Resolve this conflict:\n\n{conflict_summary}")
    ]
    
    opinion = judge_model.invoke(messages)
    opinion.judge = "DebateModerator" 
    
    # We append the new opinion. The 'debated' flag will be inferred or set in state to prevent loops.
    # We return 'debated' key to signal graph flow.
    return {"opinions": [opinion], "debated": True}

def chief_justice_node(state: AgentState) -> Dict[str, Any]:
    """
    Chief Justice Node: Synthesizes opinions into a final report using an LLM for reasoning and dialectical integration.
    """
    opinions: List[JudicialOpinion] = state.get("opinions", []) or []
    repo = state.get("repo_url", "unknown")

    # Calculate deterministic score
    deterministic_score = calculate_weighted_score(opinions)

    if not opinions:
        return {"final_report": AuditReport(
            repo_name=repo,
            total_score=0.0,
            criterion_results=[],
            summary="No judicial opinions generated.",
            recommendations=["Check pipeline for failures."]
        )}

    # Group opinions for context
    opinions_ctx = []
    for op in opinions:
        opinions_ctx.append({
            "judge": op.judge,
            "criterion": op.criterion_id,
            "score": op.score,
            "argument": op.argument,
            "cited_evidence": op.cited_evidence
        })
    
    context_str = json.dumps(opinions_ctx, indent=2)

    # Initialize LLM
    llm = get_model()
    
    # Prompt
    prompt = f"""
    You are the Chief Justice of the Automation Auditor Court.
    Your task is to synthesize the final specific Verdict and Audit Report based on the opinions submitted by the Associate Judges (Prosecutor, Defense, TechLead).
    
    INPUT OPINIONS:
    {context_str}
    
    PRE-CALCULATED SCORE:
    The deterministic weighted score for this audit is {deterministic_score:.2f}.
    
    INSTRUCTIONS:
    1. Review all opinions. Acknowledge the conflict between Prosecutor and Defense.
    2. Apply the "Standard of Evidence":
       - Prefer opinions that cite specific code evidence.
       - Acknowledge dissent if present.
    3. Use the PRE-CALCULATED SCORE ({deterministic_score:.2f}) as the 'total_score' in your output. Do not hallucinate a different score.
    4. Generate a list of concise Recommendations.
    5. Write a Summary of the verdict.
    
    OUTPUT FORMAT:
    Return a valid JSON object matching this structure:
    {{
        "total_score": {deterministic_score},
        "criterion_results": [
            {{
                "criterion": "Criterion Name (e.g., 'Security Analysis')",
                "score": float,
                "reasoning": "Synthesis of arguments for this dimension.",
                "evidence_summary": "Key evidence cited."
            }},
            ...
        ],
        "summary": "Executive summary of the audit.",
        "recommendations": ["Rec 1", "Rec 2", ...]
    }}
    """
    
    messages = [
        SystemMessage(content="You are the Chief Justice. Synthesize a fair and evidence-based verdict. Output valid JSON only."),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content
        
        # Naive JSON extraction
        json_str = content
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        
        data = json.loads(json_str.strip())
        
        results = []
        for res in data.get("criterion_results", []):
            evidence_summary = res.get("evidence_summary", "N/A")
            if isinstance(evidence_summary, list):
                evidence_summary = ", ".join(str(e) for e in evidence_summary)
            else:
                evidence_summary = str(evidence_summary)

            results.append(CriterionResult(
                criterion=res.get("criterion", "General"),
                score=float(res.get("score", 0.0)),
                reasoning=res.get("reasoning", "N/A"),
                evidence_summary=evidence_summary
            ))
            
        report = AuditReport(
            repo_name=repo,
            # Force deterministic score
            total_score=deterministic_score,
            criterion_results=results,
            summary=data.get("summary", "Summary generation failed."),
            recommendations=data.get("recommendations", [])
        )

    except Exception as e:
        # Fallback mechanism if LLM fails
        print(f"Chief Justice LLM Failed: {e}. Falling back to heuristic aggregation.")
        
        report = AuditReport(
            repo_name=repo,
            total_score=deterministic_score,
            criterion_results=[CriterionResult(criterion="Fallback Aggregation", score=deterministic_score, reasoning="LLM Synthesis Failed", evidence_summary="See raw opinions")],
            summary=f"LLM Synthesis Failed. Fallback Score: {deterministic_score:.2f}",
            recommendations=["Manual review required."]
        )
        
    return {"final_report": report}
