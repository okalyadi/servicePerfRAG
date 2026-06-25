"use client";

import { useState, useRef } from "react";
import { generateTestPlan, refineTestPlan, exportTestPlan, extractTemplateFromFile, extractTemplateFromUrl } from "@/lib/api";
import MermaidDiagram from "@/components/ui/MermaidDiagram";

interface Scenario {
  name: string;
  type: string;
  objective: string;
  description: string;
  duration: string;
  ramp_up: string;
  virtual_users: number;
  target_tps: number;
  expected_outcomes: string;
}

interface NfrRow {
  api_endpoint: string;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  error_rate_pct: number;
  tps: number;
}

interface Risk {
  risk: string;
  mitigation: string;
}

interface TestPlan {
  title: string;
  version: string;
  date: string;
  executive_summary: string;
  architecture_diagram?: string;
  scope: { in_scope: string[]; out_of_scope: string[] };
  test_environment: string;
  test_data: string;
  scenarios: Scenario[];
  nfr_mapping: NfrRow[];
  risks: Risk[];
  entry_criteria: string[];
  exit_criteria: string[];
}

const TYPE_COLORS: Record<string, string> = {
  load: "bg-blue-900/50 text-blue-300 border-blue-700",
  stress: "bg-orange-900/50 text-orange-300 border-orange-700",
  soak: "bg-purple-900/50 text-purple-300 border-purple-700",
  spike: "bg-red-900/50 text-red-300 border-red-700",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-blue-400 mb-3 border-b border-gray-800 pb-1">
        {title}
      </h3>
      {children}
    </div>
  );
}

function BulletList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="text-sm text-gray-300 flex gap-2">
          <span className="text-blue-500 mt-0.5 shrink-0">·</span>
          {item}
        </li>
      ))}
    </ul>
  );
}

function ScenarioCard({ s, index }: { s: Scenario; index: number }) {
  const colorClass = TYPE_COLORS[s.type] ?? "bg-gray-800 text-gray-300 border-gray-700";
  return (
    <div className="border border-gray-800 rounded-lg p-4 mb-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-semibold text-gray-100">{index + 1}. {s.name}</span>
        <span className={`text-xs px-2 py-0.5 rounded border font-medium uppercase ${colorClass}`}>
          {s.type}
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-3">{s.objective}</p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
        {[
          ["Duration", s.duration],
          ["Ramp-up", s.ramp_up],
          ["VUsers", String(s.virtual_users)],
          ["TPS", String(s.target_tps)],
        ].map(([label, value]) => (
          <div key={label} className="bg-gray-900 rounded px-3 py-2 text-center">
            <div className="text-xs text-gray-500">{label}</div>
            <div className="text-sm font-semibold text-gray-100">{value}</div>
          </div>
        ))}
      </div>
      <p className="text-xs text-gray-400 italic">{s.expected_outcomes}</p>
    </div>
  );
}

