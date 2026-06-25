from fastapi import APIRouter, HTTPException
from app.models.chat import ChatRequest, ChatResponse
from app.services.rag.qa import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatResponse)
async def ask(request: ChatRequest):
    try:
        return answer_question(
            question=request.question,
            project=request.project,
            doc_types=request.doc_types,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
