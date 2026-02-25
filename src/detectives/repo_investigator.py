import os
import ast
import tempfile
import subprocess
import shutil
from typing import List, Dict, Any
from pathlib import Path
from src.state import AgentState, Evidence

def clone_repo(repo_url: str) -> tempfile.TemporaryDirectory:
    """Securely clones the repo into a temporary directory."""
    temp_dir = tempfile.TemporaryDirectory()
    try:
        # Clone depth 1 might be insufficient if we want full history, 
        # but usually good strictly for code analysis. 
        # However, requirements ask for git history, so we do a full clone.
        subprocess.run(
            ["git", "clone", repo_url, temp_dir.name],
            check=True,
            capture_output=True,
            text=True
        )
        return temp_dir
    except subprocess.CalledProcessError as e:
        temp_dir.cleanup()
        raise RuntimeError(f"Failed to clone repository: {e.stderr}")

def analyze_ast_for_langgraph(directory: str) -> List[Dict[str, Any]]:
    """
    Parses Python files in the directory using AST to find 
    StateGraph instantiation and add_edge calls.
    """
    findings = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=file_path)
                    
                    for node in ast.walk(tree):
                        # Check for StateGraph instantiation
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                                findings.append({
                                    "type": "instantiation",
                                    "file": file,
                                    "line": node.lineno,
                                    "details": "Found StateGraph instantiation"
                                })
                            # Check for add_edge calls
                            elif isinstance(node.func, ast.Attribute) and node.func.attr == "add_edge":
                                findings.append({
                                    "type": "usage",
                                    "file": file,
                                    "line": node.lineno,
                                    "details": "Found add_edge call"
                                })
                except Exception:
                    # Skip files that cannot be parsed
                    continue
    return findings

def check_git_history(directory: str) -> List[str]:
    """Extracts git log to check for atomic commits."""
    try:
        result = subprocess.run(
            ["git", "-C", directory, "log", "--pretty=format:%h - %s"],
            capture_output=True,
            text=True,
            check=True
        )
        commits = result.stdout.strip().split('\n')
        return commits[:10]  # Return last 10 commits for analysis
    except subprocess.CalledProcessError:
        return []

def repo_investigator_node(state: AgentState) -> Dict:
    """
    LangGraph node that investigates the repository for specific patterns.
    """
    repo_url = state['repo_url']
    evidences = {}

    try:
        # Context manager handles cleanup automatically when temp_dir goes out of scope
        with clone_repo(repo_url) as temp_dir:
            temp_path = temp_dir.name
            
            # AST Analysis
            ast_findings = analyze_ast_for_langgraph(temp_path)
            has_graph = any(f['type'] == 'instantiation' for f in ast_findings)
            has_edges = any(f['type'] == 'usage' for f in ast_findings)
            
            graph_content = "\n".join([f"{f['file']}:{f['line']} - {f['details']}" for f in ast_findings])
            
            evidences["langgraph_structure"] = Evidence(
                goal="Identify LangGraph Implementation",
                found=has_graph and has_edges,
                content=graph_content if graph_content else "No StateGraph or add_edge calls found.",
                location="Source Code",
                rationale="AST parsing detected structural components of a graph definition.",
                confidence=1.0 if (has_graph and has_edges) else 0.5
            )

            # Git History Analysis
            commits = check_git_history(temp_path)
            commit_content = "\n".join(commits)
            
            evidences["git_history"] = Evidence(
                goal="Check Version Control Practices",
                found=len(commits) > 0,
                content=commit_content if commit_content else "No git history found.",
                location=".git",
                rationale=f"Extracted {len(commits)} recent commits for manual review of atomicity.",
                confidence=1.0
            )

    except Exception as e:
        evidences["repo_access"] = Evidence(
            goal="Access Repository",
            found=False,
            content=f"Error accessing or analyzing repo: {str(e)}",
            location="Remote",
            rationale="Failed to clone or parse repository.",
            confidence=0.0
        )

    return {"evidences": evidences}