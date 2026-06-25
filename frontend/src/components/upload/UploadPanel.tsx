"use client";

import { useState, useRef } from "react";
import { uploadDocument } from "@/lib/api";

const DOC_TYPES = ["HLD", "LLD", "ARCHITECTURE", "NFR", "OTHER"];

interface UploadPanelProps {
  project: string;
}

interface UploadStatus {
  filename: string;
  status: "uploading" | "done" | "error";
  message: string;
}

export default function UploadPanel({ project }: UploadPanelProps) {
  const [docType, setDocType] = useState("HLD");
  const [uploads, setUploads] = useState<UploadStatus[]>([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList) => {
    for (const file of Array.from(files)) {
      setUploads((prev) => [
        ...prev,
        { filename: file.name, status: "uploading", message: "Parsing & embedding — this takes 20-40s for large docs..." },
      ]);
      try {
        const result = await uploadDocument(file, project, docType);
        setUploads((prev) =>
          prev.map((u) =>
            u.filename === file.name
              ? { ...u, status: "done", message: `Done — ${result.chunks_stored} chunks indexed` }
              : u
          )
        );
      } catch (e: unknown) {
        const message = e instanceof Error ? e.message : "Upload failed";
        setUploads((prev) =>
          prev.map((u) => (u.filename === file.name ? { ...u, status: "error", message } : u))
        );
      }
    }
  };

  return (
    <div className="border border-gray-800 rounded-lg p-5">
      <h2 className="text-sm font-semibold text-gray-300 mb-4">Upload Design Documents</h2>

      <div className="flex gap-3 mb-4">
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
        >
          {DOC_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>

        <div
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onClick={() => inputRef.current?.click()}
          className={`flex-1 border-2 border-dashed rounded-lg px-4 py-3 text-center cursor-pointer transition-colors text-sm ${
            dragging ? "border-blue-400 bg-blue-400/10" : "border-gray-700 hover:border-gray-500"
          }`}
        >
          Drop files here or click to browse · PDF, DOCX, PNG, JPG, SVG
          <input ref={inputRef} type="file" multiple className="hidden" onChange={(e) => e.target.files && handleFiles(e.target.files)} />
        </div>
      </div>

      {uploads.length > 0 && (
        <div className="space-y-2 mt-2">
          {uploads.map((u, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 rounded-lg px-3 py-2 text-xs border ${
                u.status === "done"
                  ? "border-green-800 bg-green-950/40"
                  : u.status === "error"
                  ? "border-red-800 bg-red-950/40"
                  : "border-yellow-800 bg-yellow-950/30"
              }`}
            >
              <span className="mt-0.5 shrink-0">
                {u.status === "done" ? (
                  <span className="text-green-400 text-sm">✓</span>
                ) : u.status === "error" ? (
                  <span className="text-red-400 text-sm">✗</span>
                ) : (
                  <svg className="animate-spin h-3.5 w-3.5 text-yellow-400 mt-0.5" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                )}
              </span>
              <div>
                <p className="text-gray-200 font-medium">{u.filename}</p>
                <p className={u.status === "done" ? "text-green-400" : u.status === "error" ? "text-red-400" : "text-yellow-400"}>
                  {u.message}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
