from typing import Dict, Any, List
import json
import os
import ast
import base64
import mimetypes
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState, Evidence
from src.tools.repo_tools import clone_repo, extract_git_history
from src.tools.doc_tools import ingest_pdf_and_chunk, extract_images_from_pdf
from src.utils.llm import get_model

def _load_rubric():
    try:
        with open("rubric.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"dimensions": []}

def analyze_graph_structure(path: str) -> Dict[str, Any]:
    """
    Analyzes the repository structure using AST to verify rubric dimensions.
    Checks for StateGraph, parallel branches (fan-out), and conditional edges.
    """
    findings = {
        "State Management Rigor": {"found": False, "evidence": []},
        "Graph Orchestration Architecture": {"found": False, "evidence": []},
        "Structured Output Enforcement": {"found": False, "evidence": []},
        "Safe Tool Engineering": {"found": True, "evidence": []} # Assume safe until proven otherwise
    }
    
    for root, _, files in os.walk(path):
        if ".git" in root:
            continue
            
        for file in files:
            if not file.endswith(".py"):
                continue
                
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, path)
                
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    # --- Safe Tool Engineering Check ---
                    # Check for ACTUAL calls to os.system, effectively ignoring string literals checking for it
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            # Case: os.system(...)
                            if isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and node.func.attr == "system":
                                findings["Safe Tool Engineering"]["found"] = False
                                findings["Safe Tool Engineering"]["evidence"].append(f"Unsafe 'os.system' call detected in {rel_path} line {node.lineno}")

                    # --- State Management Check ---
                    if isinstance(node, ast.ClassDef):
                        for base in node.bases:
                            if (isinstance(base, ast.Name) and base.id == "TypedDict") or \
                               (isinstance(base, ast.Attribute) and base.attr == "TypedDict"):
                                findings["State Management Rigor"]["found"] = True
                                findings["State Management Rigor"]["evidence"].append(f"Found TypedDict '{node.name}' in {rel_path}")
                            
                            if (isinstance(base, ast.Name) and base.id == "BaseModel") or \
                               (isinstance(base, ast.Attribute) and base.attr == "BaseModel"):
                                findings["State Management Rigor"]["found"] = True
                                findings["State Management Rigor"]["evidence"].append(f"Found BaseModel '{node.name}' in {rel_path}")

                    # --- Graph Orchestration Check ---
                    if isinstance(node, ast.Call):
                        func = node.func
                        # 1. StateGraph Instantiation
                        if (isinstance(func, ast.Name) and func.id == "StateGraph") or \
                           (isinstance(func, ast.Attribute) and func.attr == "StateGraph"):
                            findings["Graph Orchestration Architecture"]["found"] = True
                            findings["Graph Orchestration Architecture"]["evidence"].append(f"Found StateGraph instantiation in {rel_path} line {node.lineno}")
                        
                        # 2. Graph Methods
                        if isinstance(func, ast.Attribute) and func.attr in ["add_node", "add_edge", "compile"]:
                             findings["Graph Orchestration Architecture"]["found"] = True
                             findings["Graph Orchestration Architecture"]["evidence"].append(f"Found graph method '{func.attr}' in {rel_path} line {node.lineno}")
                        
                        # 3. Parallelism / Branching Detection
                        # Check for add_conditional_edges
                        if isinstance(func, ast.Attribute) and func.attr == "add_conditional_edges":
                            findings["Graph Orchestration Architecture"]["found"] = True
                            findings["Graph Orchestration Architecture"]["evidence"].append(f"Found CONDITIONAL EDGE in {rel_path} line {node.lineno} (Non-Linear Control Flow)")

                    # --- Structured Output Check ---
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Attribute) and func.attr == "with_structured_output":
                            findings["Structured Output Enforcement"]["found"] = True
                            findings["Structured Output Enforcement"]["evidence"].append(f"Found .with_structured_output() in {rel_path} line {node.lineno}")
                        
                        if isinstance(func, ast.Attribute) and func.attr == "bind_tools":
                             findings["Structured Output Enforcement"]["evidence"].append(f"Found .bind_tools() in {rel_path} line {node.lineno}")

            except Exception as e:
                # print(f"Error parsing {file_path}: {e}")
                continue
                
    return findings

