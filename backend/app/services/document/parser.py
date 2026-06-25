import re
import uuid
import base64
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
import anthropic
from pypdf import PdfReader
from docx import Document

from app.core.config import settings
from app.services.document.embedder import _model as _embed_model

_claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _extract_text(file_path: str, suffix: str) -> str:
    if suffix == ".pdf":
        reader = PdfReader(file_path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(p for p in pages if p.strip())
    elif suffix in [".docx", ".doc"]:
        doc = Document(file_path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        with open(file_path, "r", errors="ignore") as f:
            return f.read()


def parse_document(file_path: str, filename: str) -> List[Dict[str, Any]]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        return _parse_image_with_claude(file_path, filename)

    if suffix == ".svg":
        return _parse_svg_with_claude(file_path, filename)

    full_text = _extract_text(file_path, suffix)
    chunks = _semantic_chunk(full_text)

    return [
        {"chunk_id": str(uuid.uuid4()), "text": chunk, "filename": filename}
        for chunk in chunks
    ]


def _semantic_chunk(
    text: str,
    threshold: float = 0.45,
    max_chars: int = 1500,
    min_chars: int = 80,
) -> List[str]:
    """Semantic chunking at paragraph level — fast and topic-aware.

    Splits text into paragraphs, embeds them in one batch, then merges
    adjacent paragraphs that share the same topic (high cosine similarity).
    Much faster than sentence-level embedding for large documents.
    """
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []
    if len(paragraphs) == 1:
        return paragraphs

    embeddings = _embed_model.encode(
        paragraphs, batch_size=64, convert_to_numpy=True, show_progress_bar=False
    )

    # Merge paragraphs that are semantically similar into one chunk
    chunks: List[str] = []
    current = paragraphs[0]

    for i in range(1, len(paragraphs)):
        sim = _cosine_sim(embeddings[i - 1], embeddings[i])
        candidate = current + "\n\n" + paragraphs[i]
        if sim >= threshold and len(candidate) <= max_chars:
            current = candidate
        else:
            if len(current) >= min_chars:
                chunks.append(current)
            current = paragraphs[i]

    if len(current) >= min_chars:
        chunks.append(current)

    return chunks


def _split_paragraphs(text: str) -> List[str]:
    """Split on blank lines; fall back to sentence splitting for dense text."""
    parts = re.split(r"\n{2,}", text)
    result = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= 1500:
            result.append(part)
        else:
            # Paragraph too long — split into sentences
            sentences = re.split(r"(?<=[.!?])\s+", part)
            current = ""
            for s in sentences:
                if len(current) + len(s) > 1500 and current:
                    result.append(current.strip())
                    current = s
                else:
                    current = (current + " " + s).strip()
            if current:
                result.append(current)
    return result


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b)) / denom if denom else 0.0


def _parse_svg_with_claude(file_path: str, filename: str) -> List[Dict[str, Any]]:
    import xml.etree.ElementTree as ET

    tree = ET.parse(file_path)
    root = tree.getroot()

    texts = []
    for elem in root.iter():
        if elem.text and elem.text.strip():
            texts.append(elem.text.strip())
        if elem.tail and elem.tail.strip():
            texts.append(elem.tail.strip())

    extracted = "\n".join(dict.fromkeys(texts))  # deduplicate while preserving order

    response = _claude.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": (
                f"You are analyzing an SVG architecture diagram: '{filename}'.\n\n"
                f"Text labels extracted from the SVG:\n{extracted}\n\n"
                "Based on these labels, describe: all services and components, "
                "APIs and endpoints, data flows, dependencies, databases, "
                "external integrations, and any performance-relevant details "
                "like caching, queues, or async patterns. Be thorough and structured."
            ),
        }],
    )

    return [{"chunk_id": str(uuid.uuid4()), "text": response.content[0].text, "filename": filename}]


def _parse_image_with_claude(file_path: str, filename: str) -> List[Dict[str, Any]]:
    with open(file_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    suffix = Path(file_path).suffix.lower().lstrip(".")
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    media_type = media_type_map.get(suffix, "image/png")

    response = _claude.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                {
                    "type": "text",
                    "text": (
                        "You are analyzing an architecture or design diagram. "
                        "Extract and describe: all services/components, APIs and endpoints, "
                        "data flows, dependencies, databases, external integrations, "
                        "and any performance-relevant details like caching, queues, or async patterns. "
                        "Be thorough and structured."
                    ),
                },
            ],
        }],
    )

    return [{"chunk_id": str(uuid.uuid4()), "text": response.content[0].text, "filename": filename}]
