from typing import Dict, Any, List, Optional
import json
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, AuditReport, CriterionResult, JudicialOpinion, Evidence
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

def calculate_criterion_scores(opinions: List[JudicialOpinion]) -> Dict[str, float]:
    """
    Calculates weighted scores per criterion.
    Returns a dictionary: {criterion_id: weighted_score}
    """
    scores = {}
    weights = {}
    
    role_weights = {
        "TechLead": 1.5,
        "Prosecutor": 1.0,
        "Defense": 1.0, 
        "DebateModerator": 2.0
    }

    for op in opinions:
        cid = op.criterion_id
        if cid not in scores:
            scores[cid] = 0.0
            weights[cid] = 0.0
            
        weight = role_weights.get(op.judge, 1.0)
        scores[cid] += op.score * weight
        weights[cid] += weight
        
    final_scores = {}
    for cid in scores:
        if weights[cid] > 0:
            final_scores[cid] = scores[cid] / weights[cid]
        else:
            final_scores[cid] = 0.0
            
    return final_scores

def detect_security_override(opinions: List[JudicialOpinion]) -> Optional[float]:
    """
    Deterministic check for Security Override.
    If Prosecutor gives score <= 2 AND mentions 'security'/'unsafe'/'os.system',
    return the CAP value (2.0 - Critical Failure). Otherwise return None.
    """
    for op in opinions:
        if op.judge == "Prosecutor" and op.score <= 2:
            arg_lower = op.argument.lower()
            if any(k in arg_lower for k in ["security", "unsafe", "os.system", "vulnerability", "malicious"]):
                print("DEBUG: Security Override Triggered by Prosecutor")
                return 2.0 # Cap at 2.0 for critical security failures
    return None

def apply_fact_supremacy(criterion_scores: Dict[str, float], evidences: Dict[str, List[Evidence]]) -> List[str]:
    """
    Applies 'Fact Supremacy': If RepoInvestigator finds concrete evidence (AST/Code),
    it overrides low scores based on missing docs or hallucinations.
    Returns a list of override messages.
    """
    repo_evidences = evidences.get("repo", [])
    overrides = []
    
    # Map Goals to Criterion Names (fuzzy match or direct map)
    # The rubric usually aligns Goal -> Criterion
    
    for ev in repo_evidences:
        if ev.found and ev.confidence > 0.8:
            # Strong evidence found in Code
            target_crit = None
            
            # Simple heuristic mapping based on goal keywords
            if "Structured Output" in ev.goal:
                 target_crit = "Structured Output Enforcement"
            elif "State Management" in ev.goal:
                 target_crit = "State Management Rigor"
            elif "Safe Tool" in ev.goal:
                 target_crit = "Safe Tool Engineering"
            elif "Graph Orchestration" in ev.goal:
                 target_crit = "Graph Orchestration Architecture"
                 
            if target_crit and target_crit in criterion_scores:
                current_score = criterion_scores[target_crit]
                if current_score < 4.0:
                    criterion_scores[target_crit] = 5.0 # Facts override doubts
                    overrides.append(f"Fact Supremacy: Boosted {target_crit} to 5.0 based on AST evidence.")
                    
    return overrides

def detect_variance(opinions: List[JudicialOpinion]) -> List[str]:
    """
    Detects criteria with high variance (> 2 points difference).
    Returns list of criterion_ids with high dissent.
    """
    ranges = {}
    
    for op in opinions:
        cid = op.criterion_id
        if cid not in ranges:
            ranges[cid] = []
        ranges[cid].append(op.score)
        
    dissenting_criteria = []
    for cid, scores in ranges.items():
        if len(scores) > 1 and (max(scores) - min(scores) > 2):
            dissenting_criteria.append(cid)
            
    return dissenting_criteria

