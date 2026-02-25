import os
import ast
import tempfile
import subprocess
import shutil
from typing import List, Dict, Any, Generator
from contextlib import contextmanager

@contextmanager
def clone_repo(repo_url: str) -> Generator[str, None, None]:
    """
    Securely clones the repo into a temporary directory.
    Yields the temporary directory path and cleans up afterwards.
    """
    temp_dir = tempfile.TemporaryDirectory()
    try:
        # Using subprocess for secure execution
        subprocess.run(
            ["git", "clone", repo_url, temp_dir.name],
            check=True,
            capture_output=True,
            text=True
        )
        yield temp_dir.name
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to clone repository: {e.stderr}")
    finally:
        temp_dir.cleanup()

def extract_git_history(repo_path: str) -> List[Dict[str, str]]:
    """
    Extracts git log to check for atomic commits.
    Returns a list of dictionaries with hash, timestamp, and message.
    """
    try:
        # Format: %h (hash) | %ad (author date) | %s (subject)
        result = subprocess.run(
            ["git", "-C", repo_path, "log", "--pretty=format:%h|%ad|%s", "--date=iso"],
            capture_output=True,
            text=True,
            check=True
        )
        
        history = []
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split('|', 2)
                if len(parts) == 3:
                    history.append({
                        "hash": parts[0],
                        "timestamp": parts[1],
                        "message": parts[2]
                    })
        return history
    except subprocess.CalledProcessError:
        return []

def analyze_graph_structure(repo_path: str) -> Dict[str, Any]:
    """
    Parses Python files to find StateGraph instantiations and graph structure calls.
    Returns a summary of findings.
    """
    findings = {
        "state_graph_instantiations": [],
        "add_edge_calls": [],
        "add_node_calls": [],
        "has_parallel_execution": False
    }
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=file_path)
                    
                    for node in ast.walk(tree):
                        # check methods calls
                        if isinstance(node, ast.Call):
                            # Check for StateGraph(...)
                            if isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                                findings["state_graph_instantiations"].append({
                                    "file": file,
                                    "line": node.lineno
                                })
                            
                            # Check for .add_edge(...) and .add_node(...)
                            elif isinstance(node.func, ast.Attribute):
                                if node.func.attr == "add_edge":
                                    findings["add_edge_calls"].append({
                                        "file": file,
                                        "line": node.lineno
                                    })
                                elif node.func.attr == "add_node":
                                    findings["add_node_calls"].append({
                                        "file": file,
                                        "line": node.lineno
                                    })
                                    
                except Exception:
                    continue

    # Heuristic for parallel execution: explicit parallel lists in add_edge often imply fan-out,
    # but strictly checking usage requires more complex flow analysis. 
    # AST can see list literals in args.
    # For now, we return the raw counts and locations.
    return findings
