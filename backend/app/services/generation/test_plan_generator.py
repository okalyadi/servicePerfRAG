import json
from datetime import date
from typing import Optional, List
import anthropic
from fpdf import FPDF

from app.core.config import settings
from app.services.document.embedder import embed_query
from app.services.document.vector_store import search
from app.models.chat import TestPlanRequest

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


_PLAN_SCHEMA = """{
  "title": "Performance Test Plan - <project>",
  "version": "1.0",
  "date": "<today>",
  "executive_summary": "<1-2 sentences on purpose and approach>",
  "scope": {
    "in_scope": ["3-5 items"],
    "out_of_scope": ["2-3 items"]
  },
  "test_environment": "<1 sentence>",
  "test_data": "<1 sentence>",
  "scenarios": [
    {"name": "...", "type": "load", "objective": "<1 sentence>", "description": "<1 sentence>", "duration": "40 min", "ramp_up": "5 min", "virtual_users": 500, "target_tps": 100, "expected_outcomes": "<1 sentence>"},
    {"name": "...", "type": "stress", "objective": "...", "description": "...", "duration": "30 min", "ramp_up": "5 min", "virtual_users": 1000, "target_tps": 200, "expected_outcomes": "..."},
    {"name": "...", "type": "soak", "objective": "...", "description": "...", "duration": "2 hr", "ramp_up": "5 min", "virtual_users": 300, "target_tps": 60, "expected_outcomes": "..."},
    {"name": "...", "type": "spike", "objective": "...", "description": "...", "duration": "20 min", "ramp_up": "1 min", "virtual_users": 2000, "target_tps": 400, "expected_outcomes": "..."}
  ],
  "nfr_mapping": [
    {"api_endpoint": "...", "p50_ms": 200, "p95_ms": 800, "p99_ms": 2000, "error_rate_pct": 0.1, "tps": 100}
  ],
  "risks": [
    {"risk": "...", "mitigation": "..."}
  ],
  "entry_criteria": ["2-3 items"],
  "exit_criteria": ["2-3 items"]
}"""


def _parse_json_plan(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


def generate_test_plan_json(request: TestPlanRequest) -> dict:
    query = "performance requirements, NFR, SLA, TPS, response time, user load, scalability, bottlenecks, API endpoints"
    query_vector = embed_query(query)
    chunks = search(query_vector, project=request.project, doc_types=request.doc_types, top_k=10)

    context = "\n\n---\n\n".join(
        [f"[{c['doc_type']} | {c['filename']}]\n{c['text']}" for c in chunks]
    )

    today = date.today().strftime("%B %d, %Y")

    if request.template and request.template.strip():
        output_instruction = f"""The user has provided a custom template below. Generate the test plan by following this template's structure and sections exactly. Fill every placeholder with real content drawn from the documents above (or reasonable defaults if the documents don't cover it). Return the result as JSON that matches the structure of the default schema below — keep all standard fields so the UI can render it — but let the template's section names, priorities, and any explicit values override the defaults.

Custom template provided by user:
---
{request.template.strip()}
---

Return ONLY this JSON (no markdown, no explanation):
{_PLAN_SCHEMA.replace('<project>', request.project).replace('<today>', today)}

When the template specifies concrete values (e.g. "load test: 1000 users, 30 min"), use those instead of the defaults. When it names sections or priorities not in the schema, incorporate them into the closest matching field (e.g. in executive_summary or as extra scenario objectives)."""
    else:
        output_instruction = f"""Return ONLY this JSON (no markdown, no explanation):
{_PLAN_SCHEMA.replace('<project>', request.project).replace('<today>', today)}

Use values from the documents where available."""

    prompt = f"""You are a senior performance engineer. Generate a performance test plan as JSON.

Project: {request.project}
Date: {today}

Documents:
{context}

{output_instruction}"""

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_json_plan(response.content[0].text)


def refine_test_plan(plan: dict, feedback: str, project: str) -> dict:
    prompt = f"""You are a senior performance engineer. Update the performance test plan JSON below based on user feedback.

Current plan:
{json.dumps(plan, indent=2)}

User feedback: {feedback}

Return ONLY the updated JSON (same structure as the input, no markdown, no explanation).
Keep all fields that don't need to change. Only modify what the feedback asks for.
If the feedback asks for an architecture diagram, add an "architecture_diagram" field with a Mermaid diagram string."""

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )

    return _parse_json_plan(response.content[0].text)


def export_plan_to_pdf(plan: dict, project: str) -> bytes:
    return _build_pdf(plan, project)


def generate_test_plan_pdf(request: TestPlanRequest) -> bytes:
    plan = generate_test_plan_json(request)
    return _build_pdf(plan, request.project)


