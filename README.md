# The Automation Auditor

The Automation Auditor is a specialized LangGraph-based framework designed to critically analyze code repositories and documentation for compliance, architectural soundness, and best practices. It employs a multi-agent system mimicking a judicial process to evaluate submissions.

## Architecture

The system operates in three distinct phases:

### 1. The Detective Layer (Forensics)
- **RepoInvestigator**: Securely clones remote repositories, analyzes abstract syntax trees (AST) to identify LangGraph structures (`StateGraph`, `add_edge`), and examines git commit history for atomic practices.
- **DocAnalyst**: Ingests project documentation (PDF) using semantic chunking and performs targeted queries for key conceptual frameworks like "Metacognition" and "Dialectical Synthesis".
- **VisionInspector**: (Optional/Experimental) Scans for visual artifacts and diagrams.

### 2. The Judicial Layer (Dialectics)
Three specialized "Judges" review the aggregated evidence with distinct personas:
- **The Prosecutor**: Assumes "vibe coding" and looks for flaws, security risks, and missing validations.
- **The Defense Attorney**: Highlights effort, creative workarounds, and best practices.
- **The Tech Lead**: Evaluates practical architectural soundness and maintainability.

### 3. The Justice Layer (Synthesis)
- **Chief Justice**: Synthesizes the opinions using deterministic conflict resolution rules:
    - **Security Override**: Critical security flaws flagged by the Prosecutor cap the maximum score.
    - **Fact Supremacy**: Opinions citing concrete evidence are weighed heavily.
    - **Dissent Requirement**: Significant disagreement between judges is explicitly noted.
    - Produces a final **AuditReport** with a score and actionable recommendations.

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
    Sync dependencies using the lockfile:
    ```bash
    uv sync
    source .venv/bin/activate
    ```

## Usage

### Run an Audit

Run the main script with the target repository URL and PDF report path:

```bash
# Ensure .env is configured with OPENAI_API_KEY
uv run main.py --repo "https://github.com/username/target-repo" --pdf "path/to/report.pdf"
```

### Docker

Build and run the containerized auditor:

```bash
docker build -t auditor .
docker run --env-file .env auditor uv run main.py --repo "..." --pdf "..."
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
    OPENAI_API_KEY=your_openai_key_here
    ```
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

## Reproducibility and Locking

To make builds reproducible, generate a lockfile with `uv` or pin your environment. An example lock file is included at `requirements.lock.txt`, but you should produce a lock with your environment:

```bash
# Generate a lock with uv (recommended):
uv lock

# Or create a pinned requirements file from your virtualenv
pip freeze > requirements.txt
```

## Python Version and Optional Dependencies

- **Python version**: This project targets Python 3.13+ (see `pyproject.toml`). Use `pyenv` or your system package manager to install the matching interpreter.
- **Optional dependencies**: For better PDF parsing and structured extraction you can install `docling` and `pypdf` (recommended). If you plan to run LLM-based synthesis, ensure `langchain` and `langchain-openai` are installed and API keys configured.

## Dedicated full-audit command

We've added a small CLI runner that executes the graph and streams node output. Example:

```bash
# activate virtualenv first
source .venv/bin/activate

# run the audit
python -m src.run_audit --repo https://github.com/langchain-ai/langgraph-example.git --pdf ./docs/project_specs.pdf
```

This will attempt to import `src.graph` and run the compiled graph; use `uv sync` / `uv lock` first to ensure dependencies are installed and pinned.
