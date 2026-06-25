const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export async function uploadDocument(file: File, project: string, docType: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("project", project);
  form.append("doc_type", docType);

  const res = await fetch(`${BASE_URL}/documents/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function askQuestion(question: string, project: string, docTypes?: string[]) {
  const res = await fetch(`${BASE_URL}/chat/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, project, doc_types: docTypes }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateScript(project: string, scenarioType: string, baseUrl: string, tool: string) {
  const res = await fetch(`${BASE_URL}/generate/script`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, scenario_type: scenarioType, base_url: baseUrl, tool }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateScriptFromHar(file: File, tool: string, baseUrl: string, project: string) {
  const form = new FormData();
  form.append("file", file);
  form.append("tool", tool);
  form.append("base_url", baseUrl);
  form.append("project", project);
  const res = await fetch(`${BASE_URL}/generate/script/from-har`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function generateTestPlan(
  project: string,
  template?: string
): Promise<{ plan: Record<string, unknown> }> {
  const res = await fetch(`${BASE_URL}/generate/test-plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, template: template || null }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function refineTestPlan(
  project: string,
  plan: Record<string, unknown>,
  feedback: string
): Promise<{ plan: Record<string, unknown> }> {
  const res = await fetch(`${BASE_URL}/generate/test-plan/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, plan, feedback }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function extractTemplateFromFile(file: File): Promise<{ text: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/generate/template/from-file`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function extractTemplateFromUrl(url: string): Promise<{ text: string }> {
  const res = await fetch(`${BASE_URL}/generate/template/from-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function exportTestPlan(
  project: string,
  plan: Record<string, unknown>
): Promise<{ blob: Blob; filename: string }> {
  const res = await fetch(`${BASE_URL}/generate/test-plan/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ project, plan }),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match ? match[1] : `${project}_test_plan.pdf`;
  return { blob, filename };
}
