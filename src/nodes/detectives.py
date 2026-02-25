from typing import Dict, Any, List
from src.state import AgentState, Evidence
from src.tools.repo_tools import clone_repo, analyze_graph_structure, extract_git_history
from src.tools.doc_tools import ingest_pdf, query_document

def repo_investigator(state: AgentState) -> Dict[str, Any]:
    """
    Investigates the repository for LangGraph structure and Git practices.
    Returns: {"evidences": {"repo": [Evidence, Evidence, ...]}}
    """
    repo_url = state['repo_url']
    evidences: List[Evidence] = []
    
    try:
        # Clone repo
        with clone_repo(repo_url) as temp_dir:
            # 1. Check Graph Structure
            struct_findings = analyze_graph_structure(temp_dir)
            
            # Evidence: StateGraph existence
            found_stategraph = len(struct_findings["state_graph_instantiations"]) > 0
            evidences.append(Evidence(
                goal="Identify LangGraph Implementation",
                found=found_stategraph,
                content=f"Found {len(struct_findings['state_graph_instantiations'])} distinct StateGraph instances.",
                location="Source Code",
                rationale="Parsed AST for `StateGraph()` calls.",
                confidence=1.0 if found_stategraph else 0.5
            ))
            
            # Evidence: Parallel Execution (Heuristic: >1 edge added)
            # A real parallel check is harder, but let's say having add_edge calls is a prerequisite
            found_edges = len(struct_findings["add_edge_calls"]) > 0
            evidences.append(Evidence(
                goal="Check for Graph Connectivity",
                found=found_edges,
                content=f"Found {len(struct_findings['add_edge_calls'])} add_edge calls.",
                location="Source Code",
                rationale="Parsed AST for `.add_edge()` calls.",
                confidence=1.0 if found_edges else 0.5
            ))

            # 2. Check Git History
            history = extract_git_history(temp_dir)
            found_history = len(history) > 0
            evidences.append(Evidence(
                goal="Check Version Control Atomic Commits",
                found=found_history,
                content=str(history[:5]) if found_history else "No commits found.",
                location=".git",
                rationale="Extracted recent commits to analyze granularity.",
                confidence=1.0
            ))
            
    except Exception as e:
        evidences.append(Evidence(
            goal="Access Repository",
            found=False,
            content=f"Error accessing or analyzing repo: {str(e)}",
            location="Remote",
            rationale="Failed to clone or parse repository.",
            confidence=0.0
        ))

    return {"evidences": {"repo": evidences}}

def doc_analyst(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes the documentation (PDF) for key concepts.
    Returns: {"evidences": {"doc": [Evidence, Evidence, ...]}}
    """
    pdf_path = state.get('pdf_path')
    evidences: List[Evidence] = []
    
    if not pdf_path:
        evidences.append(Evidence(
            goal="Read Documentation",
            found=False,
            content="No PDF path provided.",
            location="Input",
            rationale="Missing input parameter.",
            confidence=0.0
        ))
        return {"evidences": {"doc": evidences}}

    try:
        # Ingest
        full_text = ingest_pdf(pdf_path)
        
        # Check for 'Metacognition'
        res_metacog = query_document(full_text, "Metacognition")
        evidences.append(Evidence(
            goal="Find Concept: Metacognition",
            found=res_metacog["found"],
            content=res_metacog["details"],
            location="PDF Content",
            rationale="Keyword search in extracted text.",
            confidence=1.0
        ))
        
        # Check for 'Dialectical Synthesis' (implied requirement from context)
        res_synthesis = query_document(full_text, "Dialectical Synthesis")
        evidences.append(Evidence(
            goal="Find Concept: Dialectical Synthesis",
            found=res_synthesis["found"],
            content=res_synthesis["details"],
            location="PDF Content",
            rationale="Keyword search in extracted text.",
            confidence=1.0
        ))
        
    except Exception as e:
         evidences.append(Evidence(
            goal="Process PDF Document",
            found=False,
            content=f"Error processing PDF: {str(e)}",
            location="PDF Processor",
            rationale="Exception occurred during extraction.",
            confidence=0.0
        ))
         
    return {"evidences": {"doc": evidences}}
