import json
import re
from urllib.parse import urlparse

import anthropic

from app.core.config import settings
from app.services.document.embedder import embed_query
from app.services.document.vector_store import search
from app.models.chat import ScriptGenerationRequest, ScriptGenerationResponse

_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

SCENARIO_PROMPTS = {
    "load": "steady-state load test at expected peak TPS with gradual ramp-up over 5 minutes, sustain for 30 minutes",
    "stress": "stress test starting at 50% load, incrementing by 20% every 5 minutes until system breaks or reaches 200% of expected load",
    "soak": "soak test at 70% of peak load sustained for 4 hours to detect memory leaks and performance degradation over time",
    "spike": "spike test with sudden burst to 5x normal load for 2 minutes, then back to baseline — repeat 3 times",
    "comprehensive": "comprehensive performance test suite covering load, stress, soak, and spike scenarios",
}


def _k6_prompt(request: ScriptGenerationRequest, context: str, scenario_desc: str) -> str:
    is_comprehensive = request.scenario_type == "comprehensive"
    scenarios_section = """Include four exports or scenario functions covering:
- Load: steady ramp-up to peak TPS, sustain 30 min
- Stress: incremental load until break point
- Soak: 70% load for 4 hours
- Spike: 5x burst for 2 min, repeat 3 times
Use k6 scenarios (executor: ramping-vus) to define all four in a single file.""" if is_comprehensive else \
    f"Use k6 options with stages for the scenario: {scenario_desc}"

    return f"""You are a senior performance engineer expert in k6 load testing.

Generate a complete, production-ready k6 JavaScript script for: {scenario_desc}

Project: {request.project}
Base URL: {request.base_url}

Design document context:
{context}

Requirements:
1. {scenarios_section}
2. Include realistic think times (sleep) between requests
3. Add threshold definitions based on NFRs found in the documents
4. Parameterize with test data (use SharedArray for CSV data)
5. Add checks for response status and response time
6. Include correlation/dynamic data extraction where needed
7. Group related requests logically
8. Handle authentication (Bearer token / session) properly
9. Export a handleSummary function

Return ONLY the complete k6 script. Add inline comments."""


def _jmeter_prompt(request: ScriptGenerationRequest, context: str, scenario_desc: str) -> str:
    is_comprehensive = request.scenario_type == "comprehensive"
    thread_groups_section = """Include four Thread Groups:
- Load Test: gradual ramp-up to peak, 30 min
- Stress Test: incremental ramp to 200% peak
- Soak Test: sustained 70% load, 4 hours
- Spike Test: sudden burst to 500% for 2 min, repeat 3 times
Each Thread Group should be disabled by default so testers can enable individual scenarios.""" if is_comprehensive else \
    f"One Thread Group configured for: {scenario_desc}"

    return f"""You are a senior performance engineer expert in Apache JMeter.

Generate a complete, production-ready JMeter test plan (.jmx XML) for: {scenario_desc}

Project: {request.project}
Base URL: {request.base_url}

Design document context:
{context}

Requirements:
1. Valid JMeter 5.x JMX XML — must open directly in JMeter GUI without errors
2. {thread_groups_section}
3. HTTP Request Defaults with the base URL and common headers
4. One HTTPSamplerProxy per key API endpoint found in the documents (use sensible defaults if none found)
5. HTTP Header Manager with Content-Type and Authorization placeholder
6. Response Assertion on each sampler (status 200/201)
7. Duration Assertion based on NFR p95 targets from the documents
8. Constant Timer for think time between requests
9. Summary Report and View Results Tree listeners
10. CSV Data Set Config for parameterized test data
11. User Defined Variables for base URL, credentials, and thread counts

Return ONLY the complete JMX XML. No explanation outside the XML."""


def _summarise_har(har_bytes: bytes) -> tuple[str, str]:
    """Parse a HAR file and return (base_url, requests_summary_text)."""
    data = json.loads(har_bytes)
    entries = data.get("log", {}).get("entries", [])

    SKIP_EXTENSIONS = re.compile(r"\.(png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot|css|map)(\?|$)", re.I)
    SKIP_HOSTS = re.compile(r"(google-analytics|doubleclick|facebook|twitter|cdn\.|fonts\.googleapis)", re.I)

    seen_keys: set[str] = set()
    rows: list[str] = []
    base_host = ""

    for entry in entries:
        req = entry.get("request", {})
        method = req.get("method", "GET")
        url = req.get("url", "")

        parsed = urlparse(url)
        if SKIP_EXTENSIONS.search(parsed.path) or SKIP_HOSTS.search(parsed.netloc):
            continue

        if not base_host and parsed.netloc:
            base_host = f"{parsed.scheme}://{parsed.netloc}"

        path = parsed.path or "/"
        query = parsed.query
        key = f"{method}:{parsed.netloc}{path}"
        if key in seen_keys:
            continue
        seen_keys.add(key)

        content_type = next(
            (h["value"] for h in req.get("headers", []) if h["name"].lower() == "content-type"), ""
        )
        has_auth = any(h["name"].lower() in ("authorization", "x-auth-token") for h in req.get("headers", []))
        post_data = req.get("postData", {})
        body_preview = ""
        if post_data:
            raw = post_data.get("text", "")
            body_preview = f" body={raw[:120].replace(chr(10), ' ')}" if raw else ""

        row = f"  {method} {parsed.netloc}{path}"
        if query:
            row += f"?{query[:80]}"
        if content_type:
            row += f" [{content_type.split(';')[0]}]"
        if has_auth:
            row += " [auth]"
        if body_preview:
            row += body_preview
        rows.append(row)

        if len(rows) >= 40:
            break

    return base_host, "\n".join(rows)


