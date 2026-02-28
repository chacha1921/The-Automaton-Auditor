import argparse
import os
import sys
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from src.graph import app
from src.state import AgentState, AuditReport

def main():
    parser = argparse.ArgumentParser(description="The Automation Auditor: Analyze Repositories and Documentation.")
    parser.add_argument("--repo", type=str, required=True, help="URL of the GitHub repository to audit.")
    parser.add_argument("--pdf", type=str, required=True, help="Path to the PDF documentation.")
    
    args = parser.parse_args()
    
    repo_url = args.repo
    pdf_path = args.pdf
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)

    print(f"Starting Audit for Repo: {repo_url}")
    print(f"Analyzing PDF: {pdf_path}")
    print("-" * 50)

    initial_state = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "rubric_dimensions": ["Completeness", "Architecture", "Best Practices"],
        "evidences": {},
        "opinions": [],
        "final_report": None
    }

    try:
        # Run the graph
        # Using .invoke() for simplicity, or .stream() if we want updates.
        
        # Invoke is simpler for terminal output collection if stream is noisy
        final_state = app.invoke(initial_state)
        
        report: AuditReport = final_state.get("final_report")
        
        if report:
           print("\n" + "="*50)
           print("FINAL AUDIT REPORT")
           print("="*50)
           print(f"Repo: {report.repo_name}")
           # Handle criteria results which might be empty or problematic
           total = report.total_score if report.total_score is not None else 0.0
           print(f"Total Score: {total:.1f}/5.0")
           print("\nSummary:")
           print(report.summary)
           
           if report.criterion_results:
               print("\nDetailed Findings:")
               for res in report.criterion_results:
                   print(f"  - {res.criterion}: {res.score:.1f} | {res.reasoning}")
           
           if report.recommendations:
               print("\nRecommendations:")
               for rec in report.recommendations:
                   print(f"  * {rec}")
           print("="*50)
        else:
           print("Error: No Final Report Generated.")

    except Exception as e:
        print(f"Fatal Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