def chief_justice_node(state: AgentState) -> Dict[str, Any]:
    """
    Chief Justice Node: Synthesizes opinions into a final report using deterministic logic + LLM narrative.
    """
    opinions: List[JudicialOpinion] = state.get("opinions", []) or []
    repo = state.get("repo_url", "unknown")

    # 1. Deterministic Scoring
    weighted_score = calculate_weighted_score(opinions)
    criterion_scores = calculate_criterion_scores(opinions)
    
    # NEW: Fact Supremacy - Override scores based on AST Evidence
    evidences = state.get("evidences", {}) or {}
    # Combine all evidences into a flat list or handle nested struct
    # Evidences is Annotated[Dict[str, List[Evidence]], operator.ior]
    # So it's {"repo": List[Evidence], "doc": ...}
    
    all_repo_evidences = evidences.get("repo", [])
    supremacy_msg = apply_fact_supremacy(criterion_scores, {"repo": all_repo_evidences})
    
    # Recalculate Weighted Score if needed, but for simplicity, we treat weighted_score as 'opinion average'
    # and criterion_scores as 'final deterministic values'.
    # If Fact Supremacy changed anything, we should reflect it in the final score.
    # Simple average of criterion_scores might be better final score?
    if supremacy_msg:
        # Re-average
        sum_scores = sum(criterion_scores.values())
        count = len(criterion_scores)
        if count > 0:
            weighted_score = sum_scores / count # New baseline
            
    # 2. Security Override Logic
    security_cap = detect_security_override(opinions)
    final_score = weighted_score
    override_msg = ""
    
    if security_cap is not None and weighted_score > security_cap:
        final_score = security_cap
        override_msg = f"CRITICAL: Score capped at {security_cap} due to Security Protocol violation flagged by Prosecutor."
        
    # 3. Variance Detection
    dissent_list = detect_variance(opinions)
    dissent_msg = ""
    if dissent_list:
        dissent_msg = f"Significant Judicial Dissent detected in: {', '.join(dissent_list)}. Synthesis required."

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
    criterion_scores_str = json.dumps(criterion_scores, indent=2)

    # Initialize LLM
    llm = get_model()
    
    # Prompt - Now using PRE-COMPUTED values
    supremacy_text = "\n".join(supremacy_msg) if supremacy_msg else "None"
    
    prompt = f"""
    You are the Chief Justice. Synthesize the final Audit Report.
    
    INPUT DATA:
    - Judicial Opinions: {context_str}
    - Computed Criterion Scores: {criterion_scores_str}
    - Calculated Weighted Score: {weighted_score:.2f}
    - Security Override Status: {override_msg if override_msg else "None"}
    - Fact Supremacy Applied: {supremacy_text}
    - Dissent Notices: {dissent_msg if dissent_msg else "None"}
    
    MANDATORY INSTRUCTIONS:
    1. Your Total Score IS DETERMINED as: {final_score:.2f}. Do not recalculate it.
    2. Write a Summary that synthesizes the divergent views, explicitly mentioning the dissent in {dissent_msg} if present.
    3. If 'Fact Supremacy' is applied, explain that AST/Structural evidence overrode subjective opinions.
    4. If Security Override is active, explain specifically WHY the score was capped.
    5. Provide specific Recommendations.
    5. For 'criterion_results', use the exact scores provided in 'Computed Criterion Scores', but generate the qualitative 'reasoning'.
    6. CRITICAL: In your 'summary', explicitly surface "Top Remaining Gaps" and "Primary Remediation Priorities" to help senior engineers quickly grasp the status.

    OUTPUT FORMAT (JSON):
    {
        "total_score": {final_score:.2f}, 
        "criterion_results": [
            {
                "criterion": "Criterion Name",
                "score": float, # MUST MATCH Computed Score
                "reasoning": "Narrative explanation of the score and any conflict.",
                "evidence_summary": "Key evidence."
            }
        ],
        "summary": "Executive summary including Top Remaining Gaps and Primary Remediation Priorities...",
        "recommendations": ["..."]
    }
    """
    
    messages = [
        SystemMessage(content="You are the Chief Justice. Use the provided deterministic scores. Do not hallucinate numbers."),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        content = response.content
        
        # Robust JSON extraction
        json_str = content.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        
        # Clean potential leading/trailing non-json chars
        start = json_str.find("{")
        end = json_str.rfind("}")
        if start != -1 and end != -1:
            json_str = json_str[start:end+1]

        data = json.loads(json_str)
        
        results = []
        # Merge LLM reasoning with Deterministic Scores
        # We start with our computed scores keys to ensure coverage
        for crit, score in criterion_scores.items():
            # Find matching reasoning from LLM output
            reasoning = "Score calculated deterministically."
            evidence = "See opinions."
            
            # Try to find the LLM's narrative for this criterion
            for res in data.get("criterion_results", []):
                if res.get("criterion") == crit:
                    reasoning = res.get("reasoning", reasoning)
                    evidence = res.get("evidence_summary", evidence)
                    break
            
            results.append(CriterionResult(
                criterion=crit,
                score=score,
                reasoning=reasoning,
                evidence_summary=str(evidence)
            ))
            
        report = AuditReport(
            repo_name=repo,
            total_score=final_score,
            criterion_results=results,
            summary=data.get("summary", "Summary generation failed."),
            recommendations=data.get("recommendations", [])
        )

    except Exception as e:
        # Fallback mechanism
        print(f"Chief Justice LLM Failed: {e}")
        
        report = AuditReport(
            repo_name=repo,
            total_score=final_score,
            criterion_results=[],
            summary=f"LLM Synthesis Failed. Score: {final_score:.2f}. {override_msg}",
            recommendations=["Manual review required."]
        )
        
    return {"final_report": report}
