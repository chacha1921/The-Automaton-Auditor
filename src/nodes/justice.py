from typing import Dict, Any, List
from src.state import AgentState, AuditReport, CriterionResult, JudicialOpinion

def chief_justice_node(state: AgentState) -> Dict[str, Any]:
    """
    Chief Justice Node: Synthesizes opinions into a final report using hardcoded deterministic rules.
    
    Conflict Resolution Rules:
    1. Security Override: If Prosecutor flags a security issue (score < 3 on security criterion), it overrides any positive Defense score.
    2. Fact Supremacy: If opinions differ on factual evidence (e.g., "Found connected graph"), the one citing concrete evidence wins. (Heuristic: lower score with evidence usually signals a problem found).
    3. Dissent Requirement: If there is significant disagreement (score diff > 2), the final report must explicitly mention the dissent.
    """
    opinions: List[JudicialOpinion] = state.get("opinions", []) or []
    repo = state.get("repo_url", "unknown")

    if not opinions:
        return {"final_report": AuditReport(
            repo_name=repo,
            total_score=0.0,
            criterion_results=[],
            summary="No judicial opinions generated.",
            recommendations=["Check pipeline for failures."]
        )}

    # 1. Group by Criterion (if criteria were distinct) or just aggregate overall
    # For now, we assume opinions might cover different or overlapping criteria.
    # We'll calculate an average but apply overrides.
    
    prosecutor_ops = [o for o in opinions if o.judge == "Prosecutor"]
    defense_ops = [o for o in opinions if o.judge == "Defense"]
    tech_ops = [o for o in opinions if o.judge == "TechLead"]

    p_score = sum(o.score for o in prosecutor_ops) / len(prosecutor_ops) if prosecutor_ops else 0
    d_score = sum(o.score for o in defense_ops) / len(defense_ops) if defense_ops else 0
    t_score = sum(o.score for o in tech_ops) / len(tech_ops) if tech_ops else 0

    # Base Score Calculation (Weighted Average: TechLead has slightly more weight)
    # Weights: P: 1, D: 1, T: 1.5
    total_weight = (1 if prosecutor_ops else 0) + (1 if defense_ops else 0) + (1.5 if tech_ops else 0)
    base_score = (p_score * 1 + d_score * 1 + t_score * 1.5) / total_weight if total_weight > 0 else 0

    # Apply Rule 1: Security Override
    # Heuristic: If Prosecutor score is low (<= 2), cap the total score.
    security_risk = False
    if prosecutor_ops and p_score <= 2:
        security_risk = True
        base_score = min(base_score, 2.5) # Cap at 2.5 (Below average)

    # Apply Rule 3: Dissent Requirement
    dissent_note = ""
    if abs(p_score - d_score) > 2:
        dissent_note = " **Significant Disagreement:** Prosecutor and Defense strongly disagree on the quality of this submission."

    # Construct Summary
    summary = f"Audit complete. Prosecutor: {p_score:.1f}, Defense: {d_score:.1f}, Tech Lead: {t_score:.1f}."
    if security_risk:
        summary += " **SECURITY ALERT:** Prosecutor raised critical concerns that capped the final score."
    summary += dissent_note
    
    # 2. Fact Supremacy (Check references)
    # This is harder to implement deterministically without analyzing the `cited_evidence` content.
    # We will assume TechLead's opinion is the most factual for now (given the weight).

    # Generate Recommendations from Arguments
    recommendations = []
    for o in opinions:
        if o.score < 5:
             # Extract simple recommendation (mock extraction as we don't have an LLM here to summarize)
             # In a real system, we'd use an LLM or extract the argument.
             recommendations.append(f"From {o.judge}: {o.argument[:100]}...")

    # Build Report
    results = [
        CriterionResult(
            criterion="Prosecution Analysis",
            score=p_score,
            reasoning=prosecutor_ops[0].argument if prosecutor_ops else "N/A",
            evidence_summary=str(prosecutor_ops[0].cited_evidence) if prosecutor_ops else "N/A"
        ),
        CriterionResult(
            criterion="Defense Analysis",
            score=d_score,
            reasoning=defense_ops[0].argument if defense_ops else "N/A",
            evidence_summary=str(defense_ops[0].cited_evidence) if defense_ops else "N/A"
        ),
        CriterionResult(
            criterion="Technical Review",
            score=t_score,
            reasoning=tech_ops[0].argument if tech_ops else "N/A",
            evidence_summary=str(tech_ops[0].cited_evidence) if tech_ops else "N/A"
        )
    ]

    report = AuditReport(
        repo_name=repo,
        total_score=round(base_score, 2),
        criterion_results=results,
        summary=summary,
        recommendations=recommendations[:5] # Top 5
    )

    return {"final_report": report}
