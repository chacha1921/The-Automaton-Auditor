import argparse
import os
from dotenv import load_dotenv
from typing import Dict, Any

# Try to import the compiled graph
try:
    from src.graph import graph
except Exception:
    graph = None


def run(graph_obj, repo_url: str, pdf_path: str) -> None:
    initial_state: Dict[str, Any] = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "rubric_dimensions": ["Architecture", "Compliance", "Version Control"],
        "evidences": {},
        "opinions": [],
        "final_report": None,
    }

    if graph_obj is None:
        print("Graph not available. Make sure dependencies are installed and `src.graph` can be imported.")
        return

    # Prefer a streaming API if available, otherwise call run/execute
    if hasattr(graph_obj, "stream"):
        for output in graph_obj.stream(initial_state):
            print("Node output:", output)
    elif hasattr(graph_obj, "run"):
        result = graph_obj.run(initial_state)
        print("Run result:", result)
    else:
        # Last resort: try invoking directly
        try:
            result = graph_obj(initial_state)
            print("Direct graph call result:", result)
        except Exception as e:
            print("Unable to execute graph:", e)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run The Automation Auditor graph on a repo and PDF.")
    parser.add_argument("--repo", required=True, help="Repository URL to audit")
    parser.add_argument("--pdf", required=False, help="Path to project PDF documentation")
    args = parser.parse_args()

    run(graph, args.repo, args.pdf)


if __name__ == "__main__":
    main()
