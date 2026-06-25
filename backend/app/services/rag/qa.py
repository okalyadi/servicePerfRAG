from typing import List, Optional
import anthropic

from app.core.config import settings
from app.services.document.embedder import embed_query
from app.services.document.vector_store import search
from app.models.chat import ChatResponse, Source

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def answer_question(question: str, project: str, doc_types: Optional[List[str]] = None) -> ChatResponse:
    query_vector = embed_query(question)
    chunks = search(query_vector, project=project, doc_types=doc_types)

    if not chunks:
        return ChatResponse(
            answer="No relevant documents found for this project. Please upload HLD, LLD, or architecture documents first.",
            sources=[],
        )

    context = "\n\n---\n\n".join(
        [f"[{c['doc_type']} | {c['filename']}]\n{c['text']}" for c in chunks]
    )

    prompt = f"""You are a senior performance engineer.
Answer the question based ONLY on the context below from project: {project}.

Rules:
- Write in plain prose, 3-6 sentences max per point. No markdown headers, no bullet soup.
- Use a bullet list only if there are 3+ truly distinct items that don't read well as prose.
- Cite the source document inline in parentheses, e.g. (Agentic System Design guide).
- If the context lacks enough information, say so in one sentence and stop.
- No summary tables, no "Design Recommendation" boxes, no caveats section at the end.

Context:
{context}

Question: {question}

Answer:"""

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    sources = [
        Source(
            filename=c["filename"],
            doc_type=c["doc_type"],
            chunk_text=c["text"][:300] + "...",
            score=round(c["score"], 3),
        )
        for c in chunks
    ]

    return ChatResponse(answer=response.content[0].text, sources=sources)
