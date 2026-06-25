from pydantic import BaseModel
from enum import Enum
from datetime import datetime
from typing import Optional


class DocType(str, Enum):
    HLD = "HLD"
    LLD = "LLD"
    ARCHITECTURE = "ARCHITECTURE"
    NFR = "NFR"
    OTHER = "OTHER"


class DocumentMetadata(BaseModel):
    doc_id: str
    filename: str
    doc_type: DocType
    project: str
    uploaded_at: datetime
    page_count: Optional[int] = None


class DocumentUploadRequest(BaseModel):
    project: str
    doc_type: DocType


class DocumentUploadResponse(BaseModel):
    doc_id: str
    filename: str
    project: str
    doc_type: DocType
    chunks_stored: int
    message: str
