import shutil
import tempfile
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.chat import (
    ScriptGenerationRequest,
    ScriptGenerationResponse,
    TestPlanRequest,
    TestPlanRefineRequest,
    TestPlanExportRequest,
)
from app.services.generation.script_generator import generate_k6_script, generate_script_from_har
from app.services.generation.test_plan_generator import (
    generate_test_plan_json,
    refine_test_plan,
    export_plan_to_pdf,
)
from app.services.document.parser import _extract_text


class _TextStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str):
        self._parts.append(data)

    def get_text(self) -> str:
        return "\n".join(p.strip() for p in self._parts if p.strip())


class TemplateUrlRequest(BaseModel):
    url: str

router = APIRouter(prefix="/generate", tags=["generation"])


@router.post("/script", response_model=ScriptGenerationResponse)
async def generate_script(request: ScriptGenerationRequest):
    try:
        return generate_k6_script(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/script/from-har", response_model=ScriptGenerationResponse)
async def generate_script_from_har_endpoint(
    file: UploadFile = File(...),
    tool: str = "k6",
    base_url: str = "",
    project: str = "my-service",
):
    if not (file.filename or "").lower().endswith(".har"):
        raise HTTPException(status_code=400, detail="Only .har files are accepted.")
    try:
        content = await file.read()
        return generate_script_from_har(content, tool, base_url, project)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-plan")
async def generate_test_plan_endpoint(request: TestPlanRequest):
    try:
        plan = generate_test_plan_json(request)
        return {"plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-plan/refine")
async def refine_test_plan_endpoint(request: TestPlanRefineRequest):
    try:
        plan = refine_test_plan(request.plan, request.feedback, request.project)
        return {"plan": plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-plan/export")
async def export_test_plan_endpoint(request: TestPlanExportRequest):
    try:
        pdf_bytes = export_plan_to_pdf(request.plan, request.project)
        filename = f"{request.project}_performance_test_plan.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/template/from-file")
async def extract_template_from_file(file: UploadFile = File(...)):
    allowed = {".pdf", ".docx", ".doc", ".txt", ".md"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported template file type: {suffix}. Use PDF, DOCX, TXT, or MD.")

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        text = _extract_text(tmp_path, suffix)
        Path(tmp_path).unlink(missing_ok=True)

        if not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from the template file.")

        return {"text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/template/from-url")
async def extract_template_from_url(request: TemplateUrlRequest):
    url = request.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "servicePerfRAG/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get_content_type()
            raw = resp.read()

        suffix = Path(url.split("?")[0]).suffix.lower()

        if content_type == "application/pdf" or suffix == ".pdf":
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            text = _extract_text(tmp_path, ".pdf")
            Path(tmp_path).unlink(missing_ok=True)

        elif content_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ) or suffix in (".docx", ".doc"):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name
            text = _extract_text(tmp_path, ".docx")
            Path(tmp_path).unlink(missing_ok=True)

        elif "html" in content_type:
            parser = _TextStripper()
            parser.feed(raw.decode("utf-8", errors="ignore"))
            text = parser.get_text()

        else:
            text = raw.decode("utf-8", errors="ignore")

        if not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from the provided URL.")

        return {"text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch URL: {e}")
