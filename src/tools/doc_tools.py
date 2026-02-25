from typing import List, Dict, Any
import os
from pypdf import PdfReader


def ingest_pdf(pdf_path: str) -> str:
    """Extract text from PDF using pypdf.

    Raises:
        FileNotFoundError: if path missing
        RuntimeError: with enriched message for malformed PDFs or parse errors
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    try:
        reader = PdfReader(pdf_path)
        text_parts: List[str] = []
        for i, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text() or ""
            except Exception as pe:
                # include page number for better debugging
                raise RuntimeError(f"Error extracting text from page {i} of {pdf_path}: {pe}")
            text_parts.append(page_text)

        return "\n".join(text_parts)
    except Exception as e:
        # Provide actionable guidance for malformed PDFs
        msg = (
            f"Failed to read PDF at {pdf_path}: {e}. "
            "Possible causes: encrypted or corrupted PDF, unsupported PDF features, or malformed file. "
            "Try opening the PDF locally or re-generating the file; if behind auth, ensure the file is accessible."
        )
        raise RuntimeError(msg)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """Split raw text into overlapping chunks.

    Returns a list of dicts: {"id": int, "text": str, "start": int, "end": int}
    This simple splitter prefers breaking at whitespace to avoid cutting words.
    """
    if not text:
        return []

    chunks: List[Dict[str, Any]] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        # try to backtrack to the last whitespace to avoid breaking words
        if end < text_len:
            back = text.rfind(" ", start, end)
            if back > start:
                end = back

        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"id": len(chunks), "text": chunk, "start": start, "end": end})

        # advance start with overlap
        start = max(end - overlap, end)

    return chunks


def ingest_pdf_and_chunk(pdf_path: str, chunk_size: int = 1000, overlap: int = 200) -> List[Dict[str, Any]]:
    """Convenience: ingest PDF and return semantic chunks."""
    text = ingest_pdf(pdf_path)
    return chunk_text(text, chunk_size=chunk_size, overlap=overlap)


def query_chunks(chunks: List[Dict[str, Any]], query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Query the precomputed chunks for simple substring matches.

    Returns up to `top_k` matches with chunk id and a short snippet.
    """
    if not chunks:
        return []

    q = query.lower()
    matches: List[Dict[str, Any]] = []
    for ch in chunks:
        txt = ch.get("text", "")
        idx = txt.lower().find(q)
        if idx != -1:
            # provide a small context window around the match
            start = max(0, idx - 50)
            end = min(len(txt), idx + len(q) + 50)
            snippet = txt[start:end].replace("\n", " ")
            matches.append({"chunk_id": ch.get("id"), "snippet": snippet, "match_index": idx})

    # naive ranking: earliest occurrences first
    matches = sorted(matches, key=lambda m: (m["chunk_id"], m["match_index"]))[:top_k]
    return matches


def query_document(text: str, query: str) -> Dict[str, Any]:
    """
    Search for a query string in the text.
    Returns details about the finding.
    """
    found = query.lower() in text.lower() if text else False
    return {
        "query": query,
        "found": found,
        "details": f"Found mention of '{query}'" if found else f"'{query}' not found."
    }
