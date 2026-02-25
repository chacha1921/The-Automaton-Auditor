# The Automation Auditor

The Automation Auditor is a LangGraph-based framework designed to critically analyze code repositories and documentation for compliance, architectural soundness, and best practices.

## Overview (Interim Phase 1 & 2)

This repository contains the foundational "Detective Layer" of the auditing system. It employs a multi-agent architecture to inspect projects:

- **RepoInvestigator**: Securely clones remote repositories, analyzes abstract syntax trees (AST) to identify LangGraph structures, and examines git commit history for atomic practices.
- **DocAnalyst**: Ingests project documentation (PDF) and performs semantic checks for key conceptual frameworks like "Metacognition" and "Dialectical Synthesis".
- **EvidenceAggregator**: A synchronization node that collects findings from all detectives for downstream processing.

## Setup

This project uses `uv` for fast Python package management.

1.  **Install `uv`** (if not already installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Clone the repository**:
    ```bash
    git clone https://github.com/your-org/the-automation-auditor.git
    cd the-automation-auditor
    ```

3.  **Install dependencies**:
    Create a virtual environment and sync dependencies:
    ```bash
    uv venv
    source .venv/bin/activate
    uv sync
    # Or manually install packages
    uv pip install langgraph langchain langchain-openai pydantic python-dotenv docling
    ```

## Configuration

1.  **Environment Variables**:
    Copy the example environment file and configure your API keys.
    ```bash
    cp .env.example .env
    ```

2.  **Edit `.env`**:
    Open `.env` and fill in your keys:
    ```ini
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_API_KEY=your_langchain_api_key_here
    LANGCHAIN_PROJECT=the-automation-auditor
    OPENAI_API_KEY=your_openai_api_key_here
    ```

## Usage

You can invoke the auditor graph directly from Python. Here is an example script:

```python
import os
from dotenv import load_dotenv
from src.graph import graph

# Load environment variables
load_dotenv()

def run_audit(repo_url: str, pdf_path: str):
    """
    Run the automation auditor on a target repository and documentation.
    """
    print(f"Starting audit for {repo_url}...")
    
    initial_state = {
        "repo_url": repo_url,
        "pdf_path": pdf_path,
        "rubric_dimensions": ["Architecture", "Compliance", "Version Control"],
        "evidences": {},
        "opinions": [],
        "final_report": None
    }
    
    # helper to print streaming updates
    for output in graph.stream(initial_state):
        for key, value in output.items():
            print(f"Finished node: {key}")
            if "evidences" in value:
                for category, ev_list in value["evidences"].items():
                    print(f"  - Collected {len(ev_list)} new pieces of evidence for {category}")

if __name__ == "__main__":
    # Example Usage
    TARGET_REPO = "https://github.com/langchain-ai/langgraph-example.git"
    TARGET_PDF = "./docs/project_specs.pdf"
    
    run_audit(TARGET_REPO, TARGET_PDF)
```