def repo_investigator(state: AgentState) -> Dict[str, Any]:
    """
    Investigates the repository using deterministic AST analysis + Git history check.
    Returns: {"evidences": {"repo": [Evidence, Evidence, ...]}}
    """
    repo_url = state['repo_url']
    evidences: List[Evidence] = []
    
    print(f"DEBUG: RepoInvestigator starting deterministic analysis for {repo_url}")

    try:
        with clone_repo(repo_url) as temp_dir:
            # 1. Git Forensic Analysis
            try:
                git_history = extract_git_history(temp_dir)
                has_progression = len(git_history) > 3
                evidences.append(Evidence(
                    goal="Git Forensic Analysis",
                    found=has_progression,
                    content=f"Found {len(git_history)} commits. First: {git_history[-1]['message'] if git_history else 'None'}, Last: {git_history[0]['message'] if git_history else 'None'}",
                    location=".git",
                    rationale="More than 3 commits usually indicates iterative development.",
                    confidence=1.0
                ))
            except Exception as e:
                print(f"DEBUG: Git history extraction failed: {e}")
            
            # 2. AST Analysis
            ast_findings = analyze_graph_structure(temp_dir)
            
            # State Management
            state_data = ast_findings.get("State Management Rigor")
            evidences.append(Evidence(
                goal="State Management Rigor",
                found=state_data["found"],
                content="\n".join(state_data["evidence"][:5]) if state_data["evidence"] else "No TypedDict or BaseModel specific to state found.", 
                location="Source Code",
                rationale="AST analysis checked for TypedDict and Pydantic BaseModel definitions.",
                confidence=0.9
            ))
            
            # Graph Orchestration
            graph_data = ast_findings.get("Graph Orchestration Architecture")
            evidences.append(Evidence(
                goal="Graph Orchestration Architecture",
                found=graph_data["found"],
                content="\n".join(graph_data["evidence"][:10]) if graph_data["evidence"] else "No StateGraph instantiation found.", # Increased limit to show conditional edges
                location="Source Code",
                rationale="AST analysis checked for StateGraph, branching, and conditional edges.",
                confidence=0.9
            ))

            # Structured Output
            struct_data = ast_findings.get("Structured Output Enforcement")
            evidences.append(Evidence(
                goal="Structured Output Enforcement",
                found=struct_data["found"],
                content="\n".join(struct_data["evidence"][:5]) if struct_data["evidence"] else "No .with_structured_output usage found.",
                location="Source Code",
                rationale="AST analysis checked for .with_structured_output() method calls.",
                confidence=0.9
            ))
            
            # Safe Tool Engineering
            safe_data = ast_findings.get("Safe Tool Engineering")
            # If found=True (default in analyze_graph_structure), it means SAFE.
            # But "found" usually means "Evidence Found". 
            # Let's clarify the evidence goal.
            
            is_safe = safe_data["found"] # True if safe
            
            evidences.append(Evidence(
                goal="Safe Tool Engineering",
                found=is_safe, 
                content="\n".join(safe_data["evidence"][:5]) if not is_safe else "No unsafe constructs (os.system) found.",
                location="Source Code",
                rationale="Scanned for raw 'os.system' calls which are unsafe.",
                confidence=0.8
            ))
            
            # --- CLARIFICATION FOR LLM ---
            # If is_safe is True, we want the LLM to know this is GOOD.
            # If found=True usually implies 'I found the problem' in a detective context, this is ambiguous.
            # But here 'found' matches the 'goal'.
            # If goal is 'Safe Tool Engineering', found=True means 'It IS Safe'.
            # However, for 'Git Forensic Analysis', found=True means 'I found the history'.
            # To avoid ambiguity, let's make the content explicit.


            # File Structure Checks
            has_judges = any("judges.py" in f for root, _, files in os.walk(temp_dir) for f in files)
            evidences.append(Evidence(
                goal="Judicial Nuance and Dialectics",
                found=has_judges,
                content=f"Found 'judges.py': {has_judges}",
                location="File Structure",
                rationale="Presence of 'judges.py' suggests judicial component.",
                confidence=0.6
            ))
            
            has_justice = any("justice.py" in f for root, _, files in os.walk(temp_dir) for f in files)
            evidences.append(Evidence(
                goal="Chief Justice Synthesis Engine",
                found=has_justice,
                content=f"Found 'justice.py': {has_justice}",
                location="File Structure",
                rationale="Presence of 'justice.py' suggests synthesis engine.",
                confidence=0.6
            ))

    except Exception as e:
        evidences.append(Evidence(
            goal="Repo Access",
            found=False,
            content=f"Error accessing or analyzing repo: {str(e)}",
            location="Remote",
            rationale="Failed to clone or parse repository.",
            confidence=0.0
        ))

    # LOGGING
    print(f"Detective: repo_investigator returns {json.dumps({'evidences': {'repo': [e.model_dump() for e in evidences]}}, default=str)}")

    return {"evidences": {"repo": evidences}}

