from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import documents, chat, generation
from app.core.config import settings

app = FastAPI(
    title="servicePerfRAG",
    description="AI-powered performance testing assistant",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.ALLOWED_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(generation.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "service": "servicePerfRAG"}
