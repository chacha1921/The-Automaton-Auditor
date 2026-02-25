from typing import List, Dict, Any
import os
from pypdf import PdfReader

def ingest_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pypdf."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
        
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        raise RuntimeError(f"Error reading PDF: {str(e)}")

def query_document(text: str, query: str) -> Dict[str, Any]:
    """
    Search for a query string in the text.
    Returns details about the finding.
    """
    found = query.lower() in text.lower()
    return {
        "query": query,
        "found": found,
        "details": f"Found mention of '{query}'" if found else f"'{query}' not found."
    }
