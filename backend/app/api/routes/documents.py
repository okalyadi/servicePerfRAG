import uuid
import shutil
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.core.config import settings
from app.models.document import DocType, DocumentUploadResponse
from app.services.document.parser import parse_document
from app.services.document.embedder import embed_texts
from app.services.document.vector_store import store_chunks, delete_by_filename

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    project: str = Form(...),
    doc_type: DocType = Form(...),
):
    allowed_types = {".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".txt"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(exist_ok=True)

    doc_id = str(uuid.uuid4())
    save_path = upload_dir / f"{doc_id}{suffix}"

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks = parse_document(str(save_path), file.filename)
        if not chunks:
            raise HTTPException(status_code=422, detail="Could not extract text from document.")

        delete_by_filename(file.filename, project)
        texts = [c["text"] for c in chunks]
        embeddings = embed_texts(texts)

        metadata = {
            "doc_id": doc_id,
            "doc_type": doc_type.value,
            "project": project,
            "filename": file.filename,
            "uploaded_at": datetime.utcnow().isoformat(),
        }
        store_chunks(chunks, embeddings, metadata)

    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=file.filename,
        project=project,
        doc_type=doc_type,
        chunks_stored=len(chunks),
        message=f"Successfully processed {len(chunks)} chunks from {file.filename}",
    )
