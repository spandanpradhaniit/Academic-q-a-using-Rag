import re
import base64
from pathlib import Path
from collections.abc import Callable

import pymupdf as fitz

from app.core.config import get_settings


def extract_pdf_pages(
    path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict]:
    """Extract page-aware text, using OCR only for pages with no usable text."""
    pages: list[dict] = []
    with fitz.open(path) as pdf:
        total_pages = len(pdf)
        for index, page in enumerate(pdf):
            text = page.get_text("text").strip()
            if len(text) < 30:
                try:
                    import pytesseract

                    image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    from PIL import Image

                    import io

                    text = pytesseract.image_to_string(Image.open(io.BytesIO(image.tobytes("png")))).strip()
                except (ImportError, OSError, RuntimeError):
                    settings = get_settings()
                    if settings.openai_api_key:
                        from langchain_openai import ChatOpenAI

                        image = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                        image_url = "data:image/png;base64," + base64.b64encode(image.tobytes("png")).decode("ascii")
                        llm = ChatOpenAI(model=settings.ocr_model, api_key=settings.openai_api_key, temperature=0)
                        response = llm.invoke([
                            {"role": "system", "content": "Transcribe all readable text from this academic PDF page. Return only the text."},
                            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": image_url}}]},
                        ])
                        text = str(response.content).strip()
            normalized = re.sub(r"\s+", " ", text).strip()
            if normalized:
                pages.append({"page_number": index + 1, "content": normalized})
            if progress_callback:
                progress_callback(index + 1, total_pages)
    if not pages:
        raise ValueError("No extractable text was found in the PDF")
    return pages


def chunk_pages(pages: list[dict]) -> list[dict]:
    settings = get_settings()
    size, overlap = settings.chunk_size, settings.chunk_overlap
    chunks: list[dict] = []
    for page in pages:
        text = page["content"]
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start, end)
                if boundary > start + size // 2:
                    end = boundary
            body = text[start:end].strip()
            if body:
                chunks.append({"content": body, "page_number": page["page_number"], "token_count": max(1, len(body) // 4)})
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks
