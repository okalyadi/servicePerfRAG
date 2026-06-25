"use client";

import { useState, useRef } from "react";
import { generateScript, generateScriptFromHar } from "@/lib/api";

const TOOLS = [
  { value: "k6", label: "k6" },
  { value: "jmeter", label: "JMeter" },
];

interface ScriptsPanelProps {
  project: string;
  activeTab: "Generate Script" | "Test Plan";
}

export default function ScriptsPanel({ project }: ScriptsPanelProps) {
  const [baseUrl, setBaseUrl] = useState("https://your-service.example.com");
  const [tool, setTool] = useState("k6");
  const [result, setResult] = useState<string>("");
  const [filename, setFilename] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  // HAR state
  const [harMode, setHarMode] = useState(false);
  const [harFile, setHarFile] = useState<File | null>(null);
  const [harDragging, setHarDragging] = useState(false);
  const harFileRef = useRef<HTMLInputElement>(null);

  const resetResult = () => { setResult(""); setFilename(""); setError(""); };

  const handleGenerate = async () => {
    setLoading(true);
    resetResult();
    try {
      const data = await generateScript(project, "comprehensive", baseUrl, tool);
      setResult(data.script);
      setFilename(data.filename);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateFromHar = async () => {
    if (!harFile) return;
    setLoading(true);
    resetResult();
    try {
      const data = await generateScriptFromHar(harFile, tool, baseUrl, project);
      setResult(data.script);
      setFilename(data.filename);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setLoading(false);
    }
  };

  const downloadResult = () => {
    const blob = new Blob([result], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleHarFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".har")) {
      setError("Please upload a .har file.");
      return;
    }
    setHarFile(file);
    setError("");
    resetResult();
  };

  return (
    <div className="space-y-4">
      {/* Tool selector + base URL */}
      <div className="flex gap-3 flex-wrap items-center">
        <div className="flex rounded-lg border border-gray-700 overflow-hidden">
          {TOOLS.map((t) => (
            <button
              key={t.value}
              onClick={() => { setTool(t.value); resetResult(); }}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                tool === t.value
                  ? "bg-blue-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:text-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <input
          value={baseUrl}
          onChange={(e) => setBaseUrl(e.target.value)}
          placeholder="https://your-service.example.com"
          className="flex-1 min-w-48 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Mode toggle */}
      <div className="flex gap-1 border border-gray-700 rounded-lg overflow-hidden w-fit">
        <button
          onClick={() => { setHarMode(false); resetResult(); }}
          className={`px-4 py-1.5 text-xs font-medium transition-colors ${
            !harMode ? "bg-gray-700 text-white" : "text-gray-400 hover:text-gray-200"
          }`}
        >
          From Documents
        </button>
        <button
          onClick={() => { setHarMode(true); resetResult(); }}
          className={`px-4 py-1.5 text-xs font-medium transition-colors ${
            harMode ? "bg-gray-700 text-white" : "text-gray-400 hover:text-gray-200"
          }`}
        >
          From HAR File
        </button>
      </div>

      {/* HAR upload zone */}
      {harMode && (
        <div
          onDrop={(e) => {
            e.preventDefault();
            setHarDragging(false);
            const f = e.dataTransfer.files[0];
            if (f) handleHarFile(f);
          }}
          onDragOver={(e) => { e.preventDefault(); setHarDragging(true); }}
          onDragLeave={() => setHarDragging(false)}
          onClick={() => harFileRef.current?.click()}
          className={`border-2 border-dashed rounded-lg px-6 py-6 text-center cursor-pointer transition-colors ${
            harDragging
              ? "border-blue-400 bg-blue-400/10 text-blue-300"
              : harFile
              ? "border-green-600 bg-green-900/20 text-green-300"
              : "border-gray-700 hover:border-gray-500 text-gray-500"
          }`}
        >
          {harFile ? (
            <div>
              <p className="text-sm font-medium">{harFile.name}</p>
              <p className="text-xs mt-1 text-gray-500">{(harFile.size / 1024).toFixed(0)} KB — click to replace</p>
            </div>
          ) : (
            <div>
              <p className="text-sm">Drop a .har file here or click to browse</p>
              <p className="text-xs mt-1">Export from Chrome DevTools → Network → Export HAR</p>
            </div>
          )}
          <input
            ref={harFileRef}
            type="file"
            accept=".har"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleHarFile(f); e.target.value = ""; }}
          />
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2">
        {harMode ? (
          <button
            onClick={handleGenerateFromHar}
            disabled={loading || !harFile}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? "Generating..." : `Generate ${TOOLS.find(t => t.value === tool)?.label} Script from HAR`}
          </button>
        ) : (
          <button
            onClick={handleGenerate}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {loading ? "Generating..." : `Generate ${TOOLS.find(t => t.value === tool)?.label} Script`}
          </button>
        )}
        {result && (
          <button
            onClick={downloadResult}
            className="bg-gray-700 hover:bg-gray-600 text-white px-5 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            Download {filename}
          </button>
        )}
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {result && (
        <pre className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-xs text-gray-300 overflow-auto max-h-[480px] font-mono">
          {result}
        </pre>
      )}
    </div>
  );
}
