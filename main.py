import argparse
import os
import sys
import datetime
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from src.graph import app
from src.state import AgentState, AuditReport

def generate_markdown_report(report: AuditReport, evidences: dict, opinions: list, output_dir: str = "audit/report_onpeer_generated"):
    """
    Generates a comprehensive markdown report and saves it to the specified directory.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Create filename based on repo name and timestamp
    # Handle repo name if it's a URL
    repo_name_safe = report.repo_name.replace("https://github.com/", "").replace("/", "_")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/{repo_name_safe}_audit_report_{timestamp}.md"
    
    md = f"# Automation Auditor Report\n\n"
    md += f"**Repository:** {report.repo_name}\n"
    md += f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    # Round total score to 1 decimal place
    md += f"**Total Score:** {report.total_score:.1f}/5.0\n\n"
    
    md += "## Executive Summary\n"
    md += f"{report.summary}\n\n"
    
    md += "## Criterion Breakdown\n"
    if report.criterion_results:
        for res in report.criterion_results:
            md += f"### {res.criterion}\n"
            md += f"- **Score:** {res.score:.1f}/5.0\n"
            md += f"- **Verdict:** {res.reasoning}\n\n"
            
            md += "#### Judge Opinions\n"
            # Filter opinions for this criterion
            relevant_opinions = [op for op in opinions if op.criterion_id == res.criterion or op.criterion_id == "Overall"]
            
            if relevant_opinions:
                for op in relevant_opinions:
                     md += f"- **{op.judge}** (Score {op.score}): {op.argument}\n"
                     if op.cited_evidence:
                        md += f"  - *Evidence:* {', '.join(op.cited_evidence)}\n"
            else:
                md += "_No specific opinions recorded for this criterion._\n"
            md += "\n"
            
    md += "## Remediation Plan\n"
    if report.recommendations:
        md += "Based on the findings, the following actions are recommended:\n\n"
        for rec in report.recommendations:
            # Attempt to group/format if possible, otherwise list
            md += f"- [ ] {rec}\n"
    
    md += "\n---\n"
    md += "## Full Audit Details\n\n"
    
    md += "### 1. Evidence Collected\n"
    if evidences:
        for category, items in evidences.items():
            md += f"#### Category: {category}\n"
            for item in items:
                status = "✅ Found" if item.found else "❌ Not Found"
                md += f"- **Goal:** {item.goal}\n"
                md += f"  - **Status:** {status}\n"
                md += f"  - **Location:** `{item.location}`\n"
                md += f"  - **Rationale:** {item.rationale}\n"
                if item.content:
                    md += f"  - **Content Snippet:**\n\n```\n{item.content}\n```\n"
                else:
                    md += f"  - **Content Snippet:** N/A\n\n"
    else:
        md += "_No evidence collected._\n\n"

    md += "### 2. Judicial Opinions\n"
    if opinions:
        for op in opinions:
            md += f"#### Judge: {op.judge}\n"
            md += f"- **Criterion:** {op.criterion_id}\n"
            md += f"- **Score:** {op.score}\n"
            md += f"- **Argument:** {op.argument}\n"
            if op.cited_evidence:
                md += f"- **Cited Evidence:** {', '.join(op.cited_evidence)}\n"
            md += "\n"
    else:
        md += "_No judicial opinions recorded._\n\n"

    with open(filename, "w") as f:
        f.write(md)
        
    print(f"\n[SUCCESS] Markdown report saved to: {filename}")

def main():
    parser = argparse.ArgumentParser(description="The Automation Auditor: Analyze Repositories and Documentation.")
    parser.add_argument("--repo", type=str, required=True, help="URL of the GitHub repository to audit.")
    parser.add_argument("--pdf", type=str, required=False, help="Path to the PDF documentation (Optional).")
    parser.add_argument("--output", type=str, required=False, help="Path to save the generated report (Optional).")
    
    args = parser.parse_args()
    
    repo_url = args.repo
    pdf_path = args.pdf
    output_path = args.output
    
    if pdf_path and not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        sys.exit(1)

    print(f"Starting Audit for Repo: {repo_url}")
    if pdf_path:
        print(f"Analyzing PDF: {pdf_path}")
    else:
        print("Note: No PDF provided. Skipping documentation analysis.")
    print("-" * 50)

    initial_state = {
        "repo_url": repo_url,
        "pdf_path": pdf_path or "", # Use empty string if None to avoid key errors if typed that way
        "rubric_dimensions": ["Completeness", "Architecture", "Best Practices"],
        "evidences": {},
        "opinions": [],
        "final_report": None
    }

    try:
        # Run the graph with streaming to see node outputs
        print("\n=== EXECUTION LOG ===")
        
        # We need to capture the final state for the report
        final_state = initial_state
        
        # Use stream to print node outputs
        for event in app.stream(initial_state):
            for node, output in event.items():
                print(f"\n--- Node Completed: {node} ---")
                
                if not output:
                    continue

                # Update final state as we go
                for key, value in output.items():
                    if key == "evidences":
                        # Merge evidences
                        if key not in final_state:
                            final_state[key] = {} 
                        if isinstance(value, dict):
                            # Correctly handle dictionary merging for evidences
                            for cat, items in value.items():
                                if cat not in final_state[key]:
                                    final_state[key][cat] = []
                                final_state[key][cat].extend(items)
                    elif key == "opinions":
                        # Append opinions
                        if key not in final_state: 
                            final_state[key] = []
                        if isinstance(value, list):
                            final_state[key].extend(value)
                    else:
                        # For other keys (report, etc), update/overwrite is usually fine
                        final_state[key] = value

                # Special handling for Detectives (Evidence)
                if "evidences" in output:
                    evs = output["evidences"]
                    for category, items in evs.items():
                        print(f"  [Evidence Found]: Category '{category}' - {len(items)} item(s)")
                        for item in items:
                            # Print a snippet of the content
                            snippet = item.content[:100].replace('\n', ' ') + "..." if item.content else "No content"
                            print(f"    - Found: {item.found} | Location: {item.location} | Snippet: {snippet}")

                # Special handling for Judges (Opinions)
                if "opinions" in output:
                    for op in output["opinions"]:
                        print(f"  [Judicial Opinion]: {op.judge}")
                        print(f"    - Criterion: {op.criterion_id} | Score: {op.score} | Argument: {op.argument[:100]}...")

                # Special handling for Justice (Report)
                if "final_report" in output and output["final_report"]:
                     print("  [Justice]: Final Report Generated.")

        print("\n=== EXECUTION COMPLETE ===")
        
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
           
           print("\n" + "="*50)
           print("FULL AUDIT DETAILS (EVIDENCES & OPINIONS)")
           print("="*50)
           
           # Print All Evidence
           evidences = final_state.get("evidences", {})
           if evidences:
               print("\n--- Gathered Evidence ---")
               for category, items in evidences.items():
                   print(f"\nCategory: {category}")
                   for idx, item in enumerate(items, 1):
                        print(f"  {idx}. [Found: {item.found}] {item.goal}")
                        print(f"     Location: {item.location}")
                        print(f"     Rationale: {item.rationale}")
                        print(f"     Confidence: {item.confidence}")

           # Print All Opinions
           opinions = final_state.get("opinions", [])
           if opinions:
               print("\n--- Judicial Opinions ---")
               for op in opinions:
                   print(f"\nJudge: {op.judge}")
                   print(f"  - Criterion: {op.criterion_id} (Score: {op.score})")
                   print(f"    Argument: {op.argument}")
                   print(f"    Cited Evidence: {op.cited_evidence}")

           print("="*50)
           if output_path:
               output_directory = output_path
               print(f"[CONFIG] Using provided output directory: {output_directory}")
           else:
               # If auditing my own repo, save to "audit/report_onself_generated"
               # Otherwise, default to "audit/report_onpeer_generated"
               
               my_username = "chacha1921" # Adjust this to your GitHub username
               target_repo = repo_url.lower()
               
               if my_username.lower() in target_repo:
                   output_directory = "audit/report_onself_generated"
                   print(f"[CONFIG] Detecting self-audit for user '{my_username}'. Output set to: {output_directory}")
               else:
                   output_directory = "audit/report_onpeer_generated"
                   print(f"[CONFIG] Detecting peer-audit. Output set to: {output_directory}")

           # Generate Markdown Report
           print(f"\n[INFO] Saving final report...")
           generate_markdown_report(report, evidences, opinions, output_directory)
           
           # LangSmith Link Hint
           if os.getenv("LANGCHAIN_TRACING_V2") == "true":
               print("\n[INFO] Trace available in LangSmith project:", os.getenv("LANGCHAIN_PROJECT"))

    except Exception as e:
        print(f"Fatal Error during execution: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