def _k6_har_prompt(tool: str, base_url: str, project: str, requests_text: str) -> str:
    if tool == "jmeter":
        return f"""You are a senior performance engineer expert in Apache JMeter.

Generate a complete, production-ready JMeter test plan (.jmx XML) based on the real HTTP traffic captured below.

Project: {project}
Base URL: {base_url}

Captured requests (from HAR file):
{requests_text}

Requirements:
1. Valid JMeter 5.x JMX XML — must open directly in JMeter GUI without errors
2. One Thread Group with ramping load (ramp 5 min, sustain 30 min, 200 virtual users)
3. One HTTPSamplerProxy per unique endpoint from the captured traffic
4. HTTP Request Defaults with the base URL
5. HTTP Header Manager with Content-Type and Authorization placeholder where [auth] is noted
6. Response Assertion (status 200/201) on each sampler
7. Constant Timer (think time 1–3 s) between requests
8. CSV Data Set Config for parameterised user data
9. Summary Report and View Results Tree listeners

Return ONLY the complete JMX XML."""
    else:
        return f"""You are a senior performance engineer expert in k6 load testing.

Generate a complete, production-ready k6 JavaScript script based on the real HTTP traffic captured below.

Project: {project}
Base URL: {base_url}

Captured requests (from HAR file):
{requests_text}

Requirements:
1. Model the user journey in the order the requests appear
2. Use k6 options with stages: ramp to 200 VUs over 5 min, sustain 30 min, ramp down 2 min
3. Add thresholds: http_req_duration p(95)<2000, http_req_failed<0.01
4. Add checks for response status on each request
5. Add realistic think times (sleep 1–3 s) between requests
6. Parameterise dynamic values (IDs, tokens) with variables or SharedArray
7. Handle Authorization header as a variable from environment (Bearer token)
8. Group related requests logically
9. Export a handleSummary function

Return ONLY the complete k6 script with inline comments."""


def generate_script_from_har(har_bytes: bytes, tool: str, base_url: str, project: str) -> ScriptGenerationResponse:
    detected_base, requests_text = _summarise_har(har_bytes)
    effective_base = base_url.strip() or detected_base or "https://your-service.example.com"

    if not requests_text:
        raise ValueError("No usable HTTP requests found in the HAR file.")

    prompt = _k6_har_prompt(tool, effective_base, project, requests_text)
    ext = "jmx" if tool == "jmeter" else "js"
    tool_label = "JMeter" if tool == "jmeter" else "k6"

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": prompt}],
    )

    script = response.content[0].text
    if script.startswith("```"):
        lines = script.splitlines()
        script = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return ScriptGenerationResponse(
        scenario_type="har",
        script=script,
        filename=f"{project}_har_test.{ext}",
        description=f"{tool_label} script generated from HAR capture — {len(requests_text.splitlines())} unique endpoints",
    )


def generate_k6_script(request: ScriptGenerationRequest) -> ScriptGenerationResponse:
    return generate_script(request)


def generate_script(request: ScriptGenerationRequest) -> ScriptGenerationResponse:
    query = f"API endpoints, TPS targets, response time SLAs, user journeys, authentication for {request.project}"
    query_vector = embed_query(query)
    chunks = search(query_vector, project=request.project, doc_types=request.doc_types, top_k=8)

    context = "\n\n---\n\n".join(
        [f"[{c['doc_type']} | {c['filename']}]\n{c['text']}" for c in chunks]
    )

    scenario_desc = SCENARIO_PROMPTS.get(request.scenario_type, request.scenario_type)
    tool = request.tool.lower()

    if tool == "jmeter":
        prompt = _jmeter_prompt(request, context, scenario_desc)
        filename = f"{request.project}_{request.scenario_type}_test.jmx"
        tool_label = "JMeter"
    else:
        prompt = _k6_prompt(request, context, scenario_desc)
        filename = f"{request.project}_{request.scenario_type}_test.js"
        tool_label = "k6"

    response = _client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    script = response.content[0].text

    # Strip markdown fences if Claude wrapped the output
    if script.startswith("```"):
        lines = script.splitlines()
        script = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return ScriptGenerationResponse(
        scenario_type=request.scenario_type,
        script=script,
        filename=filename,
        description=f"{tool_label} {request.scenario_type} test for {request.project} — {scenario_desc}",
    )