def doc_analyst(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes the documentation (PDF) using LLM to verify rubric compliance.
    """
    pdf_path = state.get('pdf_path')
    evidences: List[Evidence] = []
    rubric = _load_rubric()
    dims = [d for d in rubric.get("dimensions", []) if d["target_artifact"] == "pdf_report"]
    
    if not pdf_path:
        evidences.append(Evidence(
            goal="Documentation Check",
            found=False,
            content="No PDF path provided.",
            location="args",
            rationale="User did not provide --pdf argument.",
            confidence=1.0
        ))
        
        # LOGGING
        print(f"Detective: doc_analyst returns {json.dumps({'evidences': {'doc': [e.model_dump() for e in evidences]}}, default=str)}")
        return {"evidences": {"doc": evidences}}

    try:
        chunks = ingest_pdf_and_chunk(pdf_path)
        
        # Combine chunks
        doc_text = ""
        for chunk in chunks:
            if isinstance(chunk, dict):
                 doc_text += chunk.get("text", str(chunk)) + "\n"
            elif hasattr(chunk, 'page_content'):
                doc_text += chunk.page_content + "\n"
            else:
                doc_text += str(chunk) + "\n"
        
        if len(doc_text) > 30000:
            doc_text = doc_text[:30000] + "... [TRUNCATED]"

        llm = get_model()
        
        for dim in dims:
            prompt = f"""
            You are an expert Auditor.
            SEARCH CONTEXT for evidence matching the dimension: {dim['name']}
            Success Pattern: {dim['success_pattern']}
            
            CONTEXT:
            {doc_text}
            
            Instructions:
            Does the doc meet the Success Pattern? Extract a quote.
            
            Output JSON:
            {{ "evidences": [ {{ "goal": "{dim['name']}", "found": true, "content": "quote", "location": "PDF", "rationale": "reason", "confidence": 0.95 }} ] }}
            """
            
            messages = [
                SystemMessage(content="You are a JSON generator. Output ONLY valid JSON."),
                HumanMessage(content=prompt)
            ]
            
            llm_to_use = llm
            try:
                if hasattr(llm, "bind"):
                        if "Ollama" in str(type(llm)):
                            llm_to_use = llm.bind(format="json")
                        elif "OpenAI" in str(type(llm)):
                            llm_to_use = llm.bind(response_format={"type": "json_object"})
            except:
                pass

            try:
                response = llm_to_use.invoke(messages)
                content = response.content
                
                # Robust JSON extraction
                json_str = content.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1]
                if "```" in json_str:
                    json_str = json_str.split("```")[0]
                    
                start_idx = json_str.find("{")
                end_idx = json_str.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    json_str = json_str[start_idx:end_idx+1]
                
                data = json.loads(json_str)
                
                if isinstance(data, dict):
                        evidences_list = data.get("evidences", [])
                        if not evidences_list and "goal" in data:
                            evidences_list = [data]
                elif isinstance(data, list):
                    evidences_list = data
                else:
                    evidences_list = []
                
                for item in evidences_list:
                    evidences.append(Evidence(
                        goal=item.get("goal", dim['name']),
                        found=item.get("found", False),
                        content=str(item.get("content", "No content provided")),
                        location=item.get("location", "PDF"),
                        rationale=item.get("rationale", "No rationale provided"),
                        confidence=float(item.get("confidence", 0.5))
                    ))
            except Exception:
                pass
                
    except Exception as e:
        evidences.append(Evidence(
            goal="Doc Analysis",
            found=False,
            content=f"Error analyzing docs: {str(e)}",
            location="Docs",
            rationale="Failed to ingest PDF.",
            confidence=0.0
        ))
        
    # LOGGING
    print(f"Detective: doc_analyst returns {json.dumps({'evidences': {'doc': [e.model_dump() for e in evidences]}}, default=str)}")

    return {"evidences": {"doc": evidences}}

def vision_inspector(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes visual diagrams in the repository AND the PDF report.
    Only processes up to 3 images from each source to conserve tokens.
    """
    repo_url = state.get("repo_url")
    pdf_path = state.get("pdf_path")
    evidences: List[Evidence] = []
    
    # 1. PDF Image Analysis (Priority)
    if pdf_path:
        try:
            pdf_images = extract_images_from_pdf(pdf_path, max_images=3)
            if pdf_images:
                llm = get_model()
                for img in pdf_images:
                    try:
                        messages = [
                            SystemMessage(content="You are a Vision Inspector. Analyze this technical diagram from an audit report."),
                            HumanMessage(content=[
                                {"type": "text", "text": "Is this a StateGraph diagram or a generic box diagram? Describe the node connections and structure."},
                                {"type": "image_url", "image_url": {"url": f"data:{img['mime_type']};base64,{img['base64']}"}}
                            ])
                        ]
                        
                        response = llm.invoke(messages)
                        
                        evidences.append(Evidence(
                            goal="Structure Verification",
                            found=True,
                            content=f"PDF Page {img['page']} Image Analysis: {response.content[:300]}...",
                            location=f"PDF/Page-{img['page']}",
                            rationale="Vision analysis of PDF diagrams.",
                            confidence=0.9
                        ))
                    except Exception as e:
                        print(f"Failed to analyze PDF image: {e}")
            else:
                 evidences.append(Evidence(
                    goal="Visual Clarity",
                    found=False,
                    content="No images extracted from PDF.",
                    location="PDF",
                    rationale="PDF parsing yielded no image objects.",
                    confidence=0.5
                ))
        except Exception as e:
             print(f"PDF extraction error: {e}")

    # 2. Repo Image Analysis (Secondary)
    if not repo_url:
        evidences.append(Evidence(
            goal="Visual Check",
            found=False,
            content="No repo URL provided.",
            location="args",
            rationale="Cannot inspect images without access.",
            confidence=1.0
        ))
    else:

        try:
         with clone_repo(repo_url) as temp_dir:
            image_files = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                         image_files.append(os.path.join(root, file))
            
            if not image_files:
                evidences.append(Evidence(
                    goal="Design Diagrams",
                    found=False,
                    content="No image files found in repository.",
                    location="Repository",
                    rationale="Scanned for .png, .jpg, .jpeg, .gif.",
                    confidence=1.0
                ))
            else:
                # Limit to first 3 images
                llm = get_model() # Assuming gpt-4o or capable model
                
                for img_path in image_files[:3]:
                    try:
                        mime_type, _ = mimetypes.guess_type(img_path)
                        if not mime_type:
                            mime_type = "image/png"
                            
                        with open(img_path, "rb") as image_file:
                            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                        
                        messages = [
                            SystemMessage(content="You are a Vision Inspector. Analyze this technical diagram or screenshot."),
                            HumanMessage(content=[
                                {"type": "text", "text": "Describe the architectural components, flow, or UI elements in this image. Does it look professional?"},
                                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
                            ])
                        ]
                        
                        response = llm.invoke(messages)
                        filename = os.path.basename(img_path)
                        
                        evidences.append(Evidence(
                            goal="Visual Clarity",
                            found=True,
                            content=f"Image {filename} Analysis: {response.content[:200]}...",
                            location=f"Images/{filename}",
                            rationale="Vision model analysis of repository asset.",
                            confidence=0.8
                        ))
                    except Exception as e:
                        print(f"Failed to analyze image {img_path}: {e}")
                        
        except Exception as e:
            evidences.append(Evidence(
                goal="Vision Analysis",
                found=False,
                content=f"Error accessing repo for vision check: {str(e)}",
                location="Remote",
                rationale="Failed to clone or read images.",
                confidence=0.0
            ))
            
    # LOGGING
    print(f"Detective: vision_inspector returns {json.dumps({'evidences': {'vision': [e.model_dump() for e in evidences]}}, default=str)}")
    
    return {"evidences": {"vision": evidences}}
     