export default function TestPlanPanel({ project }: { project: string }) {
  const [planData, setPlanData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [refining, setRefining] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [iterations, setIterations] = useState(0);
  const [error, setError] = useState("");
  const [template, setTemplate] = useState("");
  const [templateOpen, setTemplateOpen] = useState(false);
  const [templateSource, setTemplateSource] = useState<string>("");
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateError, setTemplateError] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [templateDragging, setTemplateDragging] = useState(false);
  const templateFileRef = useRef<HTMLInputElement>(null);

  const plan = planData as TestPlan | null;

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    setPlanData(null);
    setIterations(0);
    try {
      const { plan: p } = await generateTestPlan(project, template.trim() || undefined);
      setPlanData(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleRefine = async () => {
    if (!planData || !feedback.trim()) return;
    setRefining(true);
    setError("");
    try {
      const { plan: updated } = await refineTestPlan(project, planData, feedback.trim());
      setPlanData(updated);
      setIterations((n) => n + 1);
      setFeedback("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refinement failed");
    } finally {
      setRefining(false);
    }
  };

  const handleExport = async () => {
    if (!planData) return;
    setExporting(true);
    try {
      const { blob, filename } = await exportTestPlan(project, planData);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };

  const loadTemplateFromFile = async (file: File) => {
    setTemplateLoading(true);
    setTemplateError("");
    try {
      const { text } = await extractTemplateFromFile(file);
      setTemplate(text);
      setTemplateSource(file.name);
    } catch (e) {
      setTemplateError(e instanceof Error ? e.message : "Failed to read file");
    } finally {
      setTemplateLoading(false);
    }
  };

  const loadTemplateFromUrl = async () => {
    if (!urlInput.trim()) return;
    setTemplateLoading(true);
    setTemplateError("");
    try {
      const { text } = await extractTemplateFromUrl(urlInput.trim());
      setTemplate(text);
      setTemplateSource(urlInput.trim());
    } catch (e) {
      setTemplateError(e instanceof Error ? e.message : "Failed to fetch URL");
    } finally {
      setTemplateLoading(false);
    }
  };

  const clearTemplate = () => {
    setTemplate("");
    setTemplateSource("");
    setTemplateError("");
    setUrlInput("");
  };

  return (
    <div className="space-y-4">
      {/* Template section */}
      <div className="border border-gray-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setTemplateOpen((o) => !o)}
          className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-300 hover:bg-gray-800/50 transition-colors"
        >
          <span className="flex items-center gap-2">
            Custom Template
            {template.trim() && (
              <span className="text-xs bg-blue-900/60 text-blue-300 border border-blue-700 rounded px-2 py-0.5">
                Active{templateSource ? ` · ${templateSource.length > 30 ? "…" + templateSource.slice(-28) : templateSource}` : ""}
              </span>
            )}
          </span>
          <span className="text-gray-600 text-xs">{templateOpen ? "▲" : "▼"}</span>
        </button>

        {templateOpen && (
          <div className="px-4 pb-4 border-t border-gray-800 bg-gray-900/30 space-y-3">
            <p className="text-xs text-gray-500 mt-3">
              Provide a template via file upload, a link, or paste it directly. The plan will follow your template's structure and honour any explicit values (e.g. "load test: 1000 users, 30 min").
            </p>

            {/* File upload */}
            <div
              onDrop={(e) => {
                e.preventDefault();
                setTemplateDragging(false);
                const f = e.dataTransfer.files[0];
                if (f) loadTemplateFromFile(f);
              }}
              onDragOver={(e) => { e.preventDefault(); setTemplateDragging(true); }}
              onDragLeave={() => setTemplateDragging(false)}
              onClick={() => templateFileRef.current?.click()}
              className={`border-2 border-dashed rounded-lg px-4 py-3 text-center cursor-pointer text-xs transition-colors ${
                templateDragging ? "border-blue-400 bg-blue-400/10 text-blue-300" : "border-gray-700 hover:border-gray-500 text-gray-500"
              }`}
            >
              {templateLoading ? "Loading…" : "Drop a file here or click to browse · PDF, DOCX, TXT, MD"}
              <input
                ref={templateFileRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt,.md"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) loadTemplateFromFile(f); e.target.value = ""; }}
              />
            </div>

            {/* URL input */}
            <div className="flex gap-2">
              <input
                value={urlInput}
                onChange={(e) => setUrlInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && loadTemplateFromUrl()}
                placeholder="https://docs.example.com/perf-template.pdf"
                className="flex-1 bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={loadTemplateFromUrl}
                disabled={templateLoading || !urlInput.trim()}
                className="bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-white px-4 py-2 rounded text-xs font-medium transition-colors whitespace-nowrap"
              >
                {templateLoading ? "Fetching…" : "Fetch"}
              </button>
            </div>

            {templateError && <p className="text-red-400 text-xs">{templateError}</p>}

            {/* Editable textarea */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500">Template text {template.trim() ? `(${template.trim().split("\n").length} lines)` : "(empty — will use default)"}</span>
                {template.trim() && (
                  <button onClick={clearTemplate} className="text-xs text-gray-600 hover:text-red-400 transition-colors">
                    Clear
                  </button>
                )}
              </div>
              <textarea
                value={template}
                onChange={(e) => { setTemplate(e.target.value); if (!e.target.value.trim()) setTemplateSource(""); }}
                placeholder={`Paste template here, or use the file/URL options above.\n\nExample:\n  Load Test — 1000 users, 45 min, /api/search\n  Stress Test — 3000 users\n  NFR: p95 < 500ms, error rate < 0.5%`}
                rows={8}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-y font-mono"
              />
            </div>
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={loading || refining}
          className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {loading ? "Generating..." : planData ? "Regenerate" : "Generate Test Plan"}
        </button>
        {planData && (
          <button
            onClick={handleExport}
            disabled={exporting}
            className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            {exporting ? "Exporting..." : "Download PDF"}
          </button>
        )}
        {iterations > 0 && (
          <span className="text-xs text-gray-500">{iterations} refinement{iterations !== 1 ? "s" : ""} applied</span>
        )}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {/* Inline plan view */}
      {planData && (() => {
        const p = plan!;
        return (
        <div className="border border-gray-800 rounded-lg p-5 bg-gray-950">
          {/* Header */}
          <div className="mb-6 pb-4 border-b border-gray-800">
            <h2 className="text-lg font-bold text-blue-400">{p.title}</h2>
            <p className="text-xs text-gray-500 mt-1">v{p.version} · {p.date}</p>
          </div>

          <Section title="Executive Summary">
            <p className="text-sm text-gray-300 leading-relaxed">{p.executive_summary}</p>
          </Section>

          {p.architecture_diagram && (() => {
            const diag = p.architecture_diagram as string | { description?: string; mermaid?: string };
            const description = typeof diag === "string" ? null : diag.description;
            const mermaid = typeof diag === "string" ? diag : diag.mermaid;
            return (
              <Section title="Architecture Diagram">
                {description && <p className="text-sm text-gray-300 mb-3">{description}</p>}
                {mermaid && (
                  <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                    <MermaidDiagram chart={mermaid} />
                  </div>
                )}
              </Section>
            );
          })()}

          <Section title="Scope">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">In Scope</p>
                <BulletList items={p.scope?.in_scope ?? []} />
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">Out of Scope</p>
                <BulletList items={p.scope?.out_of_scope ?? []} />
              </div>
            </div>
          </Section>

          <Section title="Test Environment & Data">
            <p className="text-sm text-gray-300 mb-2">{p.test_environment}</p>
            <p className="text-sm text-gray-400 italic">{p.test_data}</p>
          </Section>

          <Section title="Test Scenarios">
            {(p.scenarios ?? []).map((s, i) => (
              <ScenarioCard key={i} s={s} index={i} />
            ))}
          </Section>

          <Section title="NFR Mapping">
            <div className="overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="text-gray-500 border-b border-gray-800">
                    <th className="pb-2 pr-4 font-medium">Endpoint</th>
                    <th className="pb-2 pr-3 font-medium text-right">p50</th>
                    <th className="pb-2 pr-3 font-medium text-right">p95</th>
                    <th className="pb-2 pr-3 font-medium text-right">p99</th>
                    <th className="pb-2 pr-3 font-medium text-right">Err%</th>
                    <th className="pb-2 font-medium text-right">TPS</th>
                  </tr>
                </thead>
                <tbody>
                  {(p.nfr_mapping ?? []).map((row, i) => (
                    <tr key={i} className="border-b border-gray-900 text-gray-300">
                      <td className="py-2 pr-4 text-gray-200">{row.api_endpoint}</td>
                      <td className="py-2 pr-3 text-right">{row.p50_ms}ms</td>
                      <td className="py-2 pr-3 text-right">{row.p95_ms}ms</td>
                      <td className="py-2 pr-3 text-right">{row.p99_ms}ms</td>
                      <td className="py-2 pr-3 text-right">{row.error_rate_pct}%</td>
                      <td className="py-2 text-right">{row.tps}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          <Section title="Risks & Mitigations">
            <div className="space-y-3">
              {(p.risks ?? []).map((r, i) => {
                const risk = typeof r === "string" ? r : r.risk;
                const mitigation = typeof r === "string" ? "" : r.mitigation;
                return (
                  <div key={i} className="text-sm">
                    <span className="text-gray-200">{i + 1}. {risk}</span>
                    {mitigation && (
                      <p className="text-gray-500 text-xs mt-0.5 ml-4 italic">Mitigation: {mitigation}</p>
                    )}
                  </div>
                );
              })}
            </div>
          </Section>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <Section title="Entry Criteria">
              <BulletList items={p.entry_criteria ?? []} />
            </Section>
            <Section title="Exit Criteria">
              <BulletList items={p.exit_criteria ?? []} />
            </Section>
          </div>
        </div>
        );
      })()}

      {/* Feedback / refinement */}
      {planData && (
        <div className="border border-gray-800 rounded-lg p-4 space-y-3">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Refine the plan</p>
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Describe what you'd like to change — e.g. 'Increase the load test to 2000 users', 'Add a /search endpoint to the NFR table', 'Make the soak test 4 hours'..."
            rows={3}
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 resize-none"
          />
          <button
            onClick={handleRefine}
            disabled={refining || !feedback.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {refining ? "Applying..." : "Apply Feedback"}
          </button>
        </div>
      )}
    </div>
  );
}
