from typing import List, Dict, Any
import os
try:
    from docling.document_converter import DocumentConverter
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    from pypdf import PdfReader


def ingest_pdf(pdf_path: str) -> str:
    """Extract text from PDF using Docling (or fallback to pypdf).

    Raises:
        FileNotFoundError: if path missing
        RuntimeError: with enriched message for malformed PDFs or parse errors
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    # Try Docling First (Layout-Aware)
    if DOCLING_AVAILABLE:
        try:
            print(f"Using Docling for PDF ingestion: {pdf_path}")
            converter = DocumentConverter()
            result = converter.convert(pdf_path)
            # Export to Markdown for structure preservation
            return result.document.export_to_markdown()
        except Exception as e:
            print(f"Docling failed: {e}. Falling back to PyPDF.")

    # Fallback to PyPDF
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
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

def extract_images_from_pdf(pdf_path: str, max_images: int = 3) -> List[Dict[str, Any]]:
    """
    Extracts images from a PDF file.
    Returns a list of dicts with 'page', 'index', and 'base64' encoded image data.
    Requires 'pypdf'.
    """
    if not os.path.exists(pdf_path):
        return []
        
    try:
        from pypdf import PdfReader
        import base64
        import io
    except ImportError:
        print("Missing dependencies for image extraction (pypdf)")
        return []

    images = []
    try:
        reader = PdfReader(pdf_path)
        for page_num, page in enumerate(reader.pages):
            if len(images) >= max_images:
                break
            
            # Check if page has images
            if hasattr(page, 'images') and page.images:
                 for img_idx, image_file_object in enumerate(page.images):
                    if len(images) >= max_images:
                        break
                    
                    try:
                        # image_file_object.data is the raw bytes
                        img_data = image_file_object.data
                        encoded_string = base64.b64encode(img_data).decode('utf-8')
                        
                        images.append({
                            "page": page_num + 1,
                            "index": img_idx,
                            "filename": image_file_object.name,
                            "base64": encoded_string,
                            "mime_type": "image/png"
                        })
                    except Exception as e:
                        print(f"Failed to process image {img_idx} on page {page_num}: {e}")
                
    except Exception as e:
        print(f"Error reading PDF for images: {e}")
        
    return images


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
