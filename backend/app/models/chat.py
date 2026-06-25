from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    question: str
    project: str
    doc_types: Optional[List[str]] = None  # filter by doc type


class Source(BaseModel):
    filename: str
    doc_type: str
    chunk_text: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]


class ScriptGenerationRequest(BaseModel):
    project: str
    scenario_type: str  # load, stress, soak, spike
    base_url: str
    tool: str = "k6"  # k6 or jmeter
    doc_types: Optional[List[str]] = None


class ScriptGenerationResponse(BaseModel):
    scenario_type: str
    script: str
    filename: str
    description: str


class TestPlanRequest(BaseModel):
    project: str
    doc_types: Optional[List[str]] = None
    template: Optional[str] = None


class TestPlanRefineRequest(BaseModel):
    project: str
    plan: dict
    feedback: str


class TestPlanExportRequest(BaseModel):
    project: str
    plan: dict
