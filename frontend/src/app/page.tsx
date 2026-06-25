"use client";

import { useState } from "react";
import UploadPanel from "@/components/upload/UploadPanel";
import ChatPanel from "@/components/chat/ChatPanel";
import ScriptsPanel from "@/components/scripts/ScriptsPanel";
import TestPlanPanel from "@/components/testplan/TestPlanPanel";

const TABS = ["Q&A", "Test Plan", "Generate Script"] as const;
type Tab = (typeof TABS)[number];

export default function Home() {
  const [project, setProject] = useState("my-service");
  const [activeTab, setActiveTab] = useState<Tab>("Q&A");

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <header className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-blue-400">servicePerfRAG</h1>
          <p className="text-xs text-gray-500">AI Performance Testing Assistant</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-400">Project:</label>
          <input
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1 text-sm text-white w-48 focus:outline-none focus:border-blue-500"
          />
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-6">
        <UploadPanel project={project} />

        <div className="mt-8">
          <div className="flex gap-1 border-b border-gray-800 mb-6">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-gray-400 hover:text-gray-200"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {activeTab === "Q&A" && <ChatPanel project={project} />}
          {activeTab === "Generate Script" && (
            <ScriptsPanel project={project} activeTab={activeTab} />
          )}
          {activeTab === "Test Plan" && <TestPlanPanel project={project} />}
        </div>
      </div>
    </div>
  );
}