def _build_pdf(plan: dict, project: str) -> bytes:
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    W = pdf.epw

    def reset():
        pdf.set_x(pdf.l_margin)

    # Title
    reset()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 64, 175)
    pdf.multi_cell(W, 10, _s(plan.get("title", f"Performance Test Plan - {project}")), align="C")
    reset()
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(W, 6, _s(f"Version {plan.get('version', '1.0')}   |   {plan.get('date', '')}"), align="C")
    pdf.ln(8)

    # 1. Executive Summary
    _heading(pdf, W, "1. Executive Summary")
    _body(pdf, W, plan.get("executive_summary", ""))
    pdf.ln(6)

    # 2. Scope
    _heading(pdf, W, "2. Scope")
    scope = plan.get("scope", {})
    _subheading(pdf, W, "In Scope")
    for item in scope.get("in_scope", []):
        _bullet(pdf, W, item)
    pdf.ln(2)
    _subheading(pdf, W, "Out of Scope")
    for item in scope.get("out_of_scope", []):
        _bullet(pdf, W, item)
    pdf.ln(6)

    # 3. Environment & Test Data
    _heading(pdf, W, "3. Test Environment")
    _body(pdf, W, plan.get("test_environment", ""))
    pdf.ln(4)
    _subheading(pdf, W, "Test Data Strategy")
    _body(pdf, W, plan.get("test_data", ""))
    pdf.ln(6)

    # 4. Test Scenarios
    _heading(pdf, W, "4. Test Scenarios")
    for i, s in enumerate(plan.get("scenarios", []), 1):
        _subheading(pdf, W, f"4.{i}  {_s(s.get('name', ''))}  [{s.get('type', '').upper()}]")
        _body(pdf, W, f"Objective: {_s(s.get('objective', ''))}")
        _body(pdf, W, _s(s.get("description", "")))
        pdf.ln(2)
        for label, value in [
            ("Duration", _s(s.get("duration", ""))),
            ("Ramp-up", _s(s.get("ramp_up", ""))),
            ("Virtual Users", str(s.get("virtual_users", ""))),
            ("Target TPS", str(s.get("target_tps", ""))),
        ]:
            reset()
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(W, 6, _s(f"    {label}: {value}"))
        pdf.ln(2)
        _body(pdf, W, f"Expected Outcomes: {_s(s.get('expected_outcomes', ''))}")
        pdf.ln(5)

    # 5. NFR Mapping
    _heading(pdf, W, "5. Non-Functional Requirements (NFR) Mapping")
    for nfr in plan.get("nfr_mapping", []):
        reset()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 30)
        pdf.multi_cell(W, 6, _s(nfr.get("api_endpoint", "")))
        for label, key in [("p50", "p50_ms"), ("p95", "p95_ms"), ("p99", "p99_ms"),
                            ("Error %", "error_rate_pct"), ("TPS", "tps")]:
            reset()
            pdf.set_font("Helvetica", "", 9)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(W, 5, _s(f"    {label}: {nfr.get(key, '')}"))
        pdf.ln(3)
    pdf.ln(4)

    # 6. Risks
    _heading(pdf, W, "6. Risks & Mitigations")
    for i, r in enumerate(plan.get("risks", []), 1):
        reset()
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(30, 30, 30)
        risk_text = r.get("risk", str(r)) if isinstance(r, dict) else str(r)
        pdf.multi_cell(W, 6, _s(f"{i}.  {risk_text}"))
        if isinstance(r, dict) and r.get("mitigation"):
            reset()
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(80, 80, 80)
            pdf.multi_cell(W, 6, _s(f"    Mitigation: {r['mitigation']}"))
        pdf.ln(2)
    pdf.ln(4)

    # 7. Entry / Exit Criteria
    _heading(pdf, W, "7. Entry Criteria")
    for item in plan.get("entry_criteria", []):
        _bullet(pdf, W, item)
    pdf.ln(6)

    _heading(pdf, W, "8. Exit Criteria")
    for item in plan.get("exit_criteria", []):
        _bullet(pdf, W, item)

    return bytes(pdf.output())


# Helpers

def _s(text: str) -> str:
    return (
        str(text)
        .replace("—", "--").replace("–", "-")
        .replace("‘", "'").replace("’", "'")
        .replace("“", '"').replace("”", '"')
        .replace("…", "...").replace("•", "*")
        .replace("‐", "-").replace("‑", "-")
        .encode("latin-1", errors="replace").decode("latin-1")
    )


def _heading(pdf: FPDF, w: float, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_fill_color(30, 64, 175)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(w, 9, f"  {_s(text)}", fill=True)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(3)


def _subheading(pdf: FPDF, w: float, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 64, 175)
    pdf.multi_cell(w, 7, _s(text))
    pdf.set_text_color(30, 30, 30)


def _body(pdf: FPDF, w: float, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(w, 6, _s(text))


def _bullet(pdf: FPDF, w: float, text: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(w, 6, _s(f"*  {text}"))
