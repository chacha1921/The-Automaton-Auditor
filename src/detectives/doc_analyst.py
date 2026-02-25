import os
from typing import Dict, List
from pypdf import PdfReader
from src.state import AgentState, Evidence

def extract_text_pypdf(pdf_path: str) -> str:
    """Extract text from PDF using pypdf."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def doc_analyst_node(state: AgentState) -> Dict:
    """
    LangGraph node to analyze the PDF document for specific keywords.
    """
    pdf_path = state.get("pdf_path")
    if not pdf_path or not os.path.exists(pdf_path):
        return {
            "evidences": {
                "pdf_existence": Evidence(
                    goal="Read PDF Document",
                    found=False,
                    content="PDF file not found or path not provided.",
                    location="Input Path",
                    rationale="The file path was invalid.",
                    confidence=0.0
                )
            }
        }

    try:
        # Try to use docling if available, otherwise fallback to pypdf
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(pdf_path)
            # Export to markdown as it preserves structure better than raw text
            full_text = result.document.export_to_markdown()
        except ImportError:
            # Fallback to pypdf if docling is not installed
            full_text = extract_text_pypdf(pdf_path)
        except Exception as e:
            # Fallback to pypdf on docling runtime error
             full_text = extract_text_pypdf(pdf_path)

        evidences = {}
        
        # Check for 'Dialectical Synthesis'
        keyword1 = "Dialectical Synthesis"
        found1 = keyword1.lower() in full_text.lower()
        evidences["keyword_dialectical_synthesis"] = Evidence(
            goal=f"Find keyword '{keyword1}'",
            found=found1,
            content=f"Found mention of '{keyword1}'" if found1 else f"'{keyword1}' not found in text.",
            location="PDF Content",
            rationale=f"Scanned extracted text for '{keyword1}'.",
            confidence=1.0 if found1 else 0.8
        )

        # Check for 'Metacognition'
        keyword2 = "Metacognition"
        found2 = keyword2.lower() in full_text.lower()
        evidences["keyword_metacognition"] = Evidence(
            goal=f"Find keyword '{keyword2}'",
            found=found2,
            content=f"Found mention of '{keyword2}'" if found2 else f"'{keyword2}' not found in text.",
            location="PDF Content",
            rationale=f"Scanned extracted text for '{keyword2}'.",
            confidence=1.0 if found2 else 0.8
        )

        return {"evidences": evidences}

    except Exception as e:
        return {
            "evidences": {
                "pdf_processing_error": Evidence(
                    goal="Process PDF Document",
                    found=False,
                    content=f"Error processing PDF: {str(e)}",
                    location="PDF Processor",
                    rationale="Exception occurred during PDF text extraction.",
                    confidence=0.0
                )
            }
        }
