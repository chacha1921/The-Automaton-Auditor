import pytest
from src.state import AgentState, Evidence

def test_evidence_model():
    ev = Evidence(
        goal="Test Goal",
        found=True,
        content="Some content",
        location="Some file",
        rationale="Because I said so",
        confidence=1.0
    )
    assert ev.goal == "Test Goal"
    assert ev.found is True

def test_agent_state_initialization():
    state: AgentState = {
        "repo_url": "http://example.com",
        "pdf_path": "doc.pdf",
        "rubric_dimensions": [],
        "evidences": {},
        "opinions": [],
        "final_report": None
    }
    assert state["repo_url"] == "http://example.com"
